package com.tduck.companion

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.text.AnnotatedString
import androidx.lifecycle.ViewModelProvider
import androidx.test.core.app.ActivityScenario
import androidx.test.espresso.Espresso.closeSoftKeyboard
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.*
import org.junit.Assert.*

/** Real UI/Keystore/TLS/MuJoCo path. Never uses an owner endpoint or token. */
class SecureReconnectUiTest {
 @get:Rule val compose=createEmptyComposeRule()
 private lateinit var fixture:TestBridgeFixture
 private var scenario:ActivityScenario<MainActivity>?=null
 private lateinit var model:CompanionModel
 private val credentials get()=BridgeCredentials(InstrumentationRegistry.getInstrumentation().targetContext)
 private fun launch(){scenario=ActivityScenario.launch(MainActivity::class.java);scenario!!.onActivity{model=ViewModelProvider(it)[CompanionModel::class.java]}}
 @Before fun setup(){fixture=TestBridgeFixture();credentials.clear()}
 @After fun cleanup(){scenario?.close();credentials.clear();fixture.close()}
 @Test fun settingsAndActivityRecreationKeepEndpointAndForgetRemovesConnection() {
  launch()
  val endpoint=fixture.config.getString("endpoint");val token=fixture.config.getString("token")
  compose.onNodeWithTag("tab-Settings").performClick()
  compose.onNodeWithTag("bridge-url").performScrollTo().performTextInput(endpoint)
  compose.onNodeWithTag("bridge-token").performScrollTo().performTextInput(token)
  closeSoftKeyboard();compose.onNodeWithTag("bridge-connect").performScrollTo().performClick()
  compose.waitUntil(15000){model.state.value.connected && model.state.value.source=="mujoco"}
  compose.onNodeWithTag("tab-Home").performClick();compose.onNodeWithTag("tab-Settings").performClick()
  compose.onNodeWithTag("bridge-url").performScrollTo().assert(SemanticsMatcher.expectValue(SemanticsProperties.EditableText,AnnotatedString(endpoint)))
  compose.onNodeWithTag("bridge-token").performScrollTo().assert(SemanticsMatcher.expectValue(SemanticsProperties.EditableText,AnnotatedString("")))
  scenario!!.recreate();scenario!!.onActivity{model=ViewModelProvider(it)[CompanionModel::class.java]}
  compose.waitUntil(15000){model.state.value.connected && model.state.value.source=="mujoco" && model.state.value.mode=="rest"}
  assertEquals(token,credentials.load().connection!!.token)
  assertEquals(14,model.state.value.pose!!.joints.size)
  compose.onNodeWithTag("bridge-url").performScrollTo().assert(SemanticsMatcher.expectValue(SemanticsProperties.EditableText,AnnotatedString(endpoint)))
  compose.onNodeWithTag("bridge-forget").performScrollTo().performClick()
  compose.waitUntil(5000){!model.state.value.hasSavedConnection && !model.state.value.connected}
  assertNull(credentials.load().connection)
 }
 @Test fun savedRejectedTokenIsRetainedAndDoesNotEnableControls() {
  val rejected="instrumentation-wrong-owner-token-not-a-secret"
  credentials.save(fixture.config.getString("endpoint"),rejected);launch()
  compose.waitUntil(15000){model.state.value.notice.startsWith("Authentication rejected")}
  assertFalse(model.state.value.connected);assertEquals("Offline",model.state.value.connection)
  assertTrue(model.state.value.capabilities.isEmpty());assertEquals(rejected,credentials.load().connection!!.token)
  compose.onNodeWithTag("tab-Control").performClick()
  compose.onNodeWithTag("command-forward").performScrollTo().assertIsNotEnabled()
 }
}
