import contextlib
import io
import json
import os
import threading
import time
import unittest

from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from unittest.mock import patch

from apiwells.cli import diagnose, main


SECRET = "provider-secret-value-123456"


class LeakHandler(BaseHTTPRequestHandler):
    mode = "normal"
    calls = []

    def log_message(self, *args):
        pass

    def _send_raw(
        self,
        status,
        raw,
        content_type="application/json",
    ):
        self.send_response(status)
        self.send_header(
            "Content-Type",
            content_type,
        )
        self.send_header(
            "Content-Length",
            str(len(raw)),
        )
        self.end_headers()

        try:
            self.wfile.write(raw)
        except (
            BrokenPipeError,
            ConnectionResetError,
        ):
            pass

    def do_POST(self):
        body = self.rfile.read(
            int(
                self.headers.get(
                    "Content-Length",
                    0,
                )
            )
        )

        LeakHandler.calls.append(
            (
                self.path,
                self.headers.get(
                    "Authorization"
                ),
                body,
            )
        )

        if LeakHandler.mode == "timeout":
            time.sleep(0.2)
            return

        if LeakHandler.mode == "401":
            raw = json.dumps(
                {
                    "error": (
                        "Invalid credential "
                        + SECRET
                    )
                }
            ).encode()

            self._send_raw(
                401,
                raw,
            )
            return

        if LeakHandler.mode == "403":
            raw = json.dumps(
                {
                    "error": (
                        "Permission denied for "
                        + SECRET
                    )
                }
            ).encode()

            self._send_raw(
                403,
                raw,
            )
            return

        if LeakHandler.mode == "invalid_json":
            self._send_raw(
                200,
                (
                    "not-json "
                    + SECRET
                ).encode(),
            )
            return

        raw = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "ok",
                        }
                    }
                ]
            }
        ).encode()

        self._send_raw(
            200,
            raw,
        )


class SecretLeakTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            LeakHandler,
        )

        cls.thread = threading.Thread(
            target=cls.server.serve_forever,
            daemon=True,
        )

        cls.thread.start()

        cls.base = (
            "http://127.0.0.1:"
            + str(cls.server.server_port)
            + "/v1"
        )

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        LeakHandler.mode = "normal"
        LeakHandler.calls.clear()

    def _diagnose(
        self,
        mode,
        *,
        timeout=1.0,
    ):
        LeakHandler.mode = mode

        return diagnose(
            base_url=self.base,
            key=SECRET,
            model="demo-model",
            timeout=timeout,
            allow_http=True,
        )

    def _assert_report_safe(self, report):
        rendered = json.dumps(
            report,
            ensure_ascii=True,
        )

        self.assertNotIn(
            SECRET,
            rendered,
        )

    def test_normal_response_does_not_leak_secret(self):
        report = self._diagnose(
            "normal"
        )

        self._assert_report_safe(
            report
        )

    def test_401_does_not_leak_secret(self):
        report = self._diagnose(
            "401"
        )

        self._assert_report_safe(
            report
        )

    def test_403_does_not_leak_secret(self):
        report = self._diagnose(
            "403"
        )

        self._assert_report_safe(
            report
        )

    def test_invalid_json_does_not_leak_secret(self):
        report = self._diagnose(
            "invalid_json"
        )

        self._assert_report_safe(
            report
        )

    def test_timeout_does_not_leak_secret(self):
        report = self._diagnose(
            "timeout",
            timeout=0.05,
        )

        self._assert_report_safe(
            report
        )

    def test_console_output_does_not_leak_secret(self):
        LeakHandler.mode = "normal"

        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch.dict(
                os.environ,
                {
                    "APIWELLS_API_KEY": SECRET,
                },
            ),
            contextlib.redirect_stdout(
                stdout
            ),
            contextlib.redirect_stderr(
                stderr
            ),
        ):
            exit_code = main(
                [
                    "doctor",
                    "--base-url",
                    self.base,
                    "--chat",
                    "--model",
                    "demo-model",
                    "--allow-http",
                ]
            )

        rendered = (
            stdout.getvalue()
            + stderr.getvalue()
        )

        self.assertEqual(
            exit_code,
            0,
        )

        self.assertNotIn(
            SECRET,
            rendered,
        )

    def test_json_output_does_not_leak_secret(self):
        LeakHandler.mode = "401"

        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch.dict(
                os.environ,
                {
                    "APIWELLS_API_KEY": SECRET,
                },
            ),
            contextlib.redirect_stdout(
                stdout
            ),
            contextlib.redirect_stderr(
                stderr
            ),
        ):
            exit_code = main(
                [
                    "doctor",
                    "--base-url",
                    self.base,
                    "--chat",
                    "--model",
                    "demo-model",
                    "--allow-http",
                    "--json",
                ]
            )

        rendered = (
            stdout.getvalue()
            + stderr.getvalue()
        )

        self.assertEqual(
            exit_code,
            1,
        )

        self.assertNotIn(
            SECRET,
            rendered,
        )

    def test_unexpected_exception_does_not_leak_traceback(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch.dict(
                os.environ,
                {
                    "APIWELLS_API_KEY": SECRET,
                },
            ),
            patch(
                "apiwells.cli.diagnose",
                side_effect=RuntimeError(
                    "unexpected failure "
                    + SECRET
                ),
            ),
            contextlib.redirect_stdout(
                stdout
            ),
            contextlib.redirect_stderr(
                stderr
            ),
        ):
            exit_code = main(
                [
                    "doctor",
                    "--base-url",
                    self.base,
                    "--chat",
                    "--model",
                    "demo-model",
                    "--allow-http",
                ]
            )

        rendered = (
            stdout.getvalue()
            + stderr.getvalue()
        )

        self.assertEqual(
            exit_code,
            1,
        )

        self.assertNotIn(
            SECRET,
            rendered,
        )

        self.assertNotIn(
            "Traceback",
            rendered,
        )


if __name__ == "__main__":
    unittest.main()