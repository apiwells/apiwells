import io
import os
import socket
import ssl
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import MagicMock, patch

from apiwells.transport import (
    HTTPObservation,
    StreamReadError,
    iter_response_lines,
    open_request,
    verify_tls,
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


class TLSTransportTests(unittest.TestCase):
    def setUp(self):
        self.raw_socket = MagicMock()
        self.raw_socket.makefile.side_effect = lambda *args, **kwargs: io.BytesIO(
            b"HTTP/1.1 200 Connection established\r\n\r\n"
        )
        self.tls_socket = MagicMock()
        self.tls_socket.version.return_value = "TLSv1.3"
        self.tls_socket.cipher.return_value = ("TEST_CIPHER", "TLSv1.3", 256)
        self.context = ssl.create_default_context()
        self.env = {
            "https_proxy": "http://proxy.example:8080",
            "no_proxy": "unrelated.example",
        }

    def check_route(self, env, expected_address, tunneled, use_env_proxy=True):
        # Keep the actual urllib and HTTPSConnection path, replacing only I/O.
        with patch("os.environ", dict(env)), patch(
            "ssl._create_default_https_context", return_value=self.context,
        ), patch.object(
            self.context, "wrap_socket", return_value=self.tls_socket,
        ) as wrap, patch(
            "socket.create_connection", return_value=self.raw_socket,
        ) as connect:
            metadata = verify_tls(
                "https://target.example:8443/v1", 2, use_env_proxy=use_env_proxy,
            )
            self.assertEqual(metadata, ("TLSv1.3", ("TEST_CIPHER", "TLSv1.3", 256)))
            connect.assert_called_once_with(expected_address, 2, None)
            wrap.assert_called_once_with(
                self.raw_socket, server_hostname="target.example",
            )
            self.assertTrue(self.context.check_hostname)
            self.assertEqual(self.context.verify_mode, ssl.CERT_REQUIRED)
            self.tls_socket.sendall.assert_not_called()
            self.tls_socket.close.assert_called_once()
            tls_connect_args = connect.call_args
            if tunneled:
                self.raw_socket.sendall.assert_called_once()
                sent = self.raw_socket.sendall.call_args.args[0]
                self.assertTrue(sent.startswith(b"CONNECT target.example:8443 HTTP/"))
                self.assertNotIn(b"\r\nAuthorization:", sent)
            else:
                self.raw_socket.sendall.assert_not_called()

            # The ordinary HTTP opener must select the same route and SNI.
            connect.reset_mock()
            wrap.reset_mock()
            self.tls_socket.makefile.return_value = io.BytesIO(
                b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"
            )
            with open_request(
                urllib.request.Request("https://target.example:8443/v1/models"),
                timeout=2, use_env_proxy=use_env_proxy,
            ) as response:
                self.assertEqual(response.code, 200)
            connect.assert_called_once_with(*tls_connect_args.args, **tls_connect_args.kwargs)
            wrap.assert_called_once_with(self.raw_socket, server_hostname="target.example")

    def test_env_proxy_matches_http_connect_and_validates_target(self):
        self.check_route(self.env, ("proxy.example", 8080), True)

    def test_no_proxy_matches_http_bypass(self):
        self.env["no_proxy"] = "target.example"
        self.check_route(self.env, ("target.example", 8443), False)

    def test_uppercase_https_proxy_matches_http(self):
        self.check_route(
            {"HTTPS_PROXY": "http://proxy.example:8080", "NO_PROXY": "unrelated.example"},
            ("proxy.example", 8080), True,
        )

    def test_https_proxy_lowercase_precedence_matches_http(self):
        self.env["HTTPS_PROXY"] = "http://other.example:9090"
        self.check_route(self.env, ("proxy.example", 8080), True)

    def test_http_proxy_alone_is_not_used_for_https(self):
        self.check_route(
            {"http_proxy": "http://proxy.example:8080", "no_proxy": "unrelated.example"},
            ("target.example", 8443), False,
        )

    def test_proxy_is_opt_in(self):
        self.check_route(self.env, ("target.example", 8443), False, use_env_proxy=False)

    def test_proxy_auth_is_sent_only_in_connect(self):
        self.env["https_proxy"] = "http://test-user:test-password@proxy.example:8080"
        self.check_route(self.env, ("proxy.example", 8080), True)
        connect_bytes = self.raw_socket.sendall.call_args.args[0]
        self.assertIn(b"Proxy-Authorization: Basic ", connect_bytes)
        self.assertNotIn(b"test-password", connect_bytes)
        origin_bytes = self.tls_socket.sendall.call_args.args[0]
        self.assertNotIn(b"Proxy-Authorization", origin_bytes)

    def test_failed_connect_closes_socket_without_retry(self):
        self.raw_socket.makefile.side_effect = lambda *args, **kwargs: io.BytesIO(
            b"HTTP/1.1 407 Proxy Authentication Required\r\n\r\n"
        )
        with patch.dict(os.environ, self.env, clear=True), patch(
            "socket.create_connection", return_value=self.raw_socket,
        ) as connect:
            with self.assertRaises(OSError):
                verify_tls("https://target.example/v1", 1, use_env_proxy=True)
        connect.assert_called_once()
        self.raw_socket.sendall.assert_called_once()
        self.raw_socket.close.assert_called()


if __name__ == "__main__":
    unittest.main()