import asyncio
import json
import os
import re
import time
from fractions import Fraction

import numpy as np
from aiortc import (
    AudioStreamTrack,
    MediaStreamTrack,
    RTCConfiguration,
    RTCIceServer,
    RTCPeerConnection,
    RTCRtpSender,
)
from av import VideoFrame


class SyntheticVideoTrack(MediaStreamTrack):
    kind = "video"

    def __init__(self):
        super().__init__()
        self._timestamp = 0
        self._started = time.monotonic()

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
    return [line[2:] for line in sdp.splitlines() if line.startswith("m=")]


def h264_lines(sdp: str):
    return [line for line in sdp.splitlines() if "H264" in line.upper()]


def candidate_types(sdp: str):
    types = set()
    for line in sdp.splitlines():
        if line.startswith("a=candidate:"):
            match = re.search(r" typ ([a-zA-Z0-9_-]+)", line)
            if match:
                types.add(match.group(1))
    return sorted(types)


async def main():
    os.makedirs("artifacts", exist_ok=True)

    video_caps = RTCRtpSender.getCapabilities("video")
    h264 = [c for c in video_caps.codecs if c.mimeType.lower() == "video/h264"]
    if not h264:
        raise RuntimeError("Runtime exposes no H264 WebRTC codec capability")

    config = RTCConfiguration(
        iceServers=[RTCIceServer(urls=["stun:stun.l.google.com:19302"])]
    )
    receiver_pc = RTCPeerConnection(config)
    sender_pc = RTCPeerConnection(config)

    decoded_future = asyncio.get_running_loop().create_future()
    data_open_future = asyncio.get_running_loop().create_future()

    # Build an offer with the same broad ingredients required by Nest:
    # receive-oriented audio/video plus a WebRTC data channel.
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
                    decoded_future.set_result(
                        {
                            "width": frame.width,
                            "height": frame.height,
                            "format": str(frame.format.name),
                            "image_path": image_path,
                        }
                    )
            except Exception as exc:
                if not decoded_future.done():
                    decoded_future.set_exception(exc)

        asyncio.create_task(receive_one())

    offer = await receiver_pc.createOffer()
    await receiver_pc.setLocalDescription(offer)
    local_offer = receiver_pc.localDescription

    await sender_pc.setRemoteDescription(local_offer)
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

    offer_sdp = receiver_pc.localDescription.sdp
    answer_sdp = sender_pc.localDescription.sdp

    stats = await receiver_pc.getStats()
    inbound_video = []
    codecs = {}
    for stat in stats.values():
        if getattr(stat, "type", None) == "codec":
            codecs[stat.id] = {
                "mimeType": getattr(stat, "mimeType", None),
                "payloadType": getattr(stat, "payloadType", None),
            }
        if getattr(stat, "type", None) == "inbound-rtp" and getattr(stat, "kind", None) == "video":
            inbound_video.append(
                {
                    "packetsReceived": getattr(stat, "packetsReceived", None),
                    "packetsLost": getattr(stat, "packetsLost", None),
                    "codecId": getattr(stat, "codecId", None),
                }
            )

    report = {
        "success": True,
        "h264_capability_count": len(h264),
        "h264_capabilities": [
            {
                "mimeType": c.mimeType,
                "clockRate": c.clockRate,
                "parameters": c.parameters,
            }
            for c in h264
        ],
        "offer_media_order": media_order(offer_sdp),
        "answer_media_order": media_order(answer_sdp),
        "offer_h264_lines": h264_lines(offer_sdp),
        "answer_h264_lines": h264_lines(answer_sdp),
        "offer_candidate_types": candidate_types(offer_sdp),
        "answer_candidate_types": candidate_types(answer_sdp),
        "data_channel_open": data_channel_open,
        "decoded_frame": decoded,
        "receiver_connection_state": receiver_pc.connectionState,
        "inbound_video_stats": inbound_video,
        "codec_stats": codecs,
    }

    with open("artifacts/preflight-report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    print(json.dumps(report, indent=2, default=str))

    await receiver_pc.close()
    await sender_pc.close()


if __name__ == "__main__":
    asyncio.run(main())
