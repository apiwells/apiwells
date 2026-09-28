"""final Mock Integration gap-closure tests."""

import threading

from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)

import pytest

from apiwells.models import (
    ResultStatus,
    SupportStatus,
)
from apiwells.probes.models import ModelsProbe
from apiwells.probes.streaming import StreamingProbe
from apiwells.probes.structured import (
    StructuredOutputProbe,
)
from apiwells.probes.tools import ToolCallingProbe

from mock_server.server import (
    register_invalid_structured_schema_route,
    register_invalid_tool_arguments_route,
    register_models_status_route,
)


def mock_base_url(httpserver) -> str:
    return httpserver.url_for(
        "/v1"
    ).rstrip("/")


@pytest.mark.parametrize(
    (
        "status_code",
        "expected_error_code",
    ),
    [
        (301, "HTTP_REDIRECT"),
        (302, "HTTP_REDIRECT"),
        (404, "NOT_FOUND"),
        (502, "UPSTREAM_5XX"),
        (503, "UPSTREAM_5XX"),
    ],
)
def test_models_http_status_gap_cases(
    httpserver,
    status_code,
    expected_error_code,
):
    state = register_models_status_route(
        httpserver,
        status_code=status_code,
    )

    result = ModelsProbe(
        base_url=mock_base_url(
            httpserver
        ),
        timeout=2,
    ).run()

    assert (
        result.error_code
        == expected_error_code
    )

    assert (
        result.evidence["http_status"]
        == status_code
    )

    # Exactly one /models request:
    # no hidden retry.
    assert (
        state["models_request_count"]
        == 1
    )

    # Redirects must be exposed to Endpoint Doctor,
    # never automatically followed.
    if status_code in (301, 302):
        assert (
            state["redirect_target_count"]
            == 0
        )


def test_invalid_tool_arguments_over_real_http(
    httpserver,
):
    state = (
        register_invalid_tool_arguments_route(
            httpserver
        )
    )

    result = ToolCallingProbe(
        base_url=mock_base_url(
            httpserver
        ),
        model="test-model",
        timeout=2,
    ).run()

    assert (
        result.status
        is ResultStatus.FAIL
    )

    assert (
        result.error_code
        == "TOOL_CALL_INVALID"
    )

    # Invalid first tool call must stop immediately.
    assert (
        state["request_count"]
        == 1
    )


def test_invalid_structured_schema_over_real_http(
    httpserver,
):
    state = (
        register_invalid_structured_schema_route(
            httpserver
        )
    )

    result = StructuredOutputProbe(
        base_url=mock_base_url(
            httpserver
        ),
        model="test-model",
        timeout=2,
    ).run()

    assert (
        result.status
        is ResultStatus.FAIL
    )

    assert (
        result.support
        is SupportStatus.UNKNOWN
    )

    assert (
        result.error_code
        == "STRUCTURED_OUTPUT_INVALID"
    )

    assert (
        result.evidence["outcome"]
        == "invalid_implementation"
    )

    assert (
        state["request_count"]
        == 1
    )


class InterruptedSSEHandler(
    BaseHTTPRequestHandler
):
    """Real HTTP/1.1 endpoint that truncates a chunked SSE response."""

    protocol_version = "HTTP/1.1"

    calls = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        body_length = int(
            self.headers.get(
                "Content-Length",
                0,
            )
        )

        body = self.rfile.read(
            body_length
        )

        type(self).calls.append(
            (
                self.path,
                self.headers.get(
                    "Authorization"
                ),
                body,
            )
        )

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "text/event-stream",
        )

        self.send_header(
            "Transfer-Encoding",
            "chunked",
        )

        self.end_headers()

        # First send one complete valid SSE event.
        # This proves that model output was received before
        # the transport interruption.
        first_event = (
            b'data: {"choices":['
            b'{"delta":{"content":"O"}}]}\n\n'
        )

        first_chunk = (
            f"{len(first_event):X}\r\n".encode(
                "ascii"
            )
            + first_event
            + b"\r\n"
        )

        self.wfile.write(
            first_chunk
        )

        self.wfile.flush()

        # Announce a 256-byte HTTP chunk but intentionally
        # transmit only a small fragment, then close the
        # connection without completing the chunk.
        #
        # http.client therefore raises IncompleteRead,
        # which is an HTTPException handled by
        # StreamingProbe as STREAM_INTERRUPTED.
        self.wfile.write(
            b"100\r\n"
            b'data: {"choices":['
        )

        self.wfile.flush()

        self.close_connection = True


def test_stream_interruption_over_real_http():
    InterruptedSSEHandler.calls.clear()

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        InterruptedSSEHandler,
    )

    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )

    thread.start()

    base_url = (
        "http://127.0.0.1:"
        + str(server.server_port)
        + "/v1"
    )

    try:
        result = StreamingProbe(
            base_url=base_url,
            model="test-model",
            timeout=2,
        ).run()

    finally:
        server.shutdown()
        server.server_close()
        thread.join()

    assert (
        len(
            InterruptedSSEHandler.calls
        )
        == 1
    )

    assert (
        InterruptedSSEHandler.calls[0][0]
        == "/v1/chat/completions"
    )

    assert (
        result.status
        is ResultStatus.FAIL
    )

    assert (
        result.support
        is SupportStatus.SUPPORTED
    )

    assert (
        result.error_code
        == "STREAM_INTERRUPTED"
    )

    assert (
        result.evidence[
            "content_received"
        ]
        is True
    )

    assert (
        result.evidence[
            "terminal_event_seen"
        ]
        is False
    )