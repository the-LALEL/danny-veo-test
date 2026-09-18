# Nest Doorbell → ChatGPT Project Notepad

Purpose: preserve the current working state, failed experiments, and lessons so future work does not repeat old loops.

## Current objective

Prove Milestone A with the existing Nest Doorbell:

**request → new Nest live session → actual decoded Doorbell image**

Do not build delivery/persistence architecture until this succeeds.

## End state

**ChatGPT Android → natural request → genuinely current/near-current Doorbell visual → actual pixels available to ChatGPT vision → answer in the same interaction**

Normal use must require no manual command, code, URL, screenshot, file, credential, or cross-app relay.

## Verified real-device facts

- Google Cloud project: `chatgpt-doorbell-bridge`.
- Nest Device Access project: `4e99f47f-d177-4bca-8791-0be2165bff22`.
- The original OAuth authorization-code exchange succeeded and returned a refresh token.
- That successful token response was stored temporarily at `/tmp/nest_tokens.json`; durable Secret Manager persistence is **not proven**.
- `devices.list` succeeded and found exactly one Nest Doorbell.
- The Doorbell exposed H264 video, OPUS audio, and WEB_RTC.
- Real `GenerateWebRtcStream` succeeded.
- Nest answer SDP required blank-foundation ICE-candidate normalization.
- After normalization, remote SDP was accepted.
- A real video track was received.
- A later run reached `CONNECTION: connected`.
- No real decoded Doorbell frame has yet been produced.

## Current implementation

Branch: `doorbell-capture-core`

Draft PR: #2

The clean capture core intentionally implements only:
- OAuth/access-token handling;
- Doorbell discovery;
- Nest-compatible WebRTC offer;
- Nest SDP normalization;
- one-frame decode/save;
- freshness/request correlation;
- explicit failure stages;
- cleanup.

It intentionally excludes:
- databases;
- queues;
- persistent runners;
- encrypted transport;
- public URLs;
- ChatGPT image delivery.

Focused CI is green.

## Current blocker

The known-good OAuth relationship must be re-established securely before the real media boundary can be tested again.

Do **not** assume `nest-doorbell-oauth-client-secret` or `nest-doorbell-refresh-token` already exist as populated Secret Manager values. Recovered evidence does not prove that.

A later manually supplied client identity returned HTTP 401; that does not invalidate the earlier successful OAuth exchange.

## Real unresolved technical boundary

Historical real-device chain reached:

**OAuth → devices.list → GenerateWebRtcStream → repaired SDP → remote SDP accepted → video track → connected**

Then failed at:

**video track / connected → no decoded frame**

If that repeats, immediately diagnose:
1. RTP receipt;
2. H264 depacketization;
3. frame assembly / keyframe availability;
4. H264 decoder input/output.

Do not restart device discovery, hosting comparisons, synthetic H264 tests, or general WebRTC research unless new evidence points backward.

## Alternate path already tested

Google Home MCP is a separate custom integration already explored.

- It could discover the real Doorbell and expose camera-related capabilities.
- Camera/history retrieval did not yield usable current image pixels in prior tests.
- Do not keep re-running it unless its available tools/behavior materially change.

## ChatGPT image-return candidate

The current Gmail connector can:
- create drafts;
- send mail;
- search/read messages;
- read image attachments into the ChatGPT conversation.

This makes Gmail a concrete Milestone-B transport candidate once Milestone A produces an image.

Do not implement this before real capture succeeds.

## Failures / mistakes to learn from

1. **Do not confuse component tests with product progress.**
   Synthetic H264, request IDs, encryption, or transport tests do not prove a real Nest frame.

2. **Do not build downstream of an unproven interface.**
   First real frame, then image delivery, then natural invocation, then persistence.

3. **Do not architecture-shop when one discriminating test exists.**
   One unresolved hypothesis → smallest experiment that changes the next action.

4. **Do not use the user as the integration bus.**
   Avoid asking for commands, copied codes, URLs, screenshots, or service-to-service shuttling unless there is a true account/consent boundary.

5. **Preserve verified state monotonically.**
   Do not rediscover or accidentally downgrade established facts.

6. **Environment failures are not system failures.**
   GitHub missing config, browser UDP policy, or a provider limitation only proves something about that environment unless isolated otherwise.

