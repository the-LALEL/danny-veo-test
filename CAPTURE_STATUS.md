# Doorbell capture-core status

## Objective

Prove Milestone A independently: obtain a current-session image from the existing Nest Doorbell using the existing Google Cloud / Device Access authorization relationship, with enough timing evidence to reject stale results from prior requests.

## Verified

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

## Freshness evidence boundary

A successful capture proves that a decoded frame was received from a WebRTC session created after the current capture request. The Device Access WebRTC path used here does not provide a camera-sensor exposure timestamp, so success metadata records:

- `fresh_live_session_observation: true`
- `camera_sensor_capture_time_proven: false`

That distinction is intentional. Do not claim stronger freshness evidence unless a later interface supplies a trustworthy capture timestamp.

## Live-test result

The current GitHub live smoke test did not reach Google or Nest because `NEST_BRIDGE_CONFIG` was not available to that workflow. It correctly returned `BRIDGE_CONFIG_NOT_SUPPLIED`; no Nest API request was made and no camera image was retained.

This is a configuration boundary, not evidence of an OAuth, WebRTC, decoder, or camera failure.

A separate earlier Cloud Shell attempt reached Google's OAuth token endpoint and received HTTP 401 for the manually supplied client identity. That is evidence about that credential attempt only; it does not mean the GitHub smoke workflow reached OAuth.

## Existing Google Cloud state to preserve

The experimental branch identified the existing Google Cloud project as `chatgpt-doorbell-bridge` and previously used Google Secret Manager names:

- `nest-doorbell-oauth-client-secret`
- `nest-doorbell-refresh-token`

Those values must not be committed or copied into repository files. The capture core intentionally consumes credentials through environment variables so the eventual runtime can inject them securely.

## Next discriminating test

Inject the existing, validated OAuth client identity and Nest refresh authorization into a runtime as environment variables, then run `python nest_capture.py` once.

Interpret the next result strictly by stage:

1. authentication failure → repair only OAuth credential state;
2. device discovery / Nest API failure → repair only Device Access state;
3. WebRTC/media failure → use the preserved diagnostic branch to identify the media stage;
4. current-session PNG produced → the capture primitive is proven and work can move to ChatGPT image delivery.

Do not add delivery infrastructure before case 4.
