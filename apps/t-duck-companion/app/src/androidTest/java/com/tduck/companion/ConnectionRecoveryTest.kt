package com.tduck.companion

import android.app.Application
import android.os.SystemClock
import androidx.lifecycle.ViewModelStore
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.delay
import org.json.JSONArray
import org.json.JSONObject
import org.junit.*
import org.junit.Assert.*
import java.io.IOException
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.atomic.AtomicInteger

/** Real Android Keystore + lifecycle/model; deterministic transport faults, not claimed MuJoCo evidence. */
class ConnectionRecoveryTest {
 private val application get() = InstrumentationRegistry.getInstrumentation().targetContext.applicationContext as Application
 private val credentials get() = BridgeCredentials(application)
 private val stores=mutableListOf<ViewModelStore>()
 private val models=mutableListOf<CompanionModel>()
 private val endpoint="https://instrumentation.invalid"
 private val token="public-model-test-token-never-owner-credentials"
 private fun <T> main(action:()->T):T {
  var result:Result<T>?=null
  InstrumentationRegistry.getInstrumentation().runOnMainSync { result=runCatching(action) }
  return result!!.getOrThrow()
 }
 private fun await(condition:()->Boolean) {
  val until=SystemClock.elapsedRealtime()+5000
  while(!condition()) { if(SystemClock.elapsedRealtime()>until) fail("Connection state did not arrive"); SystemClock.sleep(20) }
 }
 private class Probe {
  val connects=AtomicInteger();val reads=AtomicInteger();val commands=CopyOnWriteArrayList<String>()
  @Volatile var available=true
  @Volatile var rejected=false
  @Volatile var failNextMovement=false
  @Volatile var delayedAck=false
  fun client()=object:RobotTransport {
   override suspend fun capabilities():Set<String> {
    connects.incrementAndGet()
    if(rejected) throw BridgeAuthenticationException()
    if(!available) throw IOException("Fixture unavailable")
    return setOf("stand","forward","stop","rest")
   }
   override suspend fun telemetry():JSONObject {
    reads.incrementAndGet()
    if(!available)throw IOException("Fixture disconnected")
    return JSONObject().put("telemetry_source","reference_mock").put("battery_percent",87)
     .put("activity","Resting").put("movement_mode","rest").put("status","ready")
     .put("software_version","test-only").put("warnings",JSONArray())
   }
   override suspend fun send(command:String,ttlMs:Int):Ack {
    commands.add(command)
    if(command=="forward" && failNextMovement) { failNextMovement=false;throw IOException("Fixture dropped ack") }
    if(command=="forward" && delayedAck)delay(200)
    return Ack("fixture-${commands.size}",true,command)
   }
  }
 }
 private fun create(probe:Probe):CompanionModel=main {
  CompanionModel(application, credentials, {_,_->probe.client()}, 30, listOf(80,120,180)).also {
   val store=ViewModelStore();store.put("test",it);stores.add(store);models.add(it)
  }
 }
 @Before fun setup(){credentials.clear();credentials.save(endpoint,token)}
 @After fun cleanup(){main{models.forEach{it.onBackground()};stores.forEach{it.clear()}};credentials.clear()}
 @Test fun freshViewModelAutoConnectsSavedCredentialsWithoutMovement() {
  val p=Probe();val model=create(p);await{model.state.value.connected && p.reads.get()>0}
  assertEquals(endpoint,model.state.value.savedEndpoint);assertTrue(model.state.value.hasSavedConnection)
  assertTrue(p.commands.isEmpty())
  main{model.onBackground()};val fresh=create(p);await{fresh.state.value.connected && p.connects.get()==2}
  assertTrue(p.commands.all{it=="stop"});assertEquals(token,credentials.load().connection!!.token)
 }
 @Test fun temporaryFailureRecoversWithoutErasingCredentialsOrResumingMotion() {
  val p=Probe();p.available=false;val model=create(p)
  await{p.connects.get()>=1};assertFalse(model.state.value.connected)
  assertTrue(model.state.value.capabilities.isEmpty());assertEquals(token,credentials.load().connection!!.token)
  p.available=true;await{model.state.value.connected && p.reads.get()>0}
  assertTrue(p.commands.all{it=="stop"});assertTrue(model.state.value.hasSavedConnection)
 }
 @Test fun authenticationRejectionStopsRetriesAndKeepsCredentials() {
  val p=Probe();p.rejected=true;val model=create(p)
  await{model.state.value.notice.startsWith("Authentication rejected")}
  SystemClock.sleep(450);assertEquals(1,p.connects.get());assertEquals("Offline",model.state.value.connection)
  assertTrue(model.state.value.capabilities.isEmpty());assertEquals(token,credentials.load().connection!!.token)
  p.rejected=false;main{model.reconnectSaved()};await{model.state.value.connected}
 }
 @Test fun exhaustedRetryBudgetRequiresExplicitRetry() {
  val p=Probe();p.available=false;val model=create(p)
  await{model.state.value.notice.startsWith("Reconnect paused")};assertEquals(4,p.connects.get())
  SystemClock.sleep(300);assertEquals(4,p.connects.get());assertNotNull(credentials.load().connection)
  p.available=true;main{model.reconnectSaved()};await{model.state.value.connected};assertEquals(5,p.connects.get())
 }
 @Test fun backgroundStopsPollingAndForegroundReconnectsWithoutMovement() {
  val p=Probe();val model=create(p);await{p.reads.get()>1}
  main{model.onBackground()};val reads=p.reads.get();SystemClock.sleep(180)
  assertEquals(reads,p.reads.get());assertFalse(model.state.value.connected)
  main{model.onForeground()};await{model.state.value.connected && p.connects.get()==2}
  assertTrue(p.commands.all{it=="stop"})
 }
 @Test fun forgetPreventsReconnectionAndRemovesRecord() {
  val p=Probe();val model=create(p);await{p.reads.get()>0}
  main{model.forgetBridge();model.onBackground();model.onForeground()};SystemClock.sleep(200)
  assertFalse(model.state.value.connected);assertFalse(model.state.value.hasSavedConnection)
  assertEquals("",model.state.value.savedEndpoint);assertNull(credentials.load().connection);assertEquals(1,p.connects.get())
 }
 @Test fun lostMovementAckLocksControlsAndReconnectsWithoutRepeatingMovement() {
  val p=Probe();val model=create(p);await{p.reads.get()>0};p.failNextMovement=true
  main{model.command("forward")};await{p.connects.get()>=2 && model.state.value.connected}
  assertEquals(1,p.commands.count{it=="forward"});assertTrue(p.commands.contains("stop"))
  assertNotNull(credentials.load().connection)
 }
 @Test fun disconnectDuringRequestCannotPublishLateAckOrReconnect() {
  val p=Probe();val model=create(p);await{p.reads.get()>0};p.delayedAck=true
  main{model.command("forward")};await{p.commands.contains("forward")};main{model.disconnect()}
  SystemClock.sleep(300);assertFalse(model.state.value.connected);assertEquals("",model.state.value.lastAckCommand)
  assertEquals(1,p.connects.get());assertTrue(model.state.value.capabilities.isEmpty())
 }
}
