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

from aiortc import (
    RTCConfiguration,
    RTCIceServer,
    RTCPeerConnection,
    RTCRtpSender,
    RTCSessionDescription,
)

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

    def as_dict(self):
        return {"stage": self.stage, "code": self.code, "message": self.message}


def utc_now():
    return datetime.now(timezone.utc)


def iso(dt: datetime):
    return dt.isoformat().replace("+00:00", "Z")


def media_order(sdp: str):
    return [line[2:].split()[0] for line in sdp.splitlines() if line.startswith("m=")]


def media_sections(sdp: str):
    sections = {}
    current = None
    for line in sdp.splitlines():
        if line.startswith("m="):
            current = line[2:].split()[0]
            sections[current] = [line]
        elif current:
            sections[current].append(line)
    return {name: "\n".join(lines) for name, lines in sections.items()}


def validate_nest_offer(sdp: str):
    sections = media_sections(sdp)
    audio = sections.get("audio", "")
    video = sections.get("video", "")
    application = sections.get("application", "")
    bundle_lines = [line for line in sdp.splitlines() if line.startswith("a=group:BUNDLE ")]
    bundle_mids = bundle_lines[0].split()[1:] if len(bundle_lines) == 1 else []
    return {
        "media_order_audio_video_application": media_order(sdp) == ["audio", "video", "application"],
        "audio_recvonly": bool(re.search(r"(?m)^a=recvonly$", audio)),
        "video_recvonly": bool(re.search(r"(?m)^a=recvonly$", video)),
        "audio_offers_opus": bool(re.search(r"(?im)^a=rtpmap:\d+\s+opus/48000(?:/2)?$", audio)),
        "video_offers_h264": "H264/90000" in video.upper(),
        "h264_packetization_mode_1": "packetization-mode=1" in video,
        "h264_nest_compatible_baseline_profile": (
            "profile-level-id=42001f" in video or "profile-level-id=42e01f" in video
        ),
        "data_channel_present": "webrtc-datachannel" in application,
        "bundle_three_mids": len(bundle_mids) == 3,
        "offer_ends_with_newline": sdp.endswith("\r\n") or sdp.endswith("\n"),
    }


