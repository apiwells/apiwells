"""Probe for OpenAI-compatible non-stream Chat Completions."""

import http.client
import json
import time
import urllib.error
import urllib.request

from .. import __version__
from ..models import ProbeResult, ResultStatus, SupportStatus
from ..models.errors import classify_http_status
from ..transport import open_request
from .usage import extract_usage


RESPONSE_LIMIT = 2 * 1024 * 1024


class ChatProbe:
    """Validate one non-stream Chat Completions request."""

    def __init__(
        self,
        base_url: str,
        model: str,
        key: str = "",
        timeout: float = 15.0,
        max_tokens: int = 512,
        use_env_proxy: bool = False,
    ) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("ChatProbe requires a nonempty model.")

        self.base_url = base_url.rstrip("/")
        self.model = model
        self.key = key
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.use_env_proxy = use_env_proxy

    @staticmethod
    def _elapsed_ms(start: float) -> float:
        return round((time.monotonic() - start) * 1000, 2)

    def run(self) -> ProbeResult:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "apiwells/" + __version__,
        }

        if self.key:
            headers["Authorization"] = "Bearer " + self.key

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": "Reply OK.",
                }
            ],
            "max_tokens": self.max_tokens,
            "stream": False,
        }

        request = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
        )

        start = time.monotonic()

        try:
            response = open_request(
                request,
                timeout=self.timeout,
                use_env_proxy=self.use_env_proxy,
            )

            with response:
                http_status = response.code

                if not 200 <= http_status < 300:
                    return ProbeResult(
                        name="chat",
                        status=ResultStatus.FAIL,
                        support=SupportStatus.UNKNOWN,
                        summary=f"Chat request returned HTTP {http_status}.",
                        metrics={
                            "total_latency_ms": self._elapsed_ms(start),
                        },
                        evidence={
                            "http_status": http_status,
                            "model": self.model,
                        },
                        error_code=classify_http_status(
                            http_status
                        ),
                    )

                raw = response.read(RESPONSE_LIMIT + 1)

        except (
            urllib.error.URLError,
            OSError,
            http.client.HTTPException,
        ):
            return ProbeResult(
                name="chat",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary="Chat request failed before a valid response was received.",
                metrics={
                    "total_latency_ms": self._elapsed_ms(start),
                },
                evidence={
                    "model": self.model,
                },
                error_code="CONNECTION_ERROR",
            )

        total_latency_ms = self._elapsed_ms(start)

        if len(raw) > RESPONSE_LIMIT:
            return ProbeResult(
                name="chat",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary="Chat response exceeded the allowed size.",
                metrics={
                    "total_latency_ms": total_latency_ms,
                },
                evidence={
                    "http_status": http_status,
                    "model": self.model,
                    "response_too_large": True,
                },
            )

        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError, RecursionError):
            return ProbeResult(
                name="chat",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary="Chat response was not valid JSON.",
                metrics={
                    "total_latency_ms": total_latency_ms,
                },
                evidence={
                    "http_status": http_status,
                    "model": self.model,
                },
                error_code="INVALID_JSON",
            )

        usage = extract_usage(data)

        if not isinstance(data, dict) or "error" in data:
            return ProbeResult(
                name="chat",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary="Chat response did not contain the expected object structure.",
                metrics={
                    "total_latency_ms": total_latency_ms,
                },
                evidence={
                    "http_status": http_status,
                    "model": self.model,
                },
                error_code="INVALID_SCHEMA",
            )

        choices = data.get("choices")

        if (
            not isinstance(choices, list)
            or not choices
            or not isinstance(choices[0], dict)
        ):
            return ProbeResult(
                name="chat",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary="Chat response did not contain a valid choices list.",
                metrics={
                    "total_latency_ms": total_latency_ms,
                },
                evidence={
                    "http_status": http_status,
                    "model": self.model,
                },
                error_code="INVALID_SCHEMA",
            )

        message = choices[0].get("message")

        if (
            not isinstance(message, dict)
            or message.get("role") != "assistant"
            or not isinstance(message.get("content"), str)
            or not message["content"].strip()
        ):
            return ProbeResult(
                name="chat",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary="Chat response did not contain nonempty assistant content.",
                metrics={
                    "total_latency_ms": total_latency_ms,
                },
                evidence={
                    "http_status": http_status,
                    "model": self.model,
                },
                error_code="INVALID_SCHEMA",
            )

        return ProbeResult(
            name="chat",
            status=ResultStatus.PASS,
            support=SupportStatus.SUPPORTED,
            summary="Non-stream Chat Completions request succeeded.",
            metrics={
                "total_latency_ms": total_latency_ms,
                **usage.as_metrics(),
            },
            evidence={
                "http_status": http_status,
                "model": self.model,
            },
        )