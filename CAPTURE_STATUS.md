# Doorbell capture-core status

## Objective

Prove Milestone A independently: obtain one genuinely fresh image from the existing Nest Doorbell using the existing Google Cloud / Device Access authorization relationship.

## Verified

- The capture core is isolated from ChatGPT delivery, databases, queues, public URLs, and long-lived hosting.
- The WebRTC offer is constrained to Nest-compatible audio/video/data-channel structure.
- Nest answer SDP normalization from the prior real-session diagnostic is preserved.
- Device discovery selects the WebRTC Doorbell rather than any generic WebRTC camera.
- OAuth refresh failures distinguish client-identity mismatch from rejected refresh authorization.
- Successful capture metadata records request, stream-command, SDP-application, and frame-receipt timestamps.
- CI installs the pinned media stack, compiles the module, and passes the focused unit tests on Ubuntu.

## Live-test result

The current GitHub live smoke test did not reach Google or Nest because `NEST_BRIDGE_CONFIG` was not available to that workflow. It correctly returned `BRIDGE_CONFIG_NOT_SUPPLIED`; no Nest API request was made and no camera image was retained.

This is a configuration boundary, not evidence of a WebRTC or camera failure.

## Existing Google Cloud state to preserve

The experimental branch identified the existing Google Cloud project as `chatgpt-doorbell-bridge` and previously used Google Secret Manager names:

- `nest-doorbell-oauth-client-secret`
- `nest-doorbell-refresh-token`

Those values must not be committed or copied into repository files. The capture core intentionally consumes credentials through environment variables so the eventual runtime can inject them securely.

## Next discriminating test

Inject the existing, validated OAuth client identity and Nest refresh authorization into a runtime as environment variables, then run `python nest_capture.py` once.

The next result should be interpreted strictly by stage:

1. authentication failure → repair only OAuth credential state;
2. device discovery / Nest API failure → repair only Device Access state;
3. WebRTC/media failure → use the preserved diagnostic branch to identify the media stage;
4. fresh PNG produced → Milestone A is proven and work can move to ChatGPT image delivery.

Do not add delivery infrastructure before case 4.
