# TC-02: Android ↔ MuJoCo integration contract (protocol 1.1)

Companion branch: `feature/t-duck-companion`, draft PR #3. Robotics branch/PR #2 is read only. The companion bridge imports that branch's existing evaluator/controller from a separately checked-out, locked revision. No robotics source, mass, geometry, policy, gain, trained assets or branch history is replaced.

Implementation: `tools/t-duck-bridge/bridge.py`. Source lock: `integration-lock.json` in the same directory. Foundation `629abcd15862822c796cca6a91170fca6ba1d492`; RL `725ed0c75a73988adc4f9ede280d2d340664e997`; runtime `8837d5a3bc7cf3746f6da2b55c7b9191026b9838`; ONNX SHA256 `57cdebf36e7fa23116270dec96f013a6a64511f37311d322443f5297bdc3d6db`.

## Source and control semantics

`simulated:true` means no physical hardware. `telemetry_source:mujoco` distinguishes measured MuJoCo state from synthetic reference/mock values. The model is the actual upstream 14-joint XGO-Duck used by robotics PR #2, through its unchanged CPU BAM controller, 50 Hz ONNX policy and 200 Hz physics steps. Post-step derived state is refreshed through the foundation's `advance_physics` function.

- Stand: zero requested twist while the balance/walking policy and physics run.
- Forward: requested body twist `[0.2,0,0]` m/s, m/s, rad/s.
- Left/right: `[0.1,0,+0.5]` / `[0.1,0,-0.5]` for short leased turns.
- Stop: immediately clears desired twist; the balance policy continues, so actual momentum decays through physics. If already paused/fallen, Stop preserves that safe pause.
- Rest: explicitly pauses simulation at its current measured state. This is **not a validated sitting motion or a physical rest posture**.
- Recovery is not advertised or accepted. Falls latch, freeze physics and lock movement; restarting an episode requires an explicit bridge restart. No silent reset or teleport masks a failed episode.

Only the single simulation worker touches MuJoCo. HTTP handlers exchange validated high-level intent and locked snapshots. The worker independently expires movement intent by monotonic wall clock, including when there are no network requests, and checks posture/finite-state limits every physics step. A stopped/stale/faulting worker yields a locked fault instead of invented readings. This remains simulation safety, not physical motor or emergency-stop certification.

## Ordered owner control session

Reuse HTTPS, Bearer authentication and `/v1/capabilities`, `/v1/commands`, `/v1/telemetry`. Capabilities additionally advertise `ordered_commands:true`, `boot_id`, `telemetry_source:mujoco`, `pose_schema_version:1`, `ota:false`, `ble:false`, and omit unsupported recovery.

After capabilities, the app calls `POST /v1/session` with `{"purpose":"companion_control"}`. The authenticated bridge stops/pauses motion, retires the previous session and returns `{"session_id":"server UUID","boot_id":"process UUID"}`. Each new connection negotiates a fresh session; reconnect never restores motion.

Every command includes the negotiated `session_id` and strictly increasing integer `sequence` in addition to existing `id`, `command`, `ttl_ms`. Acknowledgements echo the ID, command, sequence, accepted flag and frame at which the intent was accepted. A newer Stop cannot be undone by a delayed lower-sequence Forward. Identical request retries return a cached acknowledgement and never renew the lease; content conflicts and malformed commands are rejected. Retired sessions cannot regain control. These ordered fields are required for this bridge; legacy protocol-1.0 clients fail closed. The updated app still works with the old synthetic mock, which does not advertise this feature.

TLS hostname/chain validation remains enabled. Sessions and commands require the owner token; redirects and cleartext are rejected. Owner tokens stay in app memory and server environment, not URLs/logs/source. The normal debug APK may trust an owner-installed local CA as documented for v0.1; no test key/CA is bundled in the delivered app. CI's ephemeral instrumentation fixture trusts a test CA only inside its test process, without disabling certificate or hostname verification.

## Actual telemetry and a future 3D twin

Telemetry is polled at 5 Hz by the app; it is not a video stream. Each packet includes source, stable device ID and process boot ID. A restart, source change, decreasing pose frame or rewound simulation time requires reconnection.

- `roll_deg`, `pitch_deg`, `yaw_deg`: trunk world rotation derived from MuJoCo's refreshed rotation matrix.
- `left_contact`, `right_contact`: actual foot/floor collision pairs, contact distance <=0.
- `left_contact_force_n`, `right_contact_force_n`: summed contact normal force magnitude from `mj_contactForce`, in newtons. These are ground truth, not physical pressure sensors or pressure in pascals.
- `linear_velocity_m_s`, `angular_velocity_rad_s`: MuJoCo free-joint generalized velocities; angular velocity follows MuJoCo's local free-joint convention.
- `movement_mode`: current controller command; `motion_state`: measured moving/balancing state, or paused/fallen/fault. Requested and measured movement must not be confused.
- `last_command_id`, `sample_monotonic_ns`, `worker_age_s`: correlation and freshness metadata.
- `battery_percent`/`battery_voltage`: null. Distance, camera, touch, temperature and motor temperature are omitted. No plausible fake battery or environmental readings are substituted. `unavailable_fields` lists them and `synthetic_fields` is empty.
- `provenance`: exact locked revisions/policy hash, MuJoCo version, 14-actuator count and CPU controller identity.

`pose` schema 1 is renderer-neutral, with `coordinate_frame:world_z_up`, metres/radians, `frame_id`, `simulation_time_s`, root `position_m:[x,y,z]`, root `quaternion_wxyz:[w,x,y,z]`, named joints with radian position/velocity, and named links with measured world-space positions/quaternions. Root state comes directly from the free joint; links come from `xpos`/`xquat`; joint ordering comes from validated ONNX metadata. Quaternions are normalized, not Euler interpolation targets.

Android parses this into immutable `SimulationPose`, `JointState` and `LinkTransform` values, separate from UI drawing. A future 3D renderer can consume these frames, bind a separately approved named model, and interpolate by simulation time. Do not animate mock guesses as measured motion. Mesh/weight redistribution rights remain unresolved; no geometry/ONNX files are packaged in the app or uploaded in reports.

## Run locally without a paid service

Use Linux/macOS with Python, Git and the foundation CPU requirements. Keep all three external source checkouts outside the companion repository, at the revisions above. Install `requirements-t-duck.txt` from the foundation checkout. Generate a unique local TLS certificate with a SAN matching the bridge hostname/IP, and trust its CA on the test phone explicitly. Do not use the repository's public test fixture key for a real owner connection or disable TLS validation.

```sh
export T_DUCK_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
python tools/t-duck-bridge/bridge.py \
  --foundation-source /path/to/pinned-foundation \
  --rl-source /path/to/pinned-rl \
  --runtime-source /path/to/pinned-runtime \
  --host 0.0.0.0 --port 8443 \
  --cert /path/to/local-cert.pem --key /path/to/local-key.pem \
  --audit /path/to/private-audit.jsonl
```

On the phone, install Companion v0.2, retain Demo mode for offline exploration, or open Settings → Local simulation bridge and enter the HTTPS base address and the owner token. Then use Control and Sensors. A reachable running bridge on your own computer/LAN is required; the APK does not host MuJoCo itself and no always-on cloud service is provided. Internet is unnecessary after the external sources/dependencies are installed.

Run bridge tests with `TC02_FOUNDATION`, `TC02_RL`, `TC02_RUNTIME` pointing to the pinned checkouts. CI creates three separate checkouts, runs actual CPU physics tests, starts the TLS bridge and reverse-forwards the Android emulator's localhost port using adb. It drives the **real app UI** through Settings and Control, checks actual displacement/turns/watchdog, asserts returned pose text is visible in Sensors, and correlates app logs and screenshot with bridge audit records. A skipped/missing end-to-end test is failure for milestone verification. Verification success and measured results are recorded only after that run passes.

## Robotics team handover

No changes are required in the foundation branch to run this adapter. For eventual upstream integration, preserve an importable session factory equivalent to `load_upstream`/`make_trial`/`advance_physics`; keep actor ownership, real contact/pose readings and independent watchdog semantics. Discuss controller changes in robotics PR #2, protocol changes in companion PR #3. Do not merge branches or copy assets to make the build convenient. Expand rest/get-up, longer mixed-motion robustness, fuller collisions and hardware behavior only after robotics validates them. The current bridge inherits the foundation's CPU-vs-training/runtime fidelity and feet-only collision limitations.
