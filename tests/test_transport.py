import io
import os
import socket
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from apiwells.transport import (
    HTTPObservation,
    StreamReadError,
    iter_response_lines,
    open_request,
)


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

    def test_iter_response_lines_is_lazy(self):
        class LazyResponse:
            def __init__(self):
                self.calls = 0
                self.lines = iter(
                    [
                        b"data: one\n",
                        b"\n",
                        b"data: two\n",
                        b"\n",
                    ]
                )

            def readline(self, size=-1):
                self.calls += 1

                try:
                    line = next(self.lines)
                except StopIteration:
                    return b""

                if size >= 0:
                    return line[:size]

                return line

        response = LazyResponse()

        lines = iter_response_lines(
            response,
            line_limit=100,
            stream_limit=1000,
        )

        self.assertEqual(
            response.calls,
            0,
        )

        self.assertEqual(
            next(lines),
            b"data: one\n",
        )

        self.assertEqual(
            response.calls,
            1,
        )

        self.assertEqual(
            next(lines),
            b"\n",
        )

        self.assertEqual(
            response.calls,
            2,
        )

    def test_iter_response_lines_preserves_raw_lines(self):
        response = io.BytesIO(
            b"data: one\r\n"
            b"\r\n"
            b"data: two\n"
            b"\n"
        )

        lines = list(
            iter_response_lines(
                response,
                line_limit=100,
                stream_limit=1000,
            )
        )

        self.assertEqual(
            lines,
            [
                b"data: one\r\n",
                b"\r\n",
                b"data: two\n",
                b"\n",
            ],
        )

    def test_iter_response_lines_stops_at_eof(self):
        response = io.BytesIO(
            b"data: one\n\n"
        )

        lines = list(
            iter_response_lines(
                response,
                line_limit=100,
                stream_limit=1000,
            )
        )

        self.assertEqual(
            lines,
            [
                b"data: one\n",
                b"\n",
            ],
        )

    def test_iter_response_lines_rejects_oversized_line(self):
        response = io.BytesIO(
            b"12345678901\n"
        )

        with self.assertRaisesRegex(
            StreamReadError,
            "line exceeded",
        ):
            list(
                iter_response_lines(
                    response,
                    line_limit=10,
                    stream_limit=100,
                )
            )

    def test_iter_response_lines_rejects_oversized_stream(self):
        response = io.BytesIO(
            b"12345\n"
            b"67890\n"
        )

        with self.assertRaisesRegex(
            StreamReadError,
            "total size",
        ):
            list(
                iter_response_lines(
                    response,
                    line_limit=10,
                    stream_limit=10,
                )
            )

    def test_iter_response_lines_accepts_exact_limits(self):
        response = io.BytesIO(
            b"1234\n"
            b"5678\n"
        )

        lines = list(
            iter_response_lines(
                response,
                line_limit=5,
                stream_limit=10,
            )
        )

        self.assertEqual(
            lines,
            [
                b"1234\n",
                b"5678\n",
            ],
        )

    def test_iter_response_lines_validates_limits(self):
        response = io.BytesIO(
            b"data: one\n\n"
        )

        with self.assertRaisesRegex(
            ValueError,
            "line_limit",
        ):
            list(
                iter_response_lines(
                    response,
                    line_limit=0,
                )
            )

        with self.assertRaisesRegex(
            ValueError,
            "stream_limit",
        ):
            list(
                iter_response_lines(
                    response,
                    stream_limit=0,
                )
            )

        with self.assertRaisesRegex(
            ValueError,
            "greater than or equal",
        ):
            list(
                iter_response_lines(
                    response,
                    line_limit=100,
                    stream_limit=50,
                )
            )

if __name__ == "__main__":
    unittest.main()