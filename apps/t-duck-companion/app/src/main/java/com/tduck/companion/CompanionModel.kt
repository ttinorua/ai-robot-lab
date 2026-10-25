package com.tduck.companion

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.tduck.companion.updates.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlin.math.sin

data class RobotUi(
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
class CompanionModel(application: Application) : AndroidViewModel(application) {
 private val mutable = MutableStateFlow(RobotUi())
 val state = mutable.asStateFlow()
 private var transport: RobotTransport? = null
 private var poll: Job? = null
 private var motion: Job? = null
 private var updating = false
 private val provisioner = SimulatedProvisioner()
 private val assistant: AssistantProvider = LocalDemoAssistant()
 private val prefs = application.getSharedPreferences("companion", 0)
 private val credentials = BridgeCredentials(application)
 fun savedBridge(): Pair<String, String>? = credentials.load()
 fun forgetBridge() { disconnect(); credentials.clear(); mutable.update { it.copy(notice = "Saved bridge connection forgotten") } }
 fun connectRemembered(url: String, token: String) {
  try { credentials.save(url.trim(), token); connectLocal(url.trim(), token) }
  catch (_: Exception) { mutable.update { it.copy(notice = "Could not securely save connection; nothing was connected") } }
 }
 init {
  mutable.update { it.copy(voiceEnabled = prefs.getBoolean("voice", true), notice = if (prefs.contains("trusted_demo")) "Trusted demo remembered · simulated connection" else it.notice) }
  credentials.load()?.let { (url, token) -> connectLocal(url, token) }
  viewModelScope.launch { var tick = 0; while (true) { delay(500); tick++; if (transport == null && state.value.connected) mutable.update { it.copy(roll = sin(tick / 3.0) * 1.2, pitch = sin(tick / 4.0) * 0.8) } } }
 }
 private fun stopPreviousBridge() { val old = transport; if (old != null) viewModelScope.launch { runCatching { old.send("stop") } } }
 fun connectDemo() { if(updating) return; stopPreviousBridge(); poll?.cancel(); motion?.cancel(); transport = null; mutable.value = RobotUi(voiceEnabled = state.value.voiceEnabled) }
 fun disconnect() { stopPreviousBridge(); motion?.cancel(); poll?.cancel(); transport = null; mutable.update { it.copy(connected = false, connection = "Disconnected", capabilities = emptySet(), availableSensors = emptySet(), pose = null, batteryAvailable = false, mode = "rest", activity = "Offline", notice = "Disconnected. Bridge watchdog must stop motion locally.") } }
 fun stop() { command("stop") }
 fun command(command: String) {
  val snapshot = state.value
  if (!snapshot.connected) return
  if (updating && command != "stop") { mutable.update { it.copy(notice = "Movement locked during simulated installation") }; return }
  if (!CommandPolicy.allowed(command, snapshot.capabilities, !snapshot.status.equals("ready", true))) { mutable.update { it.copy(notice = "Command unavailable in this state") }; return }
  motion?.cancel()
  val target = transport
  if (target == null) {
   applyCommand(command)
   if (command in setOf("forward", "left", "right")) motion = viewModelScope.launch { delay(800); applyCommand("stop") }
  } else {
   motion = viewModelScope.launch {
    try { val ack = withTimeout(1000) { target.send(command) }; check(ack.accepted) { "Command rejected" }; mutable.update { it.copy(notice = "Acknowledged: $command", lastAckId = ack.id, lastAckCommand = command) } }
    catch (e: Exception) { if (e is CancellationException) throw e; mutable.update { it.copy(notice = "No acknowledgement. Safety stop requested; bridge watchdog required.", connected = false, connection = "Connection lost", mode = "rest") }; runCatching { withTimeout(1800) { target.send("stop") } } }
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
  stopPreviousBridge(); motion?.cancel(); poll?.cancel(); transport = null
  poll = viewModelScope.launch {
   var client: HttpsRobotTransport? = null
   var retries = 0
   while (isActive && retries < 4) {
    mutable.update { it.copy(connected = false, capabilities = emptySet(), availableSensors = emptySet(), pose = null, batteryAvailable = false, connection = if(retries == 0) "Starting secure bridge… (up to 90 seconds)" else "Reconnecting ($retries/3)…") }
    try {
     val activeClient = HttpsRobotTransport(url, token, wakeSleepingHost = retries == 0); client = activeClient
     val capabilities = activeClient.capabilities()
     val first = activeClient.telemetry()
     // Identity/protocol validation occurs in transport. Never enable commands before telemetry arrives.
     transport = activeClient
     applyTelemetry(first, capabilities)
     retries = 0
     while (isActive) { delay(200); applyTelemetry(activeClient.telemetry(), capabilities) }
    } catch(e: Exception) {
     if(e is CancellationException) throw e
     transport = null; motion?.cancel()
     mutable.update { it.copy(connected = false, capabilities = emptySet(), availableSensors = emptySet(), pose = null, batteryAvailable = false, connection = "Bridge unavailable", notice = "Link lost. Movement lease expires on bridge; retrying without resuming motion.", mode = "rest") }
     val failedClient = client
     if (failedClient != null) runCatching { failedClient.send("stop") }
     retries++
     if(retries < 4) delay(1000L * retries)
    }
   }
   mutable.update { it.copy(notice = "Reconnect paused. Check HTTPS certificate, token and bridge, then connect again.") }
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
