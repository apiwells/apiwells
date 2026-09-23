"""Tool Calling probe for OpenAI-compatible Chat Completions."""

import http.client
import json
import time
import urllib.error
import urllib.request

from .. import __version__
from ..models import (
    ProbeResult,
    ResultStatus,
    SupportStatus,
)
from ..models.errors import classify_http_status
from ..transport import open_request


RESPONSE_LIMIT = 2 * 1024 * 1024


def _is_number(value: object) -> bool:
    """Return whether value is a JSON-style number suitable for this tool."""

    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
    )


def _add_numbers(
    a: int | float,
    b: int | float,
) -> int | float:
    """Side-effect-free local diagnostic tool."""

    return a + b


class ToolCallingProbe:
    """Validate a complete two-request function calling round trip."""

    TOOL_NAME = "add_numbers"

    TOOL_DEFINITION = {
        "type": "function",
        "function": {
            "name": TOOL_NAME,
            "description": (
                "Add two numbers and return their sum."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {
                        "type": "number",
                    },
                    "b": {
                        "type": "number",
                    },
                },
                "required": [
                    "a",
                    "b",
                ],
                "additionalProperties": False,
            },
        },
    }

    def __init__(
        self,
        base_url: str,
        model: str,
        key: str = "",
        timeout: float = 15.0,
        max_tokens: int = 32,
        use_env_proxy: bool = False,
    ) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError(
                "ToolCallingProbe requires a nonempty model."
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
    ) -> float:
        return round(
            (time.monotonic() - start) * 1000,
            2,
        )

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "apiwells/" + __version__,
        }

        if self.key:
            headers["Authorization"] = (
                "Bearer " + self.key
            )

        return headers

    def _request_json(
        self,
        payload: dict,
    ) -> tuple[int | None, object | None, str | None]:
        """Execute exactly one billable request without retries."""

        request = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
        )

        try:
            response = open_request(
                request,
                timeout=self.timeout,
                use_env_proxy=self.use_env_proxy,
            )

            with response:
                http_status = response.code

                if not 200 <= http_status < 300:
                    return (
                        http_status,
                        None,
                        classify_http_status(
                            http_status
                        ),
                    )

                raw = response.read(
                    RESPONSE_LIMIT + 1
                )

        except (
            urllib.error.URLError,
            OSError,
            http.client.HTTPException,
        ):
            return (
                None,
                None,
                "CONNECTION_ERROR",
            )

        if len(raw) > RESPONSE_LIMIT:
            return (
                http_status,
                None,
                "RESPONSE_TOO_LARGE",
            )

        try:
            data = json.loads(raw)

        except (
            ValueError,
            UnicodeError,
            RecursionError,
        ):
            return (
                http_status,
                None,
                "INVALID_JSON",
            )

        return (
            http_status,
            data,
            None,
        )

    @staticmethod
    def _assistant_message(
        data: object,
    ) -> dict | None:
        """Extract the first assistant message from a completion."""

        if not isinstance(data, dict):
            return None

        if "error" in data:
            return None

        choices = data.get("choices")

        if (
            not isinstance(choices, list)
            or not choices
            or not isinstance(choices[0], dict)
        ):
            return None

        message = choices[0].get(
            "message"
        )

        if not isinstance(message, dict):
            return None

        if message.get("role") != "assistant":
            return None

        return message

    @classmethod
    def _validate_tool_call(
        cls,
        message: dict,
    ) -> tuple[
        str | None,
        dict | None,
        str | None,
    ]:
        """Validate the requested diagnostic tool call."""

        tool_calls = message.get(
            "tool_calls"
        )

        if (
            not isinstance(tool_calls, list)
            or not tool_calls
        ):
            return (
                None,
                None,
                "FEATURE_UNSUPPORTED",
            )

        if len(tool_calls) != 1:
            return (
                None,
                None,
                "TOOL_CALL_INVALID",
            )

        tool_call = tool_calls[0]

        if not isinstance(tool_call, dict):
            return (
                None,
                None,
                "TOOL_CALL_INVALID",
            )

        tool_call_id = tool_call.get(
            "id"
        )

        if (
            not isinstance(tool_call_id, str)
            or not tool_call_id.strip()
        ):
            return (
                None,
                None,
                "TOOL_CALL_INVALID",
            )

        if tool_call.get("type") != "function":
            return (
                None,
                None,
                "TOOL_CALL_INVALID",
            )

        function = tool_call.get(
            "function"
        )

        if not isinstance(function, dict):
            return (
                None,
                None,
                "TOOL_CALL_INVALID",
            )

        if function.get("name") != cls.TOOL_NAME:
            return (
                None,
                None,
                "TOOL_CALL_INVALID",
            )

        raw_arguments = function.get(
            "arguments"
        )

        if not isinstance(raw_arguments, str):
            return (
                None,
                None,
                "TOOL_CALL_INVALID",
            )

        try:
            arguments = json.loads(
                raw_arguments
            )

        except (
            ValueError,
            UnicodeError,
            RecursionError,
        ):
            return (
                None,
                None,
                "TOOL_CALL_INVALID",
            )

        if not isinstance(arguments, dict):
            return (
                None,
                None,
                "TOOL_CALL_INVALID",
            )

        if set(arguments) != {
            "a",
            "b",
        }:
            return (
                None,
                None,
                "TOOL_CALL_INVALID",
            )

        if not _is_number(
            arguments["a"]
        ):
            return (
                None,
                None,
                "TOOL_CALL_INVALID",
            )

        if not _is_number(
            arguments["b"]
        ):
            return (
                None,
                None,
                "TOOL_CALL_INVALID",
            )

        # This diagnostic task deliberately asks for 17 + 25.
        # Validate that the model requested the intended operation.
        if (
            arguments["a"] != 17
            or arguments["b"] != 25
        ):
            return (
                None,
                None,
                "TOOL_CALL_INVALID",
            )

        return (
            tool_call_id,
            arguments,
            None,
        )

    def run(self) -> ProbeResult:
        start = time.monotonic()

        user_message = {
            "role": "user",
            "content": (
                "Use the add_numbers tool to calculate "
                "17 + 25. Use the tool rather than "
                "calculating the answer yourself."
            ),
        }

        first_payload = {
            "model": self.model,
            "messages": [
                user_message,
            ],
            "tools": [
                self.TOOL_DEFINITION,
            ],
            "tool_choice": {
                "type": "function",
                "function": {
                    "name": self.TOOL_NAME,
                },
            },
            "max_tokens": self.max_tokens,
            "stream": False,
        }

        (
            first_http_status,
            first_data,
            first_error,
        ) = self._request_json(
            first_payload
        )

        if first_error is not None:
            return ProbeResult(
                name="tool_calling",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary=(
                    "The first Tool Calling request "
                    "could not be validated."
                ),
                metrics={
                    "total_latency_ms": self._elapsed_ms(
                        start
                    ),
                    "request_count": 1,
                },
                evidence={
                    "model": self.model,
                    "first_http_status": (
                        first_http_status
                    ),
                    "round_trip_completed": False,
                },
                error_code=first_error,
            )

        if (
            first_http_status is None
            or not 200 <= first_http_status < 300
        ):
            return ProbeResult(
                name="tool_calling",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary=(
                    "The first Tool Calling request "
                    f"returned HTTP {first_http_status}."
                ),
                metrics={
                    "total_latency_ms": self._elapsed_ms(
                        start
                    ),
                    "request_count": 1,
                },
                evidence={
                    "model": self.model,
                    "first_http_status": (
                        first_http_status
                    ),
                    "round_trip_completed": False,
                },
            )

        first_message = self._assistant_message(
            first_data
        )

        if first_message is None:
            return ProbeResult(
                name="tool_calling",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary=(
                    "The first Tool Calling response "
                    "did not contain a valid assistant message."
                ),
                metrics={
                    "total_latency_ms": self._elapsed_ms(
                        start
                    ),
                    "request_count": 1,
                },
                evidence={
                    "model": self.model,
                    "first_http_status": (
                        first_http_status
                    ),
                    "round_trip_completed": False,
                },
                error_code="TOOL_CALL_INVALID",
            )

        (
            tool_call_id,
            arguments,
            validation_error,
        ) = self._validate_tool_call(
            first_message
        )

        if validation_error == "FEATURE_UNSUPPORTED":
            return ProbeResult(
                name="tool_calling",
                status=ResultStatus.PARTIAL,
                support=SupportStatus.UNSUPPORTED,
                summary=(
                    "The endpoint accepted the request "
                    "but did not return a tool call."
                ),
                metrics={
                    "total_latency_ms": self._elapsed_ms(
                        start
                    ),
                    "request_count": 1,
                },
                evidence={
                    "model": self.model,
                    "first_http_status": (
                        first_http_status
                    ),
                    "round_trip_completed": False,
                },
                error_code="FEATURE_UNSUPPORTED",
            )

        if validation_error is not None:
            return ProbeResult(
                name="tool_calling",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary=(
                    "The model returned an invalid "
                    "tool call."
                ),
                metrics={
                    "total_latency_ms": self._elapsed_ms(
                        start
                    ),
                    "request_count": 1,
                },
                evidence={
                    "model": self.model,
                    "first_http_status": (
                        first_http_status
                    ),
                    "round_trip_completed": False,
                },
                error_code="TOOL_CALL_INVALID",
            )

        local_result = _add_numbers(
            arguments["a"],
            arguments["b"],
        )

        second_payload = {
            "model": self.model,
            "messages": [
                user_message,
                first_message,
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": str(
                        local_result
                    ),
                },
            ],
            "tools": [
                self.TOOL_DEFINITION,
            ],
            "max_tokens": self.max_tokens,
            "stream": False,
        }

        (
            second_http_status,
            second_data,
            second_error,
        ) = self._request_json(
            second_payload
        )

        if second_error is not None:
            return ProbeResult(
                name="tool_calling",
                status=ResultStatus.FAIL,
                support=SupportStatus.SUPPORTED,
                summary=(
                    "The model produced a valid tool call, "
                    "but the second request failed."
                ),
                metrics={
                    "total_latency_ms": self._elapsed_ms(
                        start
                    ),
                    "request_count": 2,
                },
                evidence={
                    "model": self.model,
                    "first_http_status": (
                        first_http_status
                    ),
                    "second_http_status": (
                        second_http_status
                    ),
                    "local_tool_result": (
                        local_result
                    ),
                    "round_trip_completed": False,
                },
                error_code=second_error,
            )

        if (
            second_http_status is None
            or not 200 <= second_http_status < 300
        ):
            return ProbeResult(
                name="tool_calling",
                status=ResultStatus.FAIL,
                support=SupportStatus.SUPPORTED,
                summary=(
                    "The model produced a valid tool call, "
                    "but the second request returned "
                    f"HTTP {second_http_status}."
                ),
                metrics={
                    "total_latency_ms": self._elapsed_ms(
                        start
                    ),
                    "request_count": 2,
                },
                evidence={
                    "model": self.model,
                    "first_http_status": (
                        first_http_status
                    ),
                    "second_http_status": (
                        second_http_status
                    ),
                    "local_tool_result": (
                        local_result
                    ),
                    "round_trip_completed": False,
                },
            )

        final_message = self._assistant_message(
            second_data
        )

        if final_message is None:
            return ProbeResult(
                name="tool_calling",
                status=ResultStatus.FAIL,
                support=SupportStatus.SUPPORTED,
                summary=(
                    "The second Tool Calling response "
                    "did not contain a valid assistant message."
                ),
                metrics={
                    "total_latency_ms": self._elapsed_ms(
                        start
                    ),
                    "request_count": 2,
                },
                evidence={
                    "model": self.model,
                    "first_http_status": (
                        first_http_status
                    ),
                    "second_http_status": (
                        second_http_status
                    ),
                    "local_tool_result": (
                        local_result
                    ),
                    "round_trip_completed": False,
                },
                error_code="TOOL_CALL_INVALID",
            )

        final_content = final_message.get(
            "content"
        )

        if (
            not isinstance(final_content, str)
            or not final_content.strip()
            or "42" not in final_content
        ):
            return ProbeResult(
                name="tool_calling",
                status=ResultStatus.FAIL,
                support=SupportStatus.SUPPORTED,
                summary=(
                    "The second response did not use "
                    "the local tool result as expected."
                ),
                metrics={
                    "total_latency_ms": self._elapsed_ms(
                        start
                    ),
                    "request_count": 2,
                },
                evidence={
                    "model": self.model,
                    "first_http_status": (
                        first_http_status
                    ),
                    "second_http_status": (
                        second_http_status
                    ),
                    "local_tool_result": (
                        local_result
                    ),
                    "round_trip_completed": False,
                },
                error_code="TOOL_CALL_INVALID",
            )

        return ProbeResult(
            name="tool_calling",
            status=ResultStatus.PASS,
            support=SupportStatus.SUPPORTED,
            summary=(
                "Tool Calling completed a valid "
                "two-request round trip."
            ),
            metrics={
                "total_latency_ms": self._elapsed_ms(
                    start
                ),
                "request_count": 2,
            },
            evidence={
                "model": self.model,
                "first_http_status": (
                    first_http_status
                ),
                "second_http_status": (
                    second_http_status
                ),
                "tool_name": self.TOOL_NAME,
                "local_tool_result": (
                    local_result
                ),
                "round_trip_completed": True,
            },
        )