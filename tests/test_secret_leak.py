import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from apiwells.cli import diagnose


SECRET = "provider-secret-value-123456"


class LeakHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        body = json.dumps(
            {
                "error": (
                    "Invalid credential "
                    + SECRET
                )
            }
        ).encode()

        self.send_response(401)
        self.send_header(
            "Content-Type",
            "application/json",
        )
        self.send_header(
            "Content-Length",
            str(len(body)),
        )
        self.end_headers()

        self.wfile.write(body)

    def log_message(self, *args):
        pass


class SecretLeakTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(
            ("127.0.0.1", 0),
            LeakHandler,
        )

        cls.port = cls.server.server_port

        cls.thread = threading.Thread(
            target=cls.server.serve_forever,
            daemon=True,
        )

        cls.thread.start()


    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()


    def test_provider_error_body_does_not_leak_secret(self):

        report = diagnose(
            base_url=(
                f"http://127.0.0.1:"
                f"{self.port}/v1"
            ),
            key=SECRET,
            model="test-model",
            allow_http=True,
        )

        rendered = json.dumps(
            report,
            ensure_ascii=True,
        )

        self.assertNotIn(
            SECRET,
            rendered,
        )


if __name__ == "__main__":
    unittest.main()