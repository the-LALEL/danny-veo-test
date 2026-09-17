# Nest Doorbell capture core

This branch intentionally implements only **Milestone A: obtain one genuinely fresh Nest Doorbell image**.
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

## OAuth-client diagnostic

Before repeating a Nest consent flow, the existing client-ID/client-secret pair can be checked without calling the Nest API:

```bash
python nest_capture.py --probe-oauth-client
```

A valid client pair is recognized when Google accepts the client identity and rejects only the deliberately invalid authorization code (`invalid_grant`). A rejected client identity is reported as `OAUTH_CLIENT_MISMATCH`.

## One-shot capture

Install the pinned media dependencies:

```bash
python -m pip install -r requirements-doorbell.txt
```

Then run:

```bash
python nest_capture.py
```

Success creates a correlated PNG plus JSON metadata under `artifacts/real-capture/`. The metadata includes request, stream-command, SDP-application, and frame-receipt timestamps so a frame received before the current capture request cannot be presented as fresh.

## Failure boundary

The command deliberately identifies the stage of failure: authentication, configuration, device discovery, Nest API command, SDP generation/validation, WebRTC negotiation, media receipt, frame decode, freshness, or image creation.

No ChatGPT transport, database, queue, public image URL, encryption envelope, or persistent runner is part of this capture core. Those should be selected only after a real Nest frame succeeds reliably.