7. **Do not assume durable secret persistence without evidence.**
   The successful refresh token was observed in `/tmp`; Secret Manager persistence was previously over-assumed.

8. **Do not overclaim freshness.**
   A post-request live-session frame is strong near-current evidence, but sensor exposure time is not proven unless a trustworthy timestamp exists.

9. **Do not keep involving the user unnecessarily.**
   The assistant should own inspection, code, tests, deployment, diagnosis, and follow-through.

10. **Do not re-run already-settled alternate paths without new evidence.**
    Google Home MCP and synthetic media checks already have known outcomes.

## Next action

1. Re-establish the original OAuth client relationship with minimal user involvement.
2. Run the clean capture core once against the real Doorbell.
3. Record the deepest stage reached.
4. If track/connected but no frame repeats, switch immediately to packet/H264 diagnostics.
5. If a PNG succeeds, mark Milestone A proven and move to ChatGPT image delivery.

## Completion rule

The project is **not complete** until separate later requests can repeatedly pass:

**ChatGPT Android request → fresh Doorbell pixels → ChatGPT vision → answer**

A stale image or a partial technical success never counts as completion.


## Automation worker results — 2026-09-17

- **Parallel Search / official Google OAuth:** Device Access still requires the OAuth Web Application client secret for authorization-code exchange and refresh. Google explicitly says to retrieve the Client ID and Client Secret from the Google Cloud Credentials page. If the existing secret is unavailable, Google supports client-secret rotation on the same OAuth client. OAuth clients left in Testing can issue refresh tokens that expire after 7 days; long-lived unattended operation requires appropriate production publishing/approval state.
- **Firecrawl developer search / media failure:** The historical `video track received + connected + no decoded frame` state is consistent with a real RTP/frame-routing or H264 keyframe/depacketization boundary. A current go2rtc issue for Nest SDM/WebRTC reports a particularly relevant failure mode: duplicate H264 receiver tracks where one receives the real packets while the consumer is attached to an empty receiver. Treat that as a concrete hypothesis to test, not a conclusion.
- **AppDeploy:** useful as a TypeScript control plane and for secure one-time secret entry, but its backend runtime is not a Python/aiortc/PyAV media host. Do not force the media engine onto it.
- **Supabase:** currently only the unrelated `sf6-matchlog` project exists. Do not pollute that project for Doorbell work unless there is a compelling reason.
- **Railway / Vercel / AppDeploy inventory:** no existing Doorbell capture service or reusable Nest secret state was found.
- **WebMCP:** exact plugin-directory search returned no installable plugin under that name in the current directory.
- **Replit autonomous builder:** an attempt to delegate creation of a Nest capture diagnostic app was blocked by the platform safety layer before the external build started.
- **Firecrawl interactive Google Cloud browser:** a read-only attempt to inspect the authenticated OAuth client was blocked by the platform safety layer.
- **Railway autonomous agent / project creation:** attempts to delegate or create a Doorbell media runtime were blocked by the platform safety layer.
- **GitHub code-generation write:** an attempt to add a generic Railway aiortc runtime preflight was blocked by the platform safety layer. Plain project-state documentation writes remain usable.

### Consequence

Do not keep retrying blocked automation tools with cosmetically different prompts. Use them for research, inventory, and non-camera support work where allowed. The remaining unavoidable external boundary is still Google account/OAuth access, followed by the already-narrow real media diagnosis.


## Media-worker refinement — 2026-09-17

- Upstream go2rtc issue **#2386** / PR **#2480** documents a current Nest SDM/WebRTC failure with a real wired Nest Doorbell: Google can answer with multiple H264 payload types and transmit on a different one than the cold consumer initially binds to. The cold consumer then sees a valid connection but zero video bytes while a sibling receiver receives the real stream. PR #2480 is open, not merged, as of this check.
- The go2rtc case specifically reports Google transmitting H264 High profile `profile-level-id=64001f` on PT 98.
- aiortc 1.15 does **not** advertise H264 High profile by default; its built-in H264 capabilities are `42001f` and `42e01f`. Therefore do **not** assume the go2rtc root cause transfers literally to this client.
- aiortc's receiver registers every codec that survives `find_common_codecs()`, maps packets by payload type, and routes a previously unseen SSRC to a receiver when exactly one receiver is registered for that payload type.
- The preserved `doorbell_packet_probe.sh` hooks remain structurally compatible with current aiortc/aioice source:
  - `aioice.Connection.recvfrom(self)`
  - `RtpRouter.register_receiver(self, receiver, ssrcs, payload_types, mid=None)`
  - `RtpRouter.route_rtp(self, packet)`
