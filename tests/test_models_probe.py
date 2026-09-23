import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from apiwells.models import ResultStatus, SupportStatus
from apiwells.probes import AuthProbe, HTTPProbe, ModelsProbe
from apiwells.probes.models import build_models_observation
from apiwells.runner import DoctorRunner


class ModelsHandler(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        ModelsHandler.calls.append(
            (
                self.path,
                self.headers.get("Authorization"),
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

        elif prefix == "partial":
            raw = json.dumps(
                {
                    "data": [
                        {"id": "model-a"},
                        {},
                    ]
                }
            ).encode()

        elif prefix == "secret":
            raw = json.dumps(
                {
                    "data": [
                        {"id": "secret-test-key"},
                    ]
                }
            ).encode()

        else:
            raw = json.dumps(
                {
                    "data": [
                        {"id": "model-a"},
                        {"id": "model-b"},
                    ]
                }
            ).encode()

        self.wfile.write(raw)


class ModelsProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            ModelsHandler,
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
        ModelsHandler.calls.clear()

    def test_valid_models_pass(self):
        result = ModelsProbe(
            self.base + "/valid",
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.PASS,
        )

        self.assertEqual(
            result.support,
            SupportStatus.SUPPORTED,
        )

        self.assertEqual(
            result.metrics["model_count"],
            2,
        )

        self.assertEqual(
            result.evidence["http_status"],
            200,
        )

    def test_expected_model_found(self):
        result = ModelsProbe(
            self.base + "/valid",
            expected_model="model-b",
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.PASS,
        )

        self.assertTrue(
            result.evidence["target_model_found"]
        )

    def test_expected_model_missing_is_partial(self):
        result = ModelsProbe(
            self.base + "/valid",
            expected_model="missing-model",
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.PARTIAL,
        )

        self.assertEqual(
            result.support,
            SupportStatus.SUPPORTED,
        )

        self.assertFalse(
            result.evidence["target_model_found"]
        )

    def test_partial_schema_is_partial(self):
        result = ModelsProbe(
            self.base + "/partial",
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.PARTIAL,
        )

        self.assertEqual(
            result.support,
            SupportStatus.SUPPORTED,
        )

        self.assertEqual(
            result.metrics["model_count"],
            1,
        )

        self.assertEqual(
            result.evidence["invalid_model_entries"],
            1,
        )

    def test_invalid_json_fails(self):
        result = ModelsProbe(
            self.base + "/invalid",
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

    def test_http_failure_is_not_retried(self):
        result = ModelsProbe(
            self.base + "/http500",
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
            result.error_code,
            "UPSTREAM_5XX",
        )

        self.assertEqual(
            len(ModelsHandler.calls),
            1,
        )

    def test_secret_is_not_stored_in_result(self):
        result = ModelsProbe(
            self.base + "/secret",
            key="secret-test-key",
        ).run()

        self.assertEqual(
            ModelsHandler.calls[-1][1],
            "Bearer secret-test-key",
        )

        self.assertNotIn(
            "secret-test-key",
            repr(result),
        )

    def test_models_probe_runs_under_doctor_runner(self):
        runner = DoctorRunner(
            [
                ModelsProbe(
                    self.base + "/valid"
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
            "models",
        )

        self.assertEqual(
            results[0].status,
            ResultStatus.PASS,
        )

    def test_http_auth_and_models_share_one_request(self):
        observation = build_models_observation(
            self.base + "/valid",
            key="secret-test-key",
            timeout=1,
        )

        runner = DoctorRunner(
            [
                HTTPProbe(
                    observation
                ),
                AuthProbe(
                    observation
                ),
                ModelsProbe(
                    observation=observation,
                    expected_model="model-a",
                ),
            ]
        )

        results = runner.run()

        self.assertEqual(
            [result.name for result in results],
            [
                "http",
                "auth",
                "models",
            ],
        )

        self.assertEqual(
            results[0].status,
            ResultStatus.PASS,
        )

        self.assertEqual(
            results[1].status,
            ResultStatus.PASS,
        )

        self.assertEqual(
            results[2].status,
            ResultStatus.PASS,
        )

        self.assertTrue(
            results[2].evidence[
                "target_model_found"
            ]
        )

        self.assertEqual(
            len(ModelsHandler.calls),
            1,
        )

        self.assertEqual(
            ModelsHandler.calls[0][0],
            "/valid/models",
        )

        self.assertEqual(
            ModelsHandler.calls[0][1],
            "Bearer secret-test-key",
        )

if __name__ == "__main__":
    unittest.main()