def _safe_http_json(url, method="GET", headers=None, payload=None, form=None, timeout=20):
    request_headers = dict(headers or {})
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    elif form is not None:
        data = urllib.parse.urlencode(form).encode("utf-8")
        request_headers["Content-Type"] = "application/x-www-form-urlencoded"

    req = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as exc:
        # Never echo the response body: OAuth / SDM error payloads can contain
        # identifiers or other details we do not need in normal diagnostics.
        raise CaptureError("http", f"HTTP_{exc.code}", f"Remote API returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise CaptureError("http", "NETWORK_ERROR", f"Remote API request failed: {exc.reason}") from exc


def get_access_token():
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
            "No access token was provided and refresh-token credentials are incomplete",
        )

    form = {
        "client_id": client_id,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    if client_secret:
        form["client_secret"] = client_secret

    try:
        result = _safe_http_json(TOKEN_URL, method="POST", form=form)
    except CaptureError as exc:
        raise CaptureError("authentication", exc.code, "OAuth access-token refresh failed") from exc

    token = result.get("access_token")
    if not token:
        raise CaptureError("authentication", "NO_ACCESS_TOKEN", "OAuth refresh returned no access token")
    return token, "refresh_token"


def auth_headers(access_token: str):
    return {"Authorization": f"Bearer {access_token}"}


def resolve_device_name(access_token: str):
    explicit = os.environ.get("NEST_DEVICE_NAME", "").strip()
    if explicit:
        if not re.fullmatch(r"enterprises/[^/]+/devices/[^/]+", explicit):
            raise CaptureError("configuration", "BAD_DEVICE_NAME", "NEST_DEVICE_NAME has an invalid resource format")
        return explicit, "configured"

    enterprise_id = os.environ.get("NEST_ENTERPRISE_ID", "").strip()
    if not enterprise_id:
        raise CaptureError(
            "configuration",
            "MISSING_DEVICE_SELECTOR",
            "Set NEST_DEVICE_NAME or NEST_ENTERPRISE_ID in the runtime secret/configuration store",
        )

    try:
        result = _safe_http_json(
            f"{SDM_BASE}/enterprises/{urllib.parse.quote(enterprise_id, safe='')}/devices",
            headers=auth_headers(access_token),
        )
    except CaptureError as exc:
        raise CaptureError("device_discovery", exc.code, "Nest device discovery failed") from exc

    candidates = []
    for device in result.get("devices", []):
        traits = device.get("traits") or {}
        live_stream = traits.get("sdm.devices.traits.CameraLiveStream") or {}
        protocols = live_stream.get("supportedProtocols") or []
        if "WEB_RTC" in protocols:
            candidates.append(device.get("name"))

    candidates = [name for name in candidates if name]
    if len(candidates) != 1:
        raise CaptureError(
            "device_discovery",
            "AMBIGUOUS_DEVICE_SET",
            f"Expected exactly one WebRTC camera/doorbell but found {len(candidates)}",
        )
    return candidates[0], "unique_webrtc_device"


def execute_command(access_token: str, device_name: str, command: str, params: dict):
    url = f"{SDM_BASE}/{device_name}:executeCommand"
    try:
        return _safe_http_json(
            url,
            method="POST",
            headers=auth_headers(access_token),
            payload={"command": command, "params": params},
        )
    except CaptureError as exc:
        raise CaptureError("nest_api", exc.code, f"Nest command failed: {command.rsplit('.', 1)[-1]}") from exc


async def capture_one_frame(output_dir: Path, request_id: str):
    request_started = utc_now()
    output_dir.mkdir(parents=True, exist_ok=True)

    access_token, token_source = get_access_token()
    device_name, device_source = resolve_device_name(access_token)

    h264 = [
        codec
        for codec in RTCRtpSender.getCapabilities("video").codecs
        if codec.mimeType.lower() == "video/h264"
    ]
    if not h264:
        raise CaptureError("sdp_generation", "NO_H264", "Runtime exposes no H264 WebRTC capability")

    pc = RTCPeerConnection(
        RTCConfiguration(iceServers=[RTCIceServer(urls=["stun:stun.l.google.com:19302"])])
    )
    media_session_id = None
    frame_future = asyncio.get_running_loop().create_future()
    data_open_future = asyncio.get_running_loop().create_future()

    try:
        pc.addTransceiver("audio", direction="recvonly")
        video_transceiver = pc.addTransceiver("video", direction="recvonly")
        video_transceiver.setCodecPreferences(h264)
        data_channel = pc.createDataChannel("nest-doorbell-capture")

        @data_channel.on("open")
        def on_data_open():
            if not data_open_future.done():
                data_open_future.set_result(iso(utc_now()))

        @pc.on("track")
        def on_track(track):
            if track.kind != "video":
                return

            async def receive_frame():
                try:
                    frame = await asyncio.wait_for(track.recv(), timeout=15)
                    received_at = utc_now()
                    image_path = output_dir / f"{request_id}.png"
                    frame.to_image().save(image_path, format="PNG")
                    if not frame_future.done():
                        frame_future.set_result((frame, image_path, received_at))
                except Exception as exc:
                    if not frame_future.done():
                        frame_future.set_exception(exc)

            asyncio.create_task(receive_frame())

        try:
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)
        except Exception as exc:
            raise CaptureError("sdp_generation", "OFFER_FAILED", "Could not create the WebRTC offer") from exc

        offer_sdp = pc.localDescription.sdp
        contract = validate_nest_offer(offer_sdp)
        failed = [name for name, passed in contract.items() if not passed]
        if failed:
            raise CaptureError("sdp_validation", "NEST_CONTRACT_FAILED", f"Offer failed checks: {', '.join(failed)}")

        command_requested_at = utc_now()
        result = execute_command(
            access_token,
            device_name,
            GENERATE_COMMAND,
            {"offerSdp": offer_sdp},
        )
        command_completed_at = utc_now()

        results = result.get("results") or {}
        answer_sdp = results.get("answerSdp")
        media_session_id = results.get("mediaSessionId")
        stream_expires_at = results.get("expiresAt")
        if not answer_sdp:
            raise CaptureError("nest_api", "NO_ANSWER_SDP", "GenerateWebRtcStream returned no answerSdp")

        answer_age = (utc_now() - command_completed_at).total_seconds()
        if answer_age >= 25:
            raise CaptureError("webrtc_negotiation", "ANSWER_TOO_OLD", "Nest answerSdp was not applied promptly enough")

        try:
            await pc.setRemoteDescription(RTCSessionDescription(sdp=answer_sdp, type="answer"))
            answer_applied_at = utc_now()
        except Exception as exc:
            raise CaptureError("webrtc_negotiation", "REMOTE_DESCRIPTION_FAILED", "Nest answerSdp could not be applied") from exc

        try:
            frame, image_path, frame_received_at = await asyncio.wait_for(frame_future, timeout=20)
        except asyncio.TimeoutError as exc:
            raise CaptureError("media_receive", "NO_VIDEO_FRAME", "WebRTC connected but no usable video frame arrived in time") from exc
        except Exception as exc:
            raise CaptureError("frame_decode", "FRAME_DECODE_FAILED", "A video track arrived but a frame could not be decoded") from exc

        if frame_received_at <= request_started:
            raise CaptureError("freshness", "FRAME_PREDATES_REQUEST", "Decoded frame does not prove post-request freshness")

        data_channel_opened_at = None
        try:
            data_channel_opened_at = await asyncio.wait_for(data_open_future, timeout=2)
        except asyncio.TimeoutError:
            # Google requires a data channel to be created. The image capture is
            # still useful if the channel never transitions to open before the first frame.
            pass

        image_bytes = image_path.read_bytes()
        completed_at = utc_now()
        metadata = {
            "success": True,
            "request_id": request_id,
            "freshness": {
                "request_started_at": iso(request_started),
                "stream_command_requested_at": iso(command_requested_at),
                "stream_command_completed_at": iso(command_completed_at),
                "answer_applied_at": iso(answer_applied_at),
                "frame_received_at": iso(frame_received_at),
                "capture_completed_at": iso(completed_at),
                "frame_after_request": frame_received_at > request_started,
            },
            "capture": {
                "image_path": str(image_path),
                "mime_type": "image/png",
                "width": frame.width,
                "height": frame.height,
                "pixel_format": frame.format.name,
                "sha256": hashlib.sha256(image_bytes).hexdigest(),
                "bytes": len(image_bytes),
            },
            "webrtc": {
                "connection_state": pc.connectionState,
                "data_channel_opened_at": data_channel_opened_at,
                "offer_contract": contract,
                "offer_sdp_sha256": hashlib.sha256(offer_sdp.encode("utf-8")).hexdigest(),
                "stream_expires_at": stream_expires_at,
            },
            "runtime": {
                "token_source": token_source,
                "device_source": device_source,
            },
        }
        return metadata
    finally:
        if media_session_id:
            try:
                execute_command(access_token, device_name, STOP_COMMAND, {"mediaSessionId": media_session_id})
            except Exception:
                # Cleanup failure must not convert an otherwise fresh captured frame into failure.
                pass
        await pc.close()


