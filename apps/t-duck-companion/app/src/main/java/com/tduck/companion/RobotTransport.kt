package com.tduck.companion

import kotlinx.coroutines.*
import org.json.JSONObject
import java.net.URL
import java.net.SocketTimeoutException
import java.net.ConnectException
import java.util.UUID
import java.util.Timer
import java.util.TimerTask
import java.util.concurrent.atomic.AtomicLong
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
/** Every response remains bound to the authenticated capability identity for this connection. */
internal class RobotProtocolSession {
    private var deviceId: String? = null
    private var bootId: String? = null
    private var source: String? = null
    private var lastFrame = -1L
    private var lastTime = -1.0
    private fun validateEnvelope(json: JSONObject): String {
        check(json.getString("protocol_version").matches(Regex("1\\.[0-9]+"))) { "Unsupported protocol" }
        check(json.getBoolean("simulated")) { "Companion accepts simulation bridges only; hardware validation pending" }
        return json.getString("device_id").also { check(it.isNotBlank()) { "Missing device identity" } }
    }
    fun capabilities(json: JSONObject): Set<String> {
        val identity = validateEnvelope(json)
        val list = json.getJSONArray("commands")
        val commands = (0 until list.length()).map { list.getString(it) }.toSet()
        check("stop" in commands) { "Bridge must support local stop" }
        deviceId = identity
        bootId = json.optString("boot_id").takeIf { it.isNotBlank() }
        source = json.optString("telemetry_source").takeIf { it.isNotBlank() }
        if (source == "mujoco") check(bootId != null && json.optBoolean("ordered_commands")) { "MuJoCo requires an ordered control session" }
        lastFrame = -1; lastTime = -1.0
        return commands.intersect(CommandPolicy.commands)
    }
    fun telemetry(json: JSONObject): JSONObject {
        check(deviceId != null) { "Capabilities must be authenticated first" }
        check(validateEnvelope(json) == deviceId) { "Bridge identity changed; reconnect required" }
        if (bootId != null) check(json.getString("boot_id") == bootId) { "Bridge restarted; reconnect required" }
        if (source != null) check(json.getString("telemetry_source") == source) { "Telemetry source changed" }
        if (source == "mujoco") {
            val pose = SimulationPose.parse(json.getJSONObject("pose"))
            check(pose.frameId >= lastFrame && pose.simulationTimeS >= lastTime) { "Stale simulation pose" }
            lastFrame = pose.frameId; lastTime = pose.simulationTimeS
        }
        return json
    }
}
class BridgeAuthenticationException : java.io.IOException("Owner authentication rejected")
internal class SleepingBridge(val status: Int) : java.io.IOException("Bridge starting ($status)")
/** Only read-only discovery may wait for a sleeping host. Commands are never retried. */
internal suspend fun <T> awaitBridgeWake(attempts: Int = 36, request: suspend () -> T): T {
    repeat(attempts) { index ->
        try { return request() }
        catch (e: Exception) {
            if (e !is SleepingBridge && e !is SocketTimeoutException && e !is ConnectException) throw e
            if (index == attempts - 1) throw e
            delay(1500)
        }
    }
    error("No discovery attempts")
}
class HttpsRobotTransport(endpoint: String, private val token: String, private val wakeSleepingHost: Boolean = false) : RobotTransport {
    private val endpoint = BridgeEndpoint.normalize(endpoint)
    private val protocol = RobotProtocolSession()
    private var sessionId: String? = null
    private val sequence = AtomicLong(0)
    companion object { private val deadlines = Timer("tduck-network-deadlines", true) }
    init {
        val url = URL(endpoint)
        require(url.protocol == "https" && url.host.isNotBlank() && url.userInfo == null && url.query == null && url.ref == null) { "An HTTPS bridge endpoint without embedded credentials is required" }
        require(token.isNotBlank()) { "A bridge token is required" }
    }
    private suspend fun request(path: String, body: JSONObject? = null): JSONObject = withContext(Dispatchers.IO) {
        val connection = URL(endpoint.trimEnd('/') + "/v1/" + path).openConnection() as HttpsURLConnection
        // A socket read timeout alone can be extended indefinitely by trickled data.
        // Disconnect imposes an overall deadline including connection and response body.
        val deadline = object : TimerTask() { override fun run() { connection.disconnect() } }
        deadlines.schedule(deadline, 950)
        try {
            connection.connectTimeout = 800; connection.readTimeout = 800
            connection.instanceFollowRedirects = false
            connection.setRequestProperty("Authorization", "Bearer $token")
            if (body != null) { connection.requestMethod = "POST"; connection.doOutput = true; connection.setRequestProperty("Content-Type", "application/json"); connection.outputStream.use { it.write(body.toString().toByteArray()) } }
            val status = connection.responseCode
            if (status == 401 || status == 403) throw BridgeAuthenticationException()
            if (status in setOf(502, 503, 504)) throw SleepingBridge(status)
            check(status == 200) { "Bridge rejected request ($status)" }
            val data = connection.inputStream.use { stream ->
                val output = java.io.ByteArrayOutputStream(); val buffer = ByteArray(4096)
                while (output.size() <= 65536) { val n = stream.read(buffer); if (n < 0) break; output.write(buffer, 0, n) }; output.toByteArray()
            }
            check(data.size <= 65536) { "Bridge response too large" }
            JSONObject(String(data, Charsets.UTF_8))
        } finally { deadline.cancel(); deadlines.purge(); connection.disconnect() }
    }
    override suspend fun capabilities(): Set<String> {
        val json = if (wakeSleepingHost) awaitBridgeWake { request("capabilities") } else request("capabilities")
        val supported = protocol.capabilities(json)
        if (json.optBoolean("ordered_commands")) {
            val session = request("session", JSONObject().put("purpose", "companion_control"))
            check(session.getString("boot_id") == json.getString("boot_id")) { "Bridge restarted during connection" }
            sessionId = session.getString("session_id").also { check(it.isNotBlank()) }
            sequence.set(0)
        }
        return supported
    }
    override suspend fun telemetry() = protocol.telemetry(request("telemetry"))
    override suspend fun send(command: String, ttlMs: Int): Ack {
        require(command in CommandPolicy.commands) { "Unsupported command" }
        require(ttlMs in 100..1000) { "Movement lease must be 100..1000 ms" }
        val id = UUID.randomUUID().toString()
        val body = JSONObject().put("id", id).put("command", command).put("ttl_ms", ttlMs)
        val number = sequence.incrementAndGet()
        sessionId?.let { body.put("session_id", it).put("sequence", number) }
        val response = request("commands", body)
        check(response.getString("id") == id && response.getString("command") == command) { "Acknowledgement mismatch" }
        val accepted = response.getBoolean("accepted")
        if (sessionId != null && accepted) check(response.getLong("sequence") == number) { "Acknowledgement sequence mismatch" }
        return Ack(id, accepted, command)
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
