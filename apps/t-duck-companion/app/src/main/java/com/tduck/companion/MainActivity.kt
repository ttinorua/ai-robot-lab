package com.tduck.companion

import android.content.Intent
import android.os.Bundle
import android.speech.RecognizerIntent
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModelProvider

private val Navy = Color(0xFF101E30)
private val Teal = Color(0xFF39D3BC)
private val Gold = Color(0xFFF6C85F)
private val Muted = Color(0xFFAABBD0)
private val Surface = Color(0xFF1A2C42)

class MainActivity : ComponentActivity() {
    private lateinit var model: CompanionModel
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        model = ViewModelProvider(this)[CompanionModel::class.java]
        setContent {
            MaterialTheme(colorScheme = darkColorScheme(primary = Teal, secondary = Gold,
                background = Navy, surface = Surface, onPrimary = Navy, onSurface = Color.White)) {
                CompanionApp(model)
            }
        }
    }
    override fun onStop() {
        if (::model.isInitialized) model.stop()
        super.onStop()
    }
}

@Composable
private fun CompanionApp(model: CompanionModel) {
    val s by model.state.collectAsState()
    var selected by rememberSaveable { mutableIntStateOf(0) }
    val sections = listOf("Home", "Control", "Talk", "Sensors", "Settings")
    Scaffold(containerColor = Navy, bottomBar = {
        NavigationBar(containerColor = Surface) {
            sections.forEachIndexed { i, label ->
                NavigationBarItem(selected = selected == i, onClick = { selected = i }, modifier = Modifier.testTag("tab-$label"),
                    icon = { Text(listOf("⌂", "↔", "···", "◉", "⚙")[i], fontSize = 23.sp) },
                    label = { Text(label, fontSize = 11.sp) })
            }
        }
    }) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("T-DUCK", fontWeight = FontWeight.ExtraBold, fontSize = 23.sp, letterSpacing = 3.sp)
                    Text("Your little companion", color = Muted, fontSize = 12.sp)
                }
                Text(if (s.connected) "● Connected" else "○ Offline", color = if (s.connected) Teal else Gold,
                    fontSize = 12.sp)
            }
            Button(onClick = { model.stop() }, modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFB52E3D), contentColor = Color.White),
                shape = RoundedCornerShape(12.dp)) {
                Text("■  EMERGENCY STOP", fontWeight = FontWeight.Bold)
            }
            Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)) {
                Text(if (s.simulated) "DEMONSTRATION • SIMULATED DEVICE" else "LOCAL ROBOT CONNECTION",
                    fontSize = 10.sp, letterSpacing = 1.sp, color = Gold)
                if (s.notice.isNotBlank()) Info(s.notice)
                when (selected) {
                    0 -> Home(s, model, { selected = 1 }, { selected = 4 })
                    1 -> Controls(s, model)
                    2 -> Talk(s, model)
                    3 -> Sensors(s)
                    else -> Settings(s, model)
                }
                Spacer(Modifier.height(8.dp))
            }
        }
    }
}

