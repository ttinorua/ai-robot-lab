package com.tduck.companion.updates

import org.junit.Assert.*
import org.junit.Test

class UpdateVerifierTest {
    private fun check(
        manifest: UpdateManifest = DemoUpdate.manifest,
        artifact: ByteArray = DemoUpdate.artifact,
        signature: String = DemoUpdate.signatureBase64,
        key: String = DemoUpdate.publicKeyBase64,
        hardware: String = "tduck-sim-v1",
        protocol: Int = 1,
        battery: Int = 82,
        posture: String = "rest",
        channel: UpdateChannel = UpdateChannel.STABLE,
        approved: Boolean = true
    ) = UpdateVerifier.verify(manifest, artifact, signature, key, hardware, protocol,
        battery, posture, channel, approved)

    @Test fun validSignedFixturePasses() { assertTrue(check().allowed) }
    @Test fun payloadTamperingFails() {
        assertFalse(check(manifest = DemoUpdate.manifest.copy(version = "9.9.9")).allowed)
        assertFalse(check(manifest = DemoUpdate.manifest.copy(channel = UpdateChannel.EXPERIMENTAL)).allowed)
        assertFalse(check(manifest = DemoUpdate.manifest.copy(hardware = "real-robot")).allowed)
    }
    @Test fun artifactTamperingFails() { assertFalse(check(artifact = byteArrayOf(1, 2, 3)).allowed) }
    @Test fun malformedSignatureAndKeyFailClosed() {
        assertFalse(check(signature = "invalid").allowed)
        assertFalse(check(key = "invalid").allowed)
    }
    @Test fun incompatibleDeviceRejected() {
        assertFalse(check(hardware = "real-device").allowed)
        assertFalse(check(protocol = 2).allowed)
    }
    @Test fun channelIsExplicit() { assertFalse(check(channel = UpdateChannel.EXPERIMENTAL).allowed) }
    @Test fun safetyAndApprovalGates() {
        assertFalse(check(approved = false).allowed)
        assertFalse(check(battery = 39).allowed)
        assertFalse(check(battery = 101).allowed)
        assertFalse(check(posture = "standing").allowed)
        assertTrue(check(battery = 40).allowed)
    }
    @Test fun installHasPostInstallHealthCheck() {
        val session = SimulatedUpdateSession("0.1.0-demo", DemoUpdate.manifest)
        assertTrue(session.begin(check()))
        repeat(5) { session.advance() }
        assertEquals(UpdatePhase.HEALTH_CHECK, session.phase)
        assertEquals("0.1.0-demo", session.installedVersion)
        session.advance()
        assertEquals(UpdatePhase.COMPLETE, session.phase)
        assertEquals("0.1.1-demo", session.installedVersion)
    }
    @Test fun failedHealthCheckRollsBack() {
        val session = SimulatedUpdateSession("0.1.0-demo", DemoUpdate.manifest)
        session.begin(check())
        repeat(5) { session.advance() }
        session.advance(healthCheckPasses = false)
        assertEquals(UpdatePhase.ROLLED_BACK, session.phase)
        assertEquals("0.1.0-demo", session.installedVersion)
    }
    @Test fun rejectedApprovalCannotStartInstall() {
        val session = SimulatedUpdateSession("0.1.0-demo", DemoUpdate.manifest)
        assertFalse(session.begin(check(approved = false)))
        session.advance()
        assertEquals(UpdatePhase.IDLE, session.phase)
    }
    @Test fun runtimeFallAndDisconnectCannotPassHealthCheck() {
        assertTrue(UpdateSafety.canContinue(true, true, "rest", "Ready", 0, 82))
        assertFalse(UpdateSafety.canContinue(true, true, "rest", "Fallen", 1, 82))
        assertFalse(UpdateSafety.canContinue(false, true, "rest", "Ready", 0, 82))
        assertFalse(UpdateSafety.canContinue(true, false, "rest", "Ready", 0, 82))
        assertFalse(UpdateSafety.canContinue(true, true, "forward", "Ready", 0, 82))
        assertFalse(UpdateSafety.canContinue(true, true, "rest", "Ready", 0, 39))
    }
    @Test fun releaseGateBlocksRepeatedVersionAndDowngrade() {
        assertTrue(UpdateSafety.isUpgrade("0.1.0-demo", "0.1.1-demo"))
        assertFalse(UpdateSafety.isUpgrade("0.1.1-demo", "0.1.1-demo"))
        assertFalse(UpdateSafety.isUpgrade("0.2.0-demo", "0.1.1-demo"))
        assertFalse(UpdateSafety.isUpgrade("unknown", "0.1.1-demo"))
        assertFalse(UpdateSafety.isUpgrade("0.1.0-demo", "unknown"))
        assertFalse(UpdateSafety.isUpgrade("0.1.0-demo", "0.1.0-experimental"))
    }
}
