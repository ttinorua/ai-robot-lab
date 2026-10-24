# T-Duck Companion protocol 1.0 (proposal)

This describes the synthetic protocol-1.0 reference mock. The separate [TC-02 protocol-1.1 MuJoCo adapter](TC02_MUJOCO.md) wraps the pinned robotics controller and returns actual simulation state; its verification evidence is tracked in the companion progress report. Neither protocol implies physical hardware, BLE pairing or hardware OTA validation. The robotics session can implement these endpoints without depending on Android internals. Unknown additive JSON fields must be ignored; breaking changes require a new major URL prefix.

## Transport, identity and discovery

Use authenticated HTTPS REST on the local network; Internet and cloud services are unnecessary. Every endpoint requires `Authorization: Bearer <per-owner-device-token>`. Never embed credentials in source, URLs or logs. A production implementation must authenticate the device using a pinned pairing-established identity and use Android Keystore-backed credential storage. Standard hostname/certificate validation must remain enabled. TLS 1.2 minimum; TLS 1.3 preferred. Simulator HTTP is permitted only on explicit loopback tests; never allow cleartext real-device control.

Future discovery: `_tduck._tcp` mDNS advertisements contain protocol major, device ID and TLS port, never credentials. Discovery is an untrusted hint, not authentication. Manual HTTPS endpoint configuration supports bridge integration until discovery exists. Device identity from TLS must match the trusted pairing identity. Connect flow: disconnected → discovering → authenticating → connected; failures → reconnecting (1,2,4,8,16,30 second bounded backoff), then reconnect only with existing trusted identity. Every reconnect clears pending movement, refreshes capabilities and requires a new deliberate user command. A new identity requires explicit onboarding.

## REST endpoints

`GET /v1/capabilities` returns:

```json
{"protocol_version":"1.0","device_id":"t-duck-simulator-001","name":"T-Duck simulator","simulated":true,"commands":["stand","rest","forward","left","right","stop","recover"],"max_movement_lease_ms":1000,"ota":false,"ble":false}
```

Render only advertised commands. `recover` is optional; do not infer support. Unsupported commands must be rejected by the robot too. No endpoint accepts raw motor targets or arbitrary AI text.

`GET /v1/telemetry` returns this simulator sample. Optional sensors may be omitted or null; absence is never zero. SI units are identified by suffixes. Telemetry must always carry its source flag; production telemetry must set `simulated:false`.

```json
{"protocol_version":"1.0","device_id":"t-duck-simulator-001","simulated":true,"battery_percent":87,"battery_voltage":7.8,"activity":"Standing","movement_mode":"stand","status":"ready","warnings":[],"software_version":"0.1.0","roll_deg":1.2,"pitch_deg":-0.8,"yaw_deg":12.0,"left_contact":true,"right_contact":true,"distance_cm":120,"touch":false,"camera_available":false,"temperature_c":22.4,"motor_temperature_c":31.0}
```

Poll at 2–5 Hz. App marks telemetry stale after 2 seconds, disables movement and attempts local stop. Robot states include `ready`, `fallen`, `updating`, `fault`; robot-side safety checks take precedence over app state. Real motor positions and per-foot pressure require later optional fields and cannot be inferred from these mock booleans.

`POST /v1/commands` request and acknowledgement:

```json
{"id":"unique-uuid","command":"forward","ttl_ms":500}
```

```json
{"id":"unique-uuid","accepted":true,"command":"forward","status":"applied"}
```

Allowed commands: `stand`, `rest`, `forward`, `left`, `right`, `stop`, optional `recover`. `ttl_ms` is an integer 100–1000. Acknowledgements echo the exact ID and command; an uncorrelated response is not success. HTTP 400 is malformed/unsupported input; 401 authentication failure; 404 unknown endpoint; real robots may return 409 with `{accepted:false,reason:"unsafe_state",id,command}`. Applied means controller accepted the high-level action, not proof of physical completion. Cap command request/ack wait at one second. Never retry movement automatically after uncertain delivery. Stop is always safe to retry with a new ID.