async def async_main():
    request_id = os.environ.get("DOORBELL_REQUEST_ID", "").strip() or str(uuid.uuid4())
    output_dir = Path(os.environ.get("DOORBELL_OUTPUT_DIR", "artifacts/real-capture"))
    result_path = output_dir / f"{request_id}.json"

    try:
        result = await capture_one_frame(output_dir, request_id)
        result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps({
            "success": True,
            "request_id": request_id,
            "result_path": str(result_path),
            "image_path": result["capture"]["image_path"],
            "frame_received_at": result["freshness"]["frame_received_at"],
            "sha256": result["capture"]["sha256"],
        }))
        return 0
    except CaptureError as exc:
        output_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "success": False,
            "request_id": request_id,
            "failed_at": iso(utc_now()),
            "error": exc.as_dict(),
        }
        result_path.write_text(json.dumps(failure, indent=2), encoding="utf-8")
        print(json.dumps(failure), file=sys.stderr)
        return 2
    except Exception:
        output_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "success": False,
            "request_id": request_id,
            "failed_at": iso(utc_now()),
            "error": {
                "stage": "internal",
                "code": "UNEXPECTED_ERROR",
                "message": "Unexpected capture failure; inspect private runtime logs for the exception type",
            },
        }
        result_path.write_text(json.dumps(failure, indent=2), encoding="utf-8")
        print(json.dumps(failure), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
