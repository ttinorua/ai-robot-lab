# T-Duck Companion — implementation and handover

Development branch: `feature/t-duck-companion` · Draft [PR #3](https://github.com/ttinorua/ai-robot-lab/pull/3).

Companion work is isolated from [robotics PR #2](https://github.com/ttinorua/ai-robot-lab/pull/2). Main and the robotics development branch have not been modified. No merge, paid resources, production service, real hardware flashing or Play publication was performed.

## Current development: TC-03 staging tested; public hosting blocked (2026-10-25)

Issue [#5](https://github.com/ttinorua/ai-robot-lab/issues/5) defines this TC-03 as zero-cost online MuJoCo; BLE remains simulated. **TC-03 is not complete:** no public endpoint or physical-phone cloud round trip has been verified. No cloud service, owner cloud token or stable owner signing identity was provisioned. The delivered v0.2 remains the owner-install version; development CI artifacts are not a stable update channel.

Implemented: unprivileged Docker staging package with a whitelisted context, no bundled robot assets/weights, pinned private runtime fetch behind source-use approval, explicit trusted HTTPS-edge boundary, bounded request concurrency/deadlines, minimal health probe, graceful rest on SIGTERM and an independent 60-second command-idle pause. Android retains the five-tab design/demo, explains the required service, and permits bounded sleeping-host retries for read-only discovery only. Movement retains short deadlines, no retries, ordered owner sessions, acknowledgements and independent wall-clock lease expiry. Release signing reads an owner-managed key only; no debug-key fallback. Signature/package/version/non-debug preflight and emulator install/data acceptance are implemented.

Render Free (0.1 CPU/512 MB, managed TLS, sleep/wake) is the leading staging candidate, **not a verified hosted solution**. Current HF compute-Space creation requires a paid plan; Koyeb signup's card/plan charges conflict with zero spending. Render account/payment/quota state, actual hosted performance and runtime asset rights remain unverified. [Provider review, exact staging setup, safety and licensing](protocol/TC03_CLOUD.md) · [Signing/custody/migration](protocol/APK_SIGNING.md).

[Final CI 40142093488](https://github.com/ttinorua/ai-robot-lab/actions/runs/40142093488), source [f7fa479](https://github.com/ttinorua/ai-robot-lab/commit/f7fa479673761d18e03da9622ecbd7eacaed5004), passed all three jobs. **88 automated tests**: 50 JVM, 9 reference protocol, 12 real bridge/physics/TLS, 10 cloud adapter/idle/security, 7 Android. Five additional emulator update/signing acceptance checks passed, zero blocked. Debug and unsigned-release build, lint, metadata/signature and Docker checks passed. The initial [CI 40141505678](https://github.com/ttinorua/ai-robot-lab/actions/runs/40141505678), source 8e9502987b842546700263e8f06e100d00e5f779, passed the same 88 tests and four initial upgrade cases before the release-guard extension. Initial 50-test HTML and seven-test Android XML were downloaded and inspected; initial native Sensors screenshot and app/server audit were independently inspected/correlated.

Final UI Forward moved actual MuJoCo x by **0.0774046518 m (7.74 cm)**. The report's visible frame 792, simulation time 3.96 s, position x=0.1483364821 m was correlated to bridge audit by the fail-closed collector. Stand, Stop, Left, Right, Rest, watchdog expiry, fourteen named joints and unavailable battery handling were exercised. This was a **CI-local authenticated TLS endpoint**, not public cloud hosting.

Private container benchmark, no network, 0.1 CPU/512 MiB with no extra swap: peak RSS 186.23 MiB, model load 4.40 s excluding fetch, 2 seconds of physics in 0.709 s wall time. Aggregate throughput passed, but p95 tick 91.2 ms exceeds the nominal 20 ms policy period. Shared-host scheduling/HTTPS overhead/watchdog timing still require target-host validation.

Issue [#4](https://github.com/ttinorua/ai-robot-lab/issues/4): exact delivered APK hashes/signatures were checked and v0.1→v0.2 reproduced **INSTALL_FAILED_UPDATE_INCOMPATIBLE**. Candidate also cannot upgrade v0.2 under a different signing identity. Same-test-key candidate 3→4 installed with adb install -r, preserved voice/trusted-demo preferences byte for byte and relaunched. Debug release preflight was rejected as required. This does not recover the historical private key or establish stable owner-key custody. No recoverable legacy keystore was found in the workspace; the fresh-runner key was not retained. One planned migration may be necessary after owner-approved stable signing; keep v0.2 installed meanwhile.

Final CI-only APK: package com.tduck.companion, versionCode 3/versionName 0.2.1-dev; CI verified APK signature/metadata and SHA256 **6ed30c31ca0caf31740d4d4ba28c28e7ae4e789b90dfe7dfd98afd187ab7e3e0**. It is a build artifact, **not offered as a cloud-ready or seamless owner update**. [CI build artifacts](https://github.com/ttinorua/ai-robot-lab/actions/runs/40142093488). [Permanent JSON evidence and scope](../reports/t-duck-companion/tc03-001/). Raw audit/screenshots/full XML remain in linked Actions artifacts with limited retention; initial screenshot was inspected before local execution became unavailable. The source, final logs and JSON results were preserved through GitHub after that environment interruption; no new local filesystem verification is claimed afterward.

Remaining blockers: owner approval for a specific nonproduction service/workspace and cloud-token custody, verified zero-charge billing/quota state, asset/weight provenance/source-use review, approved stable signing identity/backup, actual Android-to-public-endpoint and physical-phone acceptance. No money, production deployment, merge, firmware flashing or robotics-branch edits.

## TC-02 completed milestone: local MuJoCo integration (2026-10-24)

**Actual Android UI → authenticated HTTPS → pinned MuJoCo/ONNX/BAM → measured telemetry visible in Android passed.** This is Android-emulator simulation integration, not physical phone/LAN or robot validation.

App source: [`7c6fe32`](https://github.com/ttinorua/ai-robot-lab/commit/7c6fe3284a1020ee18bb5cf146a945918c6dbb76). [Successful CI run 40128844686](https://github.com/ttinorua/ai-robot-lab/actions/runs/40128844686): both Android build and integration jobs passed. [Permanent evidence](../reports/t-duck-companion/tc02-001/) includes the app-side report, server audit, independently correlated verification summary and inspected live UI screenshot.

| Verification | Result |
| --- | --- |
| Kotlin/JVM | 46 passed, zero failures/skips |
| Synthetic reference protocol | 9 passed |
| Bridge/security/actual MuJoCo/TLS | 12 passed |
| Android 10/API29 x86_64 instrumentation | 7 passed, zero failures/errors/skips; six existing demo tests plus actual MuJoCo round trip |
| Android lint/build/metadata/APK v2 signature | Passed |
| Visible telemetry / independent audit / screenshot | Verified |

The app-issued Forward request `01fa3653-eee5-4d72-ba97-7d37368c1f90`, sequence 2, was accepted at physics frame 112. App-measured x changed from 0.0008839840 m to 0.0701667356 m: **0.0692827516 m (6.93 cm)** actual forward displacement. The independent robot-side watchdog expired the movement lease before the test sent Stop. Stand, explicit Stop, Left, Right and Rest were also driven through Control and acknowledged. Left changed measured yaw by 16.20°; the test separately asserted a decrease after Right. All observed commands were accepted in sequence; a final cleanup Stop also appears in the audit.

After both turns and Rest, the sensor UI visibly displayed x=0.146 m and simulation time=3.78 s. The underlying unrounded app frame 756 (x=0.1463096363 m, time=3.7799999999999416 s) exactly matched the server's recorded MuJoCo snapshot. Fourteen measured joint states, orientation and actual collision contacts were received. Battery availability was false, with no invented substitute. The screenshot was reconstructed from instrumentation output and visually inspected.

Delivered **T-Duck-Companion-v0.2.0.apk**, package `com.tduck.companion`, versionCode 2, minSdk 26, targetSdk 35, 8,824,601 bytes. SHA256 `88fc7d47f9578c38ec6e6dc645ed20b86529f8a5e44a52d238f300628a657267`; downloaded bytes matched CI before delivery. [APK artifact](https://github.com/ttinorua/ai-robot-lab/actions/runs/40128844686/artifacts/12574776477), [unit/lint reports](https://github.com/ttinorua/ai-robot-lab/actions/runs/40128844686/artifacts/12573917124), [integration reports/audit/screenshot](https://github.com/ttinorua/ai-robot-lab/actions/runs/40128844686/artifacts/12574501805). Actions artifacts have short retention; permanent source/evidence above remain in GitHub.

A running local bridge on the owner's computer/LAN is required for live mode; no always-on cloud endpoint was created. [Installation and local setup](protocol/TC02_MUJOCO.md) and [app guide](../apps/t-duck-companion/README.md) describe TLS/owner-token configuration. Demo mode remains available offline. A fresh debug signing key may require uninstalling the previous v0.1 test APK; no production signing or owner account credential was changed.

First TC-02 run [40128231691](https://github.com/ttinorua/ai-robot-lab/actions/runs/40128231691) passed build/46 JVM/12 bridge/six existing UI tests, but the real test failed before network connection because the exported test PEM began with PKCS12 bag metadata. `openssl x509` now emits a clean certificate for Android instrumentation; no certificate/hostname checks were bypassed. The complete integration then passed. A separate local mixed-motion sequence also remained upright with forward, stop, left, right and rest; no controller tuning or training was performed.

### Current boundaries and robotics handover

The robotics branch was read but never changed or merged. The bridge wraps a separate checkout at foundation `629abcd15862822c796cca6a91170fca6ba1d492`; all three source revisions and policy digest are enforced by the integration lock and foundation loader. No model/weight assets are committed or bundled. Future foundation changes require a deliberate lock update and repeated end-to-end validation.

Protocol 1.1 retains v1 endpoints and adds negotiated, ordered owner sessions; late movement cannot override a newer Stop. A new connection stops/pauses old intent, retires its session and never resumes motion. Actual state is source-labelled and parsed into immutable root/joint/link poses for a future 3D renderer. No cosmetic redesign or mesh redistribution was attempted. [Detailed versioned handover](protocol/TC02_MUJOCO.md).

Limits: Rest is a simulation pause, not a sitting policy; recovery is unsupported; falls latch and require explicit episode restart. CPU-vs-training/firmware fidelity and feet-only collision limits remain those of PR #2. Real BLE, hardware OTA, physical motor safety, phone speech services and physical-phone-to-LAN operation are unverified. The unrelated inherited main-branch gravity CI failure remains unchanged; its separate robotics fix is in PR #2. No merge, production deployment, spending or firmware flashing.

## Earlier v0.1 milestone ledger (historical)

The following sections preserve the earlier prototype delivery and its then-current limitations; the TC-02 status above supersedes their MuJoCo-pending statements.

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
