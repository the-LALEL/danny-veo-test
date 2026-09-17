#!/usr/bin/env bash
set -euo pipefail
umask 077

MEDIA_REF="f3f8806b97a86ac704425d54ac99465d30071cbc"
ROOT="${HOME}/.doorbell-bridge"
VENV="${ROOT}/venv"
DIAG="${ROOT}/nest_real_diagnostic.py"
FREEZE="${ROOT}/last-pip-freeze.txt"

export NEST_DEVICE_ACCESS_PROJECT_ID="${NEST_DEVICE_ACCESS_PROJECT_ID:-4e99f47f-d177-4bca-8791-0be2165bff22}"
export NEST_CLIENT_ID="${NEST_CLIENT_ID:-1055358446706-fo9pp0qshik9f1jjsoaanje1qr505jjk.apps.googleusercontent.com}"

mkdir -p "${ROOT}"
chmod 700 "${ROOT}"

if [[ ! -x "${VENV}/bin/python" ]]; then
  python3 -m venv "${VENV}"
fi

"${VENV}/bin/python" -m pip install --disable-pip-version-check --quiet --upgrade pip
"${VENV}/bin/python" -m pip install --disable-pip-version-check --quiet \
  "aiortc==1.14.0" \
  "aioice==0.10.1" \
  "av==16.0.1" \
  "requests==2.32.5" \
  "Pillow==11.3.0"

"${VENV}/bin/python" -m pip freeze > "${FREEZE}"
chmod 600 "${FREEZE}"

TMP="${DIAG}.tmp"
curl --fail --silent --show-error --location \
  "https://raw.githubusercontent.com/the-LALEL/danny-veo-test/${MEDIA_REF}/nest_real_diagnostic.py" \
  --output "${TMP}"
chmod 600 "${TMP}"
mv "${TMP}" "${DIAG}"

echo "Running the audited media self-test before any OAuth or camera request..."
"${VENV}/bin/python" "${DIAG}" --self-test

echo
echo "One-time OAuth credential gate."
echo "The secret is held only in this process environment and is not written to disk."
read -rsp 'OAuth client secret (hidden): ' NEST_CLIENT_SECRET
echo
export NEST_CLIENT_SECRET

set +e
PROBE_OUTPUT=$("${VENV}/bin/python" - <<'PY'
import os
import sys
import requests

resp = requests.post(
    "https://www.googleapis.com/oauth2/v4/token",
    data={
        "client_id": os.environ["NEST_CLIENT_ID"],
        "client_secret": os.environ["NEST_CLIENT_SECRET"],
        "code": "doorbell-credential-probe-intentionally-invalid",
        "grant_type": "authorization_code",
        "redirect_uri": "https://www.google.com",
    },
    timeout=20,
)
try:
    body = resp.json() if resp.content else {}
except ValueError:
    body = {}
error = body.get("error") if isinstance(body, dict) else None

# A valid client ID / secret pair reaches code validation, so our deliberately
# fake code must fail as invalid_grant. An invalid pair fails earlier as
# invalid_client / HTTP 401.
if error == "invalid_grant":
    print("VALID")
    raise SystemExit(0)
if resp.status_code == 401 or error == "invalid_client":
    print("MISMATCH")
    raise SystemExit(42)
print(f"UNEXPECTED:{resp.status_code}:{error or 'unknown'}")
raise SystemExit(43)
PY
)
PROBE_RC=$?
set -e

case "${PROBE_RC}" in
  0)
    echo "OAuth client credential: VALIDATED."
    ;;
  42)
    unset NEST_CLIENT_SECRET
    echo "STOPPED: CLIENT_SECRET_MISMATCH."
    echo "Google rejected this client ID/secret pair before any Nest consent or camera request."
    exit 42
    ;;
  *)
    unset NEST_CLIENT_SECRET
    echo "STOPPED: OAuth credential probe returned ${PROBE_OUTPUT}."
    echo "No Nest consent or camera request was started."
    exit "${PROBE_RC}"
    ;;
esac

echo
echo "Credential gate passed. Starting the unchanged audited Nest diagnostic."
echo "From this point, follow only the single Nest consent prompt printed by the diagnostic."
echo
exec "${VENV}/bin/python" "${DIAG}" --base-dir "${ROOT}"
