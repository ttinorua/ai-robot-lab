package com.tduck.companion

import kotlinx.coroutines.test.runTest
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class RobotTransportTest {
    private fun envelope(id: String = "sim-001", version: String = "1.0", simulated: Boolean = true) =
        JSONObject().put("device_id", id).put("protocol_version", version).put("simulated", simulated)
            .put("commands", org.json.JSONArray(listOf("stand", "stop", "raw_motor")))

    private fun reject(block: () -> Unit) {
        try { block(); fail("Invalid protocol response accepted") } catch (_: IllegalStateException) { }
    }

    @Test fun capabilitiesBindIdentityAndFilterCommands() {
        val session = RobotProtocolSession()
        assertEquals(setOf("stand", "stop"), session.capabilities(envelope()))
        assertEquals("sim-001", session.telemetry(envelope()).getString("device_id"))
    }

    @Test fun telemetryRequiresCapabilities() = reject { RobotProtocolSession().telemetry(envelope()) }

    @Test fun telemetryCannotChangeIdentity() {
        val session = RobotProtocolSession()
        session.capabilities(envelope())
        reject { session.telemetry(envelope(id = "different-robot")) }
    }

    @Test fun hardwareCannotMasqueradeAsSimulation() {
        reject { RobotProtocolSession().capabilities(envelope(simulated = false)) }
        val session = RobotProtocolSession()
        session.capabilities(envelope())
        reject { session.telemetry(envelope(simulated = false)) }
    }

    @Test fun invalidOrChangedProtocolIsRejected() {
        for (version in listOf("2.0", "1", "1.bad", "10.0"))
            reject { RobotProtocolSession().capabilities(envelope(version = version)) }
        val session = RobotProtocolSession()
        session.capabilities(envelope())
        reject { session.telemetry(envelope(version = "2.0")) }
    }

    @Test fun emptyIdentityIsRejected() = reject { RobotProtocolSession().capabilities(envelope(id = "")) }

    @Test fun additiveProtocolMinorIsAccepted() {
        assertTrue(RobotProtocolSession().capabilities(envelope(version = "1.42")).contains("stop"))
    }

    @Test fun insecureAndCredentialBearingEndpointsAreRejected() {
        for (url in listOf("http://localhost:8443", "https://user:password@localhost", "https://localhost?token=secret", "https://localhost#secret")) {
            try { HttpsRobotTransport(url, "token"); fail("Unsafe endpoint accepted") }
            catch (_: IllegalArgumentException) { }
        }
    }

    @Test fun invalidCommandsAndLeasesAreRejectedBeforeNetwork() = runTest {
        val client = HttpsRobotTransport("https://localhost:8443", "token")
        for ((command, ttl) in listOf("raw_motor" to 500, "forward" to 0, "forward" to 1001)) {
            try { client.send(command, ttl); fail("Invalid command reached network") }
            catch (_: IllegalArgumentException) { }
        }
    }
}
