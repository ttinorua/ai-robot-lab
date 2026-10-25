package com.tduck.companion

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.tduck.companion.updates.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlin.math.sin

data class RobotUi(
 val savedEndpoint: String = "", val hasSavedConnection: Boolean = false,
 val source: String = "demo", val batteryAvailable: Boolean = true,
 val pose: SimulationPose? = null, val motionState: String = "rest",
 val leftForceN: Double? = null, val rightForceN: Double? = null,
 val lastAckId: String = "", val lastAckCommand: String = "", val lastTelemetryCommandId: String = "",
 val connected: Boolean = true, val connection: String = "Demo connected", val simulated: Boolean = true,
 val battery: Int = 87, val voltage: Double = 7.8, val activity: String = "Resting", val mode: String = "rest",
 val status: String = "Ready", val warnings: List<String> = emptyList(), val version: String = "0.1.0-demo",
 val roll: Double = 0.0, val pitch: Double = 0.0, val yaw: Double = 0.0, val leftContact: Boolean = true,
 val rightContact: Boolean = true, val distance: Double = 120.0, val temperature: Double = 22.0,
 val motorTemp: Double = 31.0, val camera: Boolean = false, val capabilities: Set<String> = CommandPolicy.commands,
 val availableSensors: Set<String> = setOf("imu", "feet", "distance", "temperature", "motors", "battery", "camera"),
 val messages: List<String> = listOf("T-Duck: Hello! I'm your simulated companion. Let's explore safely."),
 val notice: String = "Demo mode · no physical robot connected", val updateProgress: Int = 0,
 val updateStatus: String = "Stable demo update 0.1.1 available", val onboardingStep: Int = 0, val voiceEnabled: Boolean = true
)
class CompanionModel @JvmOverloads constructor(
 application: Application,
 private val credentials: ConnectionCredentialStore = BridgeCredentials(application),
 private val transportFactory: (String, String) -> RobotTransport = { url, token -> HttpsRobotTransport(url, token) },
 private val pollingMs: Long = 200,
 private val retryDelaysMs: List<Long> = listOf(1000, 2000, 4000)
) : AndroidViewModel(application) {
 private val mutable = MutableStateFlow(RobotUi())
 val state = mutable.asStateFlow()
 private var transport: RobotTransport? = null
 private var poll: Job? = null
 private var motion: Job? = null
 private var updating = false
 private val provisioner = SimulatedProvisioner()
 private val assistant: AssistantProvider = LocalDemoAssistant()
 private val prefs = application.getSharedPreferences("companion", 0)
 private var reconnectAllowed = true
 private var foreground = true
 private var connectionEpoch = 0L
 private var commandLinkFailed = false
 fun forgetBridge() {
  disconnect()
  val removed = credentials.clear()
  mutable.update { it.copy(savedEndpoint = "", hasSavedConnection = false, notice = if (removed) "Saved bridge connection forgotten" else "Connection disabled. Secure storage removal failed; retry Forget.") }
 }
 fun connectRemembered(url: String, token: String): Boolean {
  if(updating) return false
  return try {
   val endpoint = BridgeEndpoint.normalize(url)
   val accessToken = token.ifBlank {
    val saved = credentials.load().connection
    require(saved != null && saved.endpoint == endpoint) { "Enter an access token for this address" }
    saved.token
   }
   credentials.save(endpoint, accessToken)
   mutable.update { it.copy(savedEndpoint = endpoint, hasSavedConnection = true) }
   reconnectAllowed = true
   connectLocal(endpoint, accessToken)
   true
  } catch (_: Exception) { mutable.update { it.copy(notice = "Could not securely save connection. Check the HTTPS address/token, or re-enter credentials if the device key changed.") }; false }
 }
 fun reconnectSaved() {
  if(updating) return
  val saved = credentials.load()
  if(saved.connection != null) {
   reconnectAllowed = true
   mutable.update { it.copy(savedEndpoint = saved.connection.endpoint, hasSavedConnection = true) }
   connectLocal(saved.connection.endpoint, saved.connection.token)
  } else if(saved.unreadable) {
   disconnect()
   mutable.update { it.copy(savedEndpoint = "", hasSavedConnection = false, notice = "Saved connection cannot be decrypted. Enter its address and token again.") }
  }
 }
 fun onForeground() {
  foreground = true
  if(reconnectAllowed && !state.value.connected && poll?.isActive != true) reconnectSaved()
 }
 fun onBackground() {
  val wasRemote = poll?.isActive == true || transport != null || state.value.source != "demo"
  foreground = false
  stopPreviousBridge(); connectionEpoch++; motion?.cancel(); poll?.cancel(); transport = null
  if(wasRemote) offline("Offline", "App in background. Movement lease remains enforced by the bridge.")
 }
 private fun offline(connection: String, notice: String) {
  mutable.update { it.copy(connected = false, connection = connection, capabilities = emptySet(), availableSensors = emptySet(), pose = null,
   batteryAvailable = false, mode = "rest", activity = "Offline", notice = notice) }
 }
 init {
  mutable.update { it.copy(voiceEnabled = prefs.getBoolean("voice", true), notice = if (prefs.contains("trusted_demo")) "Trusted demo remembered · simulated connection" else it.notice) }
  reconnectSaved()
  viewModelScope.launch { var tick = 0; while (true) { delay(500); tick++; if (foreground && transport == null && state.value.connected) mutable.update { it.copy(roll = sin(tick / 3.0) * 1.2, pitch = sin(tick / 4.0) * 0.8) } } }
 }
 private fun stopPreviousBridge() { val old = transport; if (old != null) viewModelScope.launch { runCatching { old.send("stop") } } }
 fun connectDemo() { if(updating) return; reconnectAllowed = false; connectionEpoch++; stopPreviousBridge(); poll?.cancel(); motion?.cancel(); transport = null; mutable.value = RobotUi(voiceEnabled = state.value.voiceEnabled, savedEndpoint = state.value.savedEndpoint, hasSavedConnection = state.value.hasSavedConnection) }
 fun disconnect() {
  reconnectAllowed = false; connectionEpoch++; stopPreviousBridge(); motion?.cancel(); poll?.cancel(); transport = null
  offline("Offline", "Disconnected. Saved credentials are retained; bridge watchdog stops movement locally.")
 }
 fun stop() { command("stop") }
 fun command(command: String) {
  val snapshot = state.value
  if (!snapshot.connected) return
  if (updating && command != "stop") { mutable.update { it.copy(notice = "Movement locked during simulated installation") }; return }
  if (!CommandPolicy.allowed(command, snapshot.capabilities, !snapshot.status.equals("ready", true))) { mutable.update { it.copy(notice = "Command unavailable in this state") }; return }
  motion?.cancel()
  val target = transport
  val epoch = connectionEpoch
  if (target == null) {
   applyCommand(command)
   if (command in setOf("forward", "left", "right")) motion = viewModelScope.launch { delay(800); applyCommand("stop") }
  } else {
   motion = viewModelScope.launch {
    try { val ack = withTimeout(1000) { target.send(command) }; check(ack.accepted) { "Command rejected" }; if(epoch != connectionEpoch || target !== transport) return@launch; mutable.update { it.copy(notice = "Acknowledged: $command", lastAckId = ack.id, lastAckCommand = command) } }
    catch (e: Exception) {
     if (e is CancellationException && e !is TimeoutCancellationException) throw e
     if(epoch != connectionEpoch || target !== transport) return@launch
     commandLinkFailed = true
     offline("Offline", "No acknowledgement. Safety stop requested; bridge watchdog remains authoritative.")
     runCatching { withTimeout(1800) { target.send("stop") } }
    }
   }
  }
 }
 private fun applyCommand(command: String) {
  mutable.update {
   val fallen = it.status.equals("fallen", true) && command != "recover"
   it.copy(mode = if (command == "stop" || command == "recover") "rest" else command,
   activity = when(command) { "stand" -> "Standing"; "rest" -> "Resting"; "forward" -> "Walking forward"; "left" -> "Turning left"; "right" -> "Turning right"; "recover" -> "Recovered to rest"; else -> "Stopped" },
   status = if (fallen) "Fallen" else "Ready", warnings = if (fallen) it.warnings else emptyList(), notice = "Demo acknowledgement · $command") }
 }
 fun fall() { if (state.value.source == "demo" && transport == null) { motion?.cancel(); mutable.update { it.copy(status = "Fallen", mode = "rest", activity = "Waiting for recovery", warnings = listOf("Simulated fall detected. Movement locked.")) } } }
 fun chat(text: String) {
  if (text.isBlank()) return
  val response = if (!state.value.batteryAvailable && "battery" in text.lowercase())
   if(state.value.source == "mujoco") "The MuJoCo model has no battery sensor. A battery reading is unavailable."
   else "No battery reading is available while disconnected."
   else assistant.reply(text.take(500), state.value.battery).text
  mutable.update { it.copy(messages = (it.messages + listOf("You: ${text.take(500)}", "T-Duck: $response")).takeLast(100)) }
 }
 fun setVoiceEnabled(value: Boolean) { prefs.edit().putBoolean("voice", value).apply(); mutable.update { it.copy(voiceEnabled = value) } }
 fun provision(code: String, ssid: String, password: String) {
  if(updating) return
  viewModelScope.launch { try {
   mutable.update { it.copy(onboardingStep = 1, notice = "Discovering simulated BLE device…") }
   provisioner.discover()
   mutable.update { it.copy(onboardingStep = 2, notice = "Checking demo physical-access proof…") }
   val device = provisioner.provision(code, ssid, password)
   mutable.update { it.copy(onboardingStep = 3, notice = "Simulating Wi-Fi verification…") }; delay(400)
   prefs.edit().putString("trusted_demo", device.id).apply()
   connectDemo(); mutable.update { it.copy(onboardingStep = 4, notice = "Demo setup complete. Trusted simulated identity saved; no real BLE pairing performed.") }
  } catch(e: Exception) { mutable.update { it.copy(onboardingStep = 0, notice = e.message ?: "Demo setup failed") } } }
 }
 private fun applyTelemetry(t: org.json.JSONObject, capabilities: Set<String>) {
  val sensors = buildSet {
   if (!t.isNull("roll_deg") && !t.isNull("pitch_deg") && !t.isNull("yaw_deg")) add("imu")
   if (!t.isNull("left_contact") && !t.isNull("right_contact")) add("feet")
   if (!t.isNull("distance_cm")) add("distance")
   if (!t.isNull("temperature_c")) add("temperature")
   if (!t.isNull("motor_temperature_c")) add("motors")
   if (!t.isNull("battery_voltage")) add("battery")
   if (!t.isNull("camera_available")) add("camera")
  }
  val source = t.optString("telemetry_source", "reference_mock")
  val batteryAvailable = !t.isNull("battery_percent")
  val battery = if (batteryAvailable) t.getInt("battery_percent").also { require(it in 0..100) } else 0
  val pose = if (source == "mujoco") SimulationPose.parse(t.getJSONObject("pose")) else null
  mutable.update { it.copy(connected = true, connection = if (source == "mujoco") "MuJoCo connected" else "Simulation bridge connected", capabilities = capabilities, simulated = true,
   source = source, batteryAvailable = batteryAvailable, pose = pose, motionState = t.optString("motion_state", t.getString("movement_mode")),
   leftForceN = if(t.isNull("left_contact_force_n")) null else t.getDouble("left_contact_force_n"),
   rightForceN = if(t.isNull("right_contact_force_n")) null else t.getDouble("right_contact_force_n"),
   lastTelemetryCommandId = t.optString("last_command_id", ""),
   battery = battery, voltage = t.optDouble("battery_voltage", 0.0), activity = t.getString("activity"), mode = t.getString("movement_mode"), status = t.getString("status"), version = t.getString("software_version"),
   roll = t.optDouble("roll_deg", 0.0), pitch = t.optDouble("pitch_deg", 0.0), yaw = t.optDouble("yaw_deg", 0.0), leftContact = t.optBoolean("left_contact"), rightContact = t.optBoolean("right_contact"), distance = t.optDouble("distance_cm", 0.0), temperature = t.optDouble("temperature_c", 0.0), motorTemp = t.optDouble("motor_temperature_c", 0.0), camera = t.optBoolean("camera_available"), availableSensors = sensors,
   warnings = t.getJSONArray("warnings").let { a -> (0 until a.length()).map(a::getString) }, notice = if(source == "mujoco") "Live MuJoCo state · authenticated HTTPS" else "Authenticated HTTPS · synthetic reference mock") }
 }
 fun connectLocal(url: String, token: String) {
  if(updating) return
  val endpoint = try { BridgeEndpoint.normalize(url) } catch (_: Exception) {
   mutable.update { it.copy(notice = "Enter a valid HTTPS bridge address") }; return
  }
  stopPreviousBridge(); connectionEpoch++; motion?.cancel(); poll?.cancel(); transport = null
  val epoch = connectionEpoch
  commandLinkFailed = false
  offline("Connecting", "Connecting securely. Movement remains locked until validated telemetry arrives.")
  poll = viewModelScope.launch {
   var failures = 0
   // One bounded foreground retry budget. A momentary success does not reset a flapping link forever.
   while (isActive && foreground && epoch == connectionEpoch) {
    var client: RobotTransport? = null
    try {
     val active = transportFactory(endpoint, token); client = active
     val capabilities = active.capabilities()
     val first = active.telemetry()
     ensureActive()
     if(epoch != connectionEpoch || !foreground) return@launch
     transport = active; commandLinkFailed = false
     applyTelemetry(first, capabilities)
     while (isActive && foreground && epoch == connectionEpoch) {
      delay(pollingMs)
      if(commandLinkFailed) throw java.io.IOException("Command link failed")
      val next = active.telemetry()
      ensureActive()
      if(commandLinkFailed) throw java.io.IOException("Command link failed")
      if(epoch != connectionEpoch || !foreground) return@launch
      applyTelemetry(next, capabilities)
     }
    } catch(e: Exception) {
     if(e is CancellationException) throw e
     if(epoch != connectionEpoch) return@launch
     transport = null; motion?.cancel()
     offline("Offline", "Connection unavailable. Saved credentials retained; motion will not resume automatically.")
     if(client != null) runCatching { withTimeout(1000) { client.send("stop") } }
     val terminal = e is BridgeAuthenticationException || e is javax.net.ssl.SSLException ||
      e is IllegalArgumentException || e is IllegalStateException || e is org.json.JSONException
     if(terminal || failures >= retryDelaysMs.size) {
      reconnectAllowed = false
      mutable.update { it.copy(notice = if(e is BridgeAuthenticationException) "Authentication rejected. Saved credentials retained; correct the token and reconnect." else "Reconnect paused. Check Tailscale, VPS, certificate and saved settings, then retry.") }
      return@launch
     }
     val wait = retryDelaysMs[failures++]
     mutable.update { it.copy(connection = "Connecting", notice = "Retry $failures/${retryDelaysMs.size}. Saved credentials retained; no movement will resume.") }
     delay(wait)
    }
   }
  }
 }
 fun installUpdate(ownerApproved: Boolean, channel: String) {
  if (updating) return
  val s = state.value
  fun safeToContinue(): Boolean {
   val current = state.value
   return UpdateSafety.canContinue(current.connected, transport == null, current.mode,
    current.status, current.warnings.size, current.battery)
  }
  if (!UpdateSafety.isUpgrade(s.version, DemoUpdate.manifest.version)) {
   mutable.update { it.copy(updateStatus = "No newer compatible demo release available") }; return
  }
  if (!safeToContinue()) {
   mutable.update { it.copy(updateStatus = "Update requires a connected, healthy built-in demo at rest with at least 40% battery") }; return
  }
  val decision = DemoUpdate.verifyAndApprove(batteryPercent = s.battery, posture = s.mode, selectedChannel = if(channel == "experimental") UpdateChannel.EXPERIMENTAL else UpdateChannel.STABLE, ownerApproved = ownerApproved)
  if (!decision.allowed) { mutable.update { it.copy(updateStatus = decision.reason) }; return }
  updating = true
  viewModelScope.launch {
   try {
    val session = SimulatedUpdateSession(s.version, DemoUpdate.manifest)
    check(session.begin(decision))
    var interrupted = false
    while (session.phase == UpdatePhase.INSTALLING) {
     delay(400)
     if (!safeToContinue()) interrupted = true
     session.advance()
     mutable.update { it.copy(updateProgress = session.progress, updateStatus =
      if (interrupted) "Demo update interrupted · preparing rollback" else "Simulated installation · ${session.progress}%") }
    }
    mutable.update { it.copy(updateStatus = "Simulated health check…") }; delay(500)
    session.advance(healthCheckPasses = !interrupted && safeToContinue())
    mutable.update { it.copy(version = session.installedVersion, updateStatus = if(session.phase == UpdatePhase.COMPLETE) "Demo update complete · simulated health check passed" else "Demo health check failed or connection interrupted · rolled back") }
   } finally { updating = false }
  }
 }
}
