import os
import socket
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from apiwells.transport import HTTPObservation, open_request


class TransportHandler(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        TransportHandler.calls.append(self.path)

        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/final")
            self.end_headers()
            return

        if self.path == "/error":
            self.send_response(500)
            self.end_headers()
            return

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            TransportHandler,
        )
        cls.thread = threading.Thread(
            target=cls.server.serve_forever,
            daemon=True,
        )
        cls.thread.start()

        cls.base = (
            "http://127.0.0.1:"
            + str(cls.server.server_port)
        )

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        TransportHandler.calls.clear()

    def test_redirect_is_not_followed(self):
        request = urllib.request.Request(
            self.base + "/redirect"
        )

        response = open_request(
            request,
            timeout=1,
        )

        with response:
            self.assertEqual(response.code, 302)

        self.assertEqual(
            TransportHandler.calls,
            ["/redirect"],
        )

    def test_http_error_is_returned_for_inspection(self):
        request = urllib.request.Request(
            self.base + "/error"
        )

        response = open_request(
            request,
            timeout=1,
        )

        with response:
            self.assertEqual(response.code, 500)

        self.assertEqual(
            TransportHandler.calls,
            ["/error"],
        )

    def test_request_is_not_retried(self):
        request = urllib.request.Request(
            self.base + "/error"
        )

        open_request(
            request,
            timeout=1,
        ).close()

        self.assertEqual(
            TransportHandler.calls,
            ["/error"],
        )

    def test_environment_proxy_is_ignored_by_default(self):
        request = urllib.request.Request(
            self.base + "/ok"
        )

        proxy_env = {
            "http_proxy": "http://127.0.0.1:1",
            "HTTP_PROXY": "http://127.0.0.1:1",
            "no_proxy": "",
            "NO_PROXY": "",
        }

        with patch.dict(os.environ, proxy_env):
            response = open_request(
                request,
                timeout=1,
            )

            with response:
                self.assertEqual(response.code, 200)

        self.assertEqual(
            TransportHandler.calls,
            ["/ok"],
        )

    def test_http_observation_is_lazy_and_cached(self):
        request = urllib.request.Request(
            self.base + "/ok"
        )

        observation = HTTPObservation(
            request,
            timeout=1,
        )

        self.assertEqual(
            TransportHandler.calls,
            [],
        )

        first = observation.collect()
        second = observation.collect()

        self.assertIs(
            first,
            second,
        )

        self.assertEqual(
            first.http_status,
            200,
        )

        self.assertEqual(
            first.body,
            b"ok",
        )

        self.assertIsNone(
            first.error_code,
        )

        self.assertEqual(
            TransportHandler.calls,
            ["/ok"],
        )

    def test_http_observation_preserves_http_error_status(self):
        request = urllib.request.Request(
            self.base + "/error"
        )

        observation = HTTPObservation(
            request,
            timeout=1,
        )

        result = observation.collect()

        self.assertEqual(
            result.http_status,
            500,
        )

        self.assertIsNone(
            result.error_code,
        )

        self.assertEqual(
            TransportHandler.calls,
            ["/error"],
        )

    def test_http_observation_classifies_timeout(self):
        request = urllib.request.Request(
            self.base + "/ok"
        )

        with patch(
            "apiwells.transport.open_request",
            side_effect=urllib.error.URLError(
                socket.timeout()
            ),
        ):
            observation = HTTPObservation(
                request,
                timeout=1,
            )

            result = observation.collect()

        self.assertIsNone(
            result.http_status,
        )

        self.assertEqual(
            result.error_code,
            "TIMEOUT",
        )

        self.assertEqual(
            result.body,
            b"",
        )

if __name__ == "__main__":
    unittest.main()