Forward/turn commands are short motion leases starting at robot receipt, capped at one second by the robot. Each renewal uses a new ID and deliberate active input. Duplicate IDs with identical content return the cached acknowledgement without extending the lease; conflicting content is rejected. Reference cache retains last 1024 IDs for this process only, not durable replay protection. Robot watchdog independently stops motion when lease expires, even if app disappears. On stop, app pause/background, disconnect, stale telemetry or ack timeout: clear movement intent and request stop. Real hardware also needs a physical emergency stop; the app's local stop is not a certified physical safety circuit.

## BLE onboarding contract (hardware pending)

The app demo must clearly label its simulated discovery, pairing, provisioning and identity. Hardware adapter is a separate interface, initially unimplemented. Production sequence: request runtime Android nearby-device permissions → scan service UUID assigned by robotics team → connect → physically press robot pairing button → PAKE/authenticated secure channel using unique short-lived setup code → pin device public identity → encrypt Wi-Fi credentials in the authenticated channel → robot joins selected network → verify identity over TLS → retain owner credential and identity in Keystore-backed storage → erase setup code and Wi-Fi password from app memory. A fixed public code is not proof of physical access. Require bounded setup window, rate limiting, replay protection and ownership reset through physical action. Do not use Bluetooth Just Works alone for credential confidentiality/authenticity. No real service UUID, cryptographic pairing transcript or BLE firmware exists yet; these are hardware integration requirements, not shipped security claims.

## OTA contract

See `update-manifest.schema.json` for a signed release payload proposal. Signature is detached RSA PKCS#1 v1.5 with SHA-256 (`SHA256withRSA`) over the canonical UTF-8 payload. Verify with an owner-trusted pinned release public key before installation. The demo ships only its simulator public key; never use that key as a production trust root. Canonical JSON uses this exact field order, no whitespace, strings escaped with quote/backslash escapes and control characters encoded as lower-case `\uXXXX`, all other Unicode as UTF-8: `version, hardware, protocol_major, channel, sha256, release_notes, rollback_supported, component`. See `apps/t-duck-companion/app/src/main/java/com/tduck/companion/updates/UpdateVerifier.kt` and `DemoUpdate.kt` for the executable fixture. Arbitrary JSON re-serialization is not canonical. SHA-256 checks artifact download integrity independently. Do not accept a public key supplied by the same untrusted manifest. Require matching device/hardware family, compatible protocol major, explicit stable/experimental channel selection, owner approval, sufficient battery (>=40%), safe posture (`rest`), no active movement, artifact hash, rollback capability for risky firmware, post-install health timeout and rollback on failure where supported. Never silently switch to experimental or let model/config packages bypass verification. App updates remain normal Android package updates.

Production must additionally enforce signed monotonic release sequence/anti-downgrade, bounded artifact download size, revocation and trusted key rotation. These are not supplied by the demo manifest; do not use its verifier alone as a production update system. v0.1 exercises update state transitions in-app only. The reference server advertises `ota:false` and does not flash or expose pretend firmware writes. A real bridge should advertise OTA only after matching validation and recovery implementation exists. Future endpoints: `GET /v1/updates?channel=stable`, `POST /v1/updates/prepare`, `POST /v1/updates/install` with owner-approved signed release ID, and progress telemetry. These future endpoints are intentionally not live in protocol 1.0 mock.

## Run reference simulator

Python standard library only. Generate a random token locally; no paid services needed:

```sh
export T_DUCK_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
python3 tools/t-duck-mock/server.py --insecure-loopback
python3 -m unittest discover -s tools/t-duck-mock -v
```

LAN use requires `--host 0.0.0.0 --cert path/to/cert.pem --key path/to/key.pem` and a certificate trusted by the app. Never disable certificate checks to make a self-signed certificate work. Do not log the token or commit generated certificates/private keys. The app's embedded offline mock does not require this server.

## Robotics handover

Implement the transport adapter around existing simulation/controller entry points; do not replace physics or walking policy. Validate commands against robot capabilities/state, emit actual simulated MuJoCo readings with `simulated:true`, bind identity and watchdog on the robot side, and test packet loss/app background before accepting physical deployment. Pending hardware tests: Android BLE permissions/scan on real phones, pairing MITM/replay/physical-access checks, Wi-Fi provisioning failure/reset, trusted certificate rotation, LAN discovery, loss/reconnect watchdog, physical stop, battery sag, OTA signature rejection/power-loss recovery. No hardware feature is validated by passing the mock tests.
