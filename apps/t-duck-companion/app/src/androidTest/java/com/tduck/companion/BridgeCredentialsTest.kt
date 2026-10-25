package com.tduck.companion

import android.content.Context
import android.util.Base64
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.*
import org.junit.Assert.*
import java.security.KeyStore

class BridgeCredentialsTest {
 private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
 private val prefs get() = context.getSharedPreferences(BridgeCredentials.PREFERENCES, Context.MODE_PRIVATE)
 private val endpoint = "https://instrumentation.invalid"
 private val token = "public-instrumentation-fixture-never-owner-credentials"
 @Before fun clearBefore() { BridgeCredentials(context).clear() }
 @After fun clearAfter() { BridgeCredentials(context).clear() }
 @Test fun newStoreRestoresEndpointAndTokenWithoutPlaintextPreferences() {
  BridgeCredentials(context).save(endpoint + "/", token)
  val loaded = BridgeCredentials(context).load().connection!!
  assertEquals(endpoint, loaded.endpoint); assertEquals(token, loaded.token)
  assertFalse(prefs.all.values.joinToString().contains(token))
  assertFalse(loaded.toString().contains(token))
  val xml = java.io.File(context.applicationInfo.dataDir, "shared_prefs/${BridgeCredentials.PREFERENCES}.xml").readText()
  assertFalse(xml.contains(token))
  val key=KeyStore.getInstance("AndroidKeyStore").apply{load(null)}.getKey(BridgeCredentials.ALIAS,null)
  assertNull(key.encoded)
  val info=javax.crypto.SecretKeyFactory.getInstance("AES","AndroidKeyStore").getKeySpec(key as javax.crypto.SecretKey,android.security.keystore.KeyInfo::class.java) as android.security.keystore.KeyInfo
  assertEquals(256,info.keySize)
 }
 @Test fun repeatedSaveUsesFreshGcmNonce() {
  val store=BridgeCredentials(context)
  store.save(endpoint,token);val iv=prefs.getString("iv",null);val ciphertext=prefs.getString("token",null)
  store.save(endpoint,token)
  assertNotEquals(iv,prefs.getString("iv",null));assertNotEquals(ciphertext,prefs.getString("token",null))
  assertEquals(token,store.load().connection!!.token)
 }
 @Test fun forgetDeletesRecordAndKeystoreAlias() {
  val store=BridgeCredentials(context);store.save(endpoint,token)
  assertTrue(store.clear());assertTrue(prefs.all.isEmpty());assertNull(store.load().connection)
  val ks=KeyStore.getInstance("AndroidKeyStore").apply{load(null)}
  assertFalse(ks.containsAlias(BridgeCredentials.ALIAS))
 }
 @Test fun missingKeyFailsClosedWithoutRegeneratingKey() {
  val store=BridgeCredentials(context);store.save(endpoint,token)
  val ks=KeyStore.getInstance("AndroidKeyStore").apply{load(null)};ks.deleteEntry(BridgeCredentials.ALIAS)
  val read=store.load();assertTrue(read.unreadable);assertNull(read.connection)
  assertTrue(prefs.all.isEmpty());assertFalse(ks.containsAlias(BridgeCredentials.ALIAS))
 }
 @Test fun alteredEndpointCannotRedirectSavedToken() {
  val store=BridgeCredentials(context);store.save(endpoint,token)
  prefs.edit().putString("endpoint","https://another.invalid").commit()
  assertTrue(store.load().unreadable);assertNull(store.load().connection)
 }
 @Test fun corruptCiphertextAndIncompleteRecordFailClosed() {
  val store=BridgeCredentials(context);store.save(endpoint,token)
  val bytes=Base64.decode(prefs.getString("token",null),Base64.NO_WRAP)
  bytes[bytes.lastIndex]=(bytes.last().toInt() xor 1).toByte()
  prefs.edit().putString("token",Base64.encodeToString(bytes,Base64.NO_WRAP)).commit()
  assertTrue(store.load().unreadable)
  prefs.edit().putString("endpoint",endpoint).commit()
  assertTrue(store.load().unreadable);assertTrue(prefs.all.isEmpty())
 }
 @Test fun originalPr7FormatMigratesWithoutLosingToken() {
  val store=BridgeCredentials(context);store.save(endpoint,token)
  val key=KeyStore.getInstance("AndroidKeyStore").apply{load(null)}.getKey(BridgeCredentials.ALIAS,null)
  val cipher=javax.crypto.Cipher.getInstance("AES/GCM/NoPadding")
  cipher.init(javax.crypto.Cipher.ENCRYPT_MODE,key)
  val encrypted=cipher.doFinal(token.toByteArray())
  prefs.edit().remove("format").putString("endpoint",endpoint)
   .putString("iv",Base64.encodeToString(cipher.iv,Base64.NO_WRAP))
   .putString("token",Base64.encodeToString(encrypted,Base64.NO_WRAP)).commit()
  assertEquals(token,store.load().connection!!.token)
  assertEquals(2,prefs.getInt("format",0));assertEquals(token,store.load().connection!!.token)
 }
 @Test fun invalidReplacementDoesNotEraseExistingRecord() {
  val store=BridgeCredentials(context);store.save(endpoint,token)
  for(url in listOf("http://insecure.invalid","https://user:password@invalid","https://invalid?token=bad")) {
   try{store.save(url,"replacement");fail("Unsafe address accepted")}catch(_:IllegalArgumentException){}
   assertEquals(token,store.load().connection!!.token)
  }
 }
}
