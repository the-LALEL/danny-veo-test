#!/usr/bin/env python3
import argparse
import asyncio
import getpass
import json
import logging
import os
import re
import sys
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import requests
from aioice import Connection
from aiortc import RTCPeerConnection, RTCRtpReceiver, RTCRtpSender, RTCSessionDescription
from aiortc.codecs.h264 import H264Decoder
from aiortc.jitterbuffer import JitterBuffer
from aiortc.rtcdtlstransport import RtpRouter

SDM_ROOT = "https://smartdevicemanagement.googleapis.com/v1"
TOKEN_URL = "https://www.googleapis.com/oauth2/v4/token"
PCM_BASE = "https://nestservices.google.com/partnerconnections"
GOOGLE_REDIRECT = "https://www.google.com"

GENERATE = "sdm.devices.commands.CameraLiveStream.GenerateWebRtcStream"
STOP = "sdm.devices.commands.CameraLiveStream.StopWebRtcStream"

def utc_now():
    return datetime.now(timezone.utc)

def iso(dt):
    return dt.isoformat().replace("+00:00", "Z")

def safe_json_write(path: Path, obj):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    os.chmod(path, 0o600)

def media_order(sdp: str):
    return [ln[2:].split()[0] for ln in sdp.splitlines() if ln.startswith("m=")]

def normalize_nest_answer_sdp(answer_sdp: str):
    """
    Repair the malformed blank-foundation ICE candidates observed in the
    previously working Nest session. Drop non-UDP candidates only when needed
    to preserve the previously verified behavior.
    """
    normalized = 0
    dropped_non_udp = 0
    out = []
    for raw in answer_sdp.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip("\r")
        if not line.startswith("a=candidate:"):
            out.append(line)
            continue

        suffix = line[len("a=candidate:"):]
        blank_foundation = bool(suffix[:1].isspace())
        tokens = suffix.strip().split()

        if blank_foundation:
            if len(tokens) < 6:
                raise RuntimeError("unparseable blank-foundation ICE candidate")
            transport = tokens[1].lower()
            if transport != "udp":
                dropped_non_udp += 1
                continue
            normalized += 1
            out.append(f"a=candidate:nest{normalized} " + " ".join(tokens))
            continue

        if len(tokens) >= 3 and tokens[2].lower() != "udp":
            dropped_non_udp += 1
            continue

        out.append(line)

    return "\r\n".join(out).rstrip("\r\n") + "\r\n", normalized, dropped_non_udp

def build_pcm_url(project_id: str, client_id: str):
    return (
        f"{PCM_BASE}/{quote(project_id, safe='')}/auth"
        f"?redirect_uri={quote(GOOGLE_REDIRECT, safe='')}"
        "&access_type=offline"
        "&prompt=consent"
        f"&client_id={quote(client_id, safe='')}"
        "&response_type=code"
        f"&scope={quote('https://www.googleapis.com/auth/sdm.service', safe='')}"
    )

def extract_code(value: str):
    value = value.strip()
    if not value:
        raise ValueError("empty authorization response")
    if value.startswith("http://") or value.startswith("https://"):
        code = parse_qs(urlparse(value).query).get("code", [None])[0]
        if not code:
            raise ValueError("redirect URL has no code parameter")
        return code
    return value

def http_json(method, url, *, headers=None, json_body=None, form=None, timeout=20):
    try:
        resp = requests.request(
            method,
            url,
            headers=headers,
            json=json_body,
            data=form,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"network error: {type(exc).__name__}") from exc
    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status_code}")
    try:
        return resp.json() if resp.content else {}
    except ValueError as exc:
        raise RuntimeError("remote API returned invalid JSON") from exc

