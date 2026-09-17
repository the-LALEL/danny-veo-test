#!/usr/bin/env bash
set -euo pipefail
umask 077

RUNNER_REF="${DOORBELL_RUNNER_REF:?Set DOORBELL_RUNNER_REF to the audited runner commit SHA.}"
MEDIA_REF="f3f8806b97a86ac704425d54ac99465d30071cbc"
ROOT="${HOME}/.doorbell-bridge"
VENV="${ROOT}/venv"
DIAG="${ROOT}/nest_real_diagnostic.py"
RUNNER="${ROOT}/nest_persistent_runner.py"
FREEZE="${ROOT}/last-pip-freeze.txt"

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

fetch_file() {
  local ref="$1"
  local name="$2"
  local dest="$3"
  local tmp="${dest}.tmp"
  curl --fail --silent --show-error --location \
    "https://raw.githubusercontent.com/the-LALEL/danny-veo-test/${ref}/${name}" \
    --output "${tmp}"
  chmod 600 "${tmp}"
  mv "${tmp}" "${dest}"
}

fetch_file "${MEDIA_REF}" "nest_real_diagnostic.py" "${DIAG}"
fetch_file "${RUNNER_REF}" "nest_persistent_runner.py" "${RUNNER}"

echo "Running local self-tests before any OAuth or camera request..."
"${VENV}/bin/python" "${DIAG}" --self-test
"${VENV}/bin/python" "${RUNNER}" --self-test

echo
echo "Self-tests passed."
echo "Credential policy: OAuth client secret and Nest refresh token are persisted only in Google Secret Manager."
echo "Access tokens, authorization codes, and camera frames are not stored there."
echo "The OAuth client secret is validated before any Nest consent flow is started."
echo

export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-chatgpt-doorbell-bridge}"
export NEST_DEVICE_ACCESS_PROJECT_ID="${NEST_DEVICE_ACCESS_PROJECT_ID:-4e99f47f-d177-4bca-8791-0be2165bff22}"
export NEST_CLIENT_ID="${NEST_CLIENT_ID:-1055358446706-fo9pp0qshik9f1jjsoaanje1qr505jjk.apps.googleusercontent.com}"

exec "${VENV}/bin/python" "${RUNNER}" \
  --diagnostic "${DIAG}" \
  --base-dir "${ROOT}"
