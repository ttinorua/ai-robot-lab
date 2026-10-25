package com.tduck.companion

import android.os.Process
import android.os.SystemClock
import android.util.Log
import androidx.lifecycle.ViewModelProvider
import androidx.test.core.app.ActivityScenario
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.Test
import org.junit.Assert.*
import java.io.File

/** Host executes this twice with a force-stop between runs. Excluded from ordinary test enumeration. */
class ProcessRestartTest {
 @Test fun seedOrRestore() {
  val instrumentation=InstrumentationRegistry.getInstrumentation()
  val context=instrumentation.targetContext
  val credentials=BridgeCredentials(context)
  val marker=File(context.filesDir,"reconnect-test-pid")
  val phase=InstrumentationRegistry.getArguments().getString("reconnectPhase")
  TestBridgeFixture().use { fixture ->
   val endpoint=fixture.config.getString("endpoint");val token=fixture.config.getString("token")
   when(phase) {
    "seed" -> {
     credentials.clear();credentials.save(endpoint,token)
     marker.writeText(Process.myPid().toString())
     assertEquals(token,BridgeCredentials(context).load().connection!!.token)
     val xml=File(context.applicationInfo.dataDir,"shared_prefs/${BridgeCredentials.PREFERENCES}.xml").readText()
     assertFalse(xml.contains(token))
    }
    "restore" -> {
     try {
      assertNotEquals(marker.readText().toInt(),Process.myPid())
      val loaded=credentials.load().connection!!
      assertEquals(endpoint,loaded.endpoint);assertEquals(token,loaded.token)
      ActivityScenario.launch(MainActivity::class.java).use { scenario ->
       lateinit var model:CompanionModel
       scenario.onActivity{model=ViewModelProvider(it)[CompanionModel::class.java]}
       val deadline=SystemClock.elapsedRealtime()+15000
       while(!model.state.value.connected || model.state.value.source!="mujoco") {
        if(SystemClock.elapsedRealtime()>deadline) fail("Saved bridge did not reconnect after process restart")
        SystemClock.sleep(30)
       }
       assertEquals("rest",model.state.value.mode);assertEquals("session-rest",model.state.value.lastTelemetryCommandId)
       assertEquals(14,model.state.value.pose!!.joints.size)
       assertTrue(model.state.value.hasSavedConnection)
       Log.i("RECONNECT_PROCESS",JSONObject().put("different_process",true).put("credentials_restored",true)
        .put("automatic_connection",true).put("actual_mujoco_telemetry",true).put("movement_mode","rest")
        .put("joint_count",14).put("token_in_plaintext_preferences",false).toString())
      }
     } finally {credentials.clear();marker.delete()}
    }
    else -> error("ProcessRestartTest requires explicit seed/restore host phases")
   }
  }
 }
}
