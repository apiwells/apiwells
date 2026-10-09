"""Tests for the Structured Output capability probe."""

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
from apiwells.probes.structured import StructuredOutputProbe


class StructuredHandler(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *args):
        pass

    def _send_json(
        self,
        status: int,
        payload: dict,
    ) -> None:
        raw = json.dumps(payload).encode("utf-8")

        self.send_response(status)
        self.send_header(
            "Content-Type",
            "application/json",
        )
        self.end_headers()
        self.wfile.write(raw)

    @staticmethod
    def _completion(content: str) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": content,
                    }
                }
            ]
        }

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

        prefix = self.path.split("/")[1]

        StructuredHandler.calls.append(
            (
                self.path,
                self.headers.get(
                    "Authorization"
                ),
                payload,
            )
        )

        response_format = payload.get(
            "response_format",
            {},
        )

        format_type = response_format.get(
            "type"
        )

        # Transient/upstream failure must NOT trigger
        # a json_object fallback request.
        if prefix == "http500":
            self._send_json(
                500,
                {
                    "error": {
                        "message": "temporary upstream failure"
                    }
                },
            )
            return

        # A generic client error does not prove that
        # json_schema itself is unsupported.
        if prefix == "unrelated400":
            self._send_json(
                400,
                {
                    "error": {
                        "message": "invalid unrelated parameter"
                    }
                },
            )
            return

        if prefix in {"authfeature", "ratefeature"}:
            self._send_json(
                401 if prefix == "authfeature" else 429,
                {
                    "error": {
                        "message": (
                            "response_format type is unavailable now"
                        )
                    }
                },
            )
            return

        # A feature-related rejection permits the independent
        # json_object sub-test without proving permanent non-support.
        if prefix == "unavailablenow":
            if format_type == "json_schema":
                self._send_json(
                    400,
                    {
                        "error": {
                            "code": "invalid_request_error",
                            "type": "invalid_request_error",
                            "message": (
                                "This response_format type is "
                                "unavailable now "
                                "fixture-provider-secret"
                            ),
                        }
                    },
                )
                return

            if format_type == "json_object":
                self._send_json(
                    200,
                    self._completion(
                        '{"diagnostic":42}'
                    ),
                )
                return

        # json_schema is explicitly unsupported, but
        # legacy json_object mode works.
        if prefix == "jsonobjectonly":
            if format_type == "json_schema":
                self._send_json(
                    400,
                    {
                        "error": {
                            "message": (
                                "response_format type "
                                "json_schema is not supported"
                            )
                        }
                    },
                )
                return

            if format_type == "json_object":
                self._send_json(
                    200,
                    self._completion(
                        '{"name":"diagnostic","value":42}'
                    ),
                )
                return

        if prefix in {
            "jsonobjectinvalid",
            "jsonobjectnonobject",
        }:
            if format_type == "json_schema":
                self._send_json(
                    400,
                    {
                        "error": {
                            "message": (
                                "response_format type json_schema "
                                "is not supported"
                            )
                        }
                    },
                )
                return

            content = (
                "not-json"
                if prefix == "jsonobjectinvalid"
                else "[1, 2, 3]"
            )
            self._send_json(
                200,
                self._completion(content),
            )
            return

        # Neither structured mode is supported.
        if prefix == "unsupported":
            self._send_json(
                400,
                {
                    "error": {
                        "message": (
                            "response_format type "
                            f"{format_type} is not supported"
                        )
                    }
                },
            )
            return

        # Provider accepted json_schema but returned
        # content that violates the requested schema.
        if prefix == "typeviolation":
            self._send_json(
                200,
                self._completion(
                    '{"name":"diagnostic","value":"42"}'
                ),
            )
            return

        if prefix == "extraproperty":
            self._send_json(
                200,
                self._completion(
                    (
                        '{"name":"diagnostic",'
                        '"value":42,'
                        '"extra":true}'
                    )
                ),
            )
            return

        if prefix == "invalidcontent":
            self._send_json(
                200,
                self._completion(
                    "this is not json"
                ),
            )
            return

        # Normal strict json_schema success.
        self._send_json(
            200,
            self._completion(
                '{"name":"diagnostic","value":42}'
            ),
        )


class StructuredOutputProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            StructuredHandler,
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
        StructuredHandler.calls.clear()

    def test_json_schema_success_passes(self):
        result = StructuredOutputProbe(
            self.base + "/valid",
            model="demo-model",
            key="secret-test-key",
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
            result.evidence["outcome"],
            "supported",
        )

        self.assertTrue(
            result.evidence[
                "json_schema_request_accepted"
            ]
        )

        self.assertTrue(
            result.evidence[
                "schema_validation_passed"
            ]
        )

        self.assertEqual(
            result.metrics["request_count"],
            1,
        )

        self.assertEqual(
            len(StructuredHandler.calls),
            1,
        )

        payload = StructuredHandler.calls[0][2]

        self.assertEqual(
            payload["model"],
            "demo-model",
        )

        self.assertFalse(
            payload["stream"]
        )

        response_format = payload[
            "response_format"
        ]

        self.assertEqual(
            response_format["type"],
            "json_schema",
        )

        json_schema = response_format[
            "json_schema"
        ]

        self.assertEqual(
            json_schema["name"],
            "apiwells_diagnostic",
        )

        self.assertTrue(
            json_schema["strict"]
        )

        schema = json_schema["schema"]

        self.assertEqual(
            schema["type"],
            "object",
        )

        self.assertEqual(
            set(schema["required"]),
            {
                "name",
                "value",
            },
        )

        self.assertFalse(
            schema["additionalProperties"]
        )

    def test_schema_type_violation_is_invalid_implementation(self):
        result = StructuredOutputProbe(
            self.base + "/typeviolation",
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
            result.evidence["outcome"],
            "invalid_implementation",
        )

        self.assertEqual(
            result.error_code,
            "STRUCTURED_OUTPUT_INVALID",
        )

        self.assertEqual(
            len(StructuredHandler.calls),
            1,
        )

    def test_extra_property_is_invalid_implementation(self):
        result = StructuredOutputProbe(
            self.base + "/extraproperty",
            model="demo-model",
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            result.evidence["outcome"],
            "invalid_implementation",
        )

        self.assertEqual(
            result.error_code,
            "STRUCTURED_OUTPUT_INVALID",
        )

        self.assertEqual(
            len(StructuredHandler.calls),
            1,
        )

    def test_non_json_content_is_invalid_implementation(self):
        result = StructuredOutputProbe(
            self.base + "/invalidcontent",
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
            result.evidence["outcome"],
            "invalid_implementation",
        )

        self.assertEqual(
            result.error_code,
            "STRUCTURED_OUTPUT_INVALID",
        )

        self.assertEqual(
            len(StructuredHandler.calls),
            1,
        )

    def test_json_object_only_is_partial(self):
        result = StructuredOutputProbe(
            self.base + "/jsonobjectonly",
            model="demo-model",
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.PARTIAL,
        )

        self.assertEqual(
            result.support,
            SupportStatus.UNSUPPORTED,
        )

        self.assertEqual(
            result.evidence["outcome"],
            "json_object_only",
        )

        self.assertFalse(
            result.evidence[
                "json_schema_request_accepted"
            ]
        )

        self.assertTrue(
            result.evidence[
                "json_object_request_accepted"
            ]
        )

        self.assertEqual(
            result.error_code,
            "FEATURE_UNSUPPORTED",
        )

        self.assertEqual(
            result.evidence["json_schema_support"],
            "UNSUPPORTED",
        )

        self.assertEqual(
            result.evidence["json_object_support"],
            "SUPPORTED",
        )

        self.assertEqual(
            result.metrics["request_count"],
            2,
        )

        self.assertEqual(
            len(StructuredHandler.calls),
            2,
        )

        first_payload = (
            StructuredHandler.calls[0][2]
        )

        second_payload = (
            StructuredHandler.calls[1][2]
        )

        self.assertEqual(
            first_payload[
                "response_format"
            ]["type"],
            "json_schema",
        )

        self.assertEqual(
            second_payload[
                "response_format"
            ]["type"],
            "json_object",
        )

        user_content = (
            second_payload["messages"][0][
                "content"
            ]
        )

        self.assertIn(
            "JSON",
            user_content,
        )

    def test_feature_rejection_still_tests_json_object(self):
        result = StructuredOutputProbe(
            self.base + "/unavailablenow",
            model="demo-model",
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.PARTIAL,
        )
        self.assertEqual(
            result.support,
            SupportStatus.UNKNOWN,
        )
        self.assertIsNone(result.error_code)
        self.assertEqual(
            result.metrics["request_count"],
            2,
        )
        self.assertEqual(
            result.evidence["json_schema_rejection"],
            "feature_rejected",
        )
        self.assertEqual(
            result.evidence["json_schema_support"],
            "UNKNOWN",
        )
        self.assertTrue(
            result.evidence["json_object_tested"]
        )
        self.assertEqual(
            result.evidence["json_object_support"],
            "SUPPORTED",
        )
        self.assertTrue(
            result.evidence["json_object_json_parsed"]
        )
        self.assertTrue(
            result.evidence["json_object_is_object"]
        )
        self.assertEqual(
            len(StructuredHandler.calls),
            2,
        )
        self.assertNotIn(
            "fixture-provider-secret",
            repr(result),
        )

    def test_json_object_invalid_json_keeps_support_unknown(self):
        result = StructuredOutputProbe(
            self.base + "/jsonobjectinvalid",
            model="demo-model",
        ).run()

        self.assertEqual(result.status, ResultStatus.FAIL)
        self.assertEqual(
            result.evidence["json_schema_support"],
            "UNSUPPORTED",
        )
        self.assertEqual(
            result.evidence["json_object_support"],
            "UNKNOWN",
        )
        self.assertFalse(
            result.evidence["json_object_json_parsed"]
        )
        self.assertIsNone(
            result.evidence["json_object_is_object"]
        )
        self.assertEqual(
            result.metrics["request_count"],
            2,
        )

    def test_json_object_non_object_keeps_support_unknown(self):
        result = StructuredOutputProbe(
            self.base + "/jsonobjectnonobject",
            model="demo-model",
        ).run()

        self.assertEqual(result.status, ResultStatus.FAIL)
        self.assertEqual(
            result.evidence["json_object_support"],
            "UNKNOWN",
        )
        self.assertTrue(
            result.evidence["json_object_json_parsed"]
        )
        self.assertFalse(
            result.evidence["json_object_is_object"]
        )
        self.assertEqual(
            result.metrics["request_count"],
            2,
        )

    def test_both_modes_unsupported_is_partial(self):
        result = StructuredOutputProbe(
            self.base + "/unsupported",
            model="demo-model",
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.PARTIAL,
        )

        self.assertEqual(
            result.support,
            SupportStatus.UNSUPPORTED,
        )

        self.assertEqual(
            result.evidence["outcome"],
            "unsupported",
        )

        self.assertEqual(
            result.error_code,
            "FEATURE_UNSUPPORTED",
        )

        self.assertEqual(
            result.metrics["request_count"],
            2,
        )

        self.assertEqual(
            len(StructuredHandler.calls),
            2,
        )

    def test_http_500_does_not_trigger_fallback(self):
        result = StructuredOutputProbe(
            self.base + "/http500",
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
            "UPSTREAM_5XX",
        )

        self.assertEqual(
            result.metrics["request_count"],
            1,
        )

        self.assertEqual(
            len(StructuredHandler.calls),
            1,
        )

    def test_unrelated_400_does_not_trigger_fallback(self):
        result = StructuredOutputProbe(
            self.base + "/unrelated400",
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
            result.metrics["request_count"],
            1,
        )

        self.assertEqual(
            len(StructuredHandler.calls),
            1,
        )

        self.assertFalse(
            result.evidence["json_object_tested"]
        )

    def test_auth_and_rate_limit_do_not_trigger_fallback(self):
        for path, error_code in (
            ("authfeature", "AUTH_INVALID"),
            ("ratefeature", "RATE_LIMITED"),
        ):
            with self.subTest(path=path):
                StructuredHandler.calls.clear()
                result = StructuredOutputProbe(
                    self.base + "/" + path,
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
                    error_code,
                )
                self.assertEqual(
                    result.metrics["request_count"],
                    1,
                )
                self.assertEqual(
                    len(StructuredHandler.calls),
                    1,
                )
                self.assertFalse(
                    result.evidence["json_object_tested"]
                )

    def test_secret_is_not_stored_in_result(self):
        result = StructuredOutputProbe(
            self.base + "/valid",
            model="demo-model",
            key="secret-test-key",
        ).run()

        self.assertEqual(
            StructuredHandler.calls[0][1],
            "Bearer secret-test-key",
        )

        self.assertNotIn(
            "secret-test-key",
            repr(result),
        )

    def test_requires_nonempty_model(self):
        with self.assertRaises(
            ValueError
        ):
            StructuredOutputProbe(
                self.base + "/valid",
                model="",
            )


if __name__ == "__main__":
    unittest.main()
