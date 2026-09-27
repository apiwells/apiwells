import json
import ssl
import threading
import unittest
from unittest.mock import patch
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)

from apiwells.models import (
    ResultStatus,
    SupportStatus,
)
from apiwells.runner import run_deep_diagnostics
from apiwells.transport import open_request
from apiwells.reporting import build_json_report


class DeepHandler(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        DeepHandler.calls.append(
            (
                "GET",
                self.path,
                self.headers.get(
                    "Authorization"
                ),
                None,
            )
        )

        prefix = self.path.split("/")[1]

        if prefix == "unauthorized":
            self.send_response(401)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header(
            "Content-Type",
            "application/json",
        )
        self.end_headers()

        model_id = (
            "other-model"
            if prefix == "missing"
            else "demo-model"
        )

        raw = json.dumps(
            {
                "data": [
                    {
                        "id": model_id
                    }
                ]
            }
        ).encode()

        self.wfile.write(raw)

    def do_POST(self):
        body = self.rfile.read(
            int(
                self.headers.get(
                    "Content-Length",
                    0,
                )
            )
        )

        payload = json.loads(body)

        prefix = self.path.split("/")[1]

        DeepHandler.calls.append(
            (
                "POST",
                self.path,
                self.headers.get(
                    "Authorization"
                ),
                payload,
            )
        )

        # Tool Calling requests must be detected before the
        # ordinary non-stream Chat branch because Tool Calling
        # itself also uses stream=False.
        if "tools" in payload:
            has_tool_result = any(
                isinstance(message, dict)
                and message.get("role") == "tool"
                for message in payload.get(
                    "messages",
                    []
                )
            )

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/json",
            )
            self.end_headers()

            if has_tool_result:
                raw = {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": (
                                    "The result is " + next(
                                        message["content"]
                                        for message in payload["messages"]
                                        if message.get("role") == "tool"
                                    )
                                ),
                            }
                        }
                    ]
                }

            elif prefix == "toolunsupported":
                raw = {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": (
                                    "The result is 42."
                                ),
                            }
                        }
                    ]
                }

            elif prefix == "toolinvalid":
                raw = {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call-1",
                                        "type": "function",
                                        "function": {
                                            "name": "wrong_tool",
                                            "arguments": (
                                                '{"challenge":"apiwells-tool-check"}'
                                            ),
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                }

            else:
                raw = {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call-1",
                                        "type": "function",
                                        "function": {
                                            "name": "get_diagnostic_value",
                                            "arguments": (
                                                '{"challenge":"apiwells-tool-check"}'
                                            ),
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                }

            self.wfile.write(
                json.dumps(raw).encode()
            )
            return
        # Streaming request.
        if payload.get("stream"):
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/event-stream",
            )
            self.end_headers()

            lines = [
                (
                    b'data: {"choices":['
                    b'{"delta":{"role":"assistant"}}]}\n'
                ),
                b"\n",
                (
                    b'data: {"choices":['
                    b'{"delta":{"content":"OK"}}]}\n'
                ),
                b"\n",
                b"data: [DONE]\n",
                b"\n",
            ]

            for line in lines:
                self.wfile.write(line)
                self.wfile.flush()

            return

        if (
            payload.get("response_format", {})
            .get("type")
            == "json_schema"
        ):
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/json",
            )
            self.end_headers()

            raw = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": (
                                '{"name":"diagnostic",'
                                '"value":42}'
                            ),
                        }
                    }
                ]
            }

            self.wfile.write(
                json.dumps(raw).encode()
            )
            return

        # Ordinary non-stream Chat request.
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "application/json",
        )
        self.end_headers()

        raw = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "OK",
                        }
                    }
                ]
            }
        ).encode()

        self.wfile.write(raw)


class DeepRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            DeepHandler,
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
        DeepHandler.calls.clear()

    def test_deep_chain_runs_basic_chat_streaming_and_tools(self):
        results = run_deep_diagnostics(
            self.base + "/v1",
            model="demo-model",
            key="secret-test-key",
            timeout=1,
            max_tokens=8,
        )

        self.assertEqual(
            [result.name for result in results],
            [
                "url",
                "dns",
                "tls",
                "http",
                "auth",
                "models",
                "chat",
                "streaming",
                "tool_calling",
                "structured_output",
            ],
        )

        self.assertTrue(
            all(
                result.status
                is ResultStatus.PASS
                for result in results
            )
        )

        streaming = next(
            result
            for result in results
            if result.name == "streaming"
        )

        tool_calling = next(
            result
            for result in results
            if result.name == "tool_calling"
        )

        structured = next(
            result
            for result in results
            if result.name == "structured_output"
        )

        self.assertEqual(
            streaming.support,
            SupportStatus.SUPPORTED,
        )

        self.assertIsNotNone(
            streaming.metrics["ttft_ms"]
        )

        self.assertIn(
            "total_latency_ms",
            streaming.metrics,
        )

        self.assertEqual(
            tool_calling.status,
            ResultStatus.PASS,
        )

        self.assertEqual(
            tool_calling.support,
            SupportStatus.SUPPORTED,
        )

        self.assertTrue(
            tool_calling.evidence[
                "round_trip_completed"
            ]
        )

        self.assertRegex(
            tool_calling.evidence["local_tool_result"],
            r"^apiwells-[0-9a-f]{16}$",
        )

        self.assertEqual(
            tool_calling.metrics[
                "request_count"
            ],
            2,
        )

        # 整个 Deep 链应该产生：
        # 1 x GET /models
        # 1 x Chat POST
        # 1 x Streaming POST
        # 2 x Tool Calling POST
        # 1 x Structured Output POST
        self.assertEqual(
            [call[0] for call in DeepHandler.calls],
            [
                "GET",
                "POST",
                "POST",
                "POST",
                "POST",
                "POST",
            ],
        )

        self.assertEqual(
            DeepHandler.calls[0][1],
            "/v1/models",
        )

        for call in DeepHandler.calls[1:]:
            structured_payload = (
                DeepHandler.calls[5][3]
            )

            self.assertEqual(
                structured_payload[
                    "response_format"
                ]["type"],
                "json_schema",
            )

            self.assertTrue(
                structured_payload[
                    "response_format"
                ]["json_schema"]["strict"]
            )
            self.assertEqual(
                call[1],
                "/v1/chat/completions",
            )

        # Chat request
        self.assertFalse(
            DeepHandler.calls[1][3]["stream"]
        )

        # Streaming request
        self.assertTrue(
            DeepHandler.calls[2][3]["stream"]
        )

        # ---------- Tool Calling round trip ----------

        first_tool_payload = (
            DeepHandler.calls[3][3]
        )

        second_tool_payload = (
            DeepHandler.calls[4][3]
        )

        # 第一次 Tool 请求必须真正声明 get_diagnostic_value 工具
        self.assertIn(
            "tools",
            first_tool_payload,
        )

        self.assertEqual(
            first_tool_payload[
                "tools"
            ][0]["function"]["name"],
            "get_diagnostic_value",
        )

        self.assertFalse(
            first_tool_payload["stream"]
        )

        # 第二次请求必须把本地工具执行结果回传给模型
        tool_messages = [
            message
            for message in second_tool_payload[
                "messages"
            ]
            if message.get("role") == "tool"
        ]

        self.assertEqual(
            len(tool_messages),
            1,
        )

        self.assertEqual(
            tool_messages[0][
                "tool_call_id"
            ],
            "call-1",
        )

        self.assertEqual(
            tool_messages[0][
                "content"
            ],
            tool_calling.evidence["local_tool_result"],
        )

        self.assertEqual(
            structured.status,
            ResultStatus.PASS,
        )

        self.assertEqual(
            structured.support,
            SupportStatus.SUPPORTED,
        )

        self.assertEqual(
            structured.evidence[
                "outcome"
            ],
            "supported",
        )

        self.assertTrue(
            structured.evidence[
                "schema_validation_passed"
            ],
        )

        self.assertEqual(
            structured.metrics[
                "request_count"
            ],
            1,
        )

        self.assertEqual(
            len(DeepHandler.calls),
            6,
        )

        for call in DeepHandler.calls[1:]:
            self.assertEqual(
                call[1],
                "/v1/chat/completions",
            )

    def test_basic_failure_blocks_billable_probes(self):
        results = run_deep_diagnostics(
            self.base + "/unauthorized",
            model="demo-model",
            key="bad-key",
            timeout=1,
        )

        self.assertEqual(
            [result.name for result in results],
            [
                "url",
                "dns",
                "tls",
                "http",
                "auth",
                "models",
            ],
        )

        auth = next(
            result
            for result in results
            if result.name == "auth"
        )

        self.assertEqual(
            auth.status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            DeepHandler.calls,
            [
                (
                    "GET",
                    "/unauthorized/models",
                    "Bearer bad-key",
                    None,
                )
            ],
        )

    def test_missing_target_model_blocks_billable_probes(self):
        results = run_deep_diagnostics(
            self.base + "/missing",
            model="demo-model",
            timeout=1,
            authentication_requested=False,
        )

        models = next(
            result
            for result in results
            if result.name == "models"
        )

        self.assertFalse(
            models.evidence[
                "target_model_found"
            ]
        )

        self.assertEqual(
            [call[0] for call in DeepHandler.calls],
            [
                "GET",
            ],
        )

    def test_deep_requires_nonempty_model(self):
        with self.assertRaises(ValueError):
            run_deep_diagnostics(
                self.base + "/v1",
                model="",
            )

        self.assertEqual(
            DeepHandler.calls,
            [],
        )

    def test_deep_reports_tool_calling_unsupported(self):
        results = run_deep_diagnostics(
            self.base + "/toolunsupported",
            model="demo-model",
            timeout=1,
            authentication_requested=False,
        )

        tool_result = next(
            result
            for result in results
            if result.name == "tool_calling"
        )

        self.assertEqual(
            tool_result.status,
            ResultStatus.PARTIAL,
        )

        self.assertEqual(
            tool_result.support,
            SupportStatus.UNKNOWN,
        )

        self.assertEqual(
            tool_result.error_code,
            "TOOL_CALL_INVALID",
        )

        self.assertFalse(
            tool_result.evidence[
                "round_trip_completed"
            ]
        )

        # GET models + Chat + Streaming + first Tool request.
        # No second Tool request should occur.
        self.assertEqual(
            len(DeepHandler.calls),
            5,
        )

        self.assertEqual(
            [call[0] for call in DeepHandler.calls],
            [
                "GET",
                "POST",
                "POST",
                "POST",
                "POST",
            ],
        )

    def test_deep_reports_invalid_tool_call_failure(self):
        results = run_deep_diagnostics(
            self.base + "/toolinvalid",
            model="demo-model",
            timeout=1,
            authentication_requested=False,
        )

        tool_result = next(
            result
            for result in results
            if result.name == "tool_calling"
        )

        self.assertEqual(
            tool_result.status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            tool_result.support,
            SupportStatus.UNKNOWN,
        )

        self.assertEqual(
            tool_result.error_code,
            "TOOL_CALL_INVALID",
        )

        self.assertFalse(
            tool_result.evidence[
                "round_trip_completed"
            ]
        )

        # Invalid first tool call must not trigger a second billable request.
        self.assertEqual(
            len(DeepHandler.calls),
            5,
        )


    def test_proxy_tls_result_controls_deep_gate_even_when_models_succeeds(self):
        basic_order = ["url", "dns", "tls", "http", "auth", "models"]
        for failure in (None, ssl.SSLCertVerificationError(1, "test-proxy-secret")):
            with self.subTest(tls_failure=failure is not None):
                DeepHandler.calls.clear()

                def local_http(request, timeout, use_env_proxy=False):
                    self.assertTrue(use_env_proxy)
                    # Route the HTTPS request to our existing local HTTP fixture.
                    request.full_url = request.full_url.replace("https://", "http://", 1)
                    return open_request(request, timeout, use_env_proxy=False)

                with patch(
                    "apiwells.probes.connectivity.verify_tls",
                    return_value=("TLSv1.3", ("TEST_CIPHER", "TLSv1.3", 256)),
                    side_effect=failure,
                ) as handshake, patch(
                    "apiwells.transport.open_request", side_effect=local_http,
                ), patch(
                    "apiwells.probes.streaming.open_request", side_effect=local_http,
                ), patch(
                    "apiwells.probes.chat.open_request", side_effect=local_http,
                ), patch(
                    "apiwells.probes.tools.open_request", side_effect=local_http,
                ):
                    base = self.base.replace("http://", "https://") + "/v1"
                    results = run_deep_diagnostics(
                        base, model="demo-model", key="secret-test-key",
                        timeout=1, use_env_proxy=True,
                    )
                handshake.assert_called_once_with(base, timeout=1, use_env_proxy=True)
                self.assertTrue(all(r.status is ResultStatus.PASS for r in results[3:6]))
                self.assertTrue(results[5].evidence["target_model_found"])
                order = basic_order if failure else basic_order + [
                    "chat", "streaming", "tool_calling", "structured_output",
                ]
                self.assertEqual([r.name for r in results], order)
                if failure:
                    self.assertEqual(results[2].error_code, "TLS_ERROR")
                    self.assertEqual([call[0] for call in DeepHandler.calls], ["GET"])
                else:
                    self.assertTrue(all(r.status is ResultStatus.PASS for r in results))
                    self.assertEqual([call[0] for call in DeepHandler.calls], ["GET"] + ["POST"] * 5)
                report = build_json_report(results)
                self.assertEqual(report["schema_version"], "1")
                self.assertEqual(set(report), {
                    "schema_version", "apiwells_version", "overall_status", "probes",
                })
                self.assertEqual([r["name"] for r in report["probes"]], order)
                for probe in report["probes"]:
                    self.assertEqual(set(probe), {
                        "name", "status", "support", "summary", "metrics", "evidence", "error_code",
                    })
                for secret in ("test-proxy-secret", "secret-test-key", "Authorization"):
                    self.assertNotIn(secret, json.dumps(report))


if __name__ == "__main__":
    unittest.main()