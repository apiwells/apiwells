"""Tests for the Tool Calling round-trip probe."""

import copy
import json
from dataclasses import asdict
from unittest.mock import patch

import pytest
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
                                    "The result is " + next(
                                        message["content"]
                                        for message in payload["messages"]
                                        if message.get("role") == "tool"
                                    )
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
                                            '{"challenge":"apiwells-tool-check"}'
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
                                        "name": "get_diagnostic_value",
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
                                        "name": "get_diagnostic_value",
                                        "arguments": (
                                            '{}'
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
                                        "name": "get_diagnostic_value",
                                        "arguments": (
                                            '{"challenge":"apiwells-tool-check"}'
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

        self.assertRegex(
            result.evidence["local_tool_result"],
            r"^apiwells-[0-9a-f]{16}$",
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
            "get_diagnostic_value",
        )

        self.assertNotIn(
            "tool_choice",
            first_payload,
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
            result.evidence["local_tool_result"],
        )

    def test_missing_tool_call_keeps_support_unknown(self):
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
            SupportStatus.UNKNOWN,
        )

        self.assertEqual(
            result.error_code,
            "TOOL_CALL_INVALID",
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


def diagnostic_message():
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": "call-diagnostic",
            "type": "function",
            "function": {
                "name": "get_diagnostic_value",
                "arguments": '{"challenge":"apiwells-tool-check"}',
            },
        }],
    }


@pytest.mark.parametrize("reasoning", [None, "fixture-private-reasoning"])
def test_runtime_round_trip_preserves_complete_message(reasoning):
    first_message = diagnostic_message()
    first_message["content"] = "fixture-private-content"
    first_message["provider_metadata"] = {"trace": ["fixture-private-metadata"]}
    if reasoning is not None:
        first_message["reasoning_content"] = reasoning
    original_message = copy.deepcopy(first_message)
    probe = ToolCallingProbe(
        "https://example.invalid/v1",
        model="demo-model",
        key="fixture-api-key",
    )
    payloads = []
    values = ["apiwells-" + digit * 16 for digit in ("a", "b")]

    with patch(
        "apiwells.probes.tools.secrets.token_hex",
        side_effect=["a" * 16, "b" * 16],
    ) as token_hex:
        def respond(payload):
            payloads.append(copy.deepcopy(payload))
            run_index = (len(payloads) - 1) // 2
            if len(payloads) % 2:
                # The value is generated only after the call is validated.
                assert token_hex.call_count == run_index
                assert payload["messages"] == [{
                    "role": "user",
                    "content": payload["messages"][0]["content"],
                }]
                assert "tool_choice" not in payload
                assert payload["tools"][0]["function"]["name"] == (
                    "get_diagnostic_value"
                )
                assert payload["tools"][0]["function"]["parameters"] == {
                    "type": "object",
                    "properties": {"challenge": {"type": "string"}},
                    "required": ["challenge"],
                    "additionalProperties": False,
                }
                for value in values:
                    assert value not in json.dumps(payload)
                return 200, {"choices": [{"message": first_message}]}, None

            assert token_hex.call_count == run_index + 1
            token_hex.assert_called_with(8)
            assert "tool_choice" not in payload
            assert payload["tools"] == payloads[-2]["tools"]
            assert payload["messages"] == [
                payloads[-2]["messages"][0],
                original_message,
                {
                    "role": "tool",
                    "tool_call_id": "call-diagnostic",
                    "content": values[run_index],
                },
            ]
            return 200, {"choices": [{"message": {
                "role": "assistant",
                "content": "The result is " + values[run_index],
            }}]}, None

        with patch.object(probe, "_request_json", side_effect=respond):
            results = [probe.run(), probe.run()]

    assert first_message == original_message
    assert token_hex.call_count == 2
    assert len(payloads) == 4
    for result, value in zip(results, values):
        assert result.status == ResultStatus.PASS
        assert result.support == SupportStatus.SUPPORTED
        assert result.metrics["request_count"] == 2
        assert result.evidence["local_tool_result"] == value
        assert result.evidence["round_trip_completed"] is True
        reportable = json.dumps(asdict(result))
        for private in (
            "fixture-api-key", "fixture-private-content",
            "fixture-private-metadata", "fixture-private-reasoning",
        ):
            assert private not in reportable
            assert private not in repr(result)


