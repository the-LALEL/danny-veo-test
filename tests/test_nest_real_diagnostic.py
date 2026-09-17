import importlib.util
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "nest_real_diagnostic.py"
spec = importlib.util.spec_from_file_location("nest_real_diagnostic", MODULE_PATH)
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)


class FakeResponse:
    def __init__(self, status=200, payload=None, body=b"{}"):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.content = body
        self.ok = 200 <= status < 300
        self.text = body.decode("utf-8", errors="replace")

    def json(self):
        return self._payload


class DiagnosticTests(unittest.TestCase):
    def test_nest_candidate_repair(self):
        fixed, normalized, dropped = diag.normalize_nest_answer_sdp(
            "v=0\r\n"
            "a=candidate: 1 udp 2122260223 10.0.0.2 50000 typ host\r\n"
            "a=candidate: 1 tcp 1518280447 10.0.0.2 9 typ host tcptype active\r\n"
        )
        self.assertEqual(normalized, 1)
        self.assertEqual(dropped, 1)
        self.assertIn("a=candidate:nest1 1 udp ", fixed)
        self.assertNotIn(" tcp ", fixed.lower())
        self.assertTrue(fixed.endswith("\r\n"))

    def test_request_scoped_directory_cannot_reuse_legacy_image(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            legacy = base / "doorbell.jpg"
            legacy.write_bytes(b"stale")
            run = diag.create_run_dir(base, "request-123")
            current = run / "doorbell.jpg"
            self.assertNotEqual(current, legacy)
            self.assertFalse(current.exists())
            self.assertEqual(legacy.read_bytes(), b"stale")

    def test_safe_json_write_mode_600(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "report.json"
            diag.safe_json_write(path, {"ok": True})
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_http_error_does_not_echo_response_body(self):
        response = FakeResponse(status=401, body=b"access_token=DO_NOT_ECHO")
        with patch.object(diag.requests, "request", return_value=response):
            with self.assertRaises(RuntimeError) as cm:
                diag.http_json("GET", "https://example.invalid")
        text = str(cm.exception)
        self.assertEqual(text, "HTTP 401")
        self.assertNotIn("DO_NOT_ECHO", text)

    def test_discovery_selects_one_webrtc_doorbell(self):
        payload = {
            "devices": [
                {
                    "name": "enterprises/p/devices/d",
                    "type": "sdm.devices.types.DOORBELL",
                    "traits": {
                        "sdm.devices.traits.CameraLiveStream": {
                            "supportedProtocols": ["WEB_RTC"],
                            "videoCodecs": ["H264"],
                            "audioCodecs": ["OPUS"],
                        }
                    },
                }
            ]
        }
        with patch.object(diag, "http_json", return_value=payload):
            name = diag.discover_doorbell("p", "token")
        self.assertEqual(name, "enterprises/p/devices/d")

    def test_execute_command_shape(self):
        with patch.object(diag, "http_json", return_value={"results": {}}) as mocked:
            diag.execute_command("enterprises/p/devices/d", "token", "cmd", {"x": 1})
        args, kwargs = mocked.call_args
        self.assertEqual(args[0], "POST")
        self.assertTrue(args[1].endswith("/enterprises/p/devices/d:executeCommand"))
        self.assertEqual(kwargs["json_body"], {"command": "cmd", "params": {"x": 1}})
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer token")

    def test_pcm_url_contract(self):
        url = diag.build_pcm_url("project-id", "client.apps.googleusercontent.com")
        self.assertIn("/partnerconnections/project-id/auth?", url)
        self.assertIn("access_type=offline", url)
        self.assertIn("prompt=consent", url)
        self.assertIn("response_type=code", url)
        self.assertIn("sdm.service", url)

    def test_failure_classifier_router_drop(self):
        inst = diag.Instrumentation()
        inst.wire[(100, 102)] = 5
        inst.dropped[(100, 102)] = 5
        self.assertEqual(
            diag.classify_failure(inst, True),
            "RTP_ROUTER_MAPPING_FAILURE",
        )

    def test_failure_classifier_decode(self):
        inst = diag.Instrumentation()
        inst.wire[(100, 102)] = 5
        inst.routed[(100, 102)] = 5
        inst.receiver[("video", 100, 102)] = 5
        inst.counts["video_encoded_frames"] = 1
        inst.counts["h264_decode_calls"] = 1
        inst.counts["h264_decoded_frames"] = 0
        self.assertEqual(
            diag.classify_failure(inst, True),
            "H264_DECODE_FAILURE",
        )


if __name__ == "__main__":
    unittest.main()