@Composable
private fun Home(s: RobotUi, model: CompanionModel, control: () -> Unit, settings: () -> Unit) {
    Title("Hello, friend.", "A small duck. A world to explore.")
    Card(colors = CardDefaults.cardColors(containerColor = Surface), shape = RoundedCornerShape(24.dp)) {
        Column(Modifier.fillMaxWidth().padding(20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            DuckPortrait()
            Text(s.activity.replaceFirstChar { it.uppercase() }, fontSize = 25.sp, fontWeight = FontWeight.Bold)
            Text(s.connection, color = Teal, fontSize = 13.sp)
            Spacer(Modifier.height(15.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                SmallStat("Battery", "${s.battery}%")
                SmallStat("Mode", s.mode)
                SmallStat("Software", s.version)
            }
        }
    }
    Section("Ready when you are") {
        Text("${s.status} • ${if (s.simulated) "All readings are simulated" else "Live local telemetry"}", color = Muted)
        s.warnings.forEach { Text("!  $it", color = Gold) }
        Button(onClick = control, modifier = Modifier.fillMaxWidth()) { Text("Open movement controls") }
        OutlinedButton(onClick = settings, modifier = Modifier.fillMaxWidth()) { Text("Set up your T-Duck") }
    }
    if (!s.connected) Button(onClick = model::connectDemo, modifier = Modifier.fillMaxWidth()) { Text("Meet demo T-Duck") }
}

@Composable
private fun DuckPortrait() {
    Canvas(Modifier.size(210.dp, 160.dp)) {
        val w = size.width; val h = size.height
        drawOval(Color(0xFF0F1D2E), Offset(w * .13f, h * .87f), Size(w * .74f, h * .1f))
        drawRoundRect(Color(0xFF52748D), Offset(w*.35f,h*.7f), Size(w*.07f,h*.2f), cornerRadius = androidx.compose.ui.geometry.CornerRadius(9f))
        drawRoundRect(Color(0xFF52748D), Offset(w*.60f,h*.7f), Size(w*.07f,h*.2f), cornerRadius = androidx.compose.ui.geometry.CornerRadius(9f))
        drawOval(Teal, Offset(w*.20f,h*.32f), Size(w*.59f,h*.44f))
        drawOval(Color(0xFFB0F3DD), Offset(w*.27f,h*.39f), Size(w*.38f,h*.29f))
        drawCircle(Teal, w*.18f, Offset(w*.62f,h*.29f))
        drawOval(Gold, Offset(w*.72f,h*.31f), Size(w*.20f,h*.10f))
        drawCircle(Navy, w*.025f, Offset(w*.67f,h*.25f))
        drawCircle(Color.White, w*.008f, Offset(w*.676f,h*.24f))
        drawLine(Gold, Offset(w*.26f,h*.91f), Offset(w*.43f,h*.91f), 12f)
        drawLine(Gold, Offset(w*.55f,h*.91f), Offset(w*.73f,h*.91f), 12f)
    }
}

@Composable
private fun Controls(s: RobotUi, model: CompanionModel) {
    Title("Let's move.", "Gentle steps, with safety close by.")
    Info("Movement runs in short, 800 ms bursts. Leaving the app requests stop. The robot must also enforce its own movement timeout.")
    Section("Movement • ${s.mode}") {
        CommandRow(s, model, listOf("stand" to "Stand", "rest" to "Rest"))
        CommandRow(s, model, listOf("forward" to "↑  Forward"))
        CommandRow(s, model, listOf("left" to "↶  Left", "right" to "Right  ↷"))
        CommandRow(s, model, listOf("stop" to "■  Stop", "recover" to "Recover"))
        Text("Only capabilities reported by this device are available.", color = Muted, fontSize = 12.sp)
    }
    Section("Robot state") {
        Text(s.activity, fontWeight = FontWeight.Bold)
        s.warnings.forEach { Text(it, color = Gold) }
        if (s.simulated) OutlinedButton(onClick = model::fall, enabled = s.connected) { Text("Simulate a fall") }
    }
}

@Composable
private fun CommandRow(s: RobotUi, model: CompanionModel, commands: List<Pair<String, String>>) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        commands.forEach { (command, label) ->
            Button(onClick = { model.command(command) }, enabled = s.connected && CommandPolicy.allowed(command, s.capabilities, s.status.equals("Fallen", ignoreCase = true)),
                modifier = Modifier.weight(1f).heightIn(min = 54.dp).testTag("command-$command"), shape = RoundedCornerShape(14.dp)) { Text(label) }
        }
    }
}

