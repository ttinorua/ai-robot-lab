# T-Duck Companion — implementation and handover

Development branch: `feature/t-duck-companion` · Draft [PR #3](https://github.com/ttinorua/ai-robot-lab/pull/3).

Companion work is isolated from [robotics PR #2](https://github.com/ttinorua/ai-robot-lab/pull/2). Main and the robotics development branch have not been modified. No merge, paid resources, production service, real hardware flashing or Play publication was performed.

## Milestones

| Milestone | Implemented | Remaining validation or integration |
| --- | --- | --- |
| TC-01 Android prototype | Kotlin/Compose app; five sections; dashboard; built-in simulated telemetry; capability/fall-gated controls; movement lease; persistent Stop; debug APK workflow | Physical phone installation remains an owner test |
| TC-02 Communication | Versioned protocol; replaceable transport; authenticated HTTPS client; TLS Python mock; robot identity binding; command acknowledgements; response deadlines; reconnect without motion resumption; robot-side watchdog | MuJoCo bridge must be implemented in robotics work; actual Android-to-LAN TLS exercise remains pending |
| TC-03 Onboarding | Discovery and BLE provisioning interfaces; simulated physical proof/Wi-Fi verification; trusted demo identity; no persisted Wi-Fi credentials; saved voice preference | Real BLE GATT/Android permission integration, cryptographic physical proof, mDNS discovery and hardware reconnect must be validated against chosen hardware |
| TC-04 Updates | Signed manifest and component format; RSA/SHA256 verifier; integrity, compatibility, channel, approval, version, battery and posture checks; simulated progress, health checks and rollback | Real release discovery/download/signing trust rotation, hardware flash/recovery and interruption persistence require hardware implementation; mock network bridge advertises OTA unavailable |
| TC-05 Assistant | Local provider interface; session conversation history; strict high-level intent suggestions; explicit Control confirmation; Android speech-recognition launcher; voice preference | External providers are not enabled; speech recognition depends on a phone's installed service and remains unverified |

All built-in readings, pairing and robot OTA behavior are clearly marked simulated. The app refuses bridges advertising `simulated=false`. No hardware claims are inferred from simulator tests.

## Validation

Final app source commit: [`282517a`](https://github.com/ttinorua/ai-robot-lab/commit/282517a7526d4619e1a0c3cd1d1b99429e475dfa). [Companion CI run 40107422979](https://github.com/ttinorua/ai-robot-lab/actions/runs/40107422979) passed both build and emulator jobs.

| Check | Result |
| --- | --- |
| Python protocol suite | 9 passed, 0 failed |
| Kotlin/JVM suite | 40 passed, 0 failed, 0 ignored; includes 11 real TLS socket integration tests and 12 OTA tests |
| Android emulator suite | 6 passed, 0 failures/errors/skips on Android 10/API 29 x86_64 |
| Android lint and debug assembly | Passed |
| APK signature | APK Signature Scheme v2 verified by Android apksigner |
| APK metadata | com.tduck.companion, versionName 0.1.0, versionCode 1, minSdk 26, targetSdk 35 |
| Download integrity | Extracted APK SHA256 matches CI output |

Delivered APK: **T-Duck-Companion-v0.1.0.apk**, 8,808,217 bytes. SHA256: `de7d76571225a9caca8449363efaaddeaf8e52b38ce2cd287dc550bc0e7e19cb`.

GitHub APK artifact: [T-Duck-Companion-v0.1-debug](https://github.com/ttinorua/ai-robot-lab/actions/runs/40107422979/artifacts/12565671157). GitHub artifacts have short retention; rebuild from the pinned app source if expired.

Build evidence: [40-test/lint report](https://github.com/ttinorua/ai-robot-lab/actions/runs/40107422979/artifacts/12565676061), [6-test emulator report](https://github.com/ttinorua/ai-robot-lab/actions/runs/40107422979/artifacts/12564813039). Emulator suite covers dashboard/movement timeout/fall/stop/recovery, chat cannot move, approval-gated OTA, invalid and successful simulated pairing/trusted identity storage, sensor navigation, disconnect/reconnect control locking.

Visual QA completed: [follow-up run 40108225366](https://github.com/ttinorua/ai-robot-lab/actions/runs/40108225366) passed both jobs again. Its emulator reinstall/launch returned Android `Status: ok`; the [Home screenshot and emulator report](https://github.com/ttinorua/ai-robot-lab/actions/runs/40108225366/artifacts/12565885558) were downloaded and the screenshot inspected. Header, connection indicator, persistent Stop, demo labels, duck portrait and five-section navigation render correctly; additional dashboard content is scrollable on the small emulator viewport.

Initial screenshot capture was skipped because ripgrep was absent, then because instrumentation uninstalls test APKs during cleanup. The script now reinstalls the same tested build for capture and fails on capture errors. These script/documentation-only fixes leave packaged app source unchanged from the delivered APK's pinned commit.

- Nine Python protocol tests passed locally: authentication rejection, capability/telemetry/ack roundtrip, request rejection, duplicate request handling and lease expiry without a client.
- Additional local TLS smoke passed with standard certificate verification: authenticated Python mock, accepted movement acknowledgement and lease expiry over HTTPS.
- Initial Android build, 15 JVM tests and lint passed in [run 40106587185](https://github.com/ttinorua/ai-robot-lab/actions/runs/40106587185). Its APK is superseded by the final tested build.
- Earlier failed attempts are retained in Actions. SDK setup requested an obsolete `tools` package, the emulator action launched Gradle from the repository root, and new test fixtures initially referenced Android-unavailable `com.sun` classes / an undeclared Espresso dependency. Each cause was corrected before final delivery.
- Existing robotics CI fails the unchanged main-branch `TestPhysics.test_gravity`: final height 0.6760083499334241 is not less than 0.675. See [run 40106587210](https://github.com/ttinorua/ai-robot-lab/actions/runs/40106587210). Robotics PR #2 describes its separate gravity-fixture correction; companion work deliberately leaves those files unchanged.

## Reproduce and explore

See [app build and demo guide](../apps/t-duck-companion/README.md), [protocol/hardware validation plan](protocol/README.md), and [OTA schema](protocol/update-manifest.schema.json).

Install the final debug APK on Android 8.0 or newer; open **T-Duck Companion**. Demo mode starts automatically. Try Forward (automatically stops), simulate a fall, Stop (fall remains locked), Recover, ask `walk forward` in Talk (no motion), then Rest and approve a Stable simulated update. For setup, use demo code `246810` and invented Wi-Fi credentials.

## Persistent handover to robotics

Implement the documented `/v1/capabilities`, `/v1/telemetry` and `/v1/commands` endpoints as a simulation-only bridge first. Capability advertisement must reflect actual controller support. Enforce movement leases independently of app/network/cloud. Keep local safety authority on the robot. A real hardware release also needs monotonic authenticated command/session ordering to reject delayed commands, durable owner keys and pairing proof, and physical watchdog/stop validation. Do not infer physical safety from this demo.

Use the Python mock as a reference and replace its state with a validated MuJoCo adapter. Report falls and omit/null unavailable sensors. The app validates identity and protocol, hides unavailable readings, and never resumes movement after reconnect. Network OTA is intentionally unavailable on the mock; built-in OTA is an offline, signed non-executable fixture.

No continuous background coding or cross-session agent channel has been established. GitHub PR #3 and this document hold the continuation state; CI runs on authorized branch changes. A future Work session should read these files and the latest PR checks before editing.
