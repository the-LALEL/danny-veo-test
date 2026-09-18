#!/usr/bin/env python3
"""Capture one current-session frame from a Google Nest Doorbell via Device Access WebRTC.

This module intentionally stops at the capture boundary. It does not implement
ChatGPT delivery, artifact encryption, databases, queues, or persistent hosting.
Secrets are read from environment variables and are never written to output.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SDM_BASE = "https://smartdevicemanagement.googleapis.com/v1"
TOKEN_URL = "https://oauth2.googleapis.com/token"
GENERATE_COMMAND = "sdm.devices.commands.CameraLiveStream.GenerateWebRtcStream"
STOP_COMMAND = "sdm.devices.commands.CameraLiveStream.StopWebRtcStream"


class CaptureError(RuntimeError):
    def __init__(self, stage: str, code: str, message: str):
        super().__init__(message)
        self.stage = stage
        self.code = code
        self.message = message

    def as_dict(self) -> dict[str, str]:
        return {"stage": self.stage, "code": self.code, "message": self.message}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def resolve_request_id(raw: str | None = None) -> str:
    """Return a canonical UUID request ID or reject unsafe/un-correlatable input."""
    value = (raw if raw is not None else os.environ.get("DOORBELL_REQUEST_ID", "")).strip()
    if not value:
        return str(uuid.uuid4())
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError) as exc:
        raise CaptureError(
            "request_validation",
            "INVALID_REQUEST_ID",
            "DOORBELL_REQUEST_ID must be a UUID",
        ) from exc


def _secure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass


def _secure_file(path: Path) -> None:
    try:
        path.chmod(0o600)
    except OSError:
        pass


def media_order(sdp: str) -> list[str]:
    return [line[2:].split()[0] for line in sdp.splitlines() if line.startswith("m=")]


def media_sections(sdp: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in sdp.splitlines():
        if line.startswith("m="):
            current = line[2:].split()[0]
            sections[current] = [line]
        elif current:
            sections[current].append(line)
    return {name: "\n".join(lines) for name, lines in sections.items()}


def validate_nest_offer(sdp: str) -> dict[str, bool]:
    sections = media_sections(sdp)
    audio = sections.get("audio", "")
    video = sections.get("video", "")
    application = sections.get("application", "")
    bundle_lines = [line for line in sdp.splitlines() if line.startswith("a=group:BUNDLE ")]
    bundle_mids = bundle_lines[0].split()[1:] if len(bundle_lines) == 1 else []

    audio_rtpmap = [
        line for line in audio.splitlines() if line.lower().startswith("a=rtpmap:")
    ]
    audio_only_opus = bool(audio_rtpmap) and all(
        " opus/48000" in line.lower() for line in audio_rtpmap
    )

    return {
        "media_order_audio_video_application": media_order(sdp) == ["audio", "video", "application"],
        "audio_recvonly": bool(re.search(r"(?m)^a=recvonly$", audio)),
        "video_recvonly": bool(re.search(r"(?m)^a=recvonly$", video)),
        "audio_only_opus": audio_only_opus,
        "video_offers_h264": "H264/90000" in video.upper(),
        "h264_packetization_mode_1": "packetization-mode=1" in video,
        "h264_nest_compatible_baseline_profile": (
            "profile-level-id=42001f" in video.lower()
            or "profile-level-id=42e01f" in video.lower()
        ),
        "data_channel_present": "webrtc-datachannel" in application,
        "bundle_three_mids": len(bundle_mids) == 3,
        "offer_ends_with_newline": sdp.endswith("\r\n") or sdp.endswith("\n"),
    }


def normalize_nest_answer_sdp(answer_sdp: str) -> tuple[str, int, int]:
    """Normalize malformed blank-foundation ICE candidates observed from Nest."""
    normalized = 0
    dropped_non_udp = 0
    output: list[str] = []

    for raw in answer_sdp.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip("\r")
        if not line.startswith("a=candidate:"):
            output.append(line)
            continue

        suffix = line[len("a=candidate:") :]
        blank_foundation = bool(suffix[:1].isspace())
        tokens = suffix.strip().split()

        if blank_foundation:
            if len(tokens) < 6:
                raise CaptureError(
                    "webrtc_negotiation",
                    "MALFORMED_ICE_CANDIDATE",
                    "Nest answer contained an unparseable ICE candidate",
                )
            transport = tokens[1].lower()
            if transport != "udp":
                dropped_non_udp += 1
                continue
            normalized += 1
            output.append(f"a=candidate:nest{normalized} " + " ".join(tokens))
            continue

        if len(tokens) >= 3 and tokens[2].lower() != "udp":
            dropped_non_udp += 1
            continue

        output.append(line)

    fixed = "\r\n".join(output).rstrip("\r\n") + "\r\n"
    return fixed, normalized, dropped_non_udp


def _decode_json_body(raw: bytes) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _http_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    request_headers = dict(headers or {})
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return _decode_json_body(response.read())
    except urllib.error.HTTPError as exc:
        raise CaptureError("http", f"HTTP_{exc.code}", f"Remote API returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise CaptureError("http", "NETWORK_ERROR", f"Remote API request failed: {exc.reason}") from exc


def _oauth_token_request(form: dict[str, str], timeout: int = 20) -> tuple[int, dict[str, Any]]:
    data = urllib.parse.urlencode(form).encode("utf-8")
    request = urllib.request.Request(
        TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, _decode_json_body(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, _decode_json_body(exc.read())
    except urllib.error.URLError as exc:
        raise CaptureError(
            "authentication", "OAUTH_NETWORK_ERROR", f"OAuth request failed: {exc.reason}"
        ) from exc


def probe_oauth_client(client_id: str, client_secret: str) -> bool:
    """Check whether Google gets past client authentication to grant validation."""
    status, body = _oauth_token_request(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": "doorbell-client-probe-intentionally-invalid",
            "grant_type": "authorization_code",
            "redirect_uri": "https://www.google.com",
        }
    )
    error = body.get("error") if isinstance(body, dict) else None
    if error == "invalid_grant":
        return True
    if status == 401 or error == "invalid_client":
        return False
    raise CaptureError(
        "authentication",
        "OAUTH_CLIENT_PROBE_INDETERMINATE",
        f"OAuth client probe returned HTTP {status}" + (f" ({error})" if error else ""),
    )


def get_access_token() -> tuple[str, str]:
    access_token = os.environ.get("NEST_ACCESS_TOKEN", "").strip()
    if access_token:
        return access_token, "provided_access_token"

    refresh_token = os.environ.get("NEST_REFRESH_TOKEN", "").strip()
    client_id = os.environ.get("NEST_CLIENT_ID", "").strip()
    client_secret = os.environ.get("NEST_CLIENT_SECRET", "").strip()
    if not refresh_token or not client_id:
        raise CaptureError(
            "authentication",
            "MISSING_CREDENTIALS",
            "Set NEST_ACCESS_TOKEN or provide NEST_REFRESH_TOKEN and NEST_CLIENT_ID",
        )

    form = {
        "client_id": client_id,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    if client_secret:
        form["client_secret"] = client_secret

    status, result = _oauth_token_request(form)
    if status >= 400:
        error = result.get("error") if isinstance(result, dict) else None
        if status == 401 or error == "invalid_client":
            raise CaptureError(
                "authentication",
                "OAUTH_CLIENT_MISMATCH",
                "Google rejected the OAuth client identity used with the stored Nest authorization",
            )
        if error == "invalid_grant":
            raise CaptureError(
                "authentication",
                "OAUTH_REFRESH_REJECTED",
                "Google rejected the stored Nest refresh token for this OAuth client",
            )
        raise CaptureError(
            "authentication",
            "OAUTH_REFRESH_FAILED",
            f"OAuth refresh failed with HTTP {status}" + (f" ({error})" if error else ""),
        )

    token = result.get("access_token")
    if not isinstance(token, str) or not token:
        raise CaptureError(
            "authentication", "NO_ACCESS_TOKEN", "OAuth refresh returned no access token"
        )
    return token, "refresh_token"


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _device_access_project_id() -> str:
    preferred = os.environ.get("NEST_DEVICE_ACCESS_PROJECT_ID", "").strip()
    legacy = os.environ.get("NEST_ENTERPRISE_ID", "").strip()
    if preferred and legacy and preferred != legacy:
        raise CaptureError(
            "configuration",
            "CONFLICTING_PROJECT_IDS",
            "NEST_DEVICE_ACCESS_PROJECT_ID and NEST_ENTERPRISE_ID disagree",
        )
    return preferred or legacy


def resolve_device_name(access_token: str) -> tuple[str, str]:
    explicit = os.environ.get("NEST_DEVICE_NAME", "").strip()
    if explicit:
        if not re.fullmatch(r"enterprises/[^/]+/devices/[^/]+", explicit):
            raise CaptureError(
                "configuration", "BAD_DEVICE_NAME", "NEST_DEVICE_NAME has an invalid resource format"
            )
        return explicit, "configured"

    project_id = _device_access_project_id()
    if not project_id:
        raise CaptureError(
            "configuration",
            "MISSING_DEVICE_SELECTOR",
            "Set NEST_DEVICE_NAME or NEST_DEVICE_ACCESS_PROJECT_ID",
        )

    try:
        result = _http_json(
            f"{SDM_BASE}/enterprises/{urllib.parse.quote(project_id, safe='')}/devices",
            headers=auth_headers(access_token),
        )
    except CaptureError as exc:
        raise CaptureError("device_discovery", exc.code, "Nest device discovery failed") from exc

    candidates: list[str] = []
    for device in result.get("devices", []):
        if not isinstance(device, dict):
            continue
        traits = device.get("traits") or {}
        live_stream = traits.get("sdm.devices.traits.CameraLiveStream") or {}
        protocols = live_stream.get("supportedProtocols") or []
        device_type = str(device.get("type", ""))
        name = device.get("name")
        if device_type.endswith(".DOORBELL") and "WEB_RTC" in protocols and isinstance(name, str):
            candidates.append(name)

    if len(candidates) != 1:
        raise CaptureError(
            "device_discovery",
            "AMBIGUOUS_DOORBELL_SET",
            f"Expected exactly one WebRTC Nest Doorbell but found {len(candidates)}",
        )
    return candidates[0], "unique_webrtc_doorbell"


def execute_command(
    access_token: str, device_name: str, command: str, params: dict[str, Any]
) -> dict[str, Any]:
    try:
        return _http_json(
            f"{SDM_BASE}/{device_name}:executeCommand",
            method="POST",
            headers=auth_headers(access_token),
            payload={"command": command, "params": params},
        )
    except CaptureError as exc:
        raise CaptureError(
            "nest_api", exc.code, f"Nest command failed: {command.rsplit('.', 1)[-1]}"
        ) from exc


async def _wait_ice_complete(pc: Any, timeout: int = 20) -> None:
    if pc.iceGatheringState == "complete":
        return
    complete = asyncio.Event()

    @pc.on("icegatheringstatechange")
    def on_ice_state_change() -> None:
        if pc.iceGatheringState == "complete":
            complete.set()

    if pc.iceGatheringState == "complete":
        return
    try:
        await asyncio.wait_for(complete.wait(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise CaptureError(
            "webrtc_negotiation", "ICE_GATHER_TIMEOUT", "Local ICE gathering did not complete in time"
        ) from exc


async def capture_one_frame(output_dir: Path, request_id: str) -> dict[str, Any]:
    try:
        from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCRtpSender, RTCSessionDescription
    except ImportError as exc:
        raise CaptureError(
            "runtime", "MISSING_WEBRTC_DEPENDENCY", "Install requirements-doorbell.txt before capture"
        ) from exc

    request_started = utc_now()
    _secure_dir(output_dir)

    access_token, token_source = get_access_token()
    device_name, device_source = resolve_device_name(access_token)

    opus = [
        codec
        for codec in RTCRtpSender.getCapabilities("audio").codecs
        if codec.mimeType.lower() == "audio/opus"
    ]
    h264 = [
        codec
        for codec in RTCRtpSender.getCapabilities("video").codecs
        if codec.mimeType.lower() == "video/h264"
    ]
    if not opus:
        raise CaptureError("sdp_generation", "NO_OPUS", "Runtime exposes no Opus WebRTC capability")
    if not h264:
        raise CaptureError("sdp_generation", "NO_H264", "Runtime exposes no H264 WebRTC capability")

    pc = RTCPeerConnection(
        RTCConfiguration(iceServers=[RTCIceServer(urls=["stun:stun.l.google.com:19302"])])
    )
    media_session_id: str | None = None
    frame_future = asyncio.get_running_loop().create_future()
    connection_states: list[str] = []

    try:
        audio_transceiver = pc.addTransceiver("audio", direction="recvonly")
        video_transceiver = pc.addTransceiver("video", direction="recvonly")
        audio_transceiver.setCodecPreferences(opus)
        video_transceiver.setCodecPreferences(h264)
        pc.createDataChannel("nest-doorbell-capture")

        @pc.on("connectionstatechange")
        def on_connection_state_change() -> None:
            connection_states.append(pc.connectionState)

        @pc.on("track")
        def on_track(track: Any) -> None:
            if track.kind != "video" or frame_future.done():
                return

            async def receive_frame() -> None:
                try:
                    frame = await asyncio.wait_for(track.recv(), timeout=15)
                    if not frame_future.done():
                        frame_future.set_result((frame, utc_now()))
                except Exception as exc:
                    if not frame_future.done():
                        frame_future.set_exception(exc)

            asyncio.create_task(receive_frame())

        try:
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)
            await _wait_ice_complete(pc)
        except CaptureError:
            raise
        except Exception as exc:
            raise CaptureError("sdp_generation", "OFFER_FAILED", "Could not create the WebRTC offer") from exc

        offer_sdp = pc.localDescription.sdp
        contract = validate_nest_offer(offer_sdp)
        failed = [name for name, passed in contract.items() if not passed]
        if failed:
            raise CaptureError(
                "sdp_validation",
                "NEST_CONTRACT_FAILED",
                "Offer failed Nest checks: " + ", ".join(failed),
            )

        command_requested_at = utc_now()
        result = execute_command(
            access_token, device_name, GENERATE_COMMAND, {"offerSdp": offer_sdp}
        )
        command_completed_at = utc_now()

        results = result.get("results") or {}
        answer_sdp = results.get("answerSdp")
        media_session_id = results.get("mediaSessionId")
        stream_expires_at = results.get("expiresAt")
        if not isinstance(answer_sdp, str) or not answer_sdp:
            raise CaptureError(
                "nest_api", "NO_ANSWER_SDP", "GenerateWebRtcStream returned no answerSdp"
            )
        if not isinstance(media_session_id, str) or not media_session_id:
            raise CaptureError(
                "nest_api", "NO_MEDIA_SESSION_ID", "GenerateWebRtcStream returned no mediaSessionId"
            )

        fixed_answer, normalized_candidates, dropped_non_udp = normalize_nest_answer_sdp(answer_sdp)
        if (utc_now() - command_completed_at).total_seconds() >= 25:
            raise CaptureError(
                "webrtc_negotiation",
                "ANSWER_TOO_OLD",
                "Nest answerSdp was not applied promptly enough",
            )

        try:
            await pc.setRemoteDescription(RTCSessionDescription(sdp=fixed_answer, type="answer"))
            answer_applied_at = utc_now()
        except Exception as exc:
            raise CaptureError(
                "webrtc_negotiation",
                "REMOTE_DESCRIPTION_FAILED",
                "Nest answerSdp could not be applied",
            ) from exc

        try:
            frame, frame_received_at = await asyncio.wait_for(frame_future, timeout=20)
        except asyncio.TimeoutError as exc:
            raise CaptureError(
                "media_receive", "NO_VIDEO_FRAME", "No usable Nest video frame arrived in time"
            ) from exc
        except Exception as exc:
            raise CaptureError(
                "frame_decode", "FRAME_DECODE_FAILED", "A video track arrived but its frame could not be decoded"
            ) from exc

        if frame_received_at <= command_requested_at or frame_received_at <= request_started:
            raise CaptureError(
                "freshness",
                "FRAME_PREDATES_CAPTURE_REQUEST",
                "Decoded frame does not prove a post-request live-session observation",
            )

        image_path = output_dir / f"{request_id}.png"
        try:
            frame.to_image().save(image_path, format="PNG")
            _secure_file(image_path)
        except Exception as exc:
            image_path.unlink(missing_ok=True)
            raise CaptureError(
                "image_creation", "IMAGE_SAVE_FAILED", "Decoded video frame could not be saved as PNG"
            ) from exc

        image_bytes = image_path.read_bytes()
        completed_at = utc_now()
        return {
            "success": True,
            "request_id": request_id,
            "freshness": {
                "request_started_at": iso(request_started),
                "stream_command_requested_at": iso(command_requested_at),
                "stream_command_completed_at": iso(command_completed_at),
                "answer_applied_at": iso(answer_applied_at),
                "frame_received_at": iso(frame_received_at),
                "capture_completed_at": iso(completed_at),
                "fresh_live_session_observation": frame_received_at > command_requested_at,
                "camera_sensor_capture_time_proven": False,
            },
            "capture": {
                "image_path": str(image_path),
                "mime_type": "image/png",
                "width": frame.width,
                "height": frame.height,
                "sha256": hashlib.sha256(image_bytes).hexdigest(),
                "bytes": len(image_bytes),
            },
            "webrtc": {
                "connection_state": pc.connectionState,
                "connection_states": connection_states,
                "offer_contract": contract,
                "answer_candidates_normalized": normalized_candidates,
                "answer_non_udp_candidates_dropped": dropped_non_udp,
                "stream_expires_at": stream_expires_at,
            },
            "runtime": {
                "token_source": token_source,
                "device_source": device_source,
            },
        }
    finally:
        if media_session_id:
            try:
                execute_command(
                    access_token, device_name, STOP_COMMAND, {"mediaSessionId": media_session_id}
                )
            except Exception:
                pass
        await pc.close()


def _write_result(path: Path, result: dict[str, Any]) -> None:
    _secure_dir(path.parent)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(result, indent=2), encoding="utf-8")
    _secure_file(temp)
    temp.replace(path)
    _secure_file(path)


async def async_main(output_dir: Path) -> int:
    try:
        request_id = resolve_request_id()
    except CaptureError as exc:
        print(json.dumps({"success": False, "error": exc.as_dict()}), file=sys.stderr)
        return 2

    _secure_dir(output_dir)
    result_path = output_dir / f"{request_id}.json"
    image_path = output_dir / f"{request_id}.png"

    # A repeated request ID must never make an old image look like the result of
    # a new failed capture. Remove correlated remnants before attempting Nest.
    result_path.unlink(missing_ok=True)
    image_path.unlink(missing_ok=True)

    try:
        result = await capture_one_frame(output_dir, request_id)
        _write_result(result_path, result)
        print(
            json.dumps(
                {
                    "success": True,
                    "request_id": request_id,
                    "result_path": str(result_path),
                    "image_path": result["capture"]["image_path"],
                    "frame_received_at": result["freshness"]["frame_received_at"],
                    "sha256": result["capture"]["sha256"],
                }
            )
        )
        return 0
    except CaptureError as exc:
        image_path.unlink(missing_ok=True)
        failure = {
            "success": False,
            "request_id": request_id,
            "failed_at": iso(utc_now()),
            "error": exc.as_dict(),
        }
        _write_result(result_path, failure)
        print(json.dumps(failure), file=sys.stderr)
        return 2
    except Exception:
        image_path.unlink(missing_ok=True)
        failure = {
            "success": False,
            "request_id": request_id,
            "failed_at": iso(utc_now()),
            "error": {
                "stage": "internal",
                "code": "UNEXPECTED_ERROR",
                "message": "Unexpected capture failure; inspect private runtime logs",
            },
        }
        _write_result(result_path, failure)
        print(json.dumps(failure), file=sys.stderr)
        return 3


def main() -> int:
    # Camera pixels and result metadata are sensitive. Explicit chmod calls below
    # are the primary protection; the restrictive umask also covers temporary files.
    os.umask(0o077)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default=os.environ.get("DOORBELL_OUTPUT_DIR", "artifacts/real-capture"),
        help="Directory for the correlated PNG and JSON result",
    )
    parser.add_argument(
        "--probe-oauth-client",
        action="store_true",
        help="Check NEST_CLIENT_ID/NEST_CLIENT_SECRET without calling the Nest API",
    )
    args = parser.parse_args()

    if args.probe_oauth_client:
        client_id = os.environ.get("NEST_CLIENT_ID", "").strip()
        client_secret = os.environ.get("NEST_CLIENT_SECRET", "").strip()
        if not client_id or not client_secret:
            print(
                json.dumps(
                    {
                        "success": False,
                        "error": {
                            "stage": "authentication",
                            "code": "MISSING_OAUTH_CLIENT_PAIR",
                            "message": "Set NEST_CLIENT_ID and NEST_CLIENT_SECRET for the probe",
                        },
                    }
                ),
                file=sys.stderr,
            )
            return 2
        try:
            valid = probe_oauth_client(client_id, client_secret)
        except CaptureError as exc:
            print(json.dumps({"success": False, "error": exc.as_dict()}), file=sys.stderr)
            return 2
        print(
            json.dumps(
                {
                    "success": valid,
                    "oauth_client_pair_valid": valid,
                    "error_code": None if valid else "OAUTH_CLIENT_MISMATCH",
                }
            )
        )
        return 0 if valid else 2

    return asyncio.run(async_main(Path(args.output_dir)))


if __name__ == "__main__":
    raise SystemExit(main())
