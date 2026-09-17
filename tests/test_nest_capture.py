import os
import unittest
from unittest.mock import patch

import nest_capture


VALID_OFFER = (
    "v=0\r\n"
    "a=group:BUNDLE 0 1 2\r\n"
    "m=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"
    "a=mid:0\r\n"
    "a=recvonly\r\n"
    "a=rtpmap:111 opus/48000/2\r\n"
    "m=video 9 UDP/TLS/RTP/SAVPF 102\r\n"
    "a=mid:1\r\n"
    "a=recvonly\r\n"
    "a=rtpmap:102 H264/90000\r\n"
    "a=fmtp:102 packetization-mode=1;profile-level-id=42001f\r\n"
    "m=application 9 UDP/DTLS/SCTP webrtc-datachannel\r\n"
    "a=mid:2\r\n"
)


class NestCaptureTests(unittest.TestCase):
    def test_valid_offer_contract(self):
        contract = nest_capture.validate_nest_offer(VALID_OFFER)
        self.assertTrue(all(contract.values()), contract)

    def test_offer_rejects_non_opus_audio(self):
        offer = VALID_OFFER.replace(
            "a=rtpmap:111 opus/48000/2\r\n",
            "a=rtpmap:111 opus/48000/2\r\na=rtpmap:0 PCMU/8000\r\n",
        )
        self.assertFalse(nest_capture.validate_nest_offer(offer)["audio_only_opus"])

    def test_normalize_blank_foundation_udp_and_drop_tcp(self):
        answer = (
            "v=0\r\n"
            "a=candidate: 1 udp 2122260223 10.0.0.2 50000 typ host\r\n"
            "a=candidate: 1 tcp 1518280447 10.0.0.2 9 typ host tcptype active\r\n"
        )
        fixed, normalized, dropped = nest_capture.normalize_nest_answer_sdp(answer)
        self.assertEqual(normalized, 1)
        self.assertEqual(dropped, 1)
        self.assertIn("a=candidate:nest1 1 udp ", fixed)
        self.assertNotIn(" tcp ", fixed.lower())
        self.assertTrue(fixed.endswith("\r\n"))

    def test_oauth_probe_accepts_invalid_grant_as_valid_client_pair(self):
        with patch.object(nest_capture, "_oauth_token_request", return_value=(400, {"error": "invalid_grant"})):
            self.assertTrue(nest_capture.probe_oauth_client("id", "secret"))

    def test_oauth_probe_rejects_invalid_client(self):
        with patch.object(nest_capture, "_oauth_token_request", return_value=(401, {"error": "invalid_client"})):
            self.assertFalse(nest_capture.probe_oauth_client("id", "secret"))

    def test_refresh_classifies_client_mismatch(self):
        env = {
            "NEST_REFRESH_TOKEN": "refresh",
            "NEST_CLIENT_ID": "id",
            "NEST_CLIENT_SECRET": "secret",
        }
        with patch.dict(os.environ, env, clear=True), patch.object(
            nest_capture, "_oauth_token_request", return_value=(401, {"error": "invalid_client"})
        ):
            with self.assertRaises(nest_capture.CaptureError) as ctx:
                nest_capture.get_access_token()
        self.assertEqual(ctx.exception.stage, "authentication")
        self.assertEqual(ctx.exception.code, "OAUTH_CLIENT_MISMATCH")

    def test_device_access_project_alias_conflict_is_explicit(self):
        with patch.dict(
            os.environ,
            {"NEST_DEVICE_ACCESS_PROJECT_ID": "a", "NEST_ENTERPRISE_ID": "b"},
            clear=True,
        ):
            with self.assertRaises(nest_capture.CaptureError) as ctx:
                nest_capture._device_access_project_id()
        self.assertEqual(ctx.exception.code, "CONFLICTING_PROJECT_IDS")

    def test_device_discovery_selects_doorbell_not_other_webrtc_camera(self):
        response = {
            "devices": [
                {
                    "name": "enterprises/p/devices/camera",
                    "type": "sdm.devices.types.CAMERA",
                    "traits": {
                        "sdm.devices.traits.CameraLiveStream": {"supportedProtocols": ["WEB_RTC"]}
                    },
                },
                {
                    "name": "enterprises/p/devices/doorbell",
                    "type": "sdm.devices.types.DOORBELL",
                    "traits": {
                        "sdm.devices.traits.CameraLiveStream": {"supportedProtocols": ["WEB_RTC"]}
                    },
                },
            ]
        }
        with patch.dict(os.environ, {"NEST_DEVICE_ACCESS_PROJECT_ID": "p"}, clear=True), patch.object(
            nest_capture, "_http_json", return_value=response
        ):
            name, source = nest_capture.resolve_device_name("token")
        self.assertEqual(name, "enterprises/p/devices/doorbell")
        self.assertEqual(source, "unique_webrtc_doorbell")


if __name__ == "__main__":
    unittest.main()
