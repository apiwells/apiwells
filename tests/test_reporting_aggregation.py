import unittest

from apiwells.models import (
    ProbeResult,
    ResultStatus,
    SupportStatus,
)
from apiwells.reporting.aggregation import (
    aggregate_overall_status,
)


def make_result(
    name,
    status,
    support=SupportStatus.NOT_APPLICABLE,
):
    return ProbeResult(
        name=name,
        status=status,
        support=support,
        summary=f"{name} diagnostic result.",
    )


class OverallStatusTests(unittest.TestCase):
    def test_all_pass_returns_pass(self):
        results = [
            make_result("url", ResultStatus.PASS),
            make_result("dns", ResultStatus.PASS),
            make_result("tls", ResultStatus.PASS),
            make_result("http", ResultStatus.PASS),
            make_result(
                "models",
                ResultStatus.PASS,
                SupportStatus.SUPPORTED,
            ),
        ]

        self.assertEqual(
            aggregate_overall_status(results),
            ResultStatus.PASS,
        )

    def test_basic_failure_returns_fail(self):
        results = [
            make_result("url", ResultStatus.PASS),
            make_result("dns", ResultStatus.FAIL),
        ]

        self.assertEqual(
            aggregate_overall_status(results),
            ResultStatus.FAIL,
        )

    def test_basic_partial_returns_partial(self):
        results = [
            make_result("url", ResultStatus.PASS),
            make_result("http", ResultStatus.PARTIAL),
        ]

        self.assertEqual(
            aggregate_overall_status(results),
            ResultStatus.PARTIAL,
        )

    def test_unsupported_capability_returns_partial(self):
        results = [
            make_result("url", ResultStatus.PASS),
            make_result("dns", ResultStatus.PASS),
            make_result(
                "tool_calling",
                ResultStatus.PARTIAL,
                SupportStatus.UNSUPPORTED,
            ),
        ]

        self.assertEqual(
            aggregate_overall_status(results),
            ResultStatus.PARTIAL,
        )

    def test_failed_capability_does_not_mark_endpoint_failed(self):
        results = [
            make_result("url", ResultStatus.PASS),
            make_result("dns", ResultStatus.PASS),
            make_result(
                "structured_output",
                ResultStatus.FAIL,
                SupportStatus.UNKNOWN,
            ),
        ]

        self.assertEqual(
            aggregate_overall_status(results),
            ResultStatus.PARTIAL,
        )

    def test_chat_failure_returns_fail(self):
        results = [
            make_result("url", ResultStatus.PASS),
            make_result("models", ResultStatus.PASS),
            make_result(
                "chat",
                ResultStatus.FAIL,
                SupportStatus.UNKNOWN,
            ),
        ]

        self.assertEqual(
            aggregate_overall_status(results),
            ResultStatus.FAIL,
        )

    def test_empty_results_rejected(self):
        with self.assertRaises(ValueError):
            aggregate_overall_status([])


if __name__ == "__main__":
    unittest.main()