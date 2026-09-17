#!/usr/bin/env python3
import argparse
import asyncio
import getpass
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import requests

TOKEN_URL = "https://www.googleapis.com/oauth2/v4/token"
SDM_ROOT = "https://smartdevicemanagement.googleapis.com/v1"
PCM_BASE = "https://nestservices.google.com/partnerconnections"
GOOGLE_REDIRECT = "https://www.google.com"

DEFAULT_GCP_PROJECT = "chatgpt-doorbell-bridge"
DEFAULT_DEVICE_ACCESS_PROJECT = "4e99f47f-d177-4bca-8791-0be2165bff22"
DEFAULT_CLIENT_ID = "1055358446706-fo9pp0qshik9f1jjsoaanje1qr505jjk.apps.googleusercontent.com"
CLIENT_SECRET_ID = "nest-doorbell-oauth-client-secret"
REFRESH_TOKEN_ID = "nest-doorbell-refresh-token"


def build_pcm_url(project_id: str, client_id: str) -> str:
    return (
        f"{PCM_BASE}/{quote(project_id, safe='')}/auth"
        f"?redirect_uri={quote(GOOGLE_REDIRECT, safe='')}"
        "&access_type=offline"
        "&prompt=consent"
        f"&client_id={quote(client_id, safe='')}"
        "&response_type=code"
        f"&scope={quote('https://www.googleapis.com/auth/sdm.service', safe='')}"
    )


def extract_code(value: str) -> str:
    value = value.strip()
    if not value:
        raise RuntimeError("empty authorization response")
    if value.startswith("http://") or value.startswith("https://"):
        code = parse_qs(urlparse(value).query).get("code", [None])[0]
        if not code:
            raise RuntimeError("redirect URL has no code parameter")
        return code
    return value


def token_request(form: dict, timeout: int = 20):
    try:
        response = requests.post(TOKEN_URL, data=form, timeout=timeout)
    except requests.RequestException as exc:
        raise RuntimeError(f"OAuth network error: {type(exc).__name__}") from exc
    try:
        body = response.json() if response.content else {}
    except ValueError:
        body = {}
    return response.status_code, body


def validate_client_pair(client_id: str, client_secret: str) -> bool:
    status, body = token_request(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": "doorbell-credential-probe-intentionally-invalid",
            "grant_type": "authorization_code",
            "redirect_uri": GOOGLE_REDIRECT,
        }
    )
    error = body.get("error") if isinstance(body, dict) else None
    if error == "invalid_grant":
        return True
    if status == 401 or error == "invalid_client":
        return False
    raise RuntimeError(
        f"OAuth credential probe returned unexpected HTTP {status}"
        + (f" ({error})" if error else "")
    )


def exchange_code(client_id: str, client_secret: str, code: str) -> dict:
    status, body = token_request(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": GOOGLE_REDIRECT,
        }
    )
    if status >= 400:
        error = body.get("error") if isinstance(body, dict) else None
        raise RuntimeError(
            f"authorization-code exchange failed: HTTP {status}"
            + (f" ({error})" if error else "")
        )
    return body


def exchange_refresh(client_id: str, client_secret: str, refresh_token: str):
    status, body = token_request(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    )
    if status >= 400:
        return None, status, body.get("error") if isinstance(body, dict) else None
    return body, status, None


def run_gcloud(args, *, input_text=None, check=True):
    proc = subprocess.run(
        ["gcloud", *args],
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"gcloud command failed: {' '.join(args[:3])}")
    return proc


def ensure_secret_manager(gcp_project: str):
    run_gcloud(
        ["services", "enable", "secretmanager.googleapis.com", "--project", gcp_project, "--quiet"]
    )


def secret_exists(gcp_project: str, secret_id: str) -> bool:
    proc = run_gcloud(
        ["secrets", "describe", secret_id, "--project", gcp_project],
        check=False,
    )
    return proc.returncode == 0


def secret_access(gcp_project: str, secret_id: str) -> str:
    proc = run_gcloud(
        [
            "secrets",
            "versions",
            "access",
            "latest",
            "--secret",
            secret_id,
            "--project",
            gcp_project,
        ]
    )
    value = proc.stdout.rstrip("\r\n")
    if not value:
        raise RuntimeError(f"Secret Manager value is empty: {secret_id}")
    return value


def secret_store(gcp_project: str, secret_id: str, value: str):
    if not value:
        raise RuntimeError(f"refusing to store empty secret: {secret_id}")
    if secret_exists(gcp_project, secret_id):
        run_gcloud(
            [
                "secrets",
                "versions",
                "add",
                secret_id,
                "--project",
                gcp_project,
                "--data-file=-",
            ],
            input_text=value,
        )
    else:
        run_gcloud(
            [
                "secrets",
                "create",
                secret_id,
                "--project",
                gcp_project,
                "--replication-policy=automatic",
                "--data-file=-",
            ],
            input_text=value,
        )


