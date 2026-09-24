"""Basic full-flow integration tests."""

import json

from apiwells.models import ResultStatus
from apiwells.reporting import (
    aggregate_overall_status,
    build_json_report,
    render_console_report,
)
from apiwells.runner import run_basic_diagnostics

from mock_server.server import (
    register_basic_auth_failure_routes,
    register_basic_flow_routes,
    register_basic_invalid_json_routes,
)


TEST_SECRET = (
    "sk-apiwells-ed030-basic-secret"
)


def mock_base_url(httpserver) -> str:
    return httpserver.url_for(
        "/v1"
    ).rstrip("/")


def test_basic_full_flow_happy_path(
    httpserver,
):
    state = register_basic_flow_routes(
        httpserver
    )

    results = run_basic_diagnostics(
        base_url=mock_base_url(
            httpserver
        ),
        key=TEST_SECRET,
        timeout=2,
        expected_model="test-model",
    )

    # -------------------------------------------------
    # 1. Runner / Probe contract
    # -------------------------------------------------

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

    assert all(
        result.status
        is ResultStatus.PASS
        for result in results
    )

    # -------------------------------------------------
    # 2. Real network behavior
    # -------------------------------------------------

    assert (
        state["models_request_count"]
        == 1
    )

    # Basic Doctor must remain non-billable.
    assert (
        state["chat_request_count"]
        == 0
    )

    # -------------------------------------------------
    # 3. Models result
    # -------------------------------------------------

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

    # -------------------------------------------------
    # 4. Aggregation
    # -------------------------------------------------

    overall_status = (
        aggregate_overall_status(
            results
        )
    )

    assert (
        overall_status
        is ResultStatus.PASS
    )

    # -------------------------------------------------
    # 5. Console Reporter
    # -------------------------------------------------

    console_report = (
        render_console_report(
            results,
            secrets=(TEST_SECRET,),
        )
    )

    assert (
        "Overall               PASS"
        in console_report
    )

    assert "DNS" in console_report
    assert "TLS" in console_report
    assert "HTTP" in console_report
    assert "Authentication" in console_report
    assert "/models" in console_report

    assert (
        TEST_SECRET
        not in console_report
    )

    # -------------------------------------------------
    # 6. JSON Reporter
    # -------------------------------------------------

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
    ]

    # Prove that the report remains JSON serializable.
    serialized_report = json.dumps(
        json_report,
        ensure_ascii=True,
        allow_nan=False,
    )

    assert (
        TEST_SECRET
        not in serialized_report
    )


def test_basic_full_flow_auth_failure(
    httpserver,
):
    state = (
        register_basic_auth_failure_routes(
            httpserver
        )
    )

    results = run_basic_diagnostics(
        base_url=mock_base_url(
            httpserver
        ),
        key=TEST_SECRET,
        timeout=2,
    )

    by_name = {
        result.name: result
        for result in results
    }

    # The endpoint is reachable even though authentication failed.
    assert (
        by_name["http"].status
        is ResultStatus.PASS
    )

    assert (
        by_name["http"].evidence[
            "http_status"
        ]
        == 401
    )

    assert (
        by_name["auth"].status
        is ResultStatus.FAIL
    )

    assert (
        by_name["auth"].error_code
        == "AUTH_INVALID"
    )

    # Basic still performs exactly one non-billable /models request.
    assert (
        state["models_request_count"]
        == 1
    )

    assert (
        state["chat_request_count"]
        == 0
    )

    # Core failure must make the overall result FAIL.
    assert (
        aggregate_overall_status(
            results
        )
        is ResultStatus.FAIL
    )

    console_report = render_console_report(
        results,
        secrets=(TEST_SECRET,),
    )

    assert (
        "Overall               FAIL"
        in console_report
    )

    assert "AUTH_INVALID" in console_report
    assert "HTTP 401" in console_report

    json_report = build_json_report(
        results,
        secrets=(TEST_SECRET,),
    )

    assert (
        json_report["overall_status"]
        == "FAIL"
    )

    auth_probe = next(
        probe
        for probe in json_report["probes"]
        if probe["name"] == "auth"
    )

    assert (
        auth_probe["error_code"]
        == "AUTH_INVALID"
    )

    assert (
        TEST_SECRET
        not in json.dumps(
            json_report,
            ensure_ascii=True,
            allow_nan=False,
        )
    )


def test_basic_full_flow_invalid_models_json(
    httpserver,
):
    state = (
        register_basic_invalid_json_routes(
            httpserver
        )
    )

    results = run_basic_diagnostics(
        base_url=mock_base_url(
            httpserver
        ),
        key=TEST_SECRET,
        timeout=2,
    )

    by_name = {
        result.name: result
        for result in results
    }

    # HTTP transport itself succeeded.
    assert (
        by_name["http"].status
        is ResultStatus.PASS
    )

    assert (
        by_name["http"].evidence[
            "http_status"
        ]
        == 200
    )

    # But the /models protocol payload is invalid.
    assert (
        by_name["models"].status
        is ResultStatus.FAIL
    )

    assert (
        by_name["models"].error_code
        == "INVALID_JSON"
    )

    assert (
        state["models_request_count"]
        == 1
    )

    assert (
        state["chat_request_count"]
        == 0
    )

    assert (
        aggregate_overall_status(
            results
        )
        is ResultStatus.FAIL
    )

    console_report = render_console_report(
        results,
        secrets=(TEST_SECRET,),
    )

    assert (
        "Overall               FAIL"
        in console_report
    )

    assert "INVALID_JSON" in console_report

    json_report = build_json_report(
        results,
        secrets=(TEST_SECRET,),
    )

    assert (
        json_report["overall_status"]
        == "FAIL"
    )

    models_probe = next(
        probe
        for probe in json_report["probes"]
        if probe["name"] == "models"
    )

    assert (
        models_probe["error_code"]
        == "INVALID_JSON"
    )

    assert (
        TEST_SECRET
        not in json.dumps(
            json_report,
            ensure_ascii=True,
            allow_nan=False,
        )
    )