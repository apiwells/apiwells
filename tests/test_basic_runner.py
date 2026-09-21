import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from apiwells.models import ResultStatus, SupportStatus
from apiwells.runner import run_basic_diagnostics


class BasicHandler(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        BasicHandler.calls.append(
            (
                self.path,
                self.headers.get("Authorization"),
            )
        )

        prefix = self.path.split("/")[1]

        if prefix == "unauthorized":
            self.send_response(401)
            self.end_headers()
            return

        self.send_response(200)
        self.end_headers()

        raw = json.dumps(
            {
                "data": [
                    {"id": "model-a"},
                    {"id": "model-b"},
                ]
            }
        ).encode()

        self.wfile.write(raw)


class BasicRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            BasicHandler,
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
        BasicHandler.calls.clear()

    def test_basic_probe_order_and_single_models_request(self):
        results = run_basic_diagnostics(
            self.base + "/v1",
            key="secret-test-key",
            timeout=1,
            expected_model="model-a",
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

        self.assertTrue(
            all(
                result.status is ResultStatus.PASS
                for result in results
            )
        )

        self.assertTrue(
            results[-1].evidence[
                "target_model_found"
            ]
        )

        self.assertEqual(
            BasicHandler.calls,
            [
                (
                    "/v1/models",
                    "Bearer secret-test-key",
                )
            ],
        )

    def test_anonymous_basic_marks_auth_not_applicable(self):
        results = run_basic_diagnostics(
            self.base + "/v1",
            timeout=1,
            authentication_requested=False,
        )

        auth_result = next(
            result
            for result in results
            if result.name == "auth"
        )

        self.assertEqual(
            auth_result.status,
            ResultStatus.PASS,
        )

        self.assertEqual(
            auth_result.support,
            SupportStatus.NOT_APPLICABLE,
        )

        self.assertEqual(
            BasicHandler.calls,
            [
                (
                    "/v1/models",
                    None,
                )
            ],
        )

    def test_invalid_url_stops_before_network(self):
        results = run_basic_diagnostics(
            "ftp://example.com"
        )

        self.assertEqual(
            len(results),
            1,
        )

        self.assertEqual(
            results[0].name,
            "url",
        )

        self.assertEqual(
            results[0].status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            results[0].error_code,
            "INVALID_URL",
        )

        self.assertEqual(
            BasicHandler.calls,
            [],
        )

    def test_auth_failure_is_separate_from_http_connectivity(self):
        results = run_basic_diagnostics(
            self.base + "/unauthorized",
            key="bad-key",
            timeout=1,
        )

        by_name = {
            result.name: result
            for result in results
        }

        self.assertEqual(
            by_name["http"].status,
            ResultStatus.PASS,
        )

        self.assertEqual(
            by_name["http"].evidence[
                "http_status"
            ],
            401,
        )

        self.assertEqual(
            by_name["auth"].status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            by_name["auth"].error_code,
            "AUTH_INVALID",
        )

        self.assertEqual(
            by_name["models"].status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            BasicHandler.calls,
            [
                (
                    "/unauthorized/models",
                    "Bearer bad-key",
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()