# APK signing and seamless updates — issue #4

Application ID stays `com.tduck.companion`. Distributed v0.1 code=1, v0.2 code=2; TC-03 development candidate code=3. Android compares signing identities on install; changing only versionCode cannot fix a different key. Reference: [Android app signing](https://developer.android.com/studio/publish/app-signing).

The v0.1/v0.2 workflows used each fresh runner's generated debug keystore, which was not preserved. Exact historical APKs remain available for the initial acceptance test. Do not claim original device installer error verified until emulator/device evidence is recorded. The private signing key cannot be reconstructed from an APK/public certificate. No legacy key recovery source is known; do not promise an in-place update over v0.2 without that key or a valid existing signing lineage.

## Implemented safeguards

- Release Gradle configuration reads only owner-provided environment values `T_DUCK_SIGNING_STORE`, `T_DUCK_SIGNING_STORE_PASSWORD`, `T_DUCK_SIGNING_ALIAS`, `T_DUCK_SIGNING_KEY_PASSWORD`. No signing secret is committed. With no owner key, `assembleRelease` is unsigned; no automatic debug-key fallback.
- `scripts/verify-release.py` checks actual APK signature, exact approved certificate SHA256, unchanged package, increased versionCode and non-debug release. It requires the previously distributed APK. This preflight does not replace installation acceptance.
- `scripts/upgrade-acceptance.py` uses a disposable emulator only. It checks exact historical binary hashes, records certificate fingerprints/actual historical installer response, verifies candidate signing mismatch over v0.2, then installs same-key candidate builds 3→4 with `adb install -r`, checks persisted voice/trusted-demo preferences byte for byte and launches the updated app. Candidate code=4 is test-only, never a published version claim.
- CI test artifacts are labelled `CI-only`. They are not a stable future update channel. No debug keystore is uploaded or reused as an owner credential.

## Owner signing decision still required

Do not generate, rotate or add owner signing credentials without approval. Preferred zero-cost plan: owner-controlled release keystore with long validity, strong distinct password, encrypted offline backup in two owner-controlled locations, passwords kept separately, a recorded **public** certificate fingerprint. If later authorizing CI signing, store credentials only in a protected GitHub Environment whose release workflow runs on explicit trusted commits after approval, never untrusted PR code; do not expose credentials to this development PR workflow. Keep the authoritative backup outside ephemeral CI/cache/artifact storage. No paid Play enrollment is necessary for sideloaded APKs.

Use the same approved key for all future builds, preserve applicationId and increase versionCode. Keep every distributed APK and its SHA256/public signing certificate in an owner-controlled release archive. Before each distribution, run signature preflight and `adb install -r` over the actual previous release on an emulator/device with seeded realistic app settings; verify settings and UI after relaunch. For release builds, use an instrumentation/device UI check rather than `run-as` (which is debug-only). Do not claim same-test-key CI proves historical identity continuity or guarantees updates on all phone models.

## Migration if v0.2 key cannot be recovered

A one-time uninstall/reinstall under a newly approved stable owner key is required; uninstall erases app-local preferences. Record/reapply voice preference and redo trusted **demo** setup. Current access tokens/Wi-Fi credentials are intentionally not persisted and must not be exported to issue threads/backups. Chat/live connection are session-only. Keep the existing v0.2 installed until the approved replacement is ready; do not ask owner to repeatedly uninstall development APKs. Reusing a public test key or changing applicationId would not provide the intended secure seamless upgrade path.

Historical APK artifacts expire; CI's initial historical acceptance depends on those exact artifacts, and deliberately fails if they disappear rather than silently rebuilding different binaries. Re-run acceptance with the owner's archived APKs using script path arguments after expiration. Preserve the JSON evidence from the initial successful run in Git for continuation. Stable release acceptance remains a blocker until the owner identity and retained baseline are provisioned.
