package com.tduck.companion.updates

/** Offline signed demonstration fixture. Trust applies only to tduck-sim-v1. */
object DemoUpdate {
    val artifact = "T-Duck simulated firmware v0.1.1; no executable hardware payload.\n".toByteArray(Charsets.UTF_8)
    val manifest = UpdateManifest(
        version = "0.1.1-demo", hardware = "tduck-sim-v1", protocolMajor = 1,
        channel = UpdateChannel.STABLE,
        artifactSha256 = "ada741f529e5988a194b10095d334a1edb3d3e242478c9d1f9ecce5660afbb75",
        releaseNotes = "Smoother simulated movement and clearer battery reporting."
    )
    const val publicKeyBase64 = "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAnxiuiEP4lb2P9Tm9LNNcXSxLMv2HyRfOWn0g67xPSP/doa9d8qM6/TkSj9PdH18GpxN9UEH+5yFuz+pOna9SWPYd4XiBnCe85nwfCCOCzhLefWJsBVI8uNxgDwp4BlAqvlGEgRENc0tKuQv5M7Ck9XEmS2gArLAyDk8vfefPoLBvH537oKhMXsXa7ADg/xrBW/YaFkYYbo9ld8DM7A6zx96Jx4WXeE/ZIr/U0p8IOglNqa2NhhnUPeBuLUTk8Zf6KbdjgMpSC7s9g9dYQhzX/Gdjw3Wn4nsZ8RqRRC6q+QjZwv4+mew47oRKwEixq4Qy4s+M/J1rJk6exOgG2sq6cQIDAQAB"
    const val signatureBase64 = "VxDSdxlK4HHzC6Reoe8T+N/NSYYVRE+y1L66mOj67tzrCDJNnICuI7sudLSffmKGHvWEVyTndswckeLlAXy/l+MQRV6nnGQVQuuFpwIwq94oe8Ea+8PumWkL3op/06t/amT2w0iu9JYgcCxqpE0eDzw9aykF68fW0iBYhhGa+NY4o/dJuAP3WR8h2/rg5efoIyOJPV785mOOsbkYjcrmmsplaXlhqm16Gd2fA/0pgs2IGBcWIzbuI/6ae/1Mb44KUycQabP9kcJQOv6Xtyv9VLXrOomjQK3QFv+T6s9cdGok5TWf6s+wGYjMkJcqOp6Ho98Ffb+K08Akl2a6X6Mp/g=="

    fun verifyAndApprove(
        hardware: String = "tduck-sim-v1", protocolMajor: Int = 1,
        batteryPercent: Int = 82, posture: String = "rest",
        selectedChannel: UpdateChannel = UpdateChannel.STABLE, ownerApproved: Boolean = false
    ): UpdateDecision = UpdateVerifier.verify(manifest, artifact, signatureBase64, publicKeyBase64,
        hardware, protocolMajor, batteryPercent, posture, selectedChannel, ownerApproved)
}
