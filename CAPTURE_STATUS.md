# Doorbell capture-core status

## Objective

Prove Milestone A independently: obtain a current-session image from the existing Nest Doorbell using the existing Google Cloud / Device Access authorization relationship, with enough timing evidence to reject stale results from prior requests.

## Verified capture-core behavior

- The capture core is isolated from ChatGPT delivery, databases, queues, public URLs, and long-lived hosting.
- The WebRTC offer is constrained to Nest-compatible audio/video/data-channel structure.
- Nest answer SDP normalization from the prior real-session diagnostic is preserved.
- Device discovery selects the WebRTC Doorbell rather than any generic WebRTC camera.
- OAuth refresh failures distinguish client-identity mismatch from rejected refresh authorization.
- Caller-supplied request IDs must be UUIDs, preventing path traversal and ambiguous correlation.
- A repeated request ID removes any correlated old PNG/JSON before a new capture attempt, so a failure cannot silently expose a stale image as current.
- Camera images and result metadata are written with owner-only permissions where POSIX permissions are available.
- Successful capture metadata records request, stream-command, SDP-application, and frame-receipt timestamps and explicitly distinguishes a fresh live-session observation from an unproven sensor exposure timestamp.
- CI installs the pinned media stack, compiles the module, and passes 11 focused tests on Ubuntu/Python 3.12.

## Recovered real-session evidence

Project screenshots from the original working Cloud Shell session establish the following sequence:

1. Google Cloud project `chatgpt-doorbell-bridge` was active.
2. The Nest Device Access project was `4e99f47f-d177-4bca-8791-0be2165bff22` and was shown as Sandbox.
3. The working OAuth client used the Web-application/Web-Server client ID `1055358446706-fo9pp0qshik9f1jjsoaanje1qr505jjk.apps.googleusercontent.com`.
4. The authorization-code exchange succeeded and reported `Refresh token present: true`.
5. That token response was written to `/tmp/nest_tokens.json`. The recovered evidence does not show a durable Secret Manager write.
6. `devices.list` succeeded and found exactly one `sdm.devices.types.DOORBELL` with H264, OPUS, and WEB_RTC support.
7. A real `GenerateWebRtcStream` call succeeded.
8. Nest answer SDP required normalization of blank-foundation ICE candidates; after normalization the remote SDP was accepted.
9. A video track was received and a later run reached `CONNECTION: connected`.
10. The real unresolved media boundary was downstream of connection establishment: no decoded frame arrived within the observed timeout.

This evidence materially narrows the historical failure. Basic Device Access authorization, doorbell discovery, stream generation, SDP application, and WebRTC connection/video-track delivery were demonstrated. A decoded real camera frame was not.

## Credential-state correction

Earlier project notes referred to prospective Secret Manager names `nest-doorbell-oauth-client-secret` and `nest-doorbell-refresh-token`. No recovered screenshot, Project/Library file, GitHub configuration, Railway environment, or AppDeploy secret inventory proves that those entries were ever created and populated.

Do **not** assume a durable refresh token currently exists in Secret Manager.

The successful refresh token was observed in the temporary Cloud Shell token response. Because the recovered evidence places it under `/tmp`, credential re-establishment may be required before the real media path can be tested again.

A later Cloud Shell attempt reached Google's OAuth token endpoint and returned HTTP 401 for a manually supplied client identity. That later failure does not invalidate the earlier successful OAuth exchange; it indicates that the later client ID/secret pairing was not accepted.

## Freshness evidence boundary

A successful capture proves that a decoded frame was received from a WebRTC session created after the current capture request. The Device Access WebRTC path used here does not provide a camera-sensor exposure timestamp, so success metadata records:

- `fresh_live_session_observation: true`
- `camera_sensor_capture_time_proven: false`

Do not claim stronger freshness evidence unless a later interface supplies a trustworthy capture timestamp.

## Current GitHub live-smoke result

The manual GitHub smoke workflow currently stops before Google or Nest because `NEST_BRIDGE_CONFIG` is not available to the workflow. It reports `BRIDGE_CONFIG_NOT_SUPPLIED`; no Nest API request is made and no camera image is retained.

This is a GitHub configuration boundary, not evidence of an OAuth, WebRTC, decoder, or camera failure.

## Next discriminating test

Re-establish the **same known-good OAuth client relationship** securely, then run `python nest_capture.py` once. Do not rebuild Device Access or create a new backend merely to perform this test.

Interpret the result strictly by stage:

1. authentication failure → repair only OAuth credential state;
2. device discovery / Nest API failure → repair only Device Access state;
3. WebRTC reaches a track/connection but no frame → immediately use the preserved packet-level diagnostic to isolate RTP/depacketization/frame-assembly/H264 decode;
4. current-session PNG produced → the capture primitive is proven and work can move to ChatGPT image delivery.

Do not add delivery infrastructure before case 4.
