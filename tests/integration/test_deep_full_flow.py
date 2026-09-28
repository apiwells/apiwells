"""ED-030.3 Deep full-flow integration tests."""

import json
import re

from apiwells.models import ResultStatus
from apiwells.reporting import (
    aggregate_overall_status,
    build_json_report,
    render_console_report,
)
from apiwells.runner import run_deep_diagnostics

from mock_server.server import (
    register_basic_auth_failure_routes,
    register_deep_flow_routes,
)


TEST_SECRET = (
    "sk-apiwells-ed030-deep-secret"
)


def mock_base_url(httpserver) -> str:
    return httpserver.url_for(
        "/v1"
    ).rstrip("/")


def test_deep_full_flow_happy_path(
    httpserver,
):
    state = register_deep_flow_routes(
        httpserver
    )

    results = run_deep_diagnostics(
        base_url=mock_base_url(
            httpserver
        ),
        model="test-model",
        key=TEST_SECRET,
        timeout=2,
    )

    # ---------------------------------------------
    # 1. Complete Probe order
    # ---------------------------------------------

    assert [
        result.name
        for result in results
    ] == [
        "url",
        "dns",
        "tls",
        "http",
        "auth",
        "models",
        "chat",
        "streaming",
        "tool_calling",
        "structured_output",
    ]

    assert all(
        result.status
        is ResultStatus.PASS
        for result in results
    )

    # ---------------------------------------------
    # 2. Exact network behavior
    # ---------------------------------------------

    assert (
        state["models_request_count"]
        == 1
    )

    assert (
        state["chat_request_count"]
        == 1
    )

    assert (
        state["streaming_request_count"]
        == 1
    )

    assert (
        state["tool_first_request_count"]
        == 1
    )

    assert (
        state["tool_second_request_count"]
        == 1
    )

    assert (
        state["structured_request_count"]
        == 1
    )

    total_chat_requests = (
        state["chat_request_count"]
        + state["streaming_request_count"]
        + state["tool_first_request_count"]
        + state["tool_second_request_count"]
        + state["structured_request_count"]
    )

    assert total_chat_requests == 5

    # ---------------------------------------------
    # 3. Model selection
    # ---------------------------------------------

    models_result = next(
        result
        for result in results
        if result.name == "models"
    )

    assert (
        models_result.evidence[
            "target_model_found"
        ]
        is True
    )

    # ---------------------------------------------
    # 4. Tool round trip
    # ---------------------------------------------

    tool_result = next(
        result
        for result in results
        if result.name == "tool_calling"
    )

    assert (
        tool_result.evidence[
            "round_trip_completed"
        ]
        is True
    )

    assert re.fullmatch(
        r"apiwells-[0-9a-f]{16}",
        tool_result.evidence["local_tool_result"],
    )

    # ---------------------------------------------
    # 5. Streaming
    # ---------------------------------------------

    streaming_result = next(
        result
        for result in results
        if result.name == "streaming"
    )

    assert (
        streaming_result.metrics[
            "ttft_ms"
        ]
        is not None
    )

    assert (
        streaming_result.evidence[
            "terminal_event_seen"
        ]
        is True
    )

    # ---------------------------------------------
    # 6. Structured Output
    # ---------------------------------------------

    structured_result = next(
        result
        for result in results
        if result.name
        == "structured_output"
    )

    assert (
        structured_result.evidence[
            "schema_validation_passed"
        ]
        is True
    )

    # ---------------------------------------------
    # 7. Aggregation
    # ---------------------------------------------

    assert (
        aggregate_overall_status(
            results
        )
        is ResultStatus.PASS
    )

    # ---------------------------------------------
    # 8. Console Reporter
    # ---------------------------------------------

    console_report = render_console_report(
        results,
        secrets=(TEST_SECRET,),
    )

    assert (
        "Overall               PASS"
        in console_report
    )

    assert (
        "Chat Completions"
        in console_report
    )

    assert "Streaming" in console_report
    assert "Tool Calling" in console_report

    assert (
        "Structured Output"
        in console_report
    )

    assert (
        TEST_SECRET
        not in console_report
    )

    # ---------------------------------------------
    # 9. JSON Reporter
    # ---------------------------------------------

    json_report = build_json_report(
        results,
        secrets=(TEST_SECRET,),
    )

    assert (
        json_report["schema_version"]
        == "1"
    )

    assert (
        json_report["overall_status"]
        == "PASS"
    )

    assert [
        probe["name"]
        for probe in json_report["probes"]
    ] == [
        "url",
        "dns",
        "tls",
        "http",
        "auth",
        "models",
        "chat",
        "streaming",
        "tool_calling",
        "structured_output",
    ]

    serialized_report = json.dumps(
        json_report,
        ensure_ascii=True,
        allow_nan=False,
    )

    assert (
        TEST_SECRET
        not in serialized_report
    )


def test_deep_stops_when_basic_auth_fails(
    httpserver,
):
    state = (
        register_basic_auth_failure_routes(
            httpserver
        )
    )

    results = run_deep_diagnostics(
        base_url=mock_base_url(
            httpserver
        ),
        model="test-model",
        key=TEST_SECRET,
        timeout=2,
    )

    # Deep must return only the Basic chain.
    assert [
        result.name
        for result in results
    ] == [
        "url",
        "dns",
        "tls",
        "http",
        "auth",
        "models",
    ]

    by_name = {
        result.name: result
        for result in results
    }

    assert (
        by_name["auth"].status
        is ResultStatus.FAIL
    )

    assert (
        by_name["auth"].error_code
        == "AUTH_INVALID"
    )

    assert (
        state["models_request_count"]
        == 1
    )

    # Critical control:
    # no billable Deep request may run.
    assert (
        state["chat_request_count"]
        == 0
    )


def test_deep_stops_when_requested_model_is_missing(
    httpserver,
):
    state = register_deep_flow_routes(
        httpserver
    )

    results = run_deep_diagnostics(
        base_url=mock_base_url(
            httpserver
        ),
        model="missing-model",
        key=TEST_SECRET,
        timeout=2,
    )

    # Only Basic diagnostics should be returned.
    assert [
        result.name
        for result in results
    ] == [
        "url",
        "dns",
        "tls",
        "http",
        "auth",
        "models",
    ]

    models_result = next(
        result
        for result in results
        if result.name == "models"
    )

    assert (
        models_result.evidence[
            "target_model_found"
        ]
        is False
    )

    assert (
        state["models_request_count"]
        == 1
    )

    # No billable Deep probes.
    assert (
        state["chat_request_count"]
        == 0
    )

    assert (
        state["streaming_request_count"]
        == 0
    )

    assert (
        state["tool_first_request_count"]
        == 0
    )

    assert (
        state["tool_second_request_count"]
        == 0
    )

    assert (
        state["structured_request_count"]
        == 0
    )