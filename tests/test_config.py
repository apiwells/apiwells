import unittest

from apiwells.config import normalize_endpoint


class ConfigTests(unittest.TestCase):
    def test_normalizes_trailing_slash(self):
        self.assertEqual(
            normalize_endpoint("https://example.com/v1/"),
            "https://example.com/v1",
        )

    def test_allows_loopback_http(self):
        self.assertEqual(
            normalize_endpoint("http://127.0.0.1:8000/v1"),
            "http://127.0.0.1:8000/v1",
        )

    def test_rejects_remote_http_by_default(self):
        with self.assertRaises(ValueError):
            normalize_endpoint("http://example.com/v1")

    def test_rejects_endpoint_route_instead_of_base(self):
        with self.assertRaises(ValueError):
            normalize_endpoint(
                "https://example.com/v1/models"
            )

    def test_rejects_query_credentials_and_fragments(self):
        invalid_urls = [
            "https://user:pass@example.com/v1",
            "https://example.com/v1?key=secret",
            "https://example.com/v1#fragment",
        ]

        for url in invalid_urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    normalize_endpoint(url)


if __name__ == "__main__":
    unittest.main()