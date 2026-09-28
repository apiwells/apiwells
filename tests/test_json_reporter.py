import json
import unittest

from apiwells import __version__
from apiwells.models import (
    ProbeResult,
    ResultStatus,
    SupportStatus,
)
from apiwells.reporting.json_report import (
    build_json_report,
)


SECRET = "sk-apiwells-json-reporter-secret"


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


class JsonReporterTests(unittest.TestCase):
    def test_builds_versioned_report(self):
        results = [
            make_result("url"),
            make_result("dns"),
            make_result(
                "models",
                support=SupportStatus.SUPPORTED,
            ),
        ]

        report = build_json_report(results)

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

    def test_preserves_probe_order(self):
        results = [
            make_result("url"),
            make_result("dns"),
            make_result("tls"),
            make_result("http"),
        ]

        report = build_json_report(results)

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
            ],
        )

    def test_probe_contract_has_stable_core_fields(self):
        result = make_result(
            "models",
            support=SupportStatus.SUPPORTED,
            metrics={
                "model_count": 2,
            },
            evidence={
                "http_status": 200,
            },
        )

        report = build_json_report([result])

        probe = report["probes"][0]

        self.assertEqual(
            set(probe),
            {
                "name",
                "status",
                "support",
                "summary",
                "metrics",
                "evidence",
                "error_code",
            },
        )

        self.assertEqual(
            probe["status"],
            "PASS",
        )
        self.assertEqual(
            probe["support"],
            "SUPPORTED",
        )
        self.assertEqual(
            probe["metrics"]["model_count"],
            2,
        )
        self.assertEqual(
            probe["evidence"]["http_status"],
            200,
        )
        self.assertIsNone(
            probe["error_code"]
        )

    def test_unsupported_capability_makes_overall_partial(self):
        results = [
            make_result("url"),
            make_result("dns"),
            make_result(
                "tool_calling",
                status=ResultStatus.PARTIAL,
                support=SupportStatus.UNSUPPORTED,
                error_code="FEATURE_UNSUPPORTED",
            ),
        ]

        report = build_json_report(results)

        self.assertEqual(
            report["overall_status"],
            "PARTIAL",
        )

        tool = report["probes"][-1]

        self.assertEqual(
            tool["status"],
            "PARTIAL",
        )
        self.assertEqual(
            tool["support"],
            "UNSUPPORTED",
        )
        self.assertEqual(
            tool["error_code"],
            "FEATURE_UNSUPPORTED",
        )

    def test_core_failure_makes_overall_fail(self):
        results = [
            make_result("url"),
            make_result(
                "auth",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                error_code="AUTH_INVALID",
            ),
        ]

        report = build_json_report(results)

        self.assertEqual(
            report["overall_status"],
            "FAIL",
        )

    def test_report_redacts_explicit_secret_everywhere(self):
        result = make_result(
            "models",
            summary=(
                "Provider returned secret "
                + SECRET
            ),
            metrics={
                "nested": {
                    "token": SECRET,
                }
            },
            evidence={
                "authorization": (
                    "Bearer " + SECRET
                ),
                "provider_message": (
                    "request failed for "
                    + SECRET
                ),
            },
        )

        report = build_json_report(
            [result],
            secrets=(SECRET,),
        )

        rendered = json.dumps(
            report,
            ensure_ascii=True,
            allow_nan=False,
        )

        self.assertNotIn(
            SECRET,
            rendered,
        )
        self.assertIn(
            "[REDACTED]",
            rendered,
        )

    def test_report_is_json_serializable(self):
        result = make_result(
            "streaming",
            support=SupportStatus.SUPPORTED,
            metrics={
                "ttft_ms": 123.45,
                "chunk_count": 3,
            },
            evidence={
                "terminal_event_seen": True,
            },
        )

        report = build_json_report([result])

        rendered = json.dumps(
            report,
            ensure_ascii=True,
            allow_nan=False,
        )

        decoded = json.loads(rendered)

        self.assertEqual(
            decoded,
            report,
        )

    def test_empty_results_are_rejected(self):
        with self.assertRaises(ValueError):
            build_json_report([])


if __name__ == "__main__":
    unittest.main()