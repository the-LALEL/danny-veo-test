#!/usr/bin/env bash
set -euo pipefail
umask 077

REF="${DOORBELL_DIAG_REF:?Set DOORBELL_DIAG_REF to the audited commit SHA.}"
ROOT="${HOME}/.doorbell-bridge"
VENV="${ROOT}/venv"
PYFILE="${ROOT}/nest_real_diagnostic.py"
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

RAW_BASE="https://raw.githubusercontent.com/the-LALEL/danny-veo-test/${REF}"
TMP="${PYFILE}.tmp"

curl --fail --silent --show-error --location \
  "${RAW_BASE}/nest_real_diagnostic.py" \
  --output "${TMP}"

chmod 600 "${TMP}"
mv "${TMP}" "${PYFILE}"

echo "Running local self-test before any Nest authorization or camera request..."
"${VENV}/bin/python" "${PYFILE}" --self-test

echo
echo "Self-test passed. Starting one real Nest diagnostic."
echo "No OAuth client secret, authorization code, access token, or refresh token is written to disk."
echo

exec "${VENV}/bin/python" "${PYFILE}" --base-dir "${ROOT}"
