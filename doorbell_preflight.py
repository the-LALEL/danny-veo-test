import asyncio
import hashlib
import json
import os
import re
from fractions import Fraction

import numpy as np
from aiortc import AudioStreamTrack, MediaStreamTrack, RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCRtpSender
from av import VideoFrame


class SyntheticVideoTrack(MediaStreamTrack):
    kind = "video"

    def __init__(self):
        super().__init__()
        self._timestamp = 0

    async def recv(self):
        await asyncio.sleep(1 / 30)
        self._timestamp += 3000
        image = np.zeros((240, 320, 3), dtype=np.uint8)
        image[:, :, 0] = 36
        image[:, :, 1] = 120
        image[:, :, 2] = 220
        image[35:205, 70:250] = [220, 70, 30]
        image[75:165, 110:210] = [30, 220, 70]
        frame = VideoFrame.from_ndarray(image, format="bgr24")
        frame.pts = self._timestamp
        frame.time_base = Fraction(1, 90000)
        return frame


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
    return {k: "\n".join(v) for k, v in sections.items()}


def candidate_types(sdp: str):
    types = set()
    for line in sdp.splitlines():
        if line.startswith("a=candidate:"):
            match = re.search(r" typ ([a-zA-Z0-9_-]+)", line)
            if match:
                types.add(match.group(1))
    return sorted(types)


def validate_nest_offer(sdp: str):
    sections = media_sections(sdp)
    audio = sections.get("audio", "")
    video = sections.get("video", "")
    application = sections.get("application", "")
    bundle_lines = [line for line in sdp.splitlines() if line.startswith("a=group:BUNDLE ")]
    bundle_mids = bundle_lines[0].split()[1:] if len(bundle_lines) == 1 else []
    checks = {
        "media_order_audio_video_application": media_order(sdp) == ["audio", "video", "application"],
        "audio_recvonly": bool(re.search(r"(?m)^a=recvonly$", audio)),
        "video_recvonly": bool(re.search(r"(?m)^a=recvonly$", video)),
        "audio_offers_opus": bool(re.search(r"(?im)^a=rtpmap:\d+\s+opus/48000(?:/2)?$", audio)),
        "video_offers_h264": "H264/90000" in video.upper(),
        "h264_packetization_mode_1": "packetization-mode=1" in video,
        "h264_nest_compatible_baseline_profile": ("profile-level-id=42001f" in video or "profile-level-id=42e01f" in video),
        "data_channel_present": "webrtc-datachannel" in application,
        "bundle_three_mids": len(bundle_mids) == 3,
        "offer_ends_with_newline": sdp.endswith("\r\n") or sdp.endswith("\n"),
    }
    return checks


async def main():
    os.makedirs("artifacts", exist_ok=True)

    h264 = [c for c in RTCRtpSender.getCapabilities("video").codecs if c.mimeType.lower() == "video/h264"]
    if not h264:
        raise RuntimeError("Runtime exposes no H264 WebRTC codec capability")

    config = RTCConfiguration(iceServers=[RTCIceServer(urls=["stun:stun.l.google.com:19302"])])
    receiver_pc = RTCPeerConnection(config)
    sender_pc = RTCPeerConnection(config)

    decoded_future = asyncio.get_running_loop().create_future()
    data_open_future = asyncio.get_running_loop().create_future()

    receiver_pc.addTransceiver("audio", direction="recvonly")
    video_transceiver = receiver_pc.addTransceiver("video", direction="recvonly")
    video_transceiver.setCodecPreferences(h264)
    data_channel = receiver_pc.createDataChannel("doorbell-preflight")

    @data_channel.on("open")
    def on_open():
        if not data_open_future.done():
            data_open_future.set_result(True)

    @receiver_pc.on("track")
    def on_track(track):
        if track.kind != "video":
            return

        async def receive_one():
            try:
                frame = await asyncio.wait_for(track.recv(), timeout=20)
                image_path = "artifacts/decoded-frame.png"
                frame.to_image().save(image_path)
                if not decoded_future.done():
                    decoded_future.set_result({
                        "width": frame.width,
                        "height": frame.height,
                        "format": str(frame.format.name),
                        "image_path": image_path,
                    })
            except Exception as exc:
                if not decoded_future.done():
                    decoded_future.set_exception(exc)

        asyncio.create_task(receive_one())

    offer = await receiver_pc.createOffer()
    await receiver_pc.setLocalDescription(offer)
    offer_sdp = receiver_pc.localDescription.sdp

    nest_checks = validate_nest_offer(offer_sdp)
    failed_contract_checks = [name for name, passed in nest_checks.items() if not passed]
    if failed_contract_checks:
        raise RuntimeError(f"Nest SDP contract failed: {failed_contract_checks}")

    await sender_pc.setRemoteDescription(receiver_pc.localDescription)
    sender_pc.addTrack(AudioStreamTrack())
    sender_pc.addTrack(SyntheticVideoTrack())

    sender_video = next(t for t in sender_pc.getTransceivers() if t.kind == "video")
    sender_video.setCodecPreferences(h264)

    answer = await sender_pc.createAnswer()
    await sender_pc.setLocalDescription(answer)
    await receiver_pc.setRemoteDescription(sender_pc.localDescription)

    decoded = await asyncio.wait_for(decoded_future, timeout=30)
    data_channel_open = False
    try:
        await asyncio.wait_for(data_open_future, timeout=10)
        data_channel_open = True
    except asyncio.TimeoutError:
        pass

    if not data_channel_open:
        raise RuntimeError("WebRTC data channel did not open")

    answer_sdp = sender_pc.localDescription.sdp
    stats = await receiver_pc.getStats()
    inbound_video = []
    for stat in stats.values():
        if getattr(stat, "type", None) == "inbound-rtp" and getattr(stat, "kind", None) == "video":
            inbound_video.append({
                "packetsReceived": getattr(stat, "packetsReceived", None),
                "packetsLost": getattr(stat, "packetsLost", None),
            })

    report = {
        "success": True,
        "nest_contract": nest_checks,
        "offer_sdp_sha256": hashlib.sha256(offer_sdp.encode()).hexdigest(),
        "h264_capability_count": len(h264),
        "h264_capabilities": [
            {"mimeType": c.mimeType, "clockRate": c.clockRate, "parameters": c.parameters}
            for c in h264
        ],
        "offer_media_order": media_order(offer_sdp),
        "answer_media_order": media_order(answer_sdp),
        "offer_candidate_types": candidate_types(offer_sdp),
        "answer_candidate_types": candidate_types(answer_sdp),
        "data_channel_open": data_channel_open,
        "decoded_frame": decoded,
        "receiver_connection_state": receiver_pc.connectionState,
        "inbound_video_stats": inbound_video,
    }

    with open("artifacts/preflight-report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    print(json.dumps(report, indent=2, default=str))

    await receiver_pc.close()
    await sender_pc.close()


if __name__ == "__main__":
    asyncio.run(main())
