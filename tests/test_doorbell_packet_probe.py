import unittest

from doorbell_packet_probe import Probe, summarize_video_codecs


ANSWER = (
    "v=0\r\n"
    "m=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"
    "a=rtpmap:111 opus/48000/2\r\n"
    "m=video 9 UDP/TLS/RTP/SAVPF 96 98\r\n"
    "a=rtpmap:96 H264/90000\r\n"
    "a=fmtp:96 packetization-mode=1;profile-level-id=42e01f\r\n"
    "a=rtpmap:98 H264/90000\r\n"
    "a=fmtp:98 packetization-mode=1;profile-level-id=64001f\r\n"
    "m=application 9 UDP/DTLS/SCTP webrtc-datachannel\r\n"
)


class DoorbellPacketProbeTests(unittest.TestCase):
    def test_summarize_video_codecs_keeps_only_safe_codec_metadata(self):
        codecs = summarize_video_codecs(ANSWER)
        self.assertEqual(
            codecs,
            [
                {
                    "payload_type": 96,
                    "codec": "H264/90000",
                    "profile_level_id": "42e01f",
                    "packetization_mode": "1",
                },
                {
                    "payload_type": 98,
                    "codec": "H264/90000",
                    "profile_level_id": "64001f",
                    "packetization_mode": "1",
                },
            ],
        )

    def test_probe_report_has_counts_not_media_payloads(self):
        probe = Probe()
        probe.ice_datagrams = 4
        probe.ice_bytes = 1200
        probe.ice_max_datagram_bytes = 500
        probe.datagram_classes["dtls"] = 1
        probe.datagram_classes["srtp_or_srtcp"] = 3
        probe.rtp_by_payload_type[98] = 7
        probe.rtp_by_ssrc[1234] = 7
        probe.rtp_routed = 6
        probe.rtp_dropped = 1

        report = probe.report()
        self.assertEqual(report["rtp"]["parsed_packets"], 7)
        self.assertEqual(report["rtp"]["routed_packets"], 6)
        self.assertEqual(report["rtp"]["router_dropped_packets"], 1)
        self.assertEqual(report["rtp"]["by_payload_type"], {"98": 7})
        self.assertEqual(report["rtp"]["distinct_ssrcs"], 1)
        self.assertNotIn("payload", report["transport"])


if __name__ == "__main__":
    unittest.main()
