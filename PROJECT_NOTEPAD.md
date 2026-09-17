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
