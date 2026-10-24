package com.tduck.companion
import org.json.JSONObject
import org.json.JSONArray
import org.junit.Test
import org.junit.Assert.*
class SimulationPoseTest {
 private fun telemetry() = JSONObject(javaClass.getResource("/tc02-telemetry.json")!!.readText())
 private fun caps() = JSONObject().put("protocol_version","1.1").put("device_id","t-duck-mujoco-001")
  .put("simulated",true).put("telemetry_source","mujoco").put("boot_id","fixture-boot")
  .put("ordered_commands",true).put("commands",JSONArray(listOf("stand","forward","stop")))
 private fun rejects(block: () -> Unit) { assertNotNull(runCatching(block).exceptionOrNull()) }
 @Test fun realMuJoCoFixtureParsesWithoutInventingBatteryOrDistance() {
  val t=telemetry(); val pose=SimulationPose.parse(t.getJSONObject("pose"))
  assertEquals(14,pose.joints.size);assertEquals(80L,pose.frameId)
  assertTrue(pose.positionM[0] > .01);assertTrue(t.isNull("battery_percent"));assertFalse(t.has("distance_cm"))
  assertEquals(1.0,pose.quaternionWxyz.sumOf { it*it },.0001)
 }
 @Test fun invalidQuaternionsAndFramesAreRejected() {
  val p=telemetry().getJSONObject("pose");p.put("quaternion_wxyz",JSONArray(listOf(0,0,0,0)))
  rejects { SimulationPose.parse(p) }
  val t=telemetry().getJSONObject("pose");t.put("coordinate_frame","unknown")
  rejects { SimulationPose.parse(t) }
 }
 @Test fun duplicateJointsAreRejected() {
  val p=telemetry().getJSONObject("pose");val a=p.getJSONArray("joints");a.put(1,a.getJSONObject(0))
  rejects { SimulationPose.parse(p) }
 }
 @Test fun sourceAndBootIdentityCannotChangeMidStream() {
  val s=RobotProtocolSession();s.capabilities(caps());s.telemetry(telemetry())
  rejects { s.telemetry(telemetry().put("boot_id","new-boot")) }
  rejects { s.telemetry(telemetry().put("telemetry_source","demo")) }
 }
 @Test fun oldFramesAndRewoundPhysicsTimeAreRejected() {
  val s=RobotProtocolSession();s.capabilities(caps());s.telemetry(telemetry())
  val old=telemetry();old.getJSONObject("pose").put("frame_id",0)
  rejects { s.telemetry(old) }
 }
 @Test fun stopAndOrderedSessionAreRequiredForMuJoCo() {
  rejects { RobotProtocolSession().capabilities(caps().put("commands",JSONArray(listOf("forward")))) }
  rejects { RobotProtocolSession().capabilities(caps().put("ordered_commands",false)) }
 }
}
