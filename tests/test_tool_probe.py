"""Tests for the Tool Calling round-trip probe."""

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
from apiwells.probes.tools import ToolCallingProbe


class ToolHandler(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *args):
        pass

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

        ToolHandler.calls.append(
            (
                self.path,
                self.headers.get(
                    "Authorization"
                ),
                payload,
            )
        )

        prefix = self.path.split("/")[1]

        if prefix == "http500":
            self.send_response(500)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header(
            "Content-Type",
            "application/json",
        )
        self.end_headers()

        is_second_request = any(
            isinstance(message, dict)
            and message.get("role") == "tool"
            for message in payload.get(
                "messages",
                []
            )
        )

        if is_second_request:
            if prefix == "badfinal":
                raw = {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "I received the result.",
                            }
                        }
                    ]
                }

            else:
                raw = {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": (
                                    "The result is 42."
                                ),
                            }
                        }
                    ]
                }

            self.wfile.write(
                json.dumps(raw).encode()
            )
            return

        if prefix == "unsupported":
            raw = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "42",
                        }
                    }
                ]
            }

        elif prefix == "badname":
            raw = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "wrong_tool",
                                        "arguments": (
                                            '{"a":17,"b":25}'
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }

        elif prefix == "badjson":
            raw = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "add_numbers",
                                        "arguments": (
                                            "{not-json}"
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }

        elif prefix == "badargs":
            raw = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "add_numbers",
                                        "arguments": (
                                            '{"a":17}'
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }

        else:
            raw = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "add_numbers",
                                        "arguments": (
                                            '{"a":17,"b":25}'
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }

        self.wfile.write(
            json.dumps(raw).encode()
        )


class ToolCallingProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            ToolHandler,
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
        ToolHandler.calls.clear()

    def test_valid_tool_round_trip_passes(self):
        result = ToolCallingProbe(
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

        self.assertTrue(
            result.evidence[
                "round_trip_completed"
            ]
        )

        self.assertEqual(
            result.evidence[
                "local_tool_result"
            ],
            42,
        )

        self.assertEqual(
            result.metrics[
                "request_count"
            ],
            2,
        )

        self.assertEqual(
            len(ToolHandler.calls),
            2,
        )

        first_payload = (
            ToolHandler.calls[0][2]
        )

        second_payload = (
            ToolHandler.calls[1][2]
        )

        self.assertEqual(
            first_payload["model"],
            "demo-model",
        )

        self.assertFalse(
            first_payload["stream"]
        )

        self.assertEqual(
            first_payload["tools"][0]
            ["function"]["name"],
            "add_numbers",
        )

        self.assertEqual(
            first_payload[
                "tool_choice"
            ]["function"]["name"],
            "add_numbers",
        )

        tool_messages = [
            message
            for message in second_payload[
                "messages"
            ]
            if message.get("role")
            == "tool"
        ]

        self.assertEqual(
            len(tool_messages),
            1,
        )

        self.assertEqual(
            tool_messages[0][
                "tool_call_id"
            ],
            "call-1",
        )

        self.assertEqual(
            tool_messages[0][
                "content"
            ],
            "42",
        )

    def test_missing_tool_call_is_unsupported(self):
        result = ToolCallingProbe(
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
            result.error_code,
            "FEATURE_UNSUPPORTED",
        )

        self.assertEqual(
            len(ToolHandler.calls),
            1,
        )

    def test_wrong_tool_name_fails(self):
        result = ToolCallingProbe(
            self.base + "/badname",
            model="demo-model",
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            result.error_code,
            "TOOL_CALL_INVALID",
        )

        self.assertEqual(
            len(ToolHandler.calls),
            1,
        )

    def test_invalid_tool_arguments_json_fails(self):
        result = ToolCallingProbe(
            self.base + "/badjson",
            model="demo-model",
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            result.error_code,
            "TOOL_CALL_INVALID",
        )

    def test_invalid_tool_argument_schema_fails(self):
        result = ToolCallingProbe(
            self.base + "/badargs",
            model="demo-model",
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            result.error_code,
            "TOOL_CALL_INVALID",
        )

    def test_final_answer_must_use_tool_result(self):
        result = ToolCallingProbe(
            self.base + "/badfinal",
            model="demo-model",
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            result.support,
            SupportStatus.SUPPORTED,
        )

        self.assertEqual(
            result.error_code,
            "TOOL_CALL_INVALID",
        )

        self.assertEqual(
            len(ToolHandler.calls),
            2,
        )

    def test_http_failure_is_not_retried(self):
        result = ToolCallingProbe(
            self.base + "/http500",
            model="demo-model",
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            result.error_code,
            "UPSTREAM_5XX",
        )

        self.assertEqual(
            len(ToolHandler.calls),
            1,
        )

    def test_secret_is_not_stored_in_result(self):
        result = ToolCallingProbe(
            self.base + "/valid",
            model="demo-model",
            key="secret-test-key",
        ).run()

        self.assertEqual(
            ToolHandler.calls[0][1],
            "Bearer secret-test-key",
        )

        self.assertEqual(
            ToolHandler.calls[1][1],
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
            ToolCallingProbe(
                self.base + "/valid",
                model="",
            )


if __name__ == "__main__":
    unittest.main()