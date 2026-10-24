package com.tduck.companion

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.lifecycle.ViewModelProvider
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch
import org.junit.After
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.Assert.*
import java.util.concurrent.CopyOnWriteArrayList

/** Device/emulator smoke tests: user actions checked against independently observed model state. */
class CompanionSmokeTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private lateinit var model: CompanionModel
    private val observed = CopyOnWriteArrayList<RobotUi>()
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    @Before fun resetDemo() {
        compose.runOnIdle {
            model = ViewModelProvider(compose.activity)[CompanionModel::class.java]
            model.connectDemo()
            scope.launch(start = CoroutineStart.UNDISPATCHED) { model.state.collect { observed.add(it) } }
        }
    }
    @After fun cleanup() { scope.cancel() }

    @Test fun dashboardMovementTimeoutFallAndRecovery() {
        compose.onNodeWithText("Hello, friend.").assertIsDisplayed()
        compose.onNodeWithText("DEMONSTRATION • SIMULATED DEVICE").assertIsDisplayed()
        compose.onNodeWithText("87%").assertIsDisplayed()
        compose.onNodeWithTag("tab-Control").performClick()
        compose.onNodeWithTag("command-forward").performScrollTo().assertIsEnabled().performClick()
        compose.waitUntil(4_000) { observed.any { it.notice == "Demo acknowledgement · forward" && it.mode == "forward" } }
        compose.waitUntil(4_000) { observed.any { it.notice == "Demo acknowledgement · stop" && it.mode == "rest" } }
        compose.runOnIdle { assertEquals("rest", model.state.value.mode) }

        compose.onNodeWithText("Simulate a fall").performScrollTo().performClick()
        compose.onNodeWithTag("command-forward").performScrollTo().assertIsNotEnabled()
        compose.onNodeWithText("■  EMERGENCY STOP").performClick()
        compose.onNodeWithTag("command-forward").assertIsNotEnabled()
        compose.runOnIdle { assertTrue(model.state.value.status.equals("Fallen", ignoreCase = true)) }
        compose.onNodeWithTag("command-recover").performScrollTo().assertIsEnabled().performClick()
        compose.waitUntil(3_000) { model.state.value.activity == "Recovered to rest" }
        compose.onNodeWithTag("command-forward").assertIsEnabled()
    }

    @Test fun chatCannotMoveRobot() {
        compose.onNodeWithTag("tab-Talk").performClick()
        compose.onNodeWithTag("chat-input").performScrollTo().performTextInput("walk forward")
        compose.onNodeWithTag("chat-send").performScrollTo().performClick()
        compose.waitUntil(3_000) { model.state.value.messages.any { it.contains("matching Control button") } }
        compose.runOnIdle {
            assertEquals("rest", model.state.value.mode)
            assertFalse(observed.any { it.mode in setOf("forward", "left", "right") })
        }
    }

    @Test fun simulatedUpdateRequiresOwnerApproval() {
        compose.onNodeWithTag("tab-Settings").performClick()
        compose.onNodeWithTag("ota-install").performScrollTo().assertIsNotEnabled()
        compose.onNodeWithTag("ota-approval").performScrollTo().performClick()
        compose.onNodeWithTag("ota-install").performScrollTo().assertIsEnabled().performClick()
        compose.waitUntil(10_000) { model.state.value.updateStatus.contains("Demo update complete") }
        compose.runOnIdle {
            assertEquals("0.1.1-demo", model.state.value.version)
            assertEquals(100, model.state.value.updateProgress)
            assertTrue(model.state.value.simulated)
        }
    }
}
