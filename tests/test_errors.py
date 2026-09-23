import unittest

from apiwells.models.errors import (
    classify_http_status,
)


class HTTPErrorClassificationTests(
    unittest.TestCase
):
    def test_classifies_standard_http_errors(self):
        cases = {
            301: "HTTP_REDIRECT",
            307: "HTTP_REDIRECT",
            401: "AUTH_INVALID",
            403: "PERMISSION_DENIED",
            404: "NOT_FOUND",
            429: "RATE_LIMITED",
            500: "UPSTREAM_5XX",
            502: "UPSTREAM_5XX",
            503: "UPSTREAM_5XX",
            599: "UPSTREAM_5XX",
        }

        for status, expected in cases.items():
            with self.subTest(status=status):
                self.assertEqual(
                    classify_http_status(status),
                    expected,
                )

    def test_returns_none_for_nonclassified_statuses(self):
        for status in (
            None,
            200,
            201,
            400,
            405,
            422,
        ):
            with self.subTest(status=status):
                self.assertIsNone(
                    classify_http_status(status)
                )


if __name__ == "__main__":
    unittest.main()