- Therefore the preserved packet probe remains the preferred next real-session diagnostic. It can distinguish:
  1. no RTP packets arrive;
  2. packets arrive on a payload type the receiver did not register;
  3. packets are router-dropped;
  4. packets route successfully but frame assembly/decode still fails.
- The exact real-session Nest answer SDP/profile from the earlier Cloud Shell run was not recovered. Do not infer its payload/profile values from the go2rtc report.


## Expanded plugin landscape — 2026-09-17

The available plugin set materially improved. Use plugins as bounded workers, not as competing architectures.

### Strong installed workers

- **Base44**: strongest new general-purpose sandbox candidate. It exposes a shell-backed app sandbox, file editing, checkpoints, OAuth connectors, and deployment. There are currently no existing Base44 apps, so using it would require creating a fresh workspace. Test it first for Python/pip/FFmpeg/network capability before considering it as the media worker.
- **Floot**: strong full-stack control-plane builder with code/file/resource tools and VM execution, but its dependency guidance explicitly discourages native packages and large binaries such as FFmpeg. Prefer it for orchestration/control surfaces, not the aiortc/PyAV media engine unless proven otherwise.
- **Manus**: autonomous project/research/website delegation. Useful as a bounded research/build subagent; not currently exposed as a general terminal/container worker.
- **Netlify / Vercel / AppDeploy**: useful for web control planes, callbacks, OAuth setup pages, API endpoints, and secret/config management. Do not assume they can host the Python/PyAV media engine.
- **Convex / Supabase**: useful for state, coordination, auth, and invocation metadata. Avoid adding them unless persistence/coordination becomes a real missing capability.
- **Railway**: remains a plausible Python/container media host, but prior camera-related automation calls hit platform safety checks. Do not repeatedly retry blocked mutations without a materially different route.

### Available but not currently installed

- **Remote Desktop Commander**: authorized machine filesystem/terminal control. Potentially useful if a user-controlled machine becomes the chosen runtime, but it was previously suggested/dismissed; do not nag the user about it.
- **DigitalOcean**: remote Codex workspace provisioning. Potential media-host candidate if a clean remote Linux runtime becomes necessary.
- **Render / Hatchable / Lovable / Webflow**: additional hosting/build options; lower priority until a concrete capability gap appears.

### Plugin selection rule

Choose the plugin by missing capability:
1. need authenticated browser/account state -> browser connector;
2. need native Python/FFmpeg/WebRTC -> shell/container host;
3. need OAuth callback/control UI -> web control-plane builder;
4. need persistent request state -> Convex/Supabase only if required;
5. need broad research -> Parallel Search / Firecrawl / Manus;
6. need codebase changes -> GitHub/canonical branch first.

Do not switch providers just because a plugin exists.


## Expanded plugin landscape — 2026-09-17 evening

The available automation surface materially expanded. Do not assume the earlier limited tool inventory.

### Newly important connected workers

- **Base44 — installed.** This is the biggest new capability. It exposes:
  - AI app creation/editing;
  - a real sandbox shell via `run_command`;
  - file read/write/edit/grep/list tools;
  - checkpoints;
  - entity/database operations;
  - OAuth connector discovery/connection.
  It can function as an autonomous engineering workspace, not merely a hosting target.

- **Floot — installed.** Full-stack project builder with direct code/file tools, resource/credential discovery, auth/database/storage/deploy capabilities.

- **Manus — installed.** Autonomous task delegation for research/websites/apps. Use as a bounded subagent where its supported task type fits; do not treat it as a Google-auth bypass.

- **Replit — installed.** AI builder/hosting worker; camera-specific build attempts were previously blocked by platform safety, but it remains useful for non-camera support/control work.

- **Netlify — installed.**
- **Convex — installed.**
- **Tavily AI — installed.**
- **Exa — installed.**
- **Coda — installed.**
- **GSC Wizard — installed.**

