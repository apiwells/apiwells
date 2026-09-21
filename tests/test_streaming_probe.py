"""Tests for SSE parsing and the Streaming probe."""

import json
import threading
import unittest

import pytest

from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from unittest.mock import patch

from apiwells.models import (
    ResultStatus,
    SupportStatus,
)
from apiwells.probes.streaming import (
    SSEParseError,
    SSEParser,
    StreamingProbe,
)


def collect_events(lines):
    """Feed lines into a parser and collect emitted SSE events."""

    parser = SSEParser()
    events = []

    for line in lines:
        event = parser.feed_line(line)

        if event is not None:
            events.append(event)

    return parser, events


def test_sse_parser_accepts_lf_boundary():
    parser, events = collect_events(
        [
            b'data: {"value":1}\n',
            b"\n",
        ]
    )

    assert [event.data for event in events] == [
        '{"value":1}'
    ]
    assert parser.has_pending_event is False


def test_sse_parser_accepts_crlf_boundary():
    parser, events = collect_events(
        [
            b'data: {"value":1}\r\n',
            b"\r\n",
        ]
    )

    assert [event.data for event in events] == [
        '{"value":1}'
    ]
    assert parser.has_pending_event is False


def test_sse_parser_joins_multiple_data_lines():
    parser, events = collect_events(
        [
            b"data: first\n",
            b"data: second\n",
            b"\n",
        ]
    )

    assert [event.data for event in events] == [
        "first\nsecond"
    ]
    assert parser.has_pending_event is False


def test_sse_parser_returns_multiple_events():
    parser, events = collect_events(
        [
            b"data: one\n",
            b"\n",
            b"data: two\n",
            b"\n",
        ]
    )

    assert [event.data for event in events] == [
        "one",
        "two",
    ]
    assert parser.has_pending_event is False


def test_sse_parser_ignores_comments():
    parser, events = collect_events(
        [
            b": keepalive\n",
            b"\n",
        ]
    )

    assert events == []
    assert parser.has_pending_event is False


def test_sse_parser_ignores_unknown_fields():
    parser, events = collect_events(
        [
            b"event: message\n",
            b"id: 123\n",
            b"retry: 1000\n",
            b"data: hello\n",
            b"\n",
        ]
    )

    assert [event.data for event in events] == [
        "hello"
    ]
    assert parser.has_pending_event is False


def test_sse_parser_preserves_done_event():
    parser, events = collect_events(
        [
            b"data: [DONE]\n",
            b"\n",
        ]
    )

    assert [event.data for event in events] == [
        "[DONE]"
    ]
    assert parser.has_pending_event is False


def test_sse_parser_rejects_invalid_utf8():
    parser = SSEParser()

    with pytest.raises(
        SSEParseError,
        match="valid UTF-8",
    ):
        parser.feed_line(
            b"data: \xff\n"
        )


def test_sse_parser_rejects_invalid_input_type():
    parser = SSEParser()

    with pytest.raises(
        TypeError,
        match="bytes or str",
    ):
        parser.feed_line(123)


def test_sse_parser_detects_pending_event():
    parser = SSEParser()

    event = parser.feed_line(
        b"data: unfinished\n"
    )

    assert event is None
    assert parser.has_pending_event is True


def test_sse_parser_clears_pending_event_after_boundary():
    parser = SSEParser()

    parser.feed_line(
        b"data: finished\n"
    )

    event = parser.feed_line(
        b"\n"
    )

    assert event is not None
    assert event.data == "finished"
    assert parser.has_pending_event is False


def test_sse_parser_accepts_data_field_without_colon():
    parser, events = collect_events(
        [
            b"data\n",
            b"\n",
        ]
    )

    assert [event.data for event in events] == [
        ""
    ]
    assert parser.has_pending_event is False


