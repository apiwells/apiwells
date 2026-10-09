"""Tool Calling probe for OpenAI-compatible Chat Completions."""

import http.client
import json
import secrets
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


DIAGNOSTIC_CHALLENGE = "apiwells-tool-check"


def _get_diagnostic_value(challenge: str) -> str:
    """Generate a side-effect-free local diagnostic result."""

    if challenge != DIAGNOSTIC_CHALLENGE:
        raise ValueError("Invalid diagnostic challenge.")

    return "apiwells-" + secrets.token_hex(8)


class ToolCallingProbe:
    """Validate a complete two-request function calling round trip."""

    TOOL_NAME = "get_diagnostic_value"

    TOOL_DEFINITION = {
        "type": "function",
        "function": {
            "name": TOOL_NAME,
            "description": (
                "Return a diagnostic value generated only "
                "when this tool executes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "challenge": {
                        "type": "string",
                    },
                },
                "required": [
                    "challenge",
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

    @staticmethod
    def _response_evidence(
        data: object,
    ) -> dict[str, object]:
        """Extract safe scalar diagnostics from a completion response."""

        evidence: dict[str, object] = {}

        if not isinstance(data, dict):
            return evidence

        choices = data.get("choices")

        if (
            isinstance(choices, list)
            and choices
            and isinstance(choices[0], dict)
        ):
            first_choice = choices[0]
            finish_reason = first_choice.get(
                "finish_reason"
            )

            if isinstance(finish_reason, str):
                evidence["first_finish_reason"] = (
                    finish_reason
                )

            message = first_choice.get("message")

            if isinstance(message, dict):
                reasoning = message.get(
                    "reasoning_content"
                )
                evidence[
                    "first_reasoning_content_present"
                ] = bool(
                    isinstance(reasoning, str)
                    and reasoning.strip()
                )

        usage = data.get("usage")

        if isinstance(usage, dict):
            for source, target in (
                (
                    "completion_tokens",
                    "first_completion_tokens",
                ),
                (
                    "total_tokens",
                    "first_total_tokens",
                ),
            ):
                value = usage.get(source)

                if (
                    isinstance(value, int)
                    and not isinstance(value, bool)
                    and value >= 0
                ):
                    evidence[target] = value

        return evidence

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
                "TOOL_CALL_NOT_OBSERVED",
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

        if set(arguments) != {"challenge"}:
            return (
                None,
                None,
                "TOOL_CALL_INVALID",
            )

        if (
            not isinstance(arguments["challenge"], str)
            or arguments["challenge"] != DIAGNOSTIC_CHALLENGE
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
                "This is an API Tool Calling conformance test. "
                "The diagnostic value is not present in this conversation "
                "and must not be guessed. Call get_diagnostic_value "
                'exactly once with challenge="apiwells-tool-check". '
                "Do not give a final answer before receiving the tool "
                "result. After receiving the tool result, return that "
                "exact value."
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
        first_response_evidence = (
            self._response_evidence(first_data)
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
                    **first_response_evidence,
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
                    "tool_call_observed": False,
                    "tool_call_validation": (
                        "not_observed"
                    ),
                    "round_trip_completed": False,
                    **first_response_evidence,
                },
                error_code="FEATURE_UNSUPPORTED",
            )

        if validation_error == "TOOL_CALL_NOT_OBSERVED":
            return ProbeResult(
                name="tool_calling",
                status=ResultStatus.PARTIAL,
                support=SupportStatus.UNKNOWN,
                summary=(
                    "The endpoint accepted the Tool Calling "
                    "request, but no tool call was observed."
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
                    "tool_call_observed": False,
                    "tool_call_validation": (
                        "not_observed"
                    ),
                    "round_trip_completed": False,
                    **first_response_evidence,
                },
                error_code="TOOL_CALL_INVALID",
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
                    "tool_call_observed": True,
                    "tool_call_validation": "invalid",
                    "round_trip_completed": False,
                    **first_response_evidence,
                },
                error_code="TOOL_CALL_INVALID",
            )

        local_result = _get_diagnostic_value(
            arguments["challenge"],
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
                    "tool_call_observed": True,
                    "tool_call_validation": "valid",
                    "round_trip_completed": False,
                    **first_response_evidence,
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
                    "tool_call_observed": True,
                    "tool_call_validation": "valid",
                    "round_trip_completed": False,
                    **first_response_evidence,
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
                    "tool_call_observed": True,
                    "tool_call_validation": "valid",
                    "round_trip_completed": False,
                    **first_response_evidence,
                },
                error_code="TOOL_CALL_INVALID",
            )

        final_content = final_message.get(
            "content"
        )

        if (
            not isinstance(final_content, str)
            or not final_content.strip()
            or local_result not in final_content
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
                    "tool_call_observed": True,
                    "tool_call_validation": "valid",
                    "round_trip_completed": False,
                    **first_response_evidence,
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
                "tool_call_observed": True,
                "tool_call_validation": "valid",
                "round_trip_completed": True,
                **first_response_evidence,
            },
        )
