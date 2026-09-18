#!/usr/bin/env python3
"""Run one Nest capture with sanitized WebRTC/RTP instrumentation.

This diagnostic intentionally records only coarse transport counts, negotiated
video codec metadata, RTP payload-type/SSRC routing counts, and the capture
failure stage. It never prints OAuth credentials, SDP candidates, IP addresses,
media payload bytes, or camera pixels.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

import aioice
from aiortc.rtcdtlstransport import RtpRouter

import nest_capture


def summarize_video_codecs(sdp: str) -> list[dict[str, Any]]:
    """Return only payload type / codec / fmtp metadata from the video section."""
    in_video = False
    rtpmap: dict[int, str] = {}
    fmtp: dict[int, str] = {}

    for raw in sdp.replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if line.startswith("m="):
            in_video = line.startswith("m=video ")
            continue
        if not in_video:
            continue

        if line.startswith("a=rtpmap:"):
            head, _, codec = line.partition(" ")
            try:
                pt = int(head.split(":", 1)[1])
            except (ValueError, IndexError):
                continue
            rtpmap[pt] = codec
        elif line.startswith("a=fmtp:"):
            head, _, params = line.partition(" ")
            try:
                pt = int(head.split(":", 1)[1])
            except (ValueError, IndexError):
                continue
            fmtp[pt] = params

    result: list[dict[str, Any]] = []
    for pt in sorted(set(rtpmap) | set(fmtp)):
        codec = rtpmap.get(pt, "")
        params = fmtp.get(pt, "")
        profile = None
        packetization_mode = None
        for item in params.split(";"):
            key, sep, value = item.strip().partition("=")
            if not sep:
                continue
            if key.lower() == "profile-level-id":
                profile = value
            elif key.lower() == "packetization-mode":
                packetization_mode = value

        result.append(
            {
                "payload_type": pt,
                "codec": codec,
                "profile_level_id": profile,
                "packetization_mode": packetization_mode,
            }
        )
    return result


def _kind_for_receiver(receiver: Any) -> str:
    for name in ("kind", "_kind", "_RTCRtpReceiver__kind"):
        value = getattr(receiver, name, None)
        if isinstance(value, str) and value:
            return value
    track = getattr(receiver, "track", None)
    value = getattr(track, "kind", None)
    return value if isinstance(value, str) and value else "unknown"


class Probe:
    def __init__(self) -> None:
        self.ice_datagrams = 0
        self.ice_bytes = 0
        self.ice_max_datagram_bytes = 0
        self.datagram_classes: Counter[str] = Counter()
        self.receiver_registrations: list[dict[str, Any]] = []
        self.rtp_by_payload_type: Counter[int] = Counter()
        self.rtp_by_ssrc: Counter[int] = Counter()
        self.rtp_routed = 0
        self.rtp_dropped = 0
        self.answer_video_codecs: list[dict[str, Any]] = []

        self._orig_recvfrom = aioice.Connection.recvfrom
        self._orig_register_receiver = RtpRouter.register_receiver
        self._orig_route_rtp = RtpRouter.route_rtp
        self._orig_normalize_answer = nest_capture.normalize_nest_answer_sdp

    def install(self) -> None:
        probe = self

        async def recvfrom_wrapper(connection: Any) -> tuple[bytes, int]:
            data, component = await probe._orig_recvfrom(connection)
            probe.ice_datagrams += 1
            probe.ice_bytes += len(data)
            probe.ice_max_datagram_bytes = max(probe.ice_max_datagram_bytes, len(data))
            if data:
                first = data[0]
                if 20 <= first < 64:
                    label = "dtls"
                elif 128 <= first < 192:
                    label = "srtp_or_srtcp"
                elif first < 64:
                    label = "stun_or_other"
                else:
                    label = "other"
                probe.datagram_classes[label] += 1
            return data, component

        def register_receiver_wrapper(
            router: Any,
            receiver: Any,
            ssrcs: list[int],
            payload_types: list[int],
            mid: str | None = None,
        ) -> None:
            probe.receiver_registrations.append(
                {
                    "kind": _kind_for_receiver(receiver),
                    "payload_types": sorted(int(x) for x in payload_types),
                    "ssrc_count": len(ssrcs),
                    "mid_present": mid is not None,
                }
            )
            return probe._orig_register_receiver(
                router,
                receiver,
                ssrcs=ssrcs,
                payload_types=payload_types,
                mid=mid,
            )

        def route_rtp_wrapper(router: Any, packet: Any) -> Any:
            probe.rtp_by_payload_type[int(packet.payload_type)] += 1
            probe.rtp_by_ssrc[int(packet.ssrc)] += 1
            receiver = probe._orig_route_rtp(router, packet)
            if receiver is None:
                probe.rtp_dropped += 1
            else:
                probe.rtp_routed += 1
            return receiver

        def normalize_answer_wrapper(answer_sdp: str) -> tuple[str, int, int]:
            probe.answer_video_codecs = summarize_video_codecs(answer_sdp)
            return probe._orig_normalize_answer(answer_sdp)

        aioice.Connection.recvfrom = recvfrom_wrapper
        RtpRouter.register_receiver = register_receiver_wrapper
        RtpRouter.route_rtp = route_rtp_wrapper
        nest_capture.normalize_nest_answer_sdp = normalize_answer_wrapper

    def restore(self) -> None:
        aioice.Connection.recvfrom = self._orig_recvfrom
        RtpRouter.register_receiver = self._orig_register_receiver
        RtpRouter.route_rtp = self._orig_route_rtp
        nest_capture.normalize_nest_answer_sdp = self._orig_normalize_answer

    def report(self) -> dict[str, Any]:
        return {
            "transport": {
                "ice_datagrams": self.ice_datagrams,
                "ice_bytes": self.ice_bytes,
                "ice_max_datagram_bytes": self.ice_max_datagram_bytes,
                "datagram_classes": dict(sorted(self.datagram_classes.items())),
            },
            "negotiation": {
                "answer_video_codecs": self.answer_video_codecs,
                "receiver_registrations": self.receiver_registrations,
            },
            "rtp": {
                "parsed_packets": self.rtp_routed + self.rtp_dropped,
                "routed_packets": self.rtp_routed,
                "router_dropped_packets": self.rtp_dropped,
                "by_payload_type": {
                    str(k): v for k, v in sorted(self.rtp_by_payload_type.items())
                },
                "distinct_ssrcs": len(self.rtp_by_ssrc),
            },
        }


async def run_probe() -> tuple[int, dict[str, Any]]:
    request_id = str(uuid.uuid4())
    probe = Probe()
    probe.install()

    temp_dir = Path(tempfile.mkdtemp(prefix="doorbell-media-probe-"))
    try:
        try:
            capture = await nest_capture.capture_one_frame(temp_dir, request_id)
            result: dict[str, Any] = {
                "success": True,
                "capture": {
                    "mime_type": capture["capture"]["mime_type"],
                    "width": capture["capture"]["width"],
                    "height": capture["capture"]["height"],
                    "bytes": capture["capture"]["bytes"],
                    "sha256": capture["capture"]["sha256"],
                    "fresh_live_session_observation": capture["freshness"][
                        "fresh_live_session_observation"
                    ],
                    "camera_sensor_capture_time_proven": capture["freshness"][
                        "camera_sensor_capture_time_proven"
                    ],
                },
                "probe": probe.report(),
            }
            return 0, result
        except nest_capture.CaptureError as exc:
            return 2, {
                "success": False,
                "error": exc.as_dict(),
                "probe": probe.report(),
            }
        except Exception as exc:
            return 3, {
                "success": False,
                "error": {
                    "stage": "probe_runtime",
                    "code": "UNEXPECTED_PROBE_ERROR",
                    "message": type(exc).__name__,
                },
                "probe": probe.report(),
            }
    finally:
        probe.restore()
        shutil.rmtree(temp_dir, ignore_errors=True)


def main() -> int:
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    code, result = asyncio.run(run_probe())
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
