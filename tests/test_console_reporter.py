import unittest

from apiwells import __version__
from apiwells.models import (
    ProbeResult,
    ResultStatus,
    SupportStatus,
)
from apiwells.reporting.console import (
    render_console_report,
)


SECRET = "sk-apiwells-console-reporter-secret"


def make_result(
    name,
    status=ResultStatus.PASS,
    support=SupportStatus.NOT_APPLICABLE,
    summary=None,
    metrics=None,
    evidence=None,
    error_code=None,
):
    return ProbeResult(
        name=name,
        status=status,
        support=support,
        summary=summary or f"{name} diagnostic result.",
        metrics={} if metrics is None else metrics,
        evidence={} if evidence is None else evidence,
        error_code=error_code,
    )


class ConsoleReporterTests(unittest.TestCase):
    def test_renders_header_and_overall_status(self):
        rendered = render_console_report(
            [
                make_result("url"),
                make_result("dns"),
                make_result("tls"),
            ]
        )

        self.assertIn(
            f"ApiWells Endpoint Doctor {__version__}",
            rendered,
        )
        self.assertIn(
            "Overall",
            rendered,
        )
        self.assertIn(
            "PASS",
            rendered,
        )

    def test_renders_probe_display_names(self):
        rendered = render_console_report(
            [
                make_result("url"),
                make_result("dns"),
                make_result("tls"),
                make_result("http"),
                make_result("auth"),
                make_result(
                    "models",
                    support=SupportStatus.SUPPORTED,
                ),
                make_result(
                    "chat",
                    support=SupportStatus.SUPPORTED,
                ),
                make_result(
                    "streaming",
                    support=SupportStatus.SUPPORTED,
                ),
                make_result(
                    "tool_calling",
                    support=SupportStatus.SUPPORTED,
                ),
                make_result(
                    "structured_output",
                    support=SupportStatus.SUPPORTED,
                ),
            ]
        )

        for label in (
            "URL",
            "DNS",
            "TLS",
            "HTTP",
            "Authentication",
            "/models",
            "Chat Completions",
            "Streaming",
            "Tool Calling",
            "Structured Output",
        ):
            with self.subTest(label=label):
                self.assertIn(
                    label,
                    rendered,
                )

    def test_unsupported_capability_is_partial_not_fail(self):
        rendered = render_console_report(
            [
                make_result("url"),
                make_result("dns"),
                make_result(
                    "tool_calling",
                    status=ResultStatus.PARTIAL,
                    support=SupportStatus.UNSUPPORTED,
                    summary=(
                        "Tool Calling is not supported "
                        "by the selected model."
                    ),
                    error_code="FEATURE_UNSUPPORTED",
                ),
            ]
        )

        self.assertIn(
            "Tool Calling",
            rendered,
        )
        self.assertIn(
            "PARTIAL",
            rendered,
        )
        self.assertIn(
            "UNSUPPORTED",
            rendered,
        )

        overall_line = next(
            line
            for line in rendered.splitlines()
            if line.startswith("Overall")
        )

        self.assertIn(
            "PARTIAL",
            overall_line,
        )

    def test_failure_renders_error_details_and_http_status(self):
        rendered = render_console_report(
            [
                make_result("url"),
                make_result("http"),
                make_result(
                    "auth",
                    status=ResultStatus.FAIL,
                    support=SupportStatus.UNKNOWN,
                    summary="Authentication failed.",
                    evidence={
                        "http_status": 401,
                    },
                    error_code="AUTH_INVALID",
                ),
            ]
        )

        self.assertIn(
            "Authentication",
            rendered,
        )
        self.assertIn(
            "FAIL",
            rendered,
        )
        self.assertIn(
            "HTTP 401",
            rendered,
        )
        self.assertIn(
            "AUTH_INVALID",
            rendered,
        )
        self.assertIn(
            "Authentication failed.",
            rendered,
        )

    def test_error_code_has_actionable_hint(self):
        rendered = render_console_report(
            [
                make_result(
                    "auth",
                    status=ResultStatus.FAIL,
                    support=SupportStatus.UNKNOWN,
                    summary="Authentication failed.",
                    error_code="AUTH_INVALID",
                )
            ]
        )

        self.assertIn(
            "Check:",
            rendered,
        )
        self.assertIn(
            "API key",
            rendered,
        )

    def test_unknown_probe_name_is_still_rendered(self):
        rendered = render_console_report(
            [
                make_result(
                    "future_probe",
                    status=ResultStatus.PASS,
                )
            ]
        )

        self.assertIn(
            "future_probe",
            rendered,
        )

    def test_secret_is_redacted_everywhere(self):
        rendered = render_console_report(
            [
                make_result(
                    "models",
                    status=ResultStatus.FAIL,
                    support=SupportStatus.UNKNOWN,
                    summary=(
                        "Provider exposed "
                        + SECRET
                    ),
                    metrics={
                        "token": SECRET,
                    },
                    evidence={
                        "authorization": (
                            "Bearer " + SECRET
                        ),
                        "provider_message": (
                            "failed for " + SECRET
                        ),
                    },
                    error_code="INTERNAL_ERROR",
                )
            ],
            secrets=(SECRET,),
        )

        self.assertNotIn(
            SECRET,
            rendered,
        )
        self.assertIn(
            "[REDACTED]",
            rendered,
        )

    def test_empty_results_are_rejected(self):
        with self.assertRaises(ValueError):
            render_console_report([])


if __name__ == "__main__":
    unittest.main()