@Composable
private fun Talk(s: RobotUi, model: CompanionModel) {
    var text by rememberSaveable { mutableStateOf("") }
    val context = androidx.compose.ui.platform.LocalContext.current
    val voice = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()?.let(model::chat)
    }
    Title("A little conversation.", "Say hello, ask a question, make a plan.")
    Info("Demo assistant • no paid AI service. Movement suggestions require your confirmation in Control; chat never sends motor commands.")
    s.messages.forEach { message ->
        Card(colors = CardDefaults.cardColors(containerColor = if (message.startsWith("You:")) Color(0xFF254C57) else Surface),
            modifier = Modifier.fillMaxWidth()) { Text(message, Modifier.padding(16.dp), lineHeight = 23.sp) }
    }
    Section("Talk to T-Duck") {
        OutlinedTextField(value = text, onValueChange = { text = it }, label = { Text("Your message") }, modifier = Modifier.fillMaxWidth().testTag("chat-input"))
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Button(onClick = { model.chat(text); text = "" }, enabled = text.isNotBlank(), modifier = Modifier.testTag("chat-send")) { Text("Send") }
            OutlinedButton(onClick = {
                try {
                    voice.launch(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                        .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                        .putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
                        .putExtra(RecognizerIntent.EXTRA_PROMPT, "Talk to T-Duck"))
                } catch (_: Exception) { Toast.makeText(context, "No speech recognition app is installed.", Toast.LENGTH_LONG).show() }
            }, enabled = s.voiceEnabled) { Text("Voice") }
        }
        Text("Voice uses your phone's speech service, which may require its own network access.", color = Muted, fontSize = 12.sp)
    }
}

@Composable
private fun Sensors(s: RobotUi) {
    Title("A sense of the world.", if (s.simulated) "Illustrative readings from your demo duck." else "Readings reported by your robot.")
    if ("imu" in s.availableSensors || "feet" in s.availableSensors) Section("Balance & orientation") {
        if ("imu" in s.availableSensors) {
            Reading("Roll", "%.1f°".format(s.roll)); Reading("Pitch", "%.1f°".format(s.pitch)); Reading("Yaw", "%.1f°".format(s.yaw))
        }
        if ("feet" in s.availableSensors) {
            Reading("Left foot", if (s.leftContact) "In contact" else "Raised")
            Reading("Right foot", if (s.rightContact) "In contact" else "Raised")
        }
    }
    if (s.availableSensors.any { it in setOf("distance", "temperature", "camera") }) Section("Nearby & environment") {
        if ("distance" in s.availableSensors) Reading("Obstacle distance", "%.0f cm".format(s.distance))
        if ("temperature" in s.availableSensors) Reading("Temperature", "%.1f °C".format(s.temperature))
        if ("camera" in s.availableSensors) Reading("Camera", if (s.camera) "Available" else "Not available")
    }
    if ("battery" in s.availableSensors || "motors" in s.availableSensors) Section("Power & motors") {
        if ("battery" in s.availableSensors) {
            Reading("Charge", "${s.battery}%"); Reading("Battery voltage", "%.2f V".format(s.voltage))
        }
        if ("motors" in s.availableSensors) Reading("Motor temperature", "%.1f °C".format(s.motorTemp))
    }
    Info("Only readings supplied by the connected device are shown. Pressure, touch and motor-position streams are not available in this build.")
}

