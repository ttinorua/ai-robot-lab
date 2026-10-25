package com.tduck.companion

import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import java.security.KeyStore
import java.security.cert.CertificateFactory
import javax.net.ssl.HttpsURLConnection
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManagerFactory

/** Instrumentation-only CA. No trust bypass in the installed app. */
internal class TestBridgeFixture : AutoCloseable {
 private val original=HttpsURLConnection.getDefaultSSLSocketFactory()
 val config:JSONObject
 init {
  val context=InstrumentationRegistry.getInstrumentation().context
  config=JSONObject(context.assets.open("tc02-bridge.json").bufferedReader().use{it.readText()})
  val ca=context.assets.open("tc02-ca.pem").use{CertificateFactory.getInstance("X.509").generateCertificate(it)}
  val store=KeyStore.getInstance(KeyStore.getDefaultType()).apply{load(null,null);setCertificateEntry("test-only",ca)}
  val trust=TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm()).apply{init(store)}
  val ssl=SSLContext.getInstance("TLS").apply{init(null,trust.trustManagers,null)}
  HttpsURLConnection.setDefaultSSLSocketFactory(ssl.socketFactory)
 }
 override fun close(){HttpsURLConnection.setDefaultSSLSocketFactory(original)}
}
