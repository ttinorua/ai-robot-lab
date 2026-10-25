package com.tduck.companion

import org.junit.Assert.*
import org.junit.Test

class BridgeEndpointTest {
 @Test fun normalizesRootAndKeepsPrivateHostname() {
  assertEquals("https://private.invalid",BridgeEndpoint.normalize(" https://private.invalid/ "))
  assertEquals("https://localhost:8443/prefix",BridgeEndpoint.normalize("https://localhost:8443/prefix/"))
 }
 @Test fun rejectsCredentialsAndUnsafeSchemesBeforeSaving() {
  for(input in listOf("http://localhost","file:///tmp/x","https://owner:secret@host","https://host?token=x","https://host#x","https://host:99999","https://host:0","https://bad host","https:///missing")) {
   try{BridgeEndpoint.normalize(input);fail("Invalid endpoint accepted")}catch(_:IllegalArgumentException){}
  }
 }
}
