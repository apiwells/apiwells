"""SSE parsing and OpenAI-compatible Streaming probe."""

import http.client
import json
import time
import urllib.error
import urllib.request

from dataclasses import dataclass

from .. import __version__
from ..models import ProbeResult, ResultStatus, SupportStatus
from ..transport import (
    StreamReadError,
    iter_response_lines,
    open_request,
)
from .usage import UsageObservation, extract_usage


class SSEParseError(ValueError):
    """Raised when an SSE stream cannot be parsed safely."""


@dataclass(frozen=True)
class SSEEvent:
    """One complete Server-Sent Event."""

    data: str


class SSEParser:
    """Incrementally parse SSE framing one line at a time."""

    def __init__(self) -> None:
        self._data_lines: list[str] = []

    @property
    def has_pending_event(self) -> bool:
        """Return whether data exists without a terminating event boundary."""

        return bool(self._data_lines)

    def feed_line(
        self,
        raw_line: bytes | str,
    ) -> SSEEvent | None:
        """Consume one SSE line and emit an event at a blank-line boundary."""

        if isinstance(raw_line, bytes):
            try:
                line = raw_line.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise SSEParseError(
                    "SSE stream was not valid UTF-8."
                ) from exc

        elif isinstance(raw_line, str):
            line = raw_line

        else:
            raise TypeError(
                "SSEParser.feed_line() requires bytes or str."
            )

        if line.endswith("\n"):
            line = line[:-1]

        if line.endswith("\r"):
            line = line[:-1]

        if line == "":
            if not self._data_lines:
                return None

            event = SSEEvent(
                data="\n".join(self._data_lines)
            )

            self._data_lines.clear()

            return event

        if line.startswith(":"):
            return None

        field, separator, value = line.partition(":")

        if separator and value.startswith(" "):
            value = value[1:]

        if field == "data":
            self._data_lines.append(
                value if separator else ""
            )

        return None