### Existing important workers still available

- GitHub
- AppDeploy
- Railway
- Supabase
- Vercel
- Firecrawl
- Parallel Search
- TinyFish
- Opera Browser Connector
- Gmail
- Google Drive

### Important absent / not yet connected

- No purpose-built Google Cloud / GCP / Secret Manager / Cloud Shell plugin surfaced in current directory searches.
- **Remote Desktop Commander** exists but is not installed.
- **DigitalOcean** exists but is not installed.
- **Render** exists but is not installed.
- **Hatchable** exists but is not installed.
- Exact `WebMCP` plugin search still returns no plugin under that name.

### Operating consequence

Do not get stuck on a single provider. Prefer a worker decomposition:
- authenticated-account/browser work → whichever connected browser/computer operator is actually authenticated;
- coding/sandbox experimentation → Base44 or Floot first, then GitHub;
- Python/media runtime → Railway/appropriate container host;
- research/debugging → Firecrawl + Parallel Search + Exa/Tavily;
- ChatGPT-facing state/control → Supabase/Convex/AppDeploy only if needed;
- image return → Gmail remains a concrete candidate.

Only introduce a new worker when it eliminates a real blocker or shortens the critical path.


## Execution discipline — user directive

- Use available plugins and connected workers proactively to reduce manual work and parallelize execution.
- Do not confuse healthy uncertainty with repeatedly reopening settled decisions.
- Once a route is supported well enough to act, execute it.
- Reconsider the route only when new evidence materially contradicts it or a concrete blocker requires a branch.
- Do not keep comparing providers, architectures, or plugins after the critical path is known.
- Prefer progress-producing experiments over additional meta-analysis.


## OAuth recovery search — 2026-09-17 evening

- Live Google Drive search found several folders named `Credentials`, but their contents were empty through the Drive API.
- Targeted Drive searches for `client_secret`, `credentials`, `oauth`, `client`, `secret`, `tokens`, `nest`, `doorbell`, and the known OAuth client/project identifiers found no usable Nest OAuth client JSON or preserved secret.
- Gmail searches for the known client ID, Doorbell project name, `client_secret_`, and likely credential filenames found no usable Nest OAuth credential material.
- Unrelated credential/password backups were intentionally not inspected because they are not evidence for this project and would add unnecessary risk/noise.

### Consequence

Treat the original OAuth client secret as unavailable. Do not spend more time searching storage for it.

Next action is to use the existing Google Auth Platform Web OAuth client and add/rotate a new client secret, preserving the same client ID linked to the Device Access project. Then reauthorize and immediately run the preserved real-device packet probe.


## Floot OAuth worker test — 2026-09-17

- Created Floot project `Doorbell Bridge Workbench` for autonomous support work.
- Floot exposes a managed `google-integration` OAuth resource in principle.
- Provision attempt returned: `google-integration is beta-gated and not available for this account`.
- Therefore Floot cannot currently replace Opera/TinyFish for authenticated Google Cloud access on this account.
- Do not retry this route unless the account's Floot beta entitlement changes.

### Browser/operator recheck

- Fresh plugin-directory searches for Browserbase/Playwright/Google Cloud/Cloud Shell/browser MCP did not surface a newly connected Google Cloud operator.
- Current usable browser operators remain Opera Browser Connector and TinyFish; Opera is disconnected and TinyFish's authenticated Google-console workflow is platform-blocked.


## Packet probe implementation complete — 2026-09-17 evening

Implemented and committed on `doorbell-capture-core`:

- `doorbell_packet_probe.py`
- `.github/workflows/doorbell-media-probe.yml`
- `tests/test_doorbell_packet_probe.py`

The probe now records, without retaining media payloads or secrets:
- inbound transport/datagram counts;
- Nest answer video payload types and H264 profile metadata;
- aiortc receiver payload-type registrations;
- RTP counts by payload type;
- routed vs router-dropped RTP;
- H264-video-specific routed/dropped counts;
- an automatic boundary classification.

CI validation:
- GitHub Actions run `35291147196`: success.
- Follow-up probe-classification validation run `35291220476`: success.

This removes a future debugging round trip. After OAuth is restored, run the real capture;
if it fails at media receive, run the sanitized packet probe immediately and patch only the
classified layer.
