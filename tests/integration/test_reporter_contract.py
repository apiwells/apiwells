"""Reporter contract integration tests."""

import json
from copy import deepcopy

from apiwells import __version__
from apiwells.models import (
    ResultStatus,
    SupportStatus,
)
from apiwells.probes.tools import ToolCallingProbe
from apiwells.reporting import (
    aggregate_overall_status,
    build_json_report,
    render_console_report,
)
from apiwells.runner import (
    run_basic_diagnostics,
    run_deep_diagnostics,
)

from mock_server.server import (
    register_basic_auth_failure_routes,
    register_deep_flow_routes,
    register_tool_unsupported_route,
)


TEST_SECRET = (
    "sk-apiwells-ed030-reporter-secret"
)


JSON_TOP_LEVEL_FIELDS = {
    "schema_version",
    "apiwells_version",
    "overall_status",
    "probes",
}


JSON_PROBE_FIELDS = {
    "name",
    "status",
    "support",
    "summary",
    "metrics",
    "evidence",
    "error_code",
}


def mock_base_url(httpserver) -> str:
    return httpserver.url_for(
        "/v1"
    ).rstrip("/")


def test_reporters_agree_on_real_deep_pass_results(
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

    # Preserve the exact Runner output so we can prove that
    # reporting does not mutate ProbeResult values.
    original_results = deepcopy(results)

    # Capture network state after diagnostics.
    # Reporter execution must not generate new requests.
    network_state_after_diagnostics = dict(
        state
    )

    console_report = render_console_report(
        results,
        secrets=(TEST_SECRET,),
    )

    json_report = build_json_report(
        results,
        secrets=(TEST_SECRET,),
    )

    # -------------------------------------------------
    # 1. Aggregation consistency
    # -------------------------------------------------

    assert (
        aggregate_overall_status(
            results
        )
        is ResultStatus.PASS
    )

    assert (
        "Overall               PASS"
        in console_report
    )

    assert (
        json_report["overall_status"]
        == "PASS"
    )

    # -------------------------------------------------
    # 2. Stable JSON top-level contract
    # -------------------------------------------------

    assert (
        set(json_report)
        == JSON_TOP_LEVEL_FIELDS
    )

    assert (
        json_report["schema_version"]
        == "1"
    )

    assert (
        json_report["apiwells_version"]
        == __version__
    )

    # -------------------------------------------------
    # 3. Probe order + per-probe contract
    # -------------------------------------------------

    assert [
        probe["name"]
        for probe in json_report["probes"]
    ] == [
        result.name
        for result in results
    ]

    for result, probe in zip(
        results,
        json_report["probes"],
        strict=True,
    ):
        assert (
            set(probe)
            == JSON_PROBE_FIELDS
        )

        assert (
            probe["name"]
            == result.name
        )

        assert (
            probe["status"]
            == result.status.value
        )

        assert (
            probe["support"]
            == result.support.value
        )

        assert (
            probe["error_code"]
            == result.error_code
        )

    # -------------------------------------------------
    # 4. Machine serialization
    # -------------------------------------------------

    serialized = json.dumps(
        json_report,
        ensure_ascii=True,
        allow_nan=False,
    )

    assert serialized

    # -------------------------------------------------
    # 5. Reporter purity
    # -------------------------------------------------

    assert results == original_results

    assert (
        state
        == network_state_after_diagnostics
    )


def test_reporters_agree_on_real_core_failure(
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

    original_results = deepcopy(results)

    network_state_after_diagnostics = dict(
        state
    )

    console_report = render_console_report(
        results,
        secrets=(TEST_SECRET,),
    )

    json_report = build_json_report(
        results,
        secrets=(TEST_SECRET,),
    )

    # -------------------------------------------------
    # Core failure must remain FAIL everywhere.
    # -------------------------------------------------

    assert (
        aggregate_overall_status(
            results
        )
        is ResultStatus.FAIL
    )

    assert (
        "Overall               FAIL"
        in console_report
    )

    assert (
        json_report["overall_status"]
        == "FAIL"
    )

    assert "Authentication" in console_report
    assert "HTTP 401" in console_report
    assert "AUTH_INVALID" in console_report

    auth_probe = next(
        probe
        for probe in json_report["probes"]
        if probe["name"] == "auth"
    )

    assert (
        auth_probe["status"]
        == "FAIL"
    )

    assert (
        auth_probe["error_code"]
        == "AUTH_INVALID"
    )

    # Reporter must not mutate input or perform network I/O.
    assert results == original_results

    assert (
        state
        == network_state_after_diagnostics
    )


def test_reporters_agree_on_real_capability_partial(
    httpserver,
):
    register_tool_unsupported_route(
        httpserver
    )

    tool_result = ToolCallingProbe(
        base_url=mock_base_url(
            httpserver
        ),
        model="test-model",
        key=TEST_SECRET,
        timeout=2,
    ).run()

    assert (
        tool_result.status
        is ResultStatus.PARTIAL
    )

    assert (
        tool_result.support
        is SupportStatus.UNKNOWN
    )

    results = [
        tool_result
    ]

    original_results = deepcopy(results)

    console_report = render_console_report(
        results,
        secrets=(TEST_SECRET,),
    )

    json_report = build_json_report(
        results,
        secrets=(TEST_SECRET,),
    )

    # Capability unsupported must degrade to PARTIAL,
    # not incorrectly mark the endpoint as FAIL.
    assert (
        aggregate_overall_status(
            results
        )
        is ResultStatus.PARTIAL
    )

    assert (
        "Overall               PARTIAL"
        in console_report
    )

    assert "Tool Calling" in console_report
    assert "PARTIAL" in console_report
    assert "UNKNOWN" in console_report

    assert (
        json_report["overall_status"]
        == "PARTIAL"
    )

    assert (
        len(json_report["probes"])
        == 1
    )

    tool_probe = json_report[
        "probes"
    ][0]

    assert (
        tool_probe["name"]
        == "tool_calling"
    )

    assert (
        tool_probe["status"]
        == "PARTIAL"
    )

    assert (
        tool_probe["support"]
        == "UNKNOWN"
    )

    assert (
        tool_probe["error_code"]
        == "TOOL_CALL_INVALID"
    )

    assert results == original_results