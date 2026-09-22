import json
import threading
import unittest
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)

from apiwells.models import (
    ResultStatus,
    SupportStatus,
)
from apiwells.runner import run_deep_diagnostics


class DeepHandler(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        DeepHandler.calls.append(
            (
                "GET",
                self.path,
                self.headers.get(
                    "Authorization"
                ),
                None,
            )
        )

        prefix = self.path.split("/")[1]

        if prefix == "unauthorized":
            self.send_response(401)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header(
            "Content-Type",
            "application/json",
        )
        self.end_headers()

        model_id = (
            "other-model"
            if prefix == "missing"
            else "demo-model"
        )

        raw = json.dumps(
            {
                "data": [
                    {
                        "id": model_id
                    }
                ]
            }
        ).encode()

        self.wfile.write(raw)

    def do_POST(self):
        body = self.rfile.read(
            int(
                self.headers.get(
                    "Content-Length",
                    0,
                )
            )
        )

        payload = json.loads(body)

        DeepHandler.calls.append(
            (
                "POST",
                self.path,
                self.headers.get(
                    "Authorization"
                ),
                payload,
            )
        )

        if payload.get("stream"):
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/event-stream",
            )
            self.end_headers()

            lines = [
                (
                    b'data: {"choices":['
                    b'{"delta":{"role":"assistant"}}]}\n'
                ),
                b"\n",
                (
                    b'data: {"choices":['
                    b'{"delta":{"content":"OK"}}]}\n'
                ),
                b"\n",
                b"data: [DONE]\n",
                b"\n",
            ]

            for line in lines:
                self.wfile.write(line)
                self.wfile.flush()

            return

        self.send_response(200)
        self.send_header(
            "Content-Type",
            "application/json",
        )
        self.end_headers()

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


class DeepRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            DeepHandler,
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
        DeepHandler.calls.clear()

    def test_deep_chain_runs_basic_chat_and_streaming(self):
        results = run_deep_diagnostics(
            self.base + "/v1",
            model="demo-model",
            key="secret-test-key",
            timeout=1,
            max_tokens=8,
        )

        self.assertEqual(
            [result.name for result in results],
            [
                "url",
                "dns",
                "tls",
                "http",
                "auth",
                "models",
                "chat",
                "streaming",
            ],
        )

        self.assertTrue(
            all(
                result.status
                is ResultStatus.PASS
                for result in results
            )
        )

        streaming = results[-1]

        self.assertEqual(
            streaming.support,
            SupportStatus.SUPPORTED,
        )

        self.assertIsNotNone(
            streaming.metrics["ttft_ms"]
        )

        self.assertIn(
            "total_latency_ms",
            streaming.metrics,
        )

        self.assertEqual(
            [call[0] for call in DeepHandler.calls],
            [
                "GET",
                "POST",
                "POST",
            ],
        )

        self.assertEqual(
            DeepHandler.calls[0][1],
            "/v1/models",
        )

        self.assertEqual(
            DeepHandler.calls[1][1],
            "/v1/chat/completions",
        )

        self.assertEqual(
            DeepHandler.calls[2][1],
            "/v1/chat/completions",
        )

        self.assertFalse(
            DeepHandler.calls[1][3]["stream"]
        )

        self.assertTrue(
            DeepHandler.calls[2][3]["stream"]
        )

    def test_basic_failure_blocks_billable_probes(self):
        results = run_deep_diagnostics(
            self.base + "/unauthorized",
            model="demo-model",
            key="bad-key",
            timeout=1,
        )

        self.assertEqual(
            [result.name for result in results],
            [
                "url",
                "dns",
                "tls",
                "http",
                "auth",
                "models",
            ],
        )

        auth = next(
            result
            for result in results
            if result.name == "auth"
        )

        self.assertEqual(
            auth.status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            DeepHandler.calls,
            [
                (
                    "GET",
                    "/unauthorized/models",
                    "Bearer bad-key",
                    None,
                )
            ],
        )

    def test_missing_target_model_blocks_billable_probes(self):
        results = run_deep_diagnostics(
            self.base + "/missing",
            model="demo-model",
            timeout=1,
            authentication_requested=False,
        )

        models = next(
            result
            for result in results
            if result.name == "models"
        )

        self.assertFalse(
            models.evidence[
                "target_model_found"
            ]
        )

        self.assertEqual(
            [call[0] for call in DeepHandler.calls],
            [
                "GET",
            ],
        )

    def test_deep_requires_nonempty_model(self):
        with self.assertRaises(ValueError):
            run_deep_diagnostics(
                self.base + "/v1",
                model="",
            )

        self.assertEqual(
            DeepHandler.calls,
            [],
        )


if __name__ == "__main__":
    unittest.main()