@pytest.mark.parametrize("arguments", [
    '{"challenge":"wrong-challenge"}',
    '{"challenge":"apiwells-tool-check "}',
    '{"challenge":17}',
    '{"challenge":true}',
    '{"challenge":null}',
    '{"challenge":["apiwells-tool-check"]}',
    '{"challenge":{"value":"apiwells-tool-check"}}',
    '{"challenge":"apiwells-tool-check","extra":1}',
    '{}',
    '[]',
    '"apiwells-tool-check"',
    'null',
    '{not-json}',
    {"challenge": "apiwells-tool-check"},
])
def test_invalid_challenge_stops_before_execution(arguments):
    message = diagnostic_message()
    message["tool_calls"][0]["function"]["arguments"] = arguments
    probe = ToolCallingProbe("https://example.invalid/v1", model="demo-model")
    with (
        patch.object(probe, "_request_json", return_value=(
            200, {"choices": [{"message": message}]}, None,
        )) as request,
        patch("apiwells.probes.tools.secrets.token_hex") as token_hex,
    ):
        result = probe.run()
    assert result.status == ResultStatus.FAIL
    assert result.support == SupportStatus.UNKNOWN
    assert result.error_code == "TOOL_CALL_INVALID"
    assert result.evidence["round_trip_completed"] is False
    assert result.metrics["request_count"] == 1
    request.assert_called_once()
    token_hex.assert_not_called()


@pytest.mark.parametrize("field,value", [
    ("id", None),
    ("id", ""),
    ("id", " "),
    ("id", 17),
    ("type", "unexpected"),
    ("function", None),
    ("function", {"name": "wrong_tool", "arguments": "{}"}),
])
def test_malformed_tool_call_stops_before_execution(field, value):
    message = diagnostic_message()
    message["tool_calls"][0][field] = value
    probe = ToolCallingProbe("https://example.invalid/v1", model="demo-model")
    with patch.object(probe, "_request_json", return_value=(
        200, {"choices": [{"message": message}]}, None,
    )) as request:
        result = probe.run()
    assert result.status == ResultStatus.FAIL
    assert result.support == SupportStatus.UNKNOWN
    assert result.error_code == "TOOL_CALL_INVALID"
    request.assert_called_once()


@pytest.mark.parametrize("calls", [[], None, [None], [
    diagnostic_message()["tool_calls"][0],
    diagnostic_message()["tool_calls"][0],
]])
def test_tool_call_count_validation(calls):
    message = diagnostic_message()
    message["tool_calls"] = calls
    probe = ToolCallingProbe("https://example.invalid/v1", model="demo-model")
    with patch.object(probe, "_request_json", return_value=(
        200, {"choices": [{"message": message}]}, None,
    )) as request:
        result = probe.run()
    assert result.status == (ResultStatus.FAIL if calls else ResultStatus.PARTIAL)
    assert result.support == SupportStatus.UNKNOWN
    assert result.error_code == "TOOL_CALL_INVALID"
    request.assert_called_once()


@pytest.mark.parametrize("content", [
    "42",
    "I received the result.",
    "apiwells-tool-check",
    "apiwells-ffffffffffffffff",
    "apiwells-0123456789abcde",
    "apiwells-0123456789ABCDEf",
    "",
    None,
    ["apiwells-0123456789abcdef"],
])
def test_final_answer_requires_exact_runtime_value(content):
    probe = ToolCallingProbe(
        "https://example.invalid/v1", model="demo-model", key="fixture-api-key",
    )
    with (
        patch("apiwells.probes.tools.secrets.token_hex", return_value=(
            "0123456789abcdef"
        )),
        patch.object(probe, "_request_json", side_effect=[
            (200, {"choices": [{"message": diagnostic_message()}]}, None),
            (200, {"choices": [{"message": {
                "role": "assistant", "content": content,
            }}]}, None),
        ]) as request,
    ):
        result = probe.run()
    assert result.status == ResultStatus.FAIL
    assert result.support == SupportStatus.SUPPORTED
    assert result.error_code == "TOOL_CALL_INVALID"
    assert result.evidence["round_trip_completed"] is False
    assert result.metrics["request_count"] == 2
    assert request.call_count == 2
    assert "fixture-api-key" not in json.dumps(asdict(result))


def test_second_request_failure_is_not_retried_or_reported_as_pass():
    probe = ToolCallingProbe("https://example.invalid/v1", model="demo-model")
    with patch.object(probe, "_request_json", side_effect=[
        (200, {"choices": [{"message": diagnostic_message()}]}, None),
        (500, None, "UPSTREAM_5XX"),
    ]) as request:
        result = probe.run()
    assert result.status == ResultStatus.FAIL
    assert result.support == SupportStatus.SUPPORTED
    assert result.error_code == "UPSTREAM_5XX"
    assert result.evidence["round_trip_completed"] is False
    assert request.call_count == 2


if __name__ == "__main__":
    unittest.main()