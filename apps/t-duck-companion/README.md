# T-Duck Companion v0.1

Native Kotlin/Compose Android demo (Android 8.0/API 26 or newer). No account, paid AI, cloud service or hardware required. Install the debug APK from this PR's companion workflow artifact and open **T-Duck Companion**. Demo mode starts automatically.

## Try it

- **Home:** status, battery, activity and software version; all are labelled simulated.
- **Control:** stand, rest, 800ms forward/turn bursts, Stop, simulate a fall, recover. A fall locks movement until recovery. Stop is always visible.
- **Talk:** type `walk forward` to receive a suggestion; explicitly confirm with a Control button. Chat never drives motors. Voice opens the phone's available speech-recognition service, preferring offline recognition; availability/network behavior depends on the phone.
- **Sensors:** simulated balance, contact, distance, battery and temperatures. Unavailable bridge readings are hidden.
- **Settings:** practice simulated BLE setup with code `246810` and invented Wi-Fi credentials; only the demo device identity is saved. Credentials never leave this demo or persist. Voice preference is saved.
- **Updates:** Rest first, select Stable, approve, then verify and simulate update. RSA signature and artifact SHA256 are checked before the simulation. Experimental has no release and cannot silently install stable firmware. Installation and rollback are simulation only.

## Build and tests

Requires JDK 17, Gradle 8.9 and Android SDK 35/build-tools 35.0.0:

```sh
cd apps/t-duck-companion
gradle testDebugUnitTest lintDebug assembleDebug
gradle connectedDebugAndroidTest # emulator or attached Android device
```

APK: `app/build/outputs/apk/debug/app-debug.apk`. Debug builds are test installs; a future build from a different ephemeral debug key may require uninstalling the previous test app. No production signing credentials are committed or changed. App updates use Android installation, not the robot OTA mechanism.

## Local simulation bridge

See [protocol and mock-server instructions](../../docs/protocol/README.md). Only simulated protocol-v1 devices are accepted. The client uses HTTPS with normal certificate/hostname validation and an in-memory Bearer token; no TLS bypass, no cleartext and no redirect forwarding. The debug APK additionally trusts user-installed CAs so an owner can use a local test CA. The release manifest trusts system CAs only. Install only your own test CA; no CA is installed by the app.

A bridge can run on the same Wi-Fi LAN with a certificate matching its DNS name/IP. Open Settings, enter the HTTPS address and token, then Connect locally. The server enforces movement expiry independently of app life. App reconnect never resumes a movement command. The current demo uses explicit endpoint entry behind discovery/BLE interfaces; real mDNS discovery, hardware pairing, durable device-key authentication and session-ordered commands are future hardware work.

## Architecture

`CompanionModel` owns immutable `RobotUi` StateFlow and delegates network calls to replaceable `RobotTransport`. `CommandPolicy` limits high-level intent and capability/fall checks. `BleProvisioner` and `DeviceDiscovery` isolate hardware. OTA verification/session logic is pure Kotlin and independently testable. The offline conversational provider is intentionally a fixed local interpreter; external AI providers must return suggestions through the same explicit confirmation boundary.

## Integration boundaries

This branch is based on main and changes only companion, protocol, mock-server and companion workflow files. It does not import or modify PR #2 robotics assets or control code. No actual MuJoCo connection, real BLE pairing, physical motor safety, physical OTA, production app signing, Play publication or continuous background agent execution is validated. GitHub stores the handover; another Work session must read the protocol and implement a matching robot-side bridge.