def get_valid_client_secret(gcp_project: str, client_id: str) -> str:
    if secret_exists(gcp_project, CLIENT_SECRET_ID):
        stored = secret_access(gcp_project, CLIENT_SECRET_ID)
        try:
            if validate_client_pair(client_id, stored):
                print("OAuth client credential: validated from Secret Manager.")
                return stored
        except RuntimeError:
            raise
        print("Stored OAuth client secret does not match this client ID.")
        print("Enter the current secret once; it will be validated before any Nest consent flow.")
    else:
        print("One-time bootstrap: enter the OAuth client secret once.")
        print("It will be validated before any Nest consent flow, then stored in Google Secret Manager.")

    candidate = getpass.getpass("OAuth client secret (hidden): ").strip()
    if not candidate:
        raise RuntimeError("empty OAuth client secret")
    if not validate_client_pair(client_id, candidate):
        raise RuntimeError(
            "CLIENT_SECRET_MISMATCH: Google rejected this client ID/secret pair; Nest consent was not started"
        )
    secret_store(gcp_project, CLIENT_SECRET_ID, candidate)
    print("OAuth client credential: validated and stored in Secret Manager.")
    return candidate


def verify_devices(device_access_project: str, access_token: str):
    try:
        response = requests.get(
            f"{SDM_ROOT}/enterprises/{device_access_project}/devices",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"devices.list network error: {type(exc).__name__}") from exc
    if not response.ok:
        raise RuntimeError(f"devices.list failed: HTTP {response.status_code}")
    try:
        body = response.json()
    except ValueError as exc:
        raise RuntimeError("devices.list returned invalid JSON") from exc
    devices = body.get("devices", []) if isinstance(body, dict) else []
    if not devices:
        raise RuntimeError("devices.list returned no devices")
    return body


def obtain_persistent_access_token(gcp_project: str, device_access_project: str, client_id: str):
    ensure_secret_manager(gcp_project)
    client_secret = get_valid_client_secret(gcp_project, client_id)

    if secret_exists(gcp_project, REFRESH_TOKEN_ID):
        refresh_token = secret_access(gcp_project, REFRESH_TOKEN_ID)
        token, status, error = exchange_refresh(client_id, client_secret, refresh_token)
        if token is not None and token.get("access_token"):
            print("Nest OAuth: refreshed automatically from Secret Manager.")
            return token["access_token"]
        if error not in ("invalid_grant", "invalid_client"):
            raise RuntimeError(
                f"refresh-token exchange failed: HTTP {status}"
                + (f" ({error})" if error else "")
            )
        print("Stored Nest authorization is no longer usable; one fresh consent is required.")

    print("\nOne-time Nest authorization URL:\n")
    print(build_pcm_url(device_access_project, client_id))
    print(
        "\nApprove the existing home/doorbell. Then paste the entire redirected google.com URL "
        "into the hidden prompt below. Do not paste it into ChatGPT."
    )
    redirected = getpass.getpass("\nRedirected URL (hidden): ")
    code = extract_code(redirected)
    token = exchange_code(client_id, client_secret, code)
    access_token = token.get("access_token")
    refresh_token = token.get("refresh_token")
    if not access_token:
        raise RuntimeError("token exchange returned no access_token")
    if not refresh_token:
        raise RuntimeError("token exchange returned no refresh_token; persistent bootstrap not established")

    # Google documents devices.list as the call that completes Device Access authorization.
    verify_devices(device_access_project, access_token)
    secret_store(gcp_project, REFRESH_TOKEN_ID, refresh_token)
    print("Nest OAuth: authorization completed and refresh token stored in Secret Manager.")
    print("Future runs can skip client-secret entry and Nest consent while this authorization remains valid.")
    return access_token


def load_diagnostic(path: Path):
    spec = importlib.util.spec_from_file_location("nest_real_diagnostic", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load diagnostic module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def self_test():
    url = build_pcm_url("project-id", "client.apps.googleusercontent.com")
    assert "partnerconnections/project-id/auth" in url
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fsdm.service" in url
    assert extract_code("https://www.google.com/?code=abc123&scope=x") == "abc123"
    assert CLIENT_SECRET_ID != REFRESH_TOKEN_ID
    assert "secret" not in DEFAULT_CLIENT_ID.lower()
    print("PERSISTENT AUTH SELF-TEST PASS")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--diagnostic", type=Path)
    parser.add_argument("--base-dir", type=Path, default=Path.home() / ".doorbell-bridge")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if not args.diagnostic or not args.diagnostic.is_file():
        raise RuntimeError("--diagnostic must point to the audited nest_real_diagnostic.py")

    gcp_project = os.environ.get("GOOGLE_CLOUD_PROJECT", DEFAULT_GCP_PROJECT).strip() or DEFAULT_GCP_PROJECT
    device_access_project = os.environ.get(
        "NEST_DEVICE_ACCESS_PROJECT_ID", DEFAULT_DEVICE_ACCESS_PROJECT
    ).strip() or DEFAULT_DEVICE_ACCESS_PROJECT
    client_id = os.environ.get("NEST_CLIENT_ID", DEFAULT_CLIENT_ID).strip() or DEFAULT_CLIENT_ID

    access_token = obtain_persistent_access_token(gcp_project, device_access_project, client_id)

    diagnostic = load_diagnostic(args.diagnostic)
    # Keep the audited media diagnostic unchanged. Supply only a short-lived access token in memory.
    diagnostic.obtain_access_token = lambda: (device_access_project, access_token)
    return asyncio.run(diagnostic.live_run(args.base_dir))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nSTOPPED: interrupted", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"STOPPED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