def obtain_access_token():
    project_id = os.environ.get("NEST_DEVICE_ACCESS_PROJECT_ID", "").strip()
    client_id = os.environ.get("NEST_CLIENT_ID", "").strip()
    client_secret = os.environ.get("NEST_CLIENT_SECRET", "").strip()

    if not project_id:
        project_id = input("Existing Device Access Project ID (UUID): ").strip()
    if not client_id:
        client_id = input("Existing OAuth client ID: ").strip()
    if not client_secret:
        client_secret = getpass.getpass("Existing OAuth client secret (hidden): ").strip()

    if not (project_id and client_id and client_secret):
        raise RuntimeError("missing Device Access project ID or OAuth client credentials")

    url = build_pcm_url(project_id, client_id)
    print("\nOpen this authorization URL in your normal browser:\n")
    print(url)
    print(
        "\nApprove the same home/doorbell, then copy the entire redirected "
        "google.com URL. Paste it into the hidden prompt below. Do not paste it into ChatGPT."
    )
    redirected = getpass.getpass("\nRedirected URL (hidden): ")
    code = extract_code(redirected)

    token = http_json(
        "POST",
        TOKEN_URL,
        form={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": GOOGLE_REDIRECT,
        },
    )
    access_token = token.get("access_token")
    if not access_token:
        raise RuntimeError("token exchange returned no access_token")
    # Intentionally do not persist client_secret, authorization code, access token,
    # or refresh token. This is a one-shot diagnostic.
    return project_id, access_token

