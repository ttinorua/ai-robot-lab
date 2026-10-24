package com.tduck.companion

import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import java.net.InetAddress
import java.net.SocketException
import javax.net.ssl.SSLServerSocket
import javax.net.ssl.SSLSocket
import java.security.KeyStore
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import javax.net.ssl.HttpsURLConnection
import javax.net.ssl.KeyManagerFactory
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLSocketFactory
import javax.net.ssl.TrustManagerFactory

/** Real HTTPS sockets; fixture trust applies to this test class only, never production code. */
class RobotTransportIntegrationTest {
    private lateinit var server: SSLServerSocket
    private lateinit var executor: ExecutorService
    private lateinit var originalFactory: SSLSocketFactory
    private lateinit var endpoint: String
    private val token = "public-integration-test-token-only"
    @Volatile private var ackMode = "accepted"
    @Volatile private var telemetryIdentity = "tls-simulator-001"
    @Volatile private var telemetryProtocol = "1.0"
    @Volatile private var delayCommand = false
    @Volatile private var lastCommand: JSONObject? = null

    @Before fun startServer() {
        originalFactory = HttpsURLConnection.getDefaultSSLSocketFactory()
        val fixture = KeyStore.getInstance("PKCS12")
        javaClass.getResourceAsStream("/tls/tduck-simulator-test-only.p12").use { stream ->
            checkNotNull(stream) { "Missing test TLS fixture" }
            fixture.load(stream, "test-fixture-only".toCharArray())
        }
        val keys = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm())
        keys.init(fixture, "test-fixture-only".toCharArray())
        val serverContext = SSLContext.getInstance("TLS")
        serverContext.init(keys.keyManagers, null, null)
        val trustStore = KeyStore.getInstance(KeyStore.getDefaultType())
        trustStore.load(null, null)
        trustStore.setCertificateEntry("only-test-localhost", fixture.getCertificate("tduck-test"))
        val trust = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm())
        trust.init(trustStore)
        val testClientContext = SSLContext.getInstance("TLS")
        testClientContext.init(null, trust.trustManagers, null)
        HttpsURLConnection.setDefaultSSLSocketFactory(testClientContext.socketFactory)
        server = serverContext.serverSocketFactory.createServerSocket(
            0, 50, InetAddress.getByName("127.0.0.1")) as SSLServerSocket
        executor = Executors.newCachedThreadPool { runnable -> Thread(runnable, "tduck-test-https").apply { isDaemon = true } }
        executor.submit {
            while (!server.isClosed) {
                val socket = try { server.accept() as SSLSocket } catch (_: SocketException) { break }
                executor.submit {
                    socket.use {
                        try { socket.soTimeout = 3000; handle(readRequest(socket)) }
                        catch (_: java.io.IOException) { /* Negative TLS and deadline tests close early. */ }
                        catch (_: InterruptedException) { Thread.currentThread().interrupt() }
                    }
                }
            }
        }
        endpoint = "https://localhost:${server.localPort}"
    }

    @After fun stopServer() {
        HttpsURLConnection.setDefaultSSLSocketFactory(originalFactory)
        if (::server.isInitialized) server.close()
        if (::executor.isInitialized) executor.shutdownNow()
    }

    private fun envelope(identity: String = "tls-simulator-001", version: String = "1.0") =
        JSONObject().put("device_id", identity).put("protocol_version", version).put("simulated", true)

    private data class Exchange(val socket: SSLSocket, val path: String,
                                val headers: Map<String, String>, val body: ByteArray)

    /** Tiny bounded HTTP/1.1 fixture using only java.base; no Android-unavailable HTTP modules. */
    private fun readRequest(socket: SSLSocket): Exchange {
        val input = socket.inputStream.buffered()
        val header = java.io.ByteArrayOutputStream()
        var suffix = 0
        while (suffix != 0x0d0a0d0a) {
            val byte = input.read()
            if (byte < 0) throw java.io.EOFException("Request ended before headers")
            header.write(byte)
            if (header.size() > 16384) throw java.io.IOException("Oversized test request headers")
            suffix = (suffix shl 8) or byte
        }
        val lines = header.toString("US-ASCII").split("\r\n")
        val path = lines.first().split(' ')[1]
        val headers = lines.drop(1).filter { ':' in it }.associate {
            it.substringBefore(':').trim().lowercase() to it.substringAfter(':').trim()
        }
        val size = headers["content-length"]?.toInt() ?: 0
        require(size in 0..4096)
        val body = ByteArray(size)
        var offset = 0
        while (offset < size) {
            val count = input.read(body, offset, size - offset)
            if (count < 0) throw java.io.EOFException("Incomplete request body")
            offset += count
        }
        return Exchange(socket, path, headers, body)
    }

    private fun handle(exchange: Exchange) {
        if (exchange.headers["authorization"] != "Bearer $token") {
            reply(exchange, 401, JSONObject().put("error", "unauthorized")); return
        }
        when (exchange.path) {
            "/v1/capabilities" -> reply(exchange, 200, envelope().put("commands", JSONArray(listOf("stand", "forward", "stop"))))
            "/v1/telemetry" -> reply(exchange, 200, envelope(telemetryIdentity, telemetryProtocol).put("activity", "Resting"))
            "/v1/commands" -> {
                val request = JSONObject(String(exchange.body, Charsets.UTF_8))
                lastCommand = request
                if (delayCommand) Thread.sleep(2000)
                val ack = JSONObject().put("id", if (ackMode == "wrong-id") "stale-id" else request.getString("id"))
                    .put("command", if (ackMode == "wrong-command") "stand" else request.getString("command"))
                    .put("accepted", ackMode != "rejected").put("status", "applied")
                reply(exchange, 200, ack)
            }
            else -> reply(exchange, 404, JSONObject())
        }
    }

    private fun reply(exchange: Exchange, status: Int, body: JSONObject) {
        val bytes = body.toString().toByteArray(Charsets.UTF_8)
        val reason = when (status) { 200 -> "OK"; 401 -> "Unauthorized"; else -> "Not Found" }
        val headers = "HTTP/1.1 $status $reason\r\nContent-Type: application/json\r\nContent-Length: ${bytes.size}\r\nConnection: close\r\n\r\n"
        exchange.socket.outputStream.apply { write(headers.toByteArray(Charsets.US_ASCII)); write(bytes); flush() }
    }

    private suspend fun mustFail(block: suspend () -> Unit) {
        val failure = runCatching { block() }.exceptionOrNull()
        assertNotNull("Invalid network response unexpectedly succeeded", failure)
    }

    @Test fun authenticatedHttpsCapabilitiesAndAckRoundTrip() = runBlocking {
        val client = HttpsRobotTransport(endpoint, token)
        assertEquals(setOf("stand", "forward", "stop"), client.capabilities())
        val ack = client.send("forward", 500)
        assertTrue(ack.accepted)
        assertEquals("forward", ack.command)
        assertEquals(ack.id, lastCommand!!.getString("id"))
        assertEquals(500, lastCommand!!.getInt("ttl_ms"))
    }

    @Test fun wrongBearerTokenIsRejected() = runBlocking {
        mustFail { HttpsRobotTransport(endpoint, "wrong-test-token").capabilities() }
    }

    @Test fun rejectedAckIsReturnedAsRejected() = runBlocking {
        ackMode = "rejected"
        assertFalse(HttpsRobotTransport(endpoint, token).send("stop").accepted)
    }

    @Test fun mismatchedAckIdIsRejected() = runBlocking {
        ackMode = "wrong-id"
        mustFail { HttpsRobotTransport(endpoint, token).send("stop") }
    }

    @Test fun mismatchedAckCommandIsRejected() = runBlocking {
        ackMode = "wrong-command"
        mustFail { HttpsRobotTransport(endpoint, token).send("stop") }
    }

    @Test fun telemetryPreservesUnavailableOptionalSensors() = runBlocking {
        val client = HttpsRobotTransport(endpoint, token)
        client.capabilities()
        val telemetry = client.telemetry()
        assertEquals("Resting", telemetry.getString("activity"))
        assertFalse(telemetry.has("distance_cm"))
        assertFalse(telemetry.has("camera_available"))
    }

    @Test fun differentTelemetryIdentityIsRejected() = runBlocking {
        val client = HttpsRobotTransport(endpoint, token)
        client.capabilities()
        telemetryIdentity = "untrusted-new-robot"
        mustFail { client.telemetry() }
    }

    @Test fun differentTelemetryMajorIsRejected() = runBlocking {
        val client = HttpsRobotTransport(endpoint, token)
        client.capabilities()
        telemetryProtocol = "2.0"
        mustFail { client.telemetry() }
    }

    @Test fun commandTimesOutWhenServerWithholdsAck() = runBlocking {
        val client = HttpsRobotTransport(endpoint, token)
        client.capabilities() // Warm TLS to isolate response timeout.
        delayCommand = true
        val start = System.nanoTime()
        mustFail { client.send("forward") }
        val elapsedMs = (System.nanoTime() - start) / 1_000_000
        assertTrue("Timeout took ${elapsedMs}ms", elapsedMs < 1800)
    }

    @Test fun hostnameValidationRemainsEnabled() = runBlocking {
        // Fixture cert contains only DNS localhost, never the IP address.
        mustFail { HttpsRobotTransport("https://127.0.0.1:${server.localPort}", token).capabilities() }
    }

    @Test fun platformTrustDoesNotTrustTestCertificate() = runBlocking {
        HttpsURLConnection.setDefaultSSLSocketFactory(originalFactory)
        mustFail { HttpsRobotTransport(endpoint, token).capabilities() }
    }
}
