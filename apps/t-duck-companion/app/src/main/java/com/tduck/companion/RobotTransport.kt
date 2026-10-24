package com.tduck.companion

import kotlinx.coroutines.*
import org.json.JSONObject
import java.net.URL
import java.util.UUID
import javax.net.ssl.HttpsURLConnection

data class Ack(val id: String, val accepted: Boolean, val command: String)
interface RobotTransport {
    suspend fun capabilities(): Set<String>
    suspend fun telemetry(): JSONObject
    suspend fun send(command: String, ttlMs: Int = 800): Ack
}
interface DeviceDiscovery { suspend fun discover(): List<DiscoveredDevice> }
data class DiscoveredDevice(val id: String, val name: String, val simulated: Boolean)
interface BleProvisioner {
    suspend fun provision(physicalCode: String, ssid: String, password: String): DiscoveredDevice
}
class SimulatedProvisioner : BleProvisioner, DeviceDiscovery {
    override suspend fun discover(): List<DiscoveredDevice> { delay(200); return listOf(DiscoveredDevice("demo-duck-001", "T-Duck Demo", true)) }
    override suspend fun provision(physicalCode: String, ssid: String, password: String): DiscoveredDevice {
        require(physicalCode == "246810") { "Demo physical-access code is 246810" }
        require(ssid.isNotBlank() && password.length >= 8) { "Enter a Wi-Fi name and at least 8 password characters. Use invented demo credentials." }
        delay(500)
        return discover().first() // Credentials are neither persisted nor transmitted.
    }
}
class HttpsRobotTransport(private val endpoint: String, private val token: String) : RobotTransport {
    init { require(URL(endpoint).protocol == "https") { "An HTTPS bridge is required" }; require(token.isNotBlank()) { "A bridge token is required" } }
    private suspend fun request(path: String, body: JSONObject? = null): JSONObject = withContext(Dispatchers.IO) {
        val connection = URL(endpoint.trimEnd('/') + "/v1/" + path).openConnection() as HttpsURLConnection
        try {
            connection.connectTimeout = 1500; connection.readTimeout = 1500
            connection.instanceFollowRedirects = false
            connection.setRequestProperty("Authorization", "Bearer $token")
            if (body != null) { connection.requestMethod = "POST"; connection.doOutput = true; connection.setRequestProperty("Content-Type", "application/json"); connection.outputStream.use { it.write(body.toString().toByteArray()) } }
            check(connection.responseCode == 200) { "Bridge rejected request (${connection.responseCode})" }
            val data = connection.inputStream.use { stream ->
                val output = java.io.ByteArrayOutputStream(); val buffer = ByteArray(4096)
                while (output.size() <= 65536) { val n = stream.read(buffer); if (n < 0) break; output.write(buffer, 0, n) }; output.toByteArray()
            }
            check(data.size <= 65536) { "Bridge response too large" }
            JSONObject(String(data, Charsets.UTF_8))
        } finally { connection.disconnect() }
    }
    override suspend fun capabilities(): Set<String> {
        val json = request("capabilities")
        check(json.getString("protocol_version").substringBefore('.') == "1") { "Unsupported protocol" }
        check(json.getBoolean("simulated")) { "v0.1 only accepts simulation bridges; hardware validation pending" }
        val list = json.getJSONArray("commands")
        return (0 until list.length()).map { list.getString(it) }.toSet()
    }
    override suspend fun telemetry() = request("telemetry")
    override suspend fun send(command: String, ttlMs: Int): Ack {
        val id = UUID.randomUUID().toString()
        val response = request("commands", JSONObject().put("id", id).put("command", command).put("ttl_ms", ttlMs))
        check(response.getString("id") == id && response.getString("command") == command) { "Acknowledgement mismatch" }
        return Ack(id, response.getBoolean("accepted"), command)
    }
}
object CommandPolicy {
    val commands = setOf("stand", "rest", "forward", "left", "right", "stop", "recover")
    fun allowed(command: String, capabilities: Set<String>, fallen: Boolean): Boolean =
        command in commands && command in capabilities && (!fallen || command in setOf("recover", "stop", "rest"))
    fun interpret(text: String): String? = when (text.trim().lowercase()) {
        "stand", "stand up" -> "stand"; "sit", "rest" -> "rest"; "walk", "walk forward" -> "forward"
        "turn left" -> "left"; "turn right" -> "right"; "stop", "emergency stop" -> "stop"; "recover" -> "recover"; else -> null
    }
}
