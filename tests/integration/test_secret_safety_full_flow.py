"""Secret-safety full-flow integration tests."""

import contextlib
import io
import json

import pytest

from apiwells.cli import main

from mock_server.server import (
    register_basic_secret_error_routes,
    register_basic_secret_invalid_json_routes,
    register_basic_timeout_routes,
    register_deep_flow_routes,
)


SECRET = (
    "sk-apiwells-ed030-super-secret-value"
)


def mock_base_url(httpserver) -> str:
    return httpserver.url_for(
        "/v1"
    ).rstrip("/")


def invoke_cli(
    argv,
    *,
    caplog=None,
):
    stdout = io.StringIO()
    stderr = io.StringIO()

    with (
        contextlib.redirect_stdout(stdout),
        contextlib.redirect_stderr(stderr),
    ):
        exit_code = main(argv)

    combined = (
        stdout.getvalue()
        + stderr.getvalue()
    )

    if caplog is not None:
        combined += caplog.text

    return (
        exit_code,
        stdout.getvalue(),
        stderr.getvalue(),
        combined,
    )


def assert_secret_safe(text: str):
    assert SECRET not in text
    assert "Bearer " + SECRET not in text


def test_basic_console_redacts_provider_echoed_secret(
    httpserver,
    monkeypatch,
    caplog,
):
    state = register_basic_secret_error_routes(
        httpserver,
        status_code=401,
        secret=SECRET,
    )

    monkeypatch.setenv(
        "APIWELLS_ED030_SECRET",
        SECRET,
    )

    (
        exit_code,
        stdout,
        stderr,
        combined,
    ) = invoke_cli(
        [
            "doctor",
            "--base-url",
            mock_base_url(httpserver),
            "--api-key-env",
            "APIWELLS_ED030_SECRET",
        ],
        caplog=caplog,
    )

    assert exit_code == 1

    # Prove the secret really crossed the HTTP boundary.
    assert (
        state["authorization"]
        == "Bearer " + SECRET
    )

    assert (
        state["models_request_count"]
        == 1
    )

    assert (
        state["chat_request_count"]
        == 0
    )

    assert "AUTH_INVALID" in stdout

    assert_secret_safe(stdout)
    assert_secret_safe(stderr)
    assert_secret_safe(combined)


@pytest.mark.parametrize(
    "json_flag",
    [
        "--json",
        "--v2-json",
    ],
)
def test_basic_json_paths_redact_provider_echoed_secret(
    httpserver,
    monkeypatch,
    caplog,
    json_flag,
):
    state = register_basic_secret_error_routes(
        httpserver,
        status_code=403,
        secret=SECRET,
    )

    monkeypatch.setenv(
        "APIWELLS_ED030_SECRET",
        SECRET,
    )

    (
        exit_code,
        stdout,
        stderr,
        combined,
    ) = invoke_cli(
        [
            "doctor",
            "--base-url",
            mock_base_url(httpserver),
            "--api-key-env",
            "APIWELLS_ED030_SECRET",
            json_flag,
        ],
        caplog=caplog,
    )

    assert exit_code == 1

    report = json.loads(stdout)

    assert (
        report["overall_status"]
        == "FAIL"
    )

    assert (
        state["authorization"]
        == "Bearer " + SECRET
    )

    assert_secret_safe(stdout)
    assert_secret_safe(stderr)
    assert_secret_safe(combined)