class StreamingHandler(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *args):
        pass

    def _write_lines(self, lines):
        for line in lines:
            self.wfile.write(line)
            self.wfile.flush()

    def do_POST(self):
        body = self.rfile.read(
            int(
                self.headers.get(
                    "Content-Length",
                    0,
                )
            )
        )

        StreamingHandler.calls.append(
            (
                self.path,
                self.headers.get(
                    "Authorization"
                ),
                self.headers.get(
                    "Accept"
                ),
                body,
            )
        )

        prefix = self.path.split("/")[1]

        if prefix == "http500":
            self.send_response(500)
            self.end_headers()
            return

        if prefix == "json":
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/json",
            )
            self.end_headers()

            self.wfile.write(
                json.dumps(
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
            )
            return

        content_type = (
            "application/octet-stream"
            if prefix == "wrongtype"
            else "text/event-stream"
        )

        self.send_response(200)
        self.send_header(
            "Content-Type",
            content_type,
        )
        self.end_headers()

        if prefix == "invalidjson":
            self._write_lines(
                [
                    b"data: {not-json}\n",
                    b"\n",
                ]
            )
            return

        if prefix == "pending":
            self._write_lines(
                [
                    (
                        b'data: {"choices":['
                        b'{"delta":{"content":"O"}}]}'
                    ),
                ]
            )
            return

        if prefix == "nooutput":
            self._write_lines(
                [
                    (
                        b'data: {"choices":['
                        b'{"delta":{"role":"assistant"}}]}\n'
                    ),
                    b"\n",
                    b"data: [DONE]\n",
                    b"\n",
                ]
            )
            return

        role_event = (
            b'data: {"choices":['
            b'{"delta":{"role":"assistant"}}]}\n'
        )

        content_event = (
            b'data: {"choices":['
            b'{"delta":{"content":"O"}}]}\n'
        )

        lines = [
            b"data:\n",
            b"\n",
            role_event,
            b"\n",
            content_event,
            b"\n",
        ]

        if prefix != "nodone":
            lines.extend(
                [
                    b"data: [DONE]\n",
                    b"\n",
                ]
            )

        self._write_lines(lines)


class StreamingProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            StreamingHandler,
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
        StreamingHandler.calls.clear()

    def test_valid_stream_passes_and_measures_ttft(self):
        with patch(
            "apiwells.probes.streaming.time.monotonic",
            side_effect=[
                10.0,
                10.25,
                10.90,
            ],
        ):
            result = StreamingProbe(
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

        self.assertEqual(
            result.metrics["ttft_ms"],
            250.0,
        )

        self.assertEqual(
            result.metrics["total_latency_ms"],
            900.0,
        )

        self.assertEqual(
            result.metrics["chunk_count"],
            2,
        )

        self.assertTrue(
            result.evidence["content_received"]
        )

        self.assertTrue(
            result.evidence["terminal_event_seen"]
        )

        self.assertFalse(
            result.evidence["usage_available"]
        )

        body = json.loads(
            StreamingHandler.calls[-1][3]
        )

        self.assertEqual(
            body["model"],
            "demo-model",
        )

        self.assertTrue(
            body["stream"]
        )

        self.assertEqual(
            body["max_tokens"],
            8,
        )

        self.assertEqual(
            StreamingHandler.calls[-1][2],
            "text/event-stream",
        )

    def test_non_sse_json_is_reported_unsupported(self):
        result = StreamingProbe(
            self.base + "/json",
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

        self.assertFalse(
            result.evidence["content_received"]
        )

    def test_invalid_json_event_fails(self):
        result = StreamingProbe(
            self.base + "/invalidjson",
            model="demo-model",
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            result.error_code,
            "SSE_INVALID",
        )

    def test_clean_eof_without_done_is_partial(self):
        result = StreamingProbe(
            self.base + "/nodone",
            model="demo-model",
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.PARTIAL,
        )

        self.assertEqual(
            result.support,
            SupportStatus.SUPPORTED,
        )

        self.assertTrue(
            result.evidence["content_received"]
        )

        self.assertFalse(
            result.evidence["terminal_event_seen"]
        )

    def test_stream_without_model_output_fails(self):
        result = StreamingProbe(
            self.base + "/nooutput",
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
            "INVALID_SCHEMA",
        )

        self.assertIsNone(
            result.metrics["ttft_ms"]
        )

    def test_pending_sse_event_fails(self):
        result = StreamingProbe(
            self.base + "/pending",
            model="demo-model",
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            result.error_code,
            "SSE_INVALID",
        )

    def test_wrong_content_type_is_partial_but_supported(self):
        result = StreamingProbe(
            self.base + "/wrongtype",
            model="demo-model",
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.PARTIAL,
        )

        self.assertEqual(
            result.support,
            SupportStatus.SUPPORTED,
        )

        self.assertTrue(
            result.evidence["content_received"]
        )

        self.assertTrue(
            result.evidence["terminal_event_seen"]
        )

    def test_http_failure_is_not_retried(self):
        result = StreamingProbe(
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
            len(StreamingHandler.calls),
            1,
        )

    def test_secret_is_not_stored_in_result(self):
        result = StreamingProbe(
            self.base + "/valid",
            model="demo-model",
            key="secret-test-key",
        ).run()

        self.assertEqual(
            StreamingHandler.calls[-1][1],
            "Bearer secret-test-key",
        )

        self.assertNotIn(
            "secret-test-key",
            repr(result),
        )

    def test_interrupted_stream_is_classified(self):
        class InterruptingResponse:
            code = 200
            headers = {
                "Content-Type": "text/event-stream"
            }

            def __init__(self):
                self.calls = 0

            def __enter__(self):
                return self

            def __exit__(
                self,
                exc_type,
                exc,
                traceback,
            ):
                return False

            def readline(self, size=-1):
                self.calls += 1

                if self.calls == 1:
                    return (
                        b'data: {"choices":['
                        b'{"delta":{"content":"O"}}]}\n'
                    )

                if self.calls == 2:
                    return b"\n"

                raise OSError(
                    "simulated stream interruption"
                )

        with patch(
            "apiwells.probes.streaming.open_request",
            return_value=InterruptingResponse(),
        ):
            result = StreamingProbe(
                self.base + "/ignored",
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
            "STREAM_INTERRUPTED",
        )

        self.assertTrue(
            result.evidence["content_received"]
        )

        self.assertFalse(
            result.evidence["terminal_event_seen"]
        )

    def test_requires_nonempty_model(self):
        with self.assertRaises(ValueError):
            StreamingProbe(
                self.base + "/valid",
                model="",
            )


if __name__ == "__main__":
    unittest.main()