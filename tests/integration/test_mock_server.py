import re

import pytest
from urllib.request import urlopen

from apiwells.models import (
    ResultStatus,
    SupportStatus,
)
from apiwells.probes import ChatProbe
from apiwells.probes.streaming import StreamingProbe
from apiwells.probes.structured import (
    StructuredOutputProbe,
)
from apiwells.probes.tools import ToolCallingProbe

from mock_server.server import (
    register_broken_sse_route,
    register_happy_path_routes,
    register_http_error_route,
    register_invalid_json_route,
    register_structured_json_object_only_route,
    register_tool_unsupported_route,
)


def mock_base_url(httpserver) -> str:
    return httpserver.url_for("/v1").rstrip("/")


def test_mock_models_endpoint(httpserver):
    register_happy_path_routes(httpserver)

    url = httpserver.url_for("/v1/models")

    with urlopen(url, timeout=5) as response:
        body = response.read().decode("utf-8")

        assert response.status == 200
        assert "test-model" in body


def test_chat_probe_against_mock_provider(
    httpserver,
):
    register_happy_path_routes(httpserver)

    result = ChatProbe(
        mock_base_url(httpserver),
        model="test-model",
    ).run()

    assert result.status == ResultStatus.PASS
    assert (
        result.support
        == SupportStatus.SUPPORTED
    )

    assert (
        result.metrics["usage_available"]
        is True
    )

    assert result.metrics["prompt_tokens"] == 5
    assert result.metrics["completion_tokens"] == 3
    assert result.metrics["total_tokens"] == 8


def test_streaming_probe_against_mock_provider(
    httpserver,
):
    register_happy_path_routes(httpserver)

    result = StreamingProbe(
        mock_base_url(httpserver),
        model="test-model",
    ).run()

    assert result.status == ResultStatus.PASS
    assert (
        result.support
        == SupportStatus.SUPPORTED
    )

    assert result.metrics["ttft_ms"] is not None
    assert (
        result.metrics["total_latency_ms"]
        is not None
    )

    assert (
        result.evidence["content_received"]
        is True
    )

    assert (
        result.evidence["terminal_event_seen"]
        is True
    )

    assert (
        result.metrics["usage_available"]
        is True
    )

    assert result.metrics["prompt_tokens"] == 5
    assert result.metrics["completion_tokens"] == 1
    assert result.metrics["total_tokens"] == 6


def test_tool_probe_against_mock_provider(
    httpserver,
):
    register_happy_path_routes(httpserver)

    result = ToolCallingProbe(
        mock_base_url(httpserver),
        model="test-model",
    ).run()

    assert result.status == ResultStatus.PASS
    assert (
        result.support
        == SupportStatus.SUPPORTED
    )

    assert (
        result.evidence[
            "round_trip_completed"
        ]
        is True
    )

    assert re.fullmatch(
        r"apiwells-[0-9a-f]{16}",
        result.evidence["local_tool_result"],
    )

    assert (
        result.metrics["request_count"]
        == 2
    )


def test_structured_probe_against_mock_provider(
    httpserver,
):
    register_happy_path_routes(httpserver)

    result = StructuredOutputProbe(
        mock_base_url(httpserver),
        model="test-model",
    ).run()

    assert result.status == ResultStatus.PASS
    assert (
        result.support
        == SupportStatus.SUPPORTED
    )

    assert (
        result.evidence["outcome"]
        == "supported"
    )

    assert (
        result.evidence[
            "json_schema_request_accepted"
        ]
        is True
    )

    assert (
        result.evidence[
            "schema_validation_passed"
        ]
        is True
    )

    assert (
        result.metrics["request_count"]
        == 1
    )


@pytest.mark.parametrize(
    (
        "status_code",
        "expected_error_code",
    ),
    [
        (401, "AUTH_INVALID"),
        (403, "PERMISSION_DENIED"),
        (429, "RATE_LIMITED"),
        (500, "UPSTREAM_5XX"),
    ],
)
def test_chat_http_error_classification(
    httpserver,
    status_code,
    expected_error_code,
):
    state = register_http_error_route(
        httpserver,
        status_code=status_code,
        message=f"mock HTTP {status_code}",
    )

    result = ChatProbe(
        mock_base_url(httpserver),
        model="test-model",
    ).run()

    assert result.status == ResultStatus.FAIL
    assert result.error_code == expected_error_code

    assert (
        result.evidence["http_status"]
        == status_code
    )

    # No hidden retry.
    assert state["request_count"] == 1


def test_chat_invalid_json_against_mock_provider(
    httpserver,
):
    register_invalid_json_route(
        httpserver
    )

    result = ChatProbe(
        mock_base_url(httpserver),
        model="test-model",
    ).run()

    assert result.status == ResultStatus.FAIL
    assert (
        result.support
        == SupportStatus.UNKNOWN
    )

    assert result.error_code == "INVALID_JSON"


def test_broken_sse_against_mock_provider(
    httpserver,
):
    register_broken_sse_route(
        httpserver
    )

    result = StreamingProbe(
        mock_base_url(httpserver),
        model="test-model",
    ).run()

    assert result.status == ResultStatus.FAIL
    assert result.error_code == "SSE_INVALID"


def test_tool_unsupported_against_mock_provider(
    httpserver,
):
    register_tool_unsupported_route(
        httpserver
    )

    result = ToolCallingProbe(
        mock_base_url(httpserver),
        model="test-model",
    ).run()

    assert result.status == ResultStatus.PARTIAL

    assert (
        result.support
        == SupportStatus.UNKNOWN
    )

    assert (
        result.error_code
        == "TOOL_CALL_INVALID"
    )

    assert result.metrics["request_count"] == 1


def test_structured_json_object_only_against_mock_provider(
    httpserver,
):
    state = (
        register_structured_json_object_only_route(
            httpserver
        )
    )

    result = StructuredOutputProbe(
        mock_base_url(httpserver),
        model="test-model",
    ).run()

    assert result.status == ResultStatus.PARTIAL

    assert (
        result.support
        == SupportStatus.UNSUPPORTED
    )

    assert (
        result.error_code
        == "FEATURE_UNSUPPORTED"
    )

    assert (
        result.evidence["outcome"]
        == "json_object_only"
    )

    assert (
        result.evidence[
            "json_schema_request_accepted"
        ]
        is False
    )

    assert (
        result.evidence[
            "json_object_request_accepted"
        ]
        is True
    )

    assert result.metrics["request_count"] == 2

    assert state["request_count"] == 2