def test_invalid_json_body_cannot_leak_secret(
    httpserver,
    monkeypatch,
    caplog,
):
    state = (
        register_basic_secret_invalid_json_routes(
            httpserver,
            secret=SECRET,
        )
    )

    monkeypatch.setenv(
        "APIWELLS_ED030_SECRET",
        SECRET,
    )

    (
        exit_code,
        stdout,
        stderr,
        combined,
    ) = invoke_cli(
        [
            "doctor",
            "--base-url",
            mock_base_url(httpserver),
            "--api-key-env",
            "APIWELLS_ED030_SECRET",
            "--v2-json",
        ],
        caplog=caplog,
    )

    assert exit_code == 1

    report = json.loads(stdout)

    models_probe = next(
        probe
        for probe in report["probes"]
        if probe["name"] == "models"
    )

    assert (
        models_probe["error_code"]
        == "INVALID_JSON"
    )

    assert (
        state["authorization"]
        == "Bearer " + SECRET
    )

    assert_secret_safe(stdout)
    assert_secret_safe(stderr)
    assert_secret_safe(combined)


def test_timeout_path_does_not_leak_secret(
    httpserver,
    monkeypatch,
    caplog,
):
    state = register_basic_timeout_routes(
        httpserver,
        delay=0.2,
    )

    monkeypatch.setenv(
        "APIWELLS_ED030_SECRET",
        SECRET,
    )

    (
        exit_code,
        stdout,
        stderr,
        combined,
    ) = invoke_cli(
        [
            "doctor",
            "--base-url",
            mock_base_url(httpserver),
            "--api-key-env",
            "APIWELLS_ED030_SECRET",
            "--timeout",
            "0.05",
            "--v2-json",
        ],
        caplog=caplog,
    )

    assert exit_code == 1

    report = json.loads(stdout)

    assert (
        report["overall_status"]
        == "FAIL"
    )

    assert (
        state["models_request_count"]
        == 1
    )

    assert (
        state["chat_request_count"]
        == 0
    )

    assert_secret_safe(stdout)
    assert_secret_safe(stderr)
    assert_secret_safe(combined)


def test_deep_cli_uses_secret_but_never_reports_it(
    httpserver,
    monkeypatch,
    caplog,
):
    state = register_deep_flow_routes(
        httpserver
    )

    monkeypatch.setenv(
        "APIWELLS_ED030_SECRET",
        SECRET,
    )

    (
        exit_code,
        stdout,
        stderr,
        combined,
    ) = invoke_cli(
        [
            "doctor",
            "--base-url",
            mock_base_url(httpserver),
            "--api-key-env",
            "APIWELLS_ED030_SECRET",
            "--deep",
            "--model",
            "test-model",
            "--v2-json",
        ],
        caplog=caplog,
    )

    assert exit_code == 0

    report = json.loads(stdout)

    assert (
        report["overall_status"]
        == "PASS"
    )

    # /models + 5 Deep POSTs = 6 authenticated exchanges.
    assert (
        len(
            state[
                "authorization_headers"
            ]
        )
        == 6
    )

    assert all(
        header == "Bearer " + SECRET
        for header in state[
            "authorization_headers"
        ]
    )

    assert_secret_safe(stdout)
    assert_secret_safe(stderr)
    assert_secret_safe(combined)


def test_unexpected_internal_exception_suppresses_secret_and_traceback(
    httpserver,
    monkeypatch,
    caplog,
):
    monkeypatch.setenv(
        "APIWELLS_ED030_SECRET",
        SECRET,
    )

    def explode(**kwargs):
        raise RuntimeError(
            "unexpected internal failure "
            + SECRET
        )

    monkeypatch.setattr(
        "apiwells.cli.run_basic_diagnostics",
        explode,
    )

    (
        exit_code,
        stdout,
        stderr,
        combined,
    ) = invoke_cli(
        [
            "doctor",
            "--base-url",
            mock_base_url(httpserver),
            "--api-key-env",
            "APIWELLS_ED030_SECRET",
            "--v2-json",
        ],
        caplog=caplog,
    )

    assert exit_code == 1

    report = json.loads(stdout)

    assert (
        report["overall_status"]
        == "FAIL"
    )

    assert (
        report["probes"][0][
            "error_code"
        ]
        == "INTERNAL_ERROR"
    )

    assert "Traceback" not in combined

    assert_secret_safe(stdout)
    assert_secret_safe(stderr)
    assert_secret_safe(combined)