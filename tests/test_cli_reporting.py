import contextlib
import io
import json
import unittest
from unittest.mock import patch

from apiwells import __version__
from apiwells.cli import main
from apiwells.models import (
    ProbeResult,
    ResultStatus,
    SupportStatus,
)


def make_result(
    name,
    status=ResultStatus.PASS,
    support=SupportStatus.NOT_APPLICABLE,
    summary=None,
    error_code=None,
):
    return ProbeResult(
        name=name,
        status=status,
        support=support,
        summary=summary or f"{name} diagnostic result.",
        error_code=error_code,
    )


BASIC_RESULTS = [
    make_result("url"),
    make_result("dns"),
    make_result("tls"),
    make_result("http"),
    make_result(
        "auth",
        support=SupportStatus.SUPPORTED,
    ),
    make_result(
        "models",
        support=SupportStatus.SUPPORTED,
    ),
]


class CliReportingTests(unittest.TestCase):
    def test_basic_json_uses_v1_report_contract(self):
        stdout = io.StringIO()

        with (
            patch(
                "apiwells.cli.run_basic_diagnostics",
                return_value=BASIC_RESULTS,
            ),
            contextlib.redirect_stdout(stdout),
        ):
            exit_code = main(
                [
                    "doctor",
                    "--base-url",
                    "https://example.com/v1",
                    "--anonymous",
                    "--json",
                ]
            )

        report = json.loads(
            stdout.getvalue()
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            report["schema_version"],
            "1",
        )
        self.assertEqual(
            report["apiwells_version"],
            __version__,
        )
        self.assertEqual(
            report["overall_status"],
            "PASS",
        )
        self.assertEqual(
            [
                probe["name"]
                for probe in report["probes"]
            ],
            [
                "url",
                "dns",
                "tls",
                "http",
                "auth",
                "models",
            ],
        )

    def test_basic_console_uses_human_reporter(self):
        stdout = io.StringIO()

        with (
            patch(
                "apiwells.cli.run_basic_diagnostics",
                return_value=BASIC_RESULTS,
            ),
            contextlib.redirect_stdout(stdout),
        ):
            exit_code = main(
                [
                    "doctor",
                    "--base-url",
                    "https://example.com/v1",
                    "--anonymous",
                ]
            )

        rendered = stdout.getvalue()

        self.assertEqual(exit_code, 0)
        self.assertIn(
            f"ApiWells Endpoint Doctor {__version__}",
            rendered,
        )
        self.assertIn(
            "DNS",
            rendered,
        )
        self.assertIn(
            "/models",
            rendered,
        )
        self.assertIn(
            "Overall",
            rendered,
        )

    def test_partial_result_returns_exit_one(self):
        results = [
            *BASIC_RESULTS,
            make_result(
                "tool_calling",
                status=ResultStatus.PARTIAL,
                support=SupportStatus.UNSUPPORTED,
                error_code="FEATURE_UNSUPPORTED",
            ),
        ]

        stdout = io.StringIO()

        with (
            patch(
                "apiwells.cli.run_basic_diagnostics",
                return_value=results,
            ),
            contextlib.redirect_stdout(stdout),
        ):
            exit_code = main(
                [
                    "doctor",
                    "--base-url",
                    "https://example.com/v1",
                    "--anonymous",
                    "--json",
                ]
            )

        report = json.loads(
            stdout.getvalue()
        )

        self.assertEqual(exit_code, 1)
        self.assertEqual(
            report["overall_status"],
            "PARTIAL",
        )

    def test_deep_mode_uses_deep_runner(self):
        stdout = io.StringIO()

        deep_results = [
            *BASIC_RESULTS,
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

        with (
            patch(
                "apiwells.cli.run_deep_diagnostics",
                return_value=deep_results,
            ) as deep_runner,
            contextlib.redirect_stdout(stdout),
        ):
            exit_code = main(
                [
                    "doctor",
                    "--base-url",
                    "https://example.com/v1",
                    "--anonymous",
                    "--deep",
                    "--model",
                    "demo-model",
                    "--json",
                ]
            )

        self.assertEqual(exit_code, 0)

        deep_runner.assert_called_once()

        report = json.loads(
            stdout.getvalue()
        )

        self.assertEqual(
            report["overall_status"],
            "PASS",
        )

    def test_deep_requires_model(self):
        stderr = io.StringIO()

        with (
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit) as error,
        ):
            main(
                [
                    "doctor",
                    "--base-url",
                    "https://example.com/v1",
                    "--anonymous",
                    "--deep",
                ]
            )

        self.assertEqual(
            error.exception.code,
            2,
        )

    def test_chat_and_deep_are_mutually_exclusive(self):
        stderr = io.StringIO()

        with (
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit) as error,
        ):
            main(
                [
                    "doctor",
                    "--base-url",
                    "https://example.com/v1",
                    "--anonymous",
                    "--chat",
                    "--deep",
                    "--model",
                    "demo-model",
                ]
            )

        self.assertEqual(
            error.exception.code,
            2,
        )


if __name__ == "__main__":
    unittest.main()