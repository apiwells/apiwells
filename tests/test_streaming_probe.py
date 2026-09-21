"""Tests for SSE parsing used by the Streaming probe."""

import pytest

from apiwells.probes.streaming import (
    SSEParseError,
    SSEParser,
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