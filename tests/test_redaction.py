import unittest

from apiwells.models import (
    ProbeResult,
    ResultStatus,
    SupportStatus,
)
from apiwells.reporting import (
    REDACTED,
    redact_probe_result,
    redact_text,
    redact_value,
)


SECRET = "provider-secret-value-123456"


class RedactionTests(unittest.TestCase):
    def test_redacts_explicit_secret(self):
        text = (
            f"Request failed using key {SECRET}."
        )

        result = redact_text(
            text,
            secrets=(SECRET,),
        )

        self.assertNotIn(SECRET, result)
        self.assertIn(REDACTED, result)

    def test_redacts_authorization_header(self):
        text = (
            "Authorization: "
            "Bearer sk-apiwells-secret-value"
        )

        result = redact_text(text)

        self.assertNotIn(
            "sk-apiwells-secret-value",
            result,
        )
        self.assertIn(REDACTED, result)

    def test_redacts_secret_query_parameter(self):
        text = (
            "https://example.com/v1"
            "?api_key=secret-query-value"
            "&model=test"
        )

        result = redact_text(text)

        self.assertNotIn(
            "secret-query-value",
            result,
        )
        self.assertIn(
            f"api_key={REDACTED}",
            result,
        )

    def test_recursively_redacts_nested_values(self):
        value = {
            "message": f"failed with {SECRET}",
            "nested": [
                {
                    "authorization": (
                        "Bearer "
                        "sk-nested-secret-value"
                    )
                }
            ],
        }

        result = redact_value(
            value,
            secrets=(SECRET,),
        )

        rendered = repr(result)

        self.assertNotIn(
            SECRET,
            rendered,
        )
        self.assertNotIn(
            "sk-nested-secret-value",
            rendered,
        )

    def test_redacts_exception_message(self):
        error = RuntimeError(
            f"provider rejected {SECRET}"
        )

        result = redact_value(
            error,
            secrets=(SECRET,),
        )

        self.assertNotIn(
            SECRET,
            result,
        )
        self.assertIn(
            REDACTED,
            result,
        )

    def test_redacts_probe_result_without_mutating_original(self):
        original = ProbeResult(
            name="chat",
            status=ResultStatus.FAIL,
            support=SupportStatus.UNKNOWN,
            summary=(
                f"Provider rejected {SECRET}."
            ),
            evidence={
                "provider_message": (
                    f"Authorization: Bearer {SECRET}"
                ),
                "nested": {
                    "url": (
                        "https://example.com/v1"
                        f"?api_key={SECRET}"
                    )
                },
            },
            error_code="PERMISSION_DENIED",
        )

        safe = redact_probe_result(
            original,
            secrets=(SECRET,),
        )

        self.assertIn(
            SECRET,
            original.summary,
        )

        self.assertNotIn(
            SECRET,
            safe.summary,
        )

        self.assertNotIn(
            SECRET,
            repr(safe.evidence),
        )


if __name__ == "__main__":
    unittest.main()