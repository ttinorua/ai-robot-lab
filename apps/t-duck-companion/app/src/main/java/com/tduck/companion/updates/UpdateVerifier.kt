package com.tduck.companion.updates

import java.security.KeyFactory
import java.security.MessageDigest
import java.security.Signature
import java.security.spec.X509EncodedKeySpec
import java.util.Base64

enum class UpdateChannel { STABLE, EXPERIMENTAL }
enum class UpdatePhase { IDLE, VERIFYING, AWAITING_APPROVAL, INSTALLING, HEALTH_CHECK, COMPLETE, ROLLED_BACK, FAILED }

/** A manifest's metadata and digest are all covered by the signature. No private key ships. */
data class UpdateManifest(
    val version: String,
    val hardware: String,
    val protocolMajor: Int,
    val channel: UpdateChannel,
    val artifactSha256: String,
    val releaseNotes: String,
    val rollbackSupported: Boolean = true,
    val component: String = "firmware"
) {
    /** Protocol v1 canonical JSON: fixed order, no whitespace, UTF-8, escaped strings. */
    fun canonicalPayload(): ByteArray = ("{\"version\":" + quote(version) +
        ",\"hardware\":" + quote(hardware) + ",\"protocol_major\":" + protocolMajor +
        ",\"channel\":" + quote(channel.name.lowercase()) + ",\"sha256\":" + quote(artifactSha256) +
        ",\"release_notes\":" + quote(releaseNotes) + ",\"rollback_supported\":" + rollbackSupported +
        ",\"component\":" + quote(component) + "}").toByteArray(Charsets.UTF_8)

    private fun quote(value: String): String = buildString {
        append('"')
        value.forEach { c -> when (c) {
            '"' -> append("\\\"")
            '\\' -> append("\\\\")
            else -> if (c.code < 32) append("\\u%04x".format(c.code)) else append(c)
        } }
        append('"')
    }
}

data class UpdateDecision(val allowed: Boolean, val reason: String)

object UpdateSafety {
    fun canContinue(connected: Boolean, builtInDemo: Boolean, posture: String, status: String,
                    warningCount: Int, batteryPercent: Int): Boolean =
        connected && builtInDemo && posture == "rest" && status.equals("ready", true) &&
            warningCount == 0 && batteryPercent in 40..100

    /** v0.1 numerical release gate. Same core version and unknown formats fail closed. */
    fun isUpgrade(current: String, candidate: String): Boolean {
        fun core(value: String): List<Long>? {
            val match = Regex("^(\\d+)\\.(\\d+)\\.(\\d+)(?:-[A-Za-z0-9.-]+)?$").matchEntire(value) ?: return null
            return match.groupValues.drop(1).map { it.toLongOrNull() ?: return null }
        }
        val old = core(current) ?: return false
        val next = core(candidate) ?: return false
        for (i in old.indices) if (next[i] != old[i]) return next[i] > old[i]
        return false
    }
}

object UpdateVerifier {
    fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(bytes).joinToString("") { "%02x".format(it) }

    fun verify(
        manifest: UpdateManifest,
        artifact: ByteArray,
        signatureBase64: String,
        trustedPublicKeyBase64: String,
        hardware: String,
        protocolMajor: Int,
        batteryPercent: Int,
        posture: String,
        selectedChannel: UpdateChannel,
        ownerApproved: Boolean
    ): UpdateDecision {
        fun reject(reason: String) = UpdateDecision(false, reason)
        val signatureValid = runCatching {
            val key = KeyFactory.getInstance("RSA").generatePublic(
                X509EncodedKeySpec(Base64.getDecoder().decode(trustedPublicKeyBase64)))
            Signature.getInstance("SHA256withRSA").run {
                initVerify(key)
                update(manifest.canonicalPayload())
                verify(Base64.getDecoder().decode(signatureBase64))
            }
        }.getOrDefault(false)
        if (!signatureValid) return reject("Manifest signature is invalid")
        if (sha256(artifact) != manifest.artifactSha256) return reject("Download integrity check failed")
        if (manifest.hardware != hardware || manifest.protocolMajor != protocolMajor)
            return reject("This update is incompatible with this device")
        if (manifest.channel != selectedChannel) return reject("Select this update's channel explicitly")
        if (manifest.component !in setOf("firmware", "policy", "skill", "configuration"))
            return reject("Unknown update component")
        if (batteryPercent !in 40..100) return reject("Charge T-Duck to at least 40%")
        if (posture != "rest") return reject("Rest T-Duck before updating")
        if (!ownerApproved) return reject("Owner approval required")
        return UpdateDecision(true, "Verified; ready for simulated installation")
    }
}

/** Simulation transaction; UI calls advance() on a timer. Never writes to a robot or motor. */
class SimulatedUpdateSession(private val oldVersion: String, private val manifest: UpdateManifest) {
    var phase: UpdatePhase = UpdatePhase.IDLE
        private set
    var progress: Int = 0
        private set
    var installedVersion: String = oldVersion
        private set

    fun begin(decision: UpdateDecision): Boolean {
        if (!decision.allowed || phase !in setOf(UpdatePhase.IDLE, UpdatePhase.FAILED, UpdatePhase.ROLLED_BACK)) return false
        phase = UpdatePhase.INSTALLING
        progress = 0
        return true
    }

    fun advance(healthCheckPasses: Boolean = true) {
        when (phase) {
            UpdatePhase.INSTALLING -> {
                progress = (progress + 20).coerceAtMost(100)
                if (progress == 100) phase = UpdatePhase.HEALTH_CHECK
            }
            UpdatePhase.HEALTH_CHECK -> {
                if (healthCheckPasses) {
                    installedVersion = manifest.version
                    phase = UpdatePhase.COMPLETE
                } else {
                    installedVersion = oldVersion
                    phase = if (manifest.rollbackSupported) UpdatePhase.ROLLED_BACK else UpdatePhase.FAILED
                }
            }
            else -> Unit
        }
    }
}
