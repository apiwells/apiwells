import contextlib
import io
import json
import os
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
    def test_chat_v2_json_is_rejected_before_diagnostics(self):
        secret = "BUG001-synthetic-test-key"
        for flags in (
            ["--v2-json"],
            ["--json", "--v2-json"],
            ["--v2-json", "--json"],
        ):
            for auth in (
                ["--anonymous"],
                ["--api-key-env", "APIWELLS_BUG001_TEST_KEY"],
                ["--api-key-env", "APIWELLS_BUG001_MISSING_KEY"],
            ):
                with self.subTest(flags=flags, auth=auth):
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with (
                        patch.dict(os.environ, {
                            "APIWELLS_BUG001_TEST_KEY": secret,
                            "APIWELLS_BUG001_MISSING_KEY": "",
                        }),
                        patch(
                            "apiwells.cli.diagnose",
                            side_effect=AssertionError("Diagnostics must not run"),
                        ) as diagnose,
                        patch("apiwells.cli.run_basic_diagnostics") as basic,
                        patch("apiwells.cli.run_deep_diagnostics") as deep,
                        contextlib.redirect_stdout(stdout),
                        contextlib.redirect_stderr(stderr),
                    ):
                        with self.assertRaises(SystemExit) as error:
                            main([
                                "doctor",
                                "--base-url", "https://example.com/v1",
                                "--chat",
                                "--model", "apiwells-nonexistent-model-contract-test",
                                *auth,
                                *flags,
                            ])

                    self.assertEqual(error.exception.code, 2)
                    self.assertEqual(stdout.getvalue(), "")
                    self.assertIn(
                        "--v2-json is supported for Basic and Deep diagnostics",
                        stderr.getvalue(),
                    )
                    self.assertIn(
                        "For legacy --chat, use --json",
                        stderr.getvalue(),
                    )
                    self.assertNotIn(secret, stdout.getvalue() + stderr.getvalue())
                    diagnose.assert_not_called()
                    basic.assert_not_called()
                    deep.assert_not_called()

    def test_doctor_help_explains_v2_json_scope(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit) as error,
        ):
            main(["doctor", "--help"])

        self.assertEqual(error.exception.code, 0)
        self.assertEqual(stderr.getvalue(), "")
        help_text = " ".join(stdout.getvalue().split())
        self.assertIn("Basic/Deep only; use --json for legacy --chat", help_text)

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