@Composable
private fun Settings(s: RobotUi, model: CompanionModel) {
    var code by remember { mutableStateOf("") }; var ssid by remember { mutableStateOf("") }; var password by remember { mutableStateOf("") }
    var url by remember { mutableStateOf("") }; var token by remember { mutableStateOf("") }
    var channel by rememberSaveable { mutableStateOf("stable") }; var approved by remember { mutableStateOf(false) }
    Title("Make it yours.", "Connection, preferences and a little care.")
    Section("Connection") {
        Text(s.connection, color = Teal)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = model::connectDemo) { Text("Demo mode") }
            OutlinedButton(onClick = model::disconnect) { Text("Disconnect") }
        }
    }
    Section("First-time setup • simulated BLE") {
        Text("1  Discover  →  2  Pair  →  3  Wi-Fi  →  4  Trust", color = Gold, fontSize = 12.sp)
        Text("Practice setup with a nearby simulated T-Duck. No Bluetooth radio or hardware pairing is used.", color = Muted)
        Text("Demo physical-access code: 246810", fontSize = 13.sp)
        OutlinedTextField(code, { code = it }, label = { Text("Physical-access code") }, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(ssid, { ssid = it }, label = { Text("Demo Wi-Fi name") }, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(password, { password = it }, label = { Text("Demo Wi-Fi password") }, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth())
        Button(onClick = { model.provision(code, ssid, password); password = "" }, enabled = code.isNotBlank() && ssid.isNotBlank()) { Text("Run simulated setup") }
        if (s.onboardingStep > 0) Text("Setup stage ${s.onboardingStep}/4", color = Teal)
        Text("Use example credentials. Real secure provisioning awaits hardware validation.", color = Muted, fontSize = 12.sp)
    }
    Section("Local simulation bridge") {
        Text("Connect to a protocol v1 bridge using HTTPS and a trusted certificate. Internet is not required. Credentials stay in this session.", color = Muted)
        OutlinedTextField(url, { url = it }, label = { Text("HTTPS bridge address") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(token, { token = it }, label = { Text("Owner access token") }, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth())
        Button(onClick = { model.connectLocal(url.trim(), token) }, enabled = url.isNotBlank() && token.isNotBlank()) { Text("Connect locally") }
    }
    Section("Assistant preferences") {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Enable voice input", Modifier.weight(1f))
            Switch(checked = s.voiceEnabled, onCheckedChange = model::setVoiceEnabled)
        }
        Text("Friendly demo assistant • local interpretation only", color = Muted, fontSize = 12.sp)
    }
    Section("Software care • simulated OTA") {
        Reading("Installed version", s.version)
        Text("Demo release 0.1.1: improved companion responses and safety checks. No physical firmware is flashed.", color = Muted)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(selected = channel == "stable", onClick = { channel = "stable"; approved = false }, label = { Text("Stable") })
            FilterChip(selected = channel == "experimental", onClick = { channel = "experimental"; approved = false }, label = { Text("Experimental") })
        }
        if (channel == "experimental") Text("Experimental channel: explicitly selected; may be unstable.", color = Gold)
        Text("Installation requires a verified signature, compatible device, sufficient charge, safe posture and owner approval.", fontSize = 12.sp, color = Muted)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = approved, onCheckedChange = { approved = it }, modifier = Modifier.testTag("ota-approval"))
            Text("I approve this simulated installation", fontSize = 13.sp)
        }
        Button(onClick = { model.installUpdate(approved, channel); approved = false }, enabled = approved && s.connected && s.simulated && s.updateProgress !in 1..99, modifier = Modifier.testTag("ota-install")) { Text("Verify & simulate update") }
        if (s.updateProgress in 1..99) LinearProgressIndicator(progress = { s.updateProgress / 100f }, modifier = Modifier.fillMaxWidth())
        if (s.updateStatus.isNotBlank()) Text(s.updateStatus, color = Teal)
        Text("App updates use standard Android installation. Hardware OTA and rollback are not yet validated.", color = Muted, fontSize = 12.sp)
    }
}

@Composable private fun Title(title: String, subtitle: String) {
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text(title, fontSize = 28.sp, fontWeight = FontWeight.Bold, lineHeight = 34.sp)
        Text(subtitle, color = Muted, lineHeight = 21.sp)
    }
}
@Composable private fun Section(title: String, content: @Composable ColumnScope.() -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = Surface), shape = RoundedCornerShape(20.dp), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(title, fontWeight = FontWeight.Bold, fontSize = 17.sp)
            content()
        }
    }
}
@Composable private fun Info(text: String) {
    Text(text, color = Muted, fontSize = 12.sp, lineHeight = 18.sp,
        modifier = Modifier.fillMaxWidth().background(Color(0xFF17283C), RoundedCornerShape(12.dp)).padding(12.dp))
}
@Composable private fun Reading(name: String, value: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(name, color = Muted); Text(value, color = Teal, fontWeight = FontWeight.Medium)
    }
}
@Composable private fun SmallStat(label: String, value: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(value, fontWeight = FontWeight.Bold, color = Teal, fontSize = 16.sp)
        Text(label, color = Muted, fontSize = 11.sp)
    }
}