class StreamingProbe:
    """Validate one OpenAI-compatible SSE Chat Completions stream."""

    def __init__(
        self,
        base_url: str,
        model: str,
        key: str = "",
        timeout: float = 15.0,
        max_tokens: int = 8,
        use_env_proxy: bool = False,
    ) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError(
                "StreamingProbe requires a nonempty model."
            )

        self.base_url = base_url.rstrip("/")
        self.model = model
        self.key = key
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.use_env_proxy = use_env_proxy

    @staticmethod
    def _elapsed_ms(
        start: float,
        end: float | None = None,
    ) -> float:
        if end is None:
            end = time.monotonic()

        return round(
            (end - start) * 1000,
            2,
        )

    @staticmethod
    def _is_sse_content_type(
        content_type: str,
    ) -> bool:
        media_type = (
            content_type
            .split(";", 1)[0]
            .strip()
            .lower()
        )

        return media_type == "text/event-stream"

    @staticmethod
    def _has_meaningful_output(
        chunk: dict,
    ) -> bool:
        """Return whether a chunk contains actual model output."""

        choices = chunk.get("choices")

        if not isinstance(choices, list):
            return False

        for choice in choices:
            if not isinstance(choice, dict):
                continue

            delta = choice.get("delta")

            if not isinstance(delta, dict):
                continue

            content = delta.get("content")

            if isinstance(content, str) and content != "":
                return True

            refusal = delta.get("refusal")

            if isinstance(refusal, str) and refusal != "":
                return True

        return False

    @staticmethod
    def _merge_usage(
        current: UsageObservation,
        observed: UsageObservation,
    ) -> UsageObservation:
        """Merge only token counts actually reported by the provider."""

        if not observed.available:
            return current

        return UsageObservation(
            available=True,
            prompt_tokens=(
                observed.prompt_tokens
                if observed.prompt_tokens is not None
                else current.prompt_tokens
            ),
            completion_tokens=(
                observed.completion_tokens
                if observed.completion_tokens is not None
                else current.completion_tokens
            ),
            total_tokens=(
                observed.total_tokens
                if observed.total_tokens is not None
                else current.total_tokens
            ),
        )

    @staticmethod
    def _metrics(
        total_latency_ms: float,
        ttft_ms: float | None,
        chunk_count: int,
        usage: UsageObservation | None = None,
    ) -> dict:
        if usage is None:
            usage = UsageObservation(
                available=False
            )

        return {
            "ttft_ms": ttft_ms,
            "total_latency_ms": total_latency_ms,
            "chunk_count": chunk_count,
            **usage.as_metrics(),
        }

    def run(self) -> ProbeResult:
        headers = {
            "Accept": "text/event-stream",
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
            "stream": True,
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

        except (
            urllib.error.URLError,
            OSError,
            http.client.HTTPException,
        ):
            total_latency_ms = self._elapsed_ms(start)

            return ProbeResult(
                name="streaming",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary=(
                    "Streaming request failed before "
                    "a valid response was received."
                ),
                metrics=self._metrics(
                    total_latency_ms,
                    None,
                    0,
                ),
                evidence={
                    "model": self.model,
                    "content_received": False,
                    "usage_available": False,
                    "terminal_event_seen": False,
                },
                error_code="CONNECTION_ERROR",
            )

        parser = SSEParser()

        chunk_count = 0
        ttft_ms: float | None = None
        content_received = False

        usage = UsageObservation(
            available=False
        )

        terminal_event_seen = False
        sse_event_seen = False
        completion_time: float | None = None

        with response:
            http_status = response.code

            content_type = response.headers.get(
                "Content-Type",
                "",
            )

            if not 200 <= http_status < 300:
                total_latency_ms = self._elapsed_ms(start)

                return ProbeResult(
                    name="streaming",
                    status=ResultStatus.FAIL,
                    support=SupportStatus.UNKNOWN,
                    summary=(
                        "Streaming request returned "
                        f"HTTP {http_status}."
                    ),
                    metrics=self._metrics(
                        total_latency_ms,
                        None,
                        0,
                    ),
                    evidence={
                        "http_status": http_status,
                        "model": self.model,
                        "content_type": content_type,
                        "content_received": False,
                        "usage_available": False,
                        "terminal_event_seen": False,
                    },
                )

            try:
                for raw_line in iter_response_lines(
                    response
                ):
                    event = parser.feed_line(
                        raw_line
                    )

                    if event is None:
                        continue

                    sse_event_seen = True

                    event_data = event.data.strip()

                    if not event_data:
                        continue

                    if event_data == "[DONE]":
                        terminal_event_seen = True
                        completion_time = time.monotonic()
                        break

                    try:
                        chunk = json.loads(
                            event.data
                        )

                    except (
                        ValueError,
                        UnicodeError,
                        RecursionError,
                    ):
                        total_latency_ms = self._elapsed_ms(
                            start
                        )

                        return ProbeResult(
                            name="streaming",
                            status=ResultStatus.FAIL,
                            support=(
                                SupportStatus.SUPPORTED
                                if content_received
                                else SupportStatus.UNKNOWN
                            ),
                            summary=(
                                "SSE data event was not "
                                "valid JSON."
                            ),
                            metrics=self._metrics(
                                total_latency_ms,
                                ttft_ms,
                                chunk_count,
                                usage,
                            ),
                            evidence={
                                "http_status": http_status,
                                "model": self.model,
                                "content_type": content_type,
                                "content_received": content_received,
                                "usage_available": usage.available,
                                "terminal_event_seen": (
                                    terminal_event_seen
                                ),
                            },
                            error_code="SSE_INVALID",
                        )

                    if not isinstance(chunk, dict):
                        total_latency_ms = self._elapsed_ms(
                            start
                        )

                        return ProbeResult(
                            name="streaming",
                            status=ResultStatus.FAIL,
                            support=(
                                SupportStatus.SUPPORTED
                                if content_received
                                else SupportStatus.UNKNOWN
                            ),
                            summary=(
                                "SSE JSON event did not "
                                "contain an object."
                            ),
                            metrics=self._metrics(
                                total_latency_ms,
                                ttft_ms,
                                chunk_count,
                                usage,
                            ),
                            evidence={
                                "http_status": http_status,
                                "model": self.model,
                                "content_type": content_type,
                                "content_received": content_received,
                                "usage_available": usage.available,
                                "terminal_event_seen": (
                                    terminal_event_seen
                                ),
                            },
                            error_code="INVALID_SCHEMA",
                        )

                    chunk_count += 1

                    observed_usage = extract_usage(
                        chunk
                    )

                    usage = self._merge_usage(
                        usage,
                        observed_usage,
                    )

                    if (
                        not content_received
                        and self._has_meaningful_output(
                            chunk
                        )
                    ):
                        content_received = True

                        ttft_ms = self._elapsed_ms(
                            start
                        )

                if completion_time is None:
                    completion_time = time.monotonic()

            except (
                SSEParseError,
                StreamReadError,
            ):
                total_latency_ms = self._elapsed_ms(
                    start
                )

                return ProbeResult(
                    name="streaming",
                    status=ResultStatus.FAIL,
                    support=(
                        SupportStatus.SUPPORTED
                        if content_received
                        else SupportStatus.UNKNOWN
                    ),
                    summary=(
                        "Streaming response contained "
                        "invalid SSE framing."
                    ),
                    metrics=self._metrics(
                        total_latency_ms,
                        ttft_ms,
                        chunk_count,
                        usage,
                    ),
                    evidence={
                        "http_status": http_status,
                        "model": self.model,
                        "content_type": content_type,
                        "content_received": content_received,
                        "usage_available": usage.available,
                        "terminal_event_seen": (
                            terminal_event_seen
                        ),
                    },
                    error_code="SSE_INVALID",
                )

            except (
                urllib.error.URLError,
                OSError,
                http.client.HTTPException,
            ):
                total_latency_ms = self._elapsed_ms(
                    start
                )

                return ProbeResult(
                    name="streaming",
                    status=ResultStatus.FAIL,
                    support=(
                        SupportStatus.SUPPORTED
                        if content_received
                        else SupportStatus.UNKNOWN
                    ),
                    summary=(
                        "Streaming response was interrupted "
                        "before normal completion."
                    ),
                    metrics=self._metrics(
                        total_latency_ms,
                        ttft_ms,
                        chunk_count,
                        usage,
                    ),
                    evidence={
                        "http_status": http_status,
                        "model": self.model,
                        "content_type": content_type,
                        "content_received": content_received,
                        "usage_available": usage.available,
                        "terminal_event_seen": (
                            terminal_event_seen
                        ),
                    },
                    error_code="STREAM_INTERRUPTED",
                )

        total_latency_ms = self._elapsed_ms(
            start,
            completion_time,
        )

        evidence = {
            "http_status": http_status,
            "model": self.model,
            "content_type": content_type,
            "content_received": content_received,
            "usage_available": usage.available,
            "terminal_event_seen": terminal_event_seen,
        }

        metrics = self._metrics(
            total_latency_ms,
            ttft_ms,
            chunk_count,
            usage,
        )

        if parser.has_pending_event:
            return ProbeResult(
                name="streaming",
                status=ResultStatus.FAIL,
                support=(
                    SupportStatus.SUPPORTED
                    if content_received
                    else SupportStatus.UNKNOWN
                ),
                summary=(
                    "Streaming response ended inside "
                    "an incomplete SSE event."
                ),
                metrics=metrics,
                evidence=evidence,
                error_code="SSE_INVALID",
            )

        if not sse_event_seen:
            if not self._is_sse_content_type(
                content_type
            ):
                return ProbeResult(
                    name="streaming",
                    status=ResultStatus.PARTIAL,
                    support=SupportStatus.UNSUPPORTED,
                    summary=(
                        "The endpoint returned a response, "
                        "but did not produce an SSE event stream."
                    ),
                    metrics=metrics,
                    evidence=evidence,
                    error_code="FEATURE_UNSUPPORTED",
                )

            return ProbeResult(
                name="streaming",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary=(
                    "The endpoint declared an SSE response "
                    "but no valid SSE data events were received."
                ),
                metrics=metrics,
                evidence=evidence,
                error_code="SSE_INVALID",
            )

        if not content_received:
            return ProbeResult(
                name="streaming",
                status=ResultStatus.FAIL,
                support=SupportStatus.SUPPORTED,
                summary=(
                    "The SSE stream completed without "
                    "meaningful model output."
                ),
                metrics=metrics,
                evidence=evidence,
                error_code="INVALID_SCHEMA",
            )

        if not terminal_event_seen:
            return ProbeResult(
                name="streaming",
                status=ResultStatus.PARTIAL,
                support=SupportStatus.SUPPORTED,
                summary=(
                    "Streaming produced model output but "
                    "ended without a terminal [DONE] event."
                ),
                metrics=metrics,
                evidence=evidence,
            )

        if not self._is_sse_content_type(
            content_type
        ):
            return ProbeResult(
                name="streaming",
                status=ResultStatus.PARTIAL,
                support=SupportStatus.SUPPORTED,
                summary=(
                    "Streaming worked, but the response "
                    "did not declare text/event-stream."
                ),
                metrics=metrics,
                evidence=evidence,
            )

        return ProbeResult(
            name="streaming",
            status=ResultStatus.PASS,
            support=SupportStatus.SUPPORTED,
            summary=(
                "SSE Streaming Chat Completions request succeeded."
            ),
            metrics=metrics,
            evidence=evidence,
        )