def discover_doorbell(project_id: str, access_token: str):
    doc = http_json(
        "GET",
        f"{SDM_ROOT}/enterprises/{project_id}/devices",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    matches = []
    for device in doc.get("devices", []):
        if not isinstance(device, dict):
            continue
        traits = device.get("traits", {}) or {}
        live = traits.get("sdm.devices.traits.CameraLiveStream", {}) or {}
        protocols = live.get("supportedProtocols", []) or []
        if str(device.get("type", "")).endswith(".DOORBELL") and "WEB_RTC" in protocols:
            matches.append((device, live))
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one WEB_RTC doorbell, found {len(matches)}")
    device, live = matches[0]
    name = device.get("name")
    if not isinstance(name, str) or not name:
        raise RuntimeError("selected doorbell has no device resource name")
    print("Device discovery: exactly one WEB_RTC doorbell.")
    print("  protocols:", live.get("supportedProtocols"))
    print("  videoCodecs:", live.get("videoCodecs"))
    print("  audioCodecs:", live.get("audioCodecs"))
    return name

def execute_command(device_name, access_token, command, params):
    return http_json(
        "POST",
        f"{SDM_ROOT}/{device_name}:executeCommand",
        headers={"Authorization": f"Bearer {access_token}"},
        json_body={"command": command, "params": params},
    )

class LogCounter(logging.Handler):
    def __init__(self, counts):
        super().__init__(level=logging.DEBUG)
        self.counts = counts

    def emit(self, record):
        msg = record.getMessage()
        if "SRTP unprotect failed" in msg:
            self.counts["srtp_unprotect_failures"] += 1
        elif "RTP parsing failed" in msg:
            self.counts["rtp_parse_failures"] += 1
        elif "RTP payload parsing failed" in msg:
            self.counts["payload_parse_failures"] += 1
        elif record.name == "aiortc.codecs.h264" and "failed to decode" in msg:
            self.counts["h264_decode_warnings"] += 1

class Instrumentation:
    def __init__(self):
        self.counts = Counter()
        self.wire = Counter()
        self.routed = Counter()
        self.dropped = Counter()
        self.receiver = Counter()
        self.connection_states = []
        self._patches = []
        self._logger_state = []

    def install(self):
        counts = self.counts
        wire = self.wire
        routed = self.routed
        dropped = self.dropped
        receiver = self.receiver

        old_recvfrom = Connection.recvfrom
        async def observe_recvfrom(obj):
            data, component = await old_recvfrom(obj)
            # RTP/SRTP v2 header is visible before decryption; exclude RTCP PT range.
            if len(data) >= 12 and data[0] >> 6 == 2 and not 192 <= data[1] <= 223:
                wire[(int.from_bytes(data[8:12], "big"), data[1] & 127)] += 1
            return data, component
        Connection.recvfrom = observe_recvfrom
        self._patches.append((Connection, "recvfrom", old_recvfrom))

        old_route = RtpRouter.route_rtp
        def observe_route(obj, packet):
            target = old_route(obj, packet)
            key = (packet.ssrc, packet.payload_type)
            (routed if target is not None else dropped)[key] += 1
            return target
        RtpRouter.route_rtp = observe_route
        self._patches.append((RtpRouter, "route_rtp", old_route))

        old_handle = RTCRtpReceiver._handle_rtp_packet
        async def observe_handle(obj, packet, arrival_time_ms):
            kind = getattr(getattr(obj, "_track", None), "kind", "unknown")
            receiver[(kind, packet.ssrc, packet.payload_type)] += 1
            return await old_handle(obj, packet, arrival_time_ms)
        RTCRtpReceiver._handle_rtp_packet = observe_handle
        self._patches.append((RTCRtpReceiver, "_handle_rtp_packet", old_handle))

        old_add = JitterBuffer.add
        def observe_add(obj, packet):
            pli_flag, encoded_frame = old_add(obj, packet)
            if getattr(obj, "_is_video", False):
                counts["video_jitter_packets"] += 1
                if pli_flag:
                    counts["video_jitter_pli_flags"] += 1
                if encoded_frame is not None:
                    counts["video_encoded_frames"] += 1
            return pli_flag, encoded_frame
        JitterBuffer.add = observe_add
        self._patches.append((JitterBuffer, "add", old_add))

        old_decode = H264Decoder.decode
        def observe_decode(obj, encoded_frame):
            counts["h264_decode_calls"] += 1
            frames = old_decode(obj, encoded_frame)
            counts["h264_decoded_frames"] += len(frames)
            return frames
        H264Decoder.decode = observe_decode
        self._patches.append((H264Decoder, "decode", old_decode))

        handler = LogCounter(counts)
        for name, level in (
            ("aiortc.rtcdtlstransport", logging.DEBUG),
            ("aiortc.rtcrtpreceiver", logging.DEBUG),
            ("aiortc.codecs.h264", logging.WARNING),
        ):
            logger = logging.getLogger(name)
            self._logger_state.append((logger, logger.level, logger.propagate, handler))
            logger.setLevel(level)
            logger.propagate = False
            logger.addHandler(handler)

    def restore(self):
        for cls, name, original in reversed(self._patches):
            setattr(cls, name, original)
        self._patches.clear()
        for logger, old_level, old_propagate, handler in reversed(self._logger_state):
            logger.removeHandler(handler)
            logger.setLevel(old_level)
            logger.propagate = old_propagate
        self._logger_state.clear()

    def report(self):
        return {
            "wire_rtp_like": {str(k): v for k, v in self.wire.items()},
            "routed_rtp": {str(k): v for k, v in self.routed.items()},
            "router_dropped_rtp": {str(k): v for k, v in self.dropped.items()},
            "receiver_rtp": {str(k): v for k, v in self.receiver.items()},
            "counts": dict(self.counts),
            "connection_states": self.connection_states,
        }

def classify_failure(inst: Instrumentation, got_video_track: bool):
    c = inst.counts
    if not inst.wire:
        return "NO_RTP_AT_ICE_BOUNDARY"
    if c["srtp_unprotect_failures"] > 0 and not inst.routed and not inst.dropped:
        return "SRTP_UNPROTECT_FAILURE"
    if c["rtp_parse_failures"] > 0 and not inst.routed and not inst.dropped:
        return "RTP_PARSE_FAILURE"
    if inst.dropped and not inst.routed:
        return "RTP_ROUTER_MAPPING_FAILURE"
    video_receiver_packets = sum(v for (kind, _ssrc, _pt), v in inst.receiver.items() if kind == "video")
    if video_receiver_packets and c["payload_parse_failures"] > 0 and c["video_encoded_frames"] == 0:
        return "H264_DEPAYLOAD_FAILURE"
    if video_receiver_packets and c["video_encoded_frames"] == 0:
        return "VIDEO_FRAME_ASSEMBLY_OR_KEYFRAME_FAILURE"
    if c["video_encoded_frames"] > 0 and c["h264_decode_calls"] == 0:
        return "DECODER_QUEUE_OR_THREAD_FAILURE"
    if c["h264_decode_calls"] > 0 and c["h264_decoded_frames"] == 0:
        return "H264_DECODE_FAILURE"
    if not got_video_track:
        return "NO_VIDEO_TRACK"
    return "INDETERMINATE_MEDIA_FAILURE"

async def wait_ice_complete(pc, timeout=20):
    if pc.iceGatheringState == "complete":
        return
    event = asyncio.Event()
    @pc.on("icegatheringstatechange")
    def state():
        if pc.iceGatheringState == "complete":
            event.set()
    if pc.iceGatheringState == "complete":
        return
    await asyncio.wait_for(event.wait(), timeout=timeout)

def create_run_dir(base_dir: Path, request_id: str):
    run_dir = base_dir / "runs" / request_id
    run_dir.mkdir(parents=True, exist_ok=False)
    os.chmod(run_dir, 0o700)
    return run_dir

async def live_run(base_dir: Path):
    os.umask(0o077)
    request_id = str(uuid.uuid4())
    requested_at = utc_now()
    run_dir = create_run_dir(base_dir, request_id)
    image_path = run_dir / "doorbell.jpg"
    report_path = run_dir / "diagnostic.json"

    project_id, access_token = obtain_access_token()
    device_name = discover_doorbell(project_id, access_token)

    inst = Instrumentation()
    inst.install()

    pc = RTCPeerConnection()
    session_id = None
    video_queue = asyncio.Queue()
    got_video_track = False
    frame = None
    frame_received_at = None
    generate_requested_at = None
    answer_applied_at = None

    @pc.on("connectionstatechange")
    async def connection_state():
        inst.connection_states.append(pc.connectionState)
        print("CONNECTION:", pc.connectionState)

    @pc.on("track")
    def on_track(track):
        nonlocal got_video_track
        print("TRACK:", track.kind)
        if track.kind == "video":
            got_video_track = True
            video_queue.put_nowait(track)

    audio = pc.addTransceiver("audio", direction="recvonly")
    video = pc.addTransceiver("video", direction="recvonly")
    pc.createDataChannel("nest-doorbell-diagnostic")

    opus = [
        codec for codec in RTCRtpSender.getCapabilities("audio").codecs
        if codec.mimeType.lower() == "audio/opus"
    ]
    h264 = [
        codec for codec in RTCRtpSender.getCapabilities("video").codecs
        if codec.mimeType.lower() == "video/h264"
    ]
    if not opus or not h264:
        inst.restore()
        raise RuntimeError(f"local codec gap: opus={bool(opus)} h264={bool(h264)}")

    audio.setCodecPreferences(opus)
    video.setCodecPreferences(h264)

    status = 2
    failure_code = None
    stop_ok = None
    try:
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        await wait_ice_complete(pc, timeout=20)
        offer_sdp = pc.localDescription.sdp

        order = media_order(offer_sdp)
        if order != ["audio", "video", "application"]:
            raise RuntimeError(f"Nest offer media order invalid: {order}")
        if "a=recvonly" not in offer_sdp:
            raise RuntimeError("Nest offer missing recvonly")
        if "opus/48000" not in offer_sdp.lower():
            raise RuntimeError("Nest offer missing Opus")
        if "H264/90000" not in offer_sdp.upper():
            raise RuntimeError("Nest offer missing H264")
        if not offer_sdp.endswith(("\r\n", "\n")):
            raise RuntimeError("Nest offer missing final newline")

        generate_requested_at = utc_now()
        t0 = time.monotonic()
        response = execute_command(device_name, access_token, GENERATE, {"offerSdp": offer_sdp})
        results = response.get("results", {}) or {}
        answer = results.get("answerSdp")
        session_id = results.get("mediaSessionId")
        if not answer or not session_id:
            raise RuntimeError("GenerateWebRtcStream response missing answerSdp/mediaSessionId")

        fixed, normalized, dropped_non_udp = normalize_nest_answer_sdp(answer)
        print(f"NEST SDP FIXED: normalized={normalized}, dropped_non_udp={dropped_non_udp}")

        if time.monotonic() - t0 >= 25:
            raise RuntimeError("Nest answer too old before application")

        await pc.setRemoteDescription(RTCSessionDescription(sdp=fixed, type="answer"))
        answer_applied_at = utc_now()
        print("REMOTE SDP ACCEPTED")

        try:
            track = await asyncio.wait_for(video_queue.get(), timeout=10)
        except asyncio.TimeoutError:
            track = None

        if track is not None:
            try:
                frame = await asyncio.wait_for(track.recv(), timeout=15)
                frame_received_at = utc_now()
            except asyncio.TimeoutError:
                frame = None

        if frame is not None:
            image = frame.to_image()
            image.save(image_path, format="JPEG", quality=92)
            os.chmod(image_path, 0o600)
            status = 0
            print(f"CAPTURE OK: request_id={request_id} {image.width}x{image.height}")
        else:
            failure_code = classify_failure(inst, got_video_track)
            print("CAPTURE FAILED:", failure_code)

    finally:
        if session_id:
            try:
                execute_command(device_name, access_token, STOP, {"mediaSessionId": session_id})
                stop_ok = True
                print("STREAM STOPPED")
            except Exception:
                stop_ok = False
                print("STREAM STOP FAILED")
        await pc.close()
        inst.restore()

        report = {
            "request_id": request_id,
            "requested_at": iso(requested_at),
            "generate_requested_at": iso(generate_requested_at) if generate_requested_at else None,
            "answer_applied_at": iso(answer_applied_at) if answer_applied_at else None,
            "frame_received_at": iso(frame_received_at) if frame_received_at else None,
            "fresh_live_session_observation": bool(
                frame_received_at and generate_requested_at and frame_received_at >= generate_requested_at
            ),
            "camera_sensor_capture_time_proven": False,
            "success": status == 0,
            "failure_code": failure_code,
            "stop_webrtc_stream_ok": stop_ok,
            "image_path": str(image_path) if status == 0 and image_path.is_file() else None,
            "instrumentation": inst.report(),
        }
        safe_json_write(report_path, report)

    print("DIAGNOSTIC REPORT:", report_path)
    if status == 0:
        print("REAL FRAME FILE:", image_path)
    return status

def self_test():
    fixed, n, d = normalize_nest_answer_sdp(
        "v=0\r\n"
        "m=video 9 UDP/TLS/RTP/SAVPF 102\r\n"
        "a=candidate: 1 udp 2122260223 10.0.0.2 50000 typ host\r\n"
        "a=candidate: 1 tcp 1518280447 10.0.0.2 9 typ host tcptype active\r\n"
    )
    assert n == 1 and d == 1
    assert "a=candidate:nest1 1 udp " in fixed
    assert " tcp " not in fixed.lower()
    assert fixed.endswith("\r\n")
    url = build_pcm_url("proj", "client.apps.googleusercontent.com")
    assert "partnerconnections/proj/auth" in url
    assert "access_type=offline" in url
    assert extract_code("https://www.google.com/?code=abc123&scope=x") == "abc123"

    # Validate exact private observation points expected from aiortc 1.14.0.
    import aiortc
    assert aiortc.__version__ == "1.14.0", aiortc.__version__
    assert callable(Connection.recvfrom)
    assert callable(RtpRouter.route_rtp)
    assert callable(RTCRtpReceiver._handle_rtp_packet)
    assert callable(JitterBuffer.add)
    assert callable(H264Decoder.decode)

    # Failure classifier smoke checks.
    x = Instrumentation()
    assert classify_failure(x, False) == "NO_RTP_AT_ICE_BOUNDARY"
    x.wire[(1, 102)] = 3
    x.dropped[(1, 102)] = 3
    assert classify_failure(x, True) == "RTP_ROUTER_MAPPING_FAILURE"
    print("SELF-TEST PASS")
    return 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument(
        "--base-dir",
        default=str(Path.home() / ".doorbell-bridge"),
    )
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    try:
        return asyncio.run(live_run(Path(args.base_dir)))
    except (KeyboardInterrupt, EOFError):
        print("STOPPED: user interrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        # Do not print response bodies, tokens, client secrets, or auth codes.
        print(f"STOPPED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3

if __name__ == "__main__":
    raise SystemExit(main())
