import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from apiwells.models import ResultStatus, SupportStatus
from apiwells.probes import ChatProbe
from apiwells.runner import DoctorRunner


class ChatHandler(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = self.rfile.read(
            int(self.headers.get("Content-Length", 0))
        )

        ChatHandler.calls.append(
            (
                self.path,
                self.headers.get("Authorization"),
                body,
            )
        )

        prefix = self.path.split("/")[1]

        if prefix == "http500":
            self.send_response(500)
            self.end_headers()
            return

        self.send_response(200)
        self.end_headers()

        if prefix == "invalid":
            raw = b"<html>not-json</html>"

        elif prefix == "schema":
            raw = json.dumps(
                {
                    "choices": [
                        {}
                    ]
                }
            ).encode()

        elif prefix == "empty":
            raw = json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "   ",
                            }
                        }
                    ]
                }
            ).encode()

        elif prefix == "usage":
            raw = json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "OK",
                            }
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 5,
                        "total_tokens": 15,
                    },
                }
            ).encode()

        elif prefix == "partialusage":
            raw = json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "OK",
                            }
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 5,
                    },
                }
            ).encode()

        elif prefix == "secret":
            raw = json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "secret-test-key",
                            }
                        }
                    ]
                }
            ).encode()

        else:
            raw = json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "OK",
                            }
                        }
                    ]
                }
            ).encode()

        self.wfile.write(raw)


class ChatProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            ChatHandler,
        )

        cls.thread = threading.Thread(
            target=cls.server.serve_forever,
            daemon=True,
        )

        cls.thread.start()

        cls.base = (
            "http://127.0.0.1:"
            + str(cls.server.server_port)
        )

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        ChatHandler.calls.clear()

    def test_valid_chat_passes_and_payload_is_non_stream(self):
        result = ChatProbe(
            self.base + "/valid",
            model="demo-model",
            max_tokens=8,
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.PASS,
        )

        self.assertEqual(
            result.support,
            SupportStatus.SUPPORTED,
        )

        body = json.loads(
            ChatHandler.calls[-1][2]
        )

        self.assertEqual(
            body["model"],
            "demo-model",
        )

        self.assertEqual(
            body["max_tokens"],
            8,
        )

        self.assertFalse(
            body["stream"]
        )

        self.assertIn(
            "total_latency_ms",
            result.metrics,
        )

    def test_invalid_json_fails(self):
        result = ChatProbe(
            self.base + "/invalid",
            model="demo-model",
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            result.support,
            SupportStatus.UNKNOWN,
        )

        self.assertEqual(
            result.error_code,
            "INVALID_JSON",
        )

    def test_invalid_schema_fails(self):
        result = ChatProbe(
            self.base + "/schema",
            model="demo-model",
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            result.error_code,
            "INVALID_SCHEMA",
        )

    def test_empty_assistant_content_fails(self):
        result = ChatProbe(
            self.base + "/empty",
            model="demo-model",
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            result.error_code,
            "INVALID_SCHEMA",
        )

    def test_http_failure_is_not_retried(self):
        result = ChatProbe(
            self.base + "/http500",
            model="demo-model",
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            result.evidence["http_status"],
            500,
        )

        self.assertEqual(
            len(ChatHandler.calls),
            1,
        )

    def test_secret_is_not_stored_in_result(self):
        result = ChatProbe(
            self.base + "/secret",
            model="demo-model",
            key="secret-test-key",
        ).run()

        self.assertEqual(
            ChatHandler.calls[-1][1],
            "Bearer secret-test-key",
        )

        self.assertNotIn(
            "secret-test-key",
            repr(result),
        )

    def test_requires_nonempty_model(self):
        with self.assertRaises(ValueError):
            ChatProbe(
                self.base + "/valid",
                model="",
            )

    def test_chat_probe_runs_under_doctor_runner(self):
        runner = DoctorRunner(
            [
                ChatProbe(
                    self.base + "/valid",
                    model="demo-model",
                )
            ]
        )

        results = runner.run()

        self.assertEqual(
            len(results),
            1,
        )

        self.assertEqual(
            results[0].name,
            "chat",
        )

        self.assertEqual(
            results[0].status,
            ResultStatus.PASS,
        )

    def test_complete_usage_is_added_to_metrics(self):
        result = ChatProbe(
            self.base + "/usage",
            model="demo-model",
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.PASS,
        )

        self.assertTrue(
            result.metrics["usage_available"]
        )

        self.assertEqual(
            result.metrics["prompt_tokens"],
            10,
        )

        self.assertEqual(
            result.metrics["completion_tokens"],
            5,
        )

        self.assertEqual(
            result.metrics["total_tokens"],
            15,
        )

    def test_partial_usage_is_not_estimated(self):
        result = ChatProbe(
            self.base + "/partialusage",
            model="demo-model",
        ).run()

        self.assertTrue(
            result.metrics["usage_available"]
        )

        self.assertEqual(
            result.metrics["prompt_tokens"],
            10,
        )

        self.assertEqual(
            result.metrics["completion_tokens"],
            5,
        )

        self.assertIsNone(
            result.metrics["total_tokens"]
        )

    def test_missing_usage_is_reported_unavailable(self):
        result = ChatProbe(
            self.base + "/valid",
            model="demo-model",
        ).run()

        self.assertFalse(
            result.metrics["usage_available"]
        )

        self.assertIsNone(
            result.metrics["prompt_tokens"]
        )

        self.assertIsNone(
            result.metrics["completion_tokens"]
        )

        self.assertIsNone(
            result.metrics["total_tokens"]
        )


if __name__ == "__main__":
    unittest.main()