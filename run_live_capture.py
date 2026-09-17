import base64
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REQUEST_PATH = Path("doorbell_request.json")
PLAINTEXT_DIR = Path("artifacts/live-plaintext")
STATUS_PATH = Path("artifacts/live-capture-exit-code.txt")


def utc_now():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.isoformat().replace("+00:00", "Z")


def parse_iso(value):
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return dt.astimezone(timezone.utc)


def write_failure(request_id, stage, code, message, exit_code=2):
    PLAINTEXT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "success": False,
        "request_id": request_id,
        "failed_at": iso(utc_now()),
        "error": {"stage": stage, "code": code, "message": message},
    }
    (PLAINTEXT_DIR / f"{request_id}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(str(exit_code), encoding="ascii")
    return exit_code


def validate_request():
    request = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
    request_id = request.get("request_id", "")
    uuid.UUID(request_id)
    requested_at = parse_iso(request["requested_at"])
    public_raw = base64.b64decode(request["reply_public_key_b64"], validate=True)
    if len(public_raw) != 32:
        raise ValueError("reply public key must be 32 bytes")
    return request, request_id, requested_at


def load_bridge_config():
    raw = os.environ.get("NEST_BRIDGE_CONFIG", "")
    if not raw:
        raise ValueError("NEST_BRIDGE_CONFIG secret is not configured")
    config = json.loads(raw)
    if not isinstance(config, dict):
        raise ValueError("NEST_BRIDGE_CONFIG must be a JSON object")
    required = ["client_id", "refresh_token"]
    missing = [key for key in required if not str(config.get(key, "")).strip()]
    if missing:
        raise ValueError("NEST_BRIDGE_CONFIG is missing required fields")
    if not str(config.get("device_name", "")).strip() and not str(config.get("enterprise_id", "")).strip():
        raise ValueError("NEST_BRIDGE_CONFIG needs device_name or enterprise_id")
    return config


def main():
    PLAINTEXT_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        request, request_id, requested_at = validate_request()
    except Exception:
        # A malformed request is not allowed to select arbitrary output paths.
        fallback_id = str(uuid.uuid4())
        return write_failure(fallback_id, "request_validation", "INVALID_REQUEST", "Doorbell request file is invalid")

    try:
        config = load_bridge_config()
    except Exception:
        return write_failure(request_id, "configuration", "INVALID_BRIDGE_CONFIG", "Secure Nest bridge configuration is missing or invalid")

    env = os.environ.copy()
    mapping = {
        "client_id": "NEST_CLIENT_ID",
        "client_secret": "NEST_CLIENT_SECRET",
        "refresh_token": "NEST_REFRESH_TOKEN",
        "enterprise_id": "NEST_ENTERPRISE_ID",
        "device_name": "NEST_DEVICE_NAME",
    }
    for config_key, env_key in mapping.items():
        value = str(config.get(config_key, "")).strip()
        if value:
            env[env_key] = value

    env["DOORBELL_REQUEST_ID"] = request_id
    env["DOORBELL_OUTPUT_DIR"] = str(PLAINTEXT_DIR)

    completed = subprocess.run([sys.executable, "nest_capture.py"], env=env, check=False)
    result_path = PLAINTEXT_DIR / f"{request_id}.json"
    image_path = PLAINTEXT_DIR / f"{request_id}.png"

    if not result_path.exists():
        return write_failure(request_id, "internal", "MISSING_RESULT", "Capture worker ended without a correlated result", exit_code=3)

    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result.get("request_id") != request_id:
            raise ValueError("request correlation mismatch")

        if result.get("success"):
            frame_at = parse_iso(result["freshness"]["frame_received_at"])
            if frame_at <= requested_at:
                if image_path.exists():
                    image_path.unlink()
                result = {
                    "success": False,
                    "request_id": request_id,
                    "failed_at": iso(utc_now()),
                    "error": {
                        "stage": "freshness",
                        "code": "FRAME_PREDATES_USER_REQUEST",
                        "message": "Decoded frame did not occur after the initiating ChatGPT request",
                    },
                }
                completed = subprocess.CompletedProcess(completed.args, 2)
            else:
                result["freshness"]["user_requested_at"] = iso(requested_at)
                result["freshness"]["frame_after_user_request"] = True

        result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    except Exception:
        if image_path.exists():
            image_path.unlink()
        return write_failure(request_id, "result_validation", "INVALID_RESULT", "Capture result could not be correlated and validated", exit_code=3)

    STATUS_PATH.write_text(str(completed.returncode), encoding="ascii")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
