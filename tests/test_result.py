import unittest

from apiwells.models import ProbeResult, ResultStatus, SupportStatus


class ProbeResultTests(unittest.TestCase):
    def test_valid_result(self):
        result = ProbeResult(
            name="models",
            status=ResultStatus.PASS,
            support=SupportStatus.SUPPORTED,
            summary="Models endpoint returned a valid model list.",
        )

        self.assertEqual(result.name, "models")
        self.assertEqual(result.status, ResultStatus.PASS)
        self.assertEqual(result.support, SupportStatus.SUPPORTED)
        self.assertEqual(result.metrics, {})
        self.assertEqual(result.evidence, {})
        self.assertIsNone(result.error_code)

    def test_status_and_support_are_independent(self):
        result = ProbeResult(
            name="tool_calling",
            status=ResultStatus.PARTIAL,
            support=SupportStatus.UNSUPPORTED,
            summary="Tool calling is not supported by the tested model.",
        )

        self.assertEqual(result.status, ResultStatus.PARTIAL)
        self.assertEqual(result.support, SupportStatus.UNSUPPORTED)

    def test_mutable_defaults_are_not_shared(self):
        first = ProbeResult(
            name="first",
            status=ResultStatus.PASS,
            support=SupportStatus.NOT_APPLICABLE,
            summary="First probe passed.",
        )

        second = ProbeResult(
            name="second",
            status=ResultStatus.PASS,
            support=SupportStatus.NOT_APPLICABLE,
            summary="Second probe passed.",
        )

        first.metrics["latency_ms"] = 10

        self.assertEqual(second.metrics, {})

    def test_requires_nonempty_name_and_summary(self):
        with self.assertRaises(ValueError):
            ProbeResult(
                name="",
                status=ResultStatus.PASS,
                support=SupportStatus.NOT_APPLICABLE,
                summary="Valid summary.",
            )

        with self.assertRaises(ValueError):
            ProbeResult(
                name="dns",
                status=ResultStatus.PASS,
                support=SupportStatus.NOT_APPLICABLE,
                summary="",
            )

    def test_accepts_registered_error_code(self):
        result = ProbeResult(
            name="dns",
            status=ResultStatus.FAIL,
            support=SupportStatus.NOT_APPLICABLE,
            summary="DNS resolution failed.",
            error_code="DNS_ERROR",
        )

        self.assertEqual(
            result.error_code,
            "DNS_ERROR",
        )

    def test_rejects_unknown_error_code(self):
        with self.assertRaisesRegex(
            ValueError,
            "Unknown error_code",
        ):
            ProbeResult(
                name="dns",
                status=ResultStatus.FAIL,
                support=SupportStatus.NOT_APPLICABLE,
                summary="DNS resolution failed.",
                error_code="MADE_UP_ERROR",
            )


if __name__ == "__main__":
    unittest.main()