# TC-03: on-demand online MuJoCo — staging candidate, not deployed

Tracking: [#5](https://github.com/ttinorua/ai-robot-lab/issues/5), signing [#4](https://github.com/ttinorua/ai-robot-lab/issues/4). This TC-03 is cloud connectivity; the original roadmap's BLE milestone remains simulated/unvalidated. Companion owns this adapter/packaging; robotics branch stays unchanged at `629abcd15862822c796cca6a91170fca6ba1d492`.

**Current status: no cloud endpoint or physical-phone round trip has been verified.** Local MuJoCo tests and Android emulator tests are separate evidence. Do not advertise TC-03 as complete or distribute a cloud-ready APK on that basis. The app cannot create/start a cloud service that has not been provisioned. Once approved and deployed, an HTTPS discovery request can wake a sleeping service; it cannot bypass provider suspension, exhausted quota or a failed build.

## Provider review, 25 October 2026

These are current primary documentation findings, not an account billing audit or a free-host availability guarantee.

| Candidate | CPU/RAM, lifecycle and TLS | Account/cost constraint | Decision |
|---|---|---|---|
| Render Free web service | 0.1 CPU/512 MB, managed HTTPS, ephemeral disk, sleeps after 15 minutes without inbound requests, approximately one-minute wake; 750 instance-hours/workspace/month | Docs allow operation without payment method; excess bandwidth suspends services if none is attached, otherwise overage can bill. Builds also have quota. Existing workspace/payment status unverified. | Best staging candidate from measured resource demand, **not verified hosted capacity**. Use only explicit `free` compute, no attached payment method, no auto-deploy. No service created. |
| Hugging Face CPU Basic | 2 vCPU/16 GB, hourly compute listed as free | Current overview says creating compute Gradio/Docker Spaces requires PRO/Team/Enterprise; static hosting is free. ZeroGPU Gradio allowance is not persistent CPU hosting for this bridge. | Reject under hard zero additional spending; do not infer availability from the $0/hour row alone. |
| Koyeb Free | 0.1 vCPU/512 MB/2 GB, one free instance | Current pricing FAQ requires card, $29 authorization hold and charges prorated selected plan (Pro default). | Reject signup under zero spending. |
| Oracle Always Free | AMD/Arm compute exists; network/security/HTTPS management and capacity availability remain owner's responsibility | Card verification and account setup required; no existing authorized account verified. Architecture/runtime compatibility untested. | Alternative investigation only; do not use trial credits or upgrade account. |
| GitHub Pages / Actions | Pages serves static files; standard public Actions runners support finite builds/integration tests | CI is not an always-on robot service; no keepalive/tunnel farming or scheduled jobs used for hosting | Continue CI testing only. |
| Colab free | Interactive notebook with finite/idle runtime | Managed runtime policies restrict unrelated web services/proxies and prioritize interactive work | Not a hosted backend workaround. |

Sources read: [Render free](https://render.com/docs/free), [compute plans](https://render.com/docs/compute-plans), [deploys](https://render.com/docs/deploys), [health checks](https://render.com/docs/health-checks), [HF Spaces](https://huggingface.co/docs/hub/en/spaces-overview), [Koyeb pricing FAQ](https://www.koyeb.com/docs/faqs/pricing), [Oracle FAQ](https://www.oracle.com/cloud/free/faq/), [Colab FAQ](https://research.google.com/colaboratory/faq.html), [Actions billing](https://docs.github.com/en/actions/concepts/billing-and-usage).

Local resource benchmark: use `tools/t-duck-cloud/benchmark.py` with the pinned source paths. Initial x86_64 run measured ~179 MiB peak RSS and ~4% of one core at 50 Hz/200 Hz; this does not establish performance on a throttled/shared cloud CPU. Telemetry is ~6.5 KB/sample, about 112 MiB/hour at 5 Hz before TLS/HTTP overhead. Owner should disconnect when finished. No keepalive requests or external wake monitors are configured. A connected app polling will keep the provider active; after disconnect the provider's inactivity policy can sleep it. The independent simulation idle timer pauses physics after 60 seconds without a newly applied command, even while telemetry is polled. This reduces CPU, not provider billing hours.

## Reproducible staging package

Only first-party bridge code and CPU dependency requirements enter `tools/t-duck-cloud/Dockerfile`; no robot geometry, runtime source or policy weights are copied into the image or APK. The image runs as unprivileged uid 10001 with single-thread math defaults. Before deployment, test this exact package locally/CI:

```sh
docker build -f tools/t-duck-cloud/Dockerfile -t tduck-staging-candidate .
```

After owner approval, deploy **one nonproduction Render Web Service**, runtime Docker, this repository/companion commit, Dockerfile above, context repository root, compute explicitly `free`, no disk/database/domain/paid add-ons, auto-deploy Off, health path `/healthz`, default port 10000. Do not omit compute plan (provider defaults can be paid). No Blueprint auto-applies or deploy hooks are installed.

Required runtime configuration, to be supplied through owner-approved secret handling, **not** committed values:

- `T_DUCK_TOKEN`: owner-managed random token, at least 24 printable characters. Never send it through URLs, logs, issues or chat. Creation/storage is a separate approval boundary; no owner token has been provisioned by TC-03.
- `T_DUCK_SOURCE_USE_APPROVED=yes`: explicit source-use review gate. Default startup fails before fetching anything. This flag is not legal evidence; see licensing below.
- `T_DUCK_EDGE_HTTPS=trusted-provider-edge-only`: explicitly acknowledges provider HTTPS termination. Android still uses HTTPS with normal chain/hostname checks. The container's HTTP port must be reachable **only through the trusted provider edge**, which must overwrite `X-Forwarded-Proto`. Direct HTTP deployment is unsupported. Validate that boundary before enabling controls; do not trust client-supplied forwarding headers on an Internet-facing socket.

Startup shallow-fetches exact foundation/RL/runtime commits from integration-lock.json into private ephemeral `/sources`, verifies revisions, and uses the unchanged foundation loader to validate the exact ONNX hash. No public source image/archive with assets is published. A failed download, missing permission or source mismatch fails closed. Cold-start fetch latency is unmeasured on the provider and may exceed Android's wake budget; app must report unavailable, never fabricate telemetry.

Endpoints/session/telemetry remain [protocol 1.1](TC02_MUJOCO.md). `/healthz` returns only `{ready: boolean}`, no state or motion, and does not create a session/renew idle. All `/v1/*` require the bearer token; edge mode additionally requires the trusted HTTPS forwarding header. Max eight concurrent requests with bounded socket/body deadlines. SIGTERM requests rest before server shutdown. No raw motor endpoint, cloud safety dependency or real firmware flashing.

Android read-only capability discovery can retry 502/503/504, socket timeout or connection refusal up to 36 attempts (~87 seconds including per-request deadlines). Auth failures, certificate failures, invalid identity/protocol and malformed telemetry fail rather than being accepted as warmup. Movement/Stop requests retain 800 ms socket and 950 ms overall deadlines, short leases and no automatic retries. A new owner session clears previous motion and pauses physics. Existing source/boot/frame validation and independent wall-clock lease expiry stay active. Remote Stop is best effort: **network loss must be handled by the simulation watchdog**, never assumed safe merely because a cloud Stop was sent.

## Licensing and robotics handover

Pinned code's Apache-2.0 notice is not treated as proof for every inherited mesh or exported weight. Read-only inspection of the pinned source checkouts still finds RL code LICENSE, no runtime root LICENSE, and no resolved file-level grants for all assets/weights in foundation's `docs/T_DUCK_PROGRESS.md` and `docs/T_DUCK_LICENSE_INQUIRY.md`. No upstream files or model weights are bundled publicly; no maintainer outreach was sent. Before runtime hosting, record exact file provenance/grants and required notices or obtain permission through owner-approved outreach. No robotics code change is requested for current protocol; handover asks robotics to confirm the source-use review and future state/reset semantics. Rest remains physics pause, not a sitting controller; recovery unsupported.

## Acceptance after deployment approval

1. Confirm target workspace with owner, inspect actual payment-method/quota status without changing billing. If zero spending cannot be verified, stop before provisioning. Never upgrade or add a card.
2. Complete source-use review; approve the specific staging service and token custody. Keep auto-deploy off and no production traffic.
3. Build/deploy exact tested commit, wait for terminal live state, validate HTTPS certificate/hostname and overwritten forwarding headers, verify unauthenticated `/v1` rejects. Run resource benchmark on the actual host; ensure physics responsiveness/watchdog under its CPU limit.
4. On a physical Android phone (mobile data, no PC/LAN dependency), enter approved endpoint/token in Settings. Observe explicit starting/connected states. Issue stand, forward, Stop, left, right, rest. Correlate app ACK IDs and actual changed MjData frame/position/contacts with server audit. Capture Sensors UI showing the same frame; redact all access fields.
5. Test idle cold start, network loss during movement, owner-session replacement, stale/reordered command, token rejection, TLS rejection, boot change and provider restart. Verify short leases expire without telemetry or app participation and reconnection never resumes intent.
6. Save timestamped app/server/UI evidence and measured CPU/RSS/cold-start latency, then offer the approved signed APK. Until these pass, `android_to_public_mujoco_verified=false` and `physical_phone_verified=false`.

If hosting remains blocked, the existing local TLS bridge and offline demo still work. A browser-local physics approach could remove a server dependency but requires a separate MuJoCo-WASM/ONNX/BAM port and asset licensing work; it is not equivalent to the existing static simulation playback viewer and has not been implemented/claimed here.
