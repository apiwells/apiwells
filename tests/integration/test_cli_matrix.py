"""CLI compatibility matrix integration tests."""

import contextlib
import io
import json

import pytest

from apiwells import __version__
from apiwells.cli import main

from mock_server.server import (
    register_basic_auth_failure_routes,
    register_basic_flow_routes,
    register_deep_flow_routes,
)


def mock_base_url(httpserver) -> str:
    return httpserver.url_for(
        "/v1"
    ).rstrip("/")


def invoke_cli(argv):
    """Run the real CLI main() and capture stdout."""

    stdout = io.StringIO()

    with contextlib.redirect_stdout(stdout):
        exit_code = main(argv)

    return exit_code, stdout.getvalue()


def test_cli_basic_console_real_flow(
    httpserver,
):
    state = register_basic_flow_routes(
        httpserver
    )

    exit_code, output = invoke_cli(
        [
            "doctor",
            "--base-url",
            mock_base_url(httpserver),
            "--anonymous",
        ]
    )

    assert exit_code == 0

    assert (
        f"ApiWells Endpoint Doctor {__version__}"
        in output
    )

    assert "URL" in output
    assert "DNS" in output
    assert "TLS" in output
    assert "HTTP" in output
    assert "Authentication" in output
    assert "/models" in output

    assert (
        "Overall               PASS"
        in output
    )

    # Basic must remain non-billable.
    assert (
        state["models_request_count"]
        == 1
    )

    assert (
        state["chat_request_count"]
        == 0
    )


@pytest.mark.parametrize(
    (
        "json_flag",
        "expects_compat_ok",
    ),
    [
        ("--json", True),
        ("--v2-json", False),
    ],
)
def test_cli_basic_json_contracts_real_flow(
    httpserver,
    json_flag,
    expects_compat_ok,
):
    state = register_basic_flow_routes(
        httpserver
    )

    exit_code, output = invoke_cli(
        [
            "doctor",
            "--base-url",
            mock_base_url(httpserver),
            "--anonymous",
            json_flag,
        ]
    )

    assert exit_code == 0

    report = json.loads(output)

    assert (
        report["schema_version"]
        == "1"
    )

    assert (
        report["apiwells_version"]
        == __version__
    )

    assert (
        report["overall_status"]
        == "PASS"
    )

    assert [
        probe["name"]
        for probe in report["probes"]
    ] == [
        "url",
        "dns",
        "tls",
        "http",
        "auth",
        "models",
    ]

    # --json is the compatibility path.
    # --v2-json is the formal v0.2 reporter.
    if expects_compat_ok:
        assert report["ok"] is True
    else:
        assert "ok" not in report

    assert (
        state["models_request_count"]
        == 1
    )

    assert (
        state["chat_request_count"]
        == 0
    )


def test_cli_deep_v2_json_real_flow(
    httpserver,
):
    state = register_deep_flow_routes(
        httpserver
    )

    exit_code, output = invoke_cli(
        [
            "doctor",
            "--base-url",
            mock_base_url(httpserver),
            "--anonymous",
            "--deep",
            "--model",
            "test-model",
            "--v2-json",
        ]
    )

    assert exit_code == 0

    report = json.loads(output)

    assert (
        report["schema_version"]
        == "1"
    )

    assert (
        report["overall_status"]
        == "PASS"
    )

    assert [
        probe["name"]
        for probe in report["probes"]
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

    # Verify that CLI really executed the whole Deep chain.
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


def test_cli_legacy_chat_json_real_flow(
    httpserver,
):
    state = register_deep_flow_routes(
        httpserver
    )

    exit_code, output = invoke_cli(
        [
            "doctor",
            "--base-url",
            mock_base_url(httpserver),
            "--anonymous",
            "--chat",
            "--model",
            "test-model",
            "--json",
        ]
    )

    assert exit_code == 0

    report = json.loads(output)

    # Legacy diagnose() contract is intentionally
    # different from the v0.2 Reporter contract.
    assert report["schema_version"] == 1
    assert report["version"] == __version__
    assert report["check"] == "chat"
    assert report["ok"] is True

    assert "apiwells_version" not in report
    assert "probes" not in report

    # Legacy --chat must remain a single request.
    assert (
        state["models_request_count"]
        == 0
    )

    assert (
        state["chat_request_count"]
        == 1
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


def test_cli_real_core_failure_returns_exit_one(
    httpserver,
    monkeypatch,
):
    state = (
        register_basic_auth_failure_routes(
            httpserver
        )
    )

    monkeypatch.setenv(
        "APIWELLS_ED030_TEST_KEY",
        "bad-test-key",
    )

    exit_code, output = invoke_cli(
        [
            "doctor",
            "--base-url",
            mock_base_url(httpserver),
            "--api-key-env",
            "APIWELLS_ED030_TEST_KEY",
            "--v2-json",
        ]
    )

    assert exit_code == 1

    report = json.loads(output)

    assert (
        report["overall_status"]
        == "FAIL"
    )

    auth_probe = next(
        probe
        for probe in report["probes"]
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

    assert (
        state["models_request_count"]
        == 1
    )

    # Basic failure still must not start billable probes.
    assert (
        state["chat_request_count"]
        == 0
    )