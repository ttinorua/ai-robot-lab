package com.tduck.companion

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.tduck.companion.updates.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlin.math.sin

data class RobotUi(
 val connected: Boolean = true, val connection: String = "Demo connected", val simulated: Boolean = true,
 val battery: Int = 87, val voltage: Double = 7.8, val activity: String = "Resting", val mode: String = "rest",
 val status: String = "Ready", val warnings: List<String> = emptyList(), val version: String = "0.1.0-demo",
 val roll: Double = 0.0, val pitch: Double = 0.0, val yaw: Double = 0.0, val leftContact: Boolean = true,
 val rightContact: Boolean = true, val distance: Double = 120.0, val temperature: Double = 22.0,
 val motorTemp: Double = 31.0, val camera: Boolean = false, val capabilities: Set<String> = CommandPolicy.commands,
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
 private val prefs = application.getSharedPreferences("companion", 0)
 init {
  mutable.update { it.copy(voiceEnabled = prefs.getBoolean("voice", true), notice = if (prefs.contains("trusted_demo")) "Trusted demo remembered · simulated connection" else it.notice) }
  viewModelScope.launch { var tick = 0; while (true) { delay(500); tick++; if (transport == null && state.value.connected) mutable.update { it.copy(roll = sin(tick / 3.0) * 1.2, pitch = sin(tick / 4.0) * 0.8) } } }
 }
 fun connectDemo() { poll?.cancel(); motion?.cancel(); transport = null; mutable.value = RobotUi(voiceEnabled = state.value.voiceEnabled) }
 fun disconnect() { stop(); poll?.cancel(); transport = null; mutable.update { it.copy(connected = false, connection = "Disconnected", capabilities = emptySet(), mode = "rest", activity = "Offline", notice = "Disconnected. Bridge watchdog must stop motion locally.") } }
 fun stop() { command("stop") }
 fun command(command: String) {
  val snapshot = state.value
  if (!snapshot.connected) return
  if (updating && command != "stop") { mutable.update { it.copy(notice = "Movement locked during simulated installation") }; return }
  if (!CommandPolicy.allowed(command, snapshot.capabilities, snapshot.status == "Fallen")) { mutable.update { it.copy(notice = "Command unavailable in this state") }; return }
  motion?.cancel()
  val target = transport
  if (target == null) {
   applyCommand(command)
   if (command in setOf("forward", "left", "right")) motion = viewModelScope.launch { delay(800); applyCommand("stop") }
  } else {
   motion = viewModelScope.launch {
    try { val ack = withTimeout(2000) { target.send(command) }; check(ack.accepted) { "Command rejected" }; mutable.update { it.copy(notice = "Acknowledged: $command") } }
    catch (e: Exception) { if (e is CancellationException) throw e; mutable.update { it.copy(notice = "No acknowledgement. Safety stop requested; bridge watchdog required.", connected = false, connection = "Connection lost", mode = "rest") }; runCatching { withTimeout(1800) { target.send("stop") } } }
   }
  }
 }
 private fun applyCommand(command: String) {
  mutable.update { it.copy(mode = if (command == "stop" || command == "recover") "rest" else command,
   activity = when(command) { "stand" -> "Standing"; "rest" -> "Resting"; "forward" -> "Walking forward"; "left" -> "Turning left"; "right" -> "Turning right"; "recover" -> "Recovered to rest"; else -> "Stopped" },
   status = "Ready", warnings = emptyList(), notice = "Demo acknowledgement · $command") }
 }
 fun fall() { if (transport == null) { motion?.cancel(); mutable.update { it.copy(status = "Fallen", mode = "rest", activity = "Waiting for recovery", warnings = listOf("Simulated fall detected. Movement locked.")) } } }
 fun chat(text: String) {
  if (text.isBlank()) return
  val proposed = CommandPolicy.interpret(text)
  val response = when { proposed != null -> "I understood '$proposed'. Use the matching Control button to confirm. I never move from chat alone."
   "battery" in text.lowercase() -> "My ${if(state.value.simulated) "simulated " else ""}battery is ${state.value.battery}%."
   else -> "Quack! I'm a local simulated assistant. Try asking about my battery or saying 'walk forward'." }
  mutable.update { it.copy(messages = (it.messages + listOf("You: ${text.take(500)}", "T-Duck: $response")).takeLast(100)) }
 }
 fun setVoiceEnabled(value: Boolean) { prefs.edit().putBoolean("voice", value).apply(); mutable.update { it.copy(voiceEnabled = value) } }
 fun provision(code: String, ssid: String, password: String) {
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
 fun connectLocal(url: String, token: String) {
  stop(); poll?.cancel()
  poll = viewModelScope.launch {
   mutable.update { it.copy(connected = false, connection = "Connecting…") }
   try {
    val client = HttpsRobotTransport(url, token)
    val capabilities = client.capabilities()
    transport = client
    mutable.update { it.copy(capabilities = capabilities, connected = true, connection = "Simulation bridge connected") }
    while (isActive) {
     val t = client.telemetry()
     check(t.getBoolean("simulated"))
     mutable.update { it.copy(connected = true, connection = "Simulation bridge connected", simulated = true,
      battery = t.getInt("battery_percent"), voltage = t.getDouble("battery_voltage"), activity = t.getString("activity"), mode = t.getString("movement_mode"), status = t.getString("status"), version = t.getString("software_version"),
      roll = t.getDouble("roll_deg"), pitch = t.getDouble("pitch_deg"), yaw = t.getDouble("yaw_deg"), leftContact = t.getBoolean("left_contact"), rightContact = t.getBoolean("right_contact"), distance = t.getDouble("distance_cm"), temperature = t.getDouble("temperature_c"), motorTemp = t.getDouble("motor_temperature_c"), camera = t.getBoolean("camera_available"),
      warnings = t.getJSONArray("warnings").let { a -> (0 until a.length()).map(a::getString) }, notice = "Authenticated HTTPS · simulated bridge") }
     delay(500)
    }
   } catch(e: Exception) { if(e is CancellationException) throw e; mutable.update { it.copy(connected = false, connection = "Bridge unavailable", notice = "Connection failed. Check HTTPS certificate, token and bridge. Reconnect in Settings.", mode = "rest") } }
  }
 }
 fun installUpdate(ownerApproved: Boolean, channel: String) {
  if (updating) return
  val s = state.value
  if (transport != null || !s.connected) { mutable.update { it.copy(updateStatus = "Update demo requires the built-in simulated device") }; return }
  val decision = DemoUpdate.verifyAndApprove(batteryPercent = s.battery, posture = s.mode, selectedChannel = if(channel == "experimental") UpdateChannel.EXPERIMENTAL else UpdateChannel.STABLE, ownerApproved = ownerApproved)
  if (!decision.allowed) { mutable.update { it.copy(updateStatus = decision.reason) }; return }
  updating = true
  viewModelScope.launch {
   try {
    for (p in 0..100 step 20) { mutable.update { it.copy(updateProgress = p, updateStatus = "Simulated installation · $p%") }; delay(400) }
    mutable.update { it.copy(updateStatus = "Simulated health check…") }; delay(500)
    mutable.update { it.copy(version = "0.1.1-demo", updateStatus = "Demo update complete · simulated health check passed") }
   } finally { updating = false }
  }
 }
}
