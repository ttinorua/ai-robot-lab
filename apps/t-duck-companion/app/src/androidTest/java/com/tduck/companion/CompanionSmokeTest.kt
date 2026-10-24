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
import androidx.compose.ui.test.performTextReplacement
import androidx.test.espresso.Espresso.closeSoftKeyboard
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

    @Test fun simulatedProvisioningRejectsWrongProofAndStoresOnlyTrustedIdentity() {
        compose.runOnIdle { compose.activity.getSharedPreferences("companion", 0).edit().remove("trusted_demo").commit() }
        compose.onNodeWithTag("tab-Settings").performClick()
        compose.onNodeWithText("Physical-access code").performScrollTo().performTextInput("000000")
        compose.onNodeWithText("Demo Wi-Fi name").performScrollTo().performTextInput("Invented demo network")
        compose.onNodeWithText("Demo Wi-Fi password").performScrollTo().performTextInput("invented-demo-password")
        closeSoftKeyboard()
        compose.onNodeWithText("Run simulated setup").performScrollTo().performClick()
        compose.waitUntil(5_000) { model.state.value.notice == "Demo physical-access code is 246810" }
        compose.runOnIdle {
            assertEquals(0, model.state.value.onboardingStep)
            assertNull(compose.activity.getSharedPreferences("companion", 0).getString("trusted_demo", null))
        }
        compose.onNodeWithText("Physical-access code").performScrollTo().performTextReplacement("246810")
        // The UI intentionally clears the password after every setup request.
        compose.onNodeWithText("Demo Wi-Fi password").performScrollTo().performTextInput("invented-demo-password")
        closeSoftKeyboard()
        compose.onNodeWithText("Run simulated setup").performScrollTo().performClick()
        compose.waitUntil(6_000) { model.state.value.onboardingStep == 4 }
        compose.runOnIdle {
            val stored = compose.activity.getSharedPreferences("companion", 0)
            assertEquals("demo-duck-001", stored.getString("trusted_demo", null))
            assertTrue(model.state.value.connected)
            assertTrue(model.state.value.simulated)
            assertFalse(stored.all.values.any { it == "invented-demo-password" || it == "Invented demo network" })
        }
    }

    @Test fun sensorsAndSettingsNavigationShowsAvailableReadings() {
        compose.onNodeWithTag("tab-Sensors").performClick()
        compose.onNodeWithText("A sense of the world.").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("Balance & orientation").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("Roll").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("Obstacle distance").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("Power & motors").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("Battery voltage").performScrollTo().assertIsDisplayed()
        compose.onNodeWithTag("tab-Settings").performClick()
        compose.onNodeWithText("Make it yours.").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("Assistant preferences").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("Software care • simulated OTA").performScrollTo().assertIsDisplayed()
    }

    @Test fun disconnectLocksControlsAndDemoReconnectRestoresThem() {
        compose.onNodeWithTag("tab-Settings").performClick()
        compose.onNodeWithText("Disconnect").performScrollTo().performClick()
        compose.runOnIdle { assertFalse(model.state.value.connected) }
        compose.onNodeWithTag("tab-Control").performClick()
        compose.onNodeWithTag("command-forward").performScrollTo().assertIsNotEnabled()
        compose.onNodeWithTag("command-stand").performScrollTo().assertIsNotEnabled()
        compose.onNodeWithTag("tab-Settings").performClick()
        compose.onNodeWithText("Demo mode").performScrollTo().performClick()
        compose.runOnIdle { assertTrue(model.state.value.connected) }
        compose.onNodeWithTag("tab-Control").performClick()
        compose.onNodeWithTag("command-forward").performScrollTo().assertIsEnabled()
        compose.onNodeWithTag("command-stand").performScrollTo().assertIsEnabled()
    }

}
