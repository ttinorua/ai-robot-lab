package com.tduck.companion

import java.net.URI

internal object BridgeEndpoint {
    fun normalize(input: String): String {
        val uri = try { URI(input.trim()) } catch (_: Exception) { throw IllegalArgumentException("Enter a valid HTTPS bridge address") }
        require(uri.scheme.equals("https", true) && !uri.host.isNullOrBlank() && uri.rawUserInfo == null &&
            uri.rawQuery == null && uri.rawFragment == null && (uri.port == -1 || uri.port in 1..65535)) {
            "Use HTTPS without embedded credentials, query or fragment"
        }
        return "https://" + uri.rawAuthority + uri.rawPath.orEmpty().trimEnd('/')
    }
}
