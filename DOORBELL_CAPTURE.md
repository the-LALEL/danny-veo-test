# Nest Doorbell capture core

This branch intentionally implements only **Milestone A: obtain one current-session Nest Doorbell image**.
It does not yet implement delivery of that image to ChatGPT.

## Reused existing state

Keep the existing Google Cloud project, OAuth client, Nest Device Access project, and authorization relationship. Do not create replacements merely to run this code.

The capture process reads credentials from the runtime environment; it never writes OAuth credentials or tokens to result files.

## Configuration

Use either a short-lived access token:

- `NEST_ACCESS_TOKEN`

or unattended refresh credentials:

- `NEST_CLIENT_ID`
- `NEST_REFRESH_TOKEN`
- `NEST_CLIENT_SECRET` when required by the existing OAuth client type

Select the existing doorbell with either:

- `NEST_DEVICE_NAME=enterprises/.../devices/...`, or
- `NEST_DEVICE_ACCESS_PROJECT_ID=<existing Device Access Project ID>`

`NEST_ENTERPRISE_ID` remains accepted as a compatibility alias for the experimental branch.

`DOORBELL_REQUEST_ID`, when supplied, must be a UUID. Reusing an ID first removes any correlated old PNG/JSON so a failed new capture cannot accidentally leave stale imagery looking current.

## OAuth-client diagnostic

Before repeating a Nest consent flow, the existing client-ID/client-secret pair can be checked without calling the Nest API:

```bash
python nest_capture.py --probe-oauth-client
```

The probe deliberately supplies an invalid authorization code. `invalid_grant` means Google got past client authentication to grant validation; `invalid_client`/HTTP 401 is reported as `OAUTH_CLIENT_MISMATCH`.

## One-shot capture

Install the pinned media dependencies:

```bash
python -m pip install -r requirements-doorbell.txt
```

Then run:

```bash
python nest_capture.py
```

Success creates a correlated PNG plus JSON metadata under `artifacts/real-capture/`. The output directory is restricted to the current user where POSIX permissions are available, and image/result files are written as owner-only.

The metadata includes request, stream-command, SDP-application, and frame-receipt timestamps. A successful result proves that the decoded frame was received from a live WebRTC session created after the current request. Nest does not provide a camera-sensor exposure timestamp through this path, so the metadata explicitly records `camera_sensor_capture_time_proven: false` rather than overstating that evidence.

## Failure boundary

The command deliberately identifies the stage of failure: request validation, authentication, configuration, device discovery, Nest API command, SDP generation/validation, WebRTC negotiation, media receipt, frame decode, freshness, or image creation.

No ChatGPT transport, database, queue, public image URL, encryption envelope, or persistent runner is part of this capture core. Those should be selected only after a real Nest frame succeeds reliably.

## Live smoke test

`.github/workflows/doorbell-live-smoke.yml` is manual-only. It expects a repository secret named `NEST_BRIDGE_CONFIG`, attempts one real capture, uploads nothing, and deletes any camera pixels before the ephemeral runner exits.

The repository does not currently expose that secret to the workflow. Therefore the present live-smoke result is `BRIDGE_CONFIG_NOT_SUPPLIED`; no Nest API request is made in that state.


## Sanitized media packet probe

`doorbell_packet_probe.py` is now the preferred diagnostic if a real capture again reaches
the media stage without producing a frame.

It instruments the same capture path and records only:

- coarse inbound ICE/DTLS/SRTP-like datagram counts;
- remote video codec payload types and H264 profile metadata;
- receiver payload-type registrations;
- parsed RTP packet counts by payload type;
- routed versus router-dropped RTP counts;
- H264-video-specific routed/dropped packet counts;
- an automatic deepest-boundary classification.

It deliberately does **not** retain or print OAuth credentials, SDP candidate addresses,
IP addresses, media payload bytes, or camera pixels. Any temporary PNG created after a
successful decode is deleted with the temporary probe directory.

The manual workflow `.github/workflows/doorbell-media-probe.yml` uses the same
`NEST_BRIDGE_CONFIG` secret contract as the live smoke workflow and prints only the
sanitized JSON diagnostic. The probe implementation and its tests compile and pass in
GitHub Actions on Python 3.12 with the pinned media runtime.
