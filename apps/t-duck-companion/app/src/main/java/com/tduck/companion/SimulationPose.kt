package com.tduck.companion

import org.json.JSONObject

/** Renderer-neutral measured state. Future 3D rendering consumes this immutable frame. */
data class JointState(val name: String, val positionRad: Double, val velocityRadS: Double)
data class LinkTransform(val name: String, val positionM: List<Double>, val quaternionWxyz: List<Double>)
data class SimulationPose(val frameId: Long, val simulationTimeS: Double, val positionM: List<Double>,
 val quaternionWxyz: List<Double>, val joints: List<JointState>, val links: List<LinkTransform>) {
 companion object {
  fun parse(json: JSONObject): SimulationPose {
   require(json.getInt("schema_version") == 1 && json.getString("coordinate_frame") == "world_z_up") { "Unsupported pose schema" }
   fun vector(value: JSONObject, key: String, count: Int): List<Double> {
    val array = value.getJSONArray(key); require(array.length() == count)
    return (0 until count).map { array.getDouble(it).also { n -> require(n.isFinite()) } }
   }
   fun quaternion(value: JSONObject): List<Double> = vector(value, "quaternion_wxyz", 4).also { q ->
    require(kotlin.math.abs(q.sumOf { it * it } - 1.0) < 0.01) { "Invalid pose quaternion" }
   }
   val frame = json.getLong("frame_id"); val time = json.getDouble("simulation_time_s")
   require(frame >= 0 && time.isFinite() && time >= 0)
   val array = json.getJSONArray("joints"); require(array.length() in 1..64)
   val joints = (0 until array.length()).map {
    val j = array.getJSONObject(it)
    JointState(j.getString("name"), j.getDouble("position_rad"), j.getDouble("velocity_rad_s")).also { v ->
     require(v.name.isNotBlank() && v.positionRad.isFinite() && v.velocityRadS.isFinite())
    }
   }
   require(joints.map { it.name }.distinct().size == joints.size)
   val linkArray = json.getJSONArray("links"); require(linkArray.length() in 1..128)
   val links = (0 until linkArray.length()).map {
    val link = linkArray.getJSONObject(it)
    LinkTransform(link.getString("name"), vector(link, "position_m", 3), quaternion(link))
   }
   require(links.all { it.name.isNotBlank() } && links.map { it.name }.distinct().size == links.size)
   return SimulationPose(frame, time, vector(json, "position_m", 3), quaternion(json), joints, links)
  }
 }
}
