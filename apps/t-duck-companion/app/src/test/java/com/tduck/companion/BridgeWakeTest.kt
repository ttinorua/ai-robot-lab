package com.tduck.companion

import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test
import java.net.SocketTimeoutException
import javax.net.ssl.SSLHandshakeException

class BridgeWakeTest {
    @Test fun sleepingHostDiscoveryEventuallySucceeds() = runTest {
        var calls = 0
        val value = awaitBridgeWake { calls++; if (calls < 3) throw SleepingBridge(503); "capabilities" }
        assertEquals("capabilities", value); assertEquals(3, calls)
    }
    @Test fun socketTimeoutMayWakeButBudgetIsBounded() = runTest {
        var calls = 0
        try { awaitBridgeWake(attempts = 3) { calls++; throw SocketTimeoutException() }; fail() }
        catch (_: SocketTimeoutException) { assertEquals(3, calls) }
    }
    @Test fun certificateFailureIsNeverRetried() = runTest {
        var calls = 0
        try { awaitBridgeWake { calls++; throw SSLHandshakeException("untrusted") }; fail() }
        catch (_: SSLHandshakeException) { assertEquals(1, calls) }
    }
    @Test fun authenticationFailureIsNeverRetried() = runTest {
        var calls = 0
        try { awaitBridgeWake { calls++; error("401") }; fail() }
        catch (_: IllegalStateException) { assertEquals(1, calls) }
    }
}
