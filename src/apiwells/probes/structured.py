"""Structured Output probe for OpenAI-compatible Chat Completions."""

import json
import time
import urllib.request

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from .. import __version__
from ..models import (
    ProbeResult,
    ResultStatus,
    SupportStatus,
)
from ..models.errors import classify_http_status
from ..transport import observe_request


class StructuredOutputProbe:
    """Validate strict json_schema Structured Output support."""

    SCHEMA_NAME = "apiwells_diagnostic"

    OUTPUT_SCHEMA = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
            },
            "value": {
                "type": "integer",
            },
        },
        "required": [
            "name",
            "value",
        ],
        "additionalProperties": False,
    }

    def __init__(
        self,
        base_url: str,
        model: str,
        key: str = "",
        timeout: float = 15.0,
        max_tokens: int = 64,
        use_env_proxy: bool = False,
    ) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError(
                "StructuredOutputProbe requires a nonempty model."
            )

        self.base_url = base_url.rstrip("/")
        self.model = model
        self.key = key
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.use_env_proxy = use_env_proxy

        # Validate our own static schema before using it.
        Draft202012Validator.check_schema(
            self.OUTPUT_SCHEMA
        )

        self._validator = Draft202012Validator(
            self.OUTPUT_SCHEMA
        )

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

    def _payload(
        self,
        format_type: str,
    ) -> dict:
        user_message = {
            "role": "user",
            "content": (
                "Return JSON only. Return an object "
                'with name "diagnostic" and value 42.'
            ),
        }

        payload = {
            "model": self.model,
            "messages": [
                user_message,
            ],
            "max_tokens": self.max_tokens,
            "stream": False,
        }

        if format_type == "json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": self.SCHEMA_NAME,
                    "strict": True,
                    "schema": self.OUTPUT_SCHEMA,
                },
            }

        elif format_type == "json_object":
            payload["response_format"] = {
                "type": "json_object",
            }

        else:
            raise ValueError(
                "Unknown structured output format."
            )

        return payload

    def _request(
        self,
        payload: dict,
    ):
        request = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode(
                "utf-8"
            ),
            headers=self._headers(),
        )

        observation = observe_request(
            request,
            timeout=self.timeout,
            use_env_proxy=self.use_env_proxy,
        )

        data = None

        if (
            observation.body
            and not observation.response_too_large
        ):
            try:
                data = json.loads(
                    observation.body
                )
            except (
                ValueError,
                UnicodeError,
                RecursionError,
            ):
                data = None

        return observation, data

    @staticmethod
    def _assistant_content(
        data: object,
    ) -> str | None:
        if not isinstance(data, dict):
            return None

        if "error" in data:
            return None

        choices = data.get(
            "choices"
        )

        if (
            not isinstance(choices, list)
            or not choices
            or not isinstance(
                choices[0],
                dict,
            )
        ):
            return None

        message = choices[0].get(
            "message"
        )

        if not isinstance(
            message,
            dict,
        ):
            return None

        if (
            message.get("role")
            != "assistant"
        ):
            return None

        content = message.get(
            "content"
        )

        if (
            not isinstance(content, str)
            or not content.strip()
        ):
            return None

        return content

    @staticmethod
    def _provider_message(
        data: object,
    ) -> str:
        if not isinstance(data, dict):
            return ""

        error = data.get(
            "error"
        )

        if isinstance(error, dict):
            message = error.get(
                "message"
            )

            if isinstance(message, str):
                return message

        return ""

    @classmethod
    def _explicitly_unsupported(
        cls,
        data: object,
        format_type: str,
    ) -> bool:
        message = cls._provider_message(
            data
        ).lower()

        if not message:
            return False

        unsupported_words = (
            "not supported",
            "unsupported",
            "does not support",
        )

        if not any(
            word in message
            for word in unsupported_words
        ):
            return False

        return (
            format_type.lower()
            in message
            or "response_format"
            in message
        )

    @staticmethod
    def _http_error_code(
        http_status: int | None,
    ) -> str | None:
        return classify_http_status(
            http_status
        )

    def _invalid_implementation(
        self,
        start: float,
        request_count: int,
        json_schema_http_status: int | None,
        json_object_http_status: int | None = None,
    ) -> ProbeResult:
        return ProbeResult(
            name="structured_output",
            status=ResultStatus.FAIL,
            support=SupportStatus.UNKNOWN,
            summary=(
                "The endpoint accepted a Structured "
                "Output request but returned invalid output."
            ),
            metrics={
                "total_latency_ms": self._elapsed_ms(
                    start
                ),
                "request_count": request_count,
            },
            evidence={
                "model": self.model,
                "outcome": (
                    "invalid_implementation"
                ),
                "json_schema_http_status": (
                    json_schema_http_status
                ),
                "json_object_http_status": (
                    json_object_http_status
                ),
                "json_schema_request_accepted": True,
                "schema_validation_passed": False,
            },
            error_code=(
                "STRUCTURED_OUTPUT_INVALID"
            ),
        )

    def run(self) -> ProbeResult:
        start = time.monotonic()

        # -------------------------------------------------
        # Sub-test 1: strict json_schema
        # -------------------------------------------------

        schema_payload = self._payload(
            "json_schema"
        )

        (
            schema_observation,
            schema_data,
        ) = self._request(
            schema_payload
        )

        schema_status = (
            schema_observation.http_status
        )

        if schema_observation.error_code:
            return ProbeResult(
                name="structured_output",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary=(
                    "The json_schema request failed "
                    "before a valid HTTP response was received."
                ),
                metrics={
                    "total_latency_ms": self._elapsed_ms(
                        start
                    ),
                    "request_count": 1,
                },
                evidence={
                    "model": self.model,
                    "outcome": "unknown",
                    "json_schema_http_status": (
                        schema_status
                    ),
                    "json_schema_request_accepted": False,
                },
                error_code=(
                    schema_observation.error_code
                ),
            )

        if schema_observation.response_too_large:
            return ProbeResult(
                name="structured_output",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary=(
                    "The json_schema response exceeded "
                    "the allowed size."
                ),
                metrics={
                    "total_latency_ms": self._elapsed_ms(
                        start
                    ),
                    "request_count": 1,
                },
                evidence={
                    "model": self.model,
                    "outcome": "unknown",
                    "json_schema_http_status": (
                        schema_status
                    ),
                    "json_schema_request_accepted": False,
                },
                error_code="RESPONSE_TOO_LARGE",
            )

        if (
            schema_status is None
            or not 200 <= schema_status < 300
        ):
            if not self._explicitly_unsupported(
                schema_data,
                "json_schema",
            ):
                return ProbeResult(
                    name="structured_output",
                    status=ResultStatus.FAIL,
                    support=SupportStatus.UNKNOWN,
                    summary=(
                        "The json_schema request was "
                        "rejected without proving that "
                        "the capability is unsupported."
                    ),
                    metrics={
                        "total_latency_ms": self._elapsed_ms(
                            start
                        ),
                        "request_count": 1,
                    },
                    evidence={
                        "model": self.model,
                        "outcome": "unknown",
                        "json_schema_http_status": (
                            schema_status
                        ),
                        "json_schema_request_accepted": False,
                    },
                    error_code=self._http_error_code(
                        schema_status
                    ),
                )

            # ---------------------------------------------
            # Sub-test 2: legacy json_object
            #
            # This is an independent capability test,
            # not a retry of the json_schema request.
            # ---------------------------------------------

            object_payload = self._payload(
                "json_object"
            )

            (
                object_observation,
                object_data,
            ) = self._request(
                object_payload
            )

            object_status = (
                object_observation.http_status
            )

            if object_observation.error_code:
                return ProbeResult(
                    name="structured_output",
                    status=ResultStatus.FAIL,
                    support=SupportStatus.UNSUPPORTED,
                    summary=(
                        "json_schema is unsupported, "
                        "but the json_object capability "
                        "test could not complete."
                    ),
                    metrics={
                        "total_latency_ms": self._elapsed_ms(
                            start
                        ),
                        "request_count": 2,
                    },
                    evidence={
                        "model": self.model,
                        "outcome": "unknown",
                        "json_schema_http_status": (
                            schema_status
                        ),
                        "json_object_http_status": (
                            object_status
                        ),
                        "json_schema_request_accepted": False,
                        "json_object_request_accepted": False,
                    },
                    error_code=(
                        object_observation.error_code
                    ),
                )

            if object_observation.response_too_large:
                return ProbeResult(
                    name="structured_output",
                    status=ResultStatus.FAIL,
                    support=SupportStatus.UNSUPPORTED,
                    summary=(
                        "json_schema is unsupported, "
                        "but the json_object response "
                        "exceeded the allowed size."
                    ),
                    metrics={
                        "total_latency_ms": self._elapsed_ms(
                            start
                        ),
                        "request_count": 2,
                    },
                    evidence={
                        "model": self.model,
                        "outcome": "unknown",
                        "json_schema_http_status": (
                            schema_status
                        ),
                        "json_object_http_status": (
                            object_status
                        ),
                        "json_schema_request_accepted": False,
                        "json_object_request_accepted": False,
                    },
                    error_code="RESPONSE_TOO_LARGE",
                )

            if (
                object_status is None
                or not 200 <= object_status < 300
            ):
                if self._explicitly_unsupported(
                    object_data,
                    "json_object",
                ):
                    return ProbeResult(
                        name="structured_output",
                        status=ResultStatus.PARTIAL,
                        support=SupportStatus.UNSUPPORTED,
                        summary=(
                            "Neither json_schema nor "
                            "json_object Structured Output "
                            "mode is supported."
                        ),
                        metrics={
                            "total_latency_ms": self._elapsed_ms(
                                start
                            ),
                            "request_count": 2,
                        },
                        evidence={
                            "model": self.model,
                            "outcome": "unsupported",
                            "json_schema_http_status": (
                                schema_status
                            ),
                            "json_object_http_status": (
                                object_status
                            ),
                            "json_schema_request_accepted": False,
                            "json_object_request_accepted": False,
                        },
                        error_code="FEATURE_UNSUPPORTED",
                    )

                return ProbeResult(
                    name="structured_output",
                    status=ResultStatus.FAIL,
                    support=SupportStatus.UNSUPPORTED,
                    summary=(
                        "json_schema is unsupported, "
                        "but the json_object capability "
                        "test was rejected without proving "
                        "that json_object is unsupported."
                    ),
                    metrics={
                        "total_latency_ms": self._elapsed_ms(
                            start
                        ),
                        "request_count": 2,
                    },
                    evidence={
                        "model": self.model,
                        "outcome": "unknown",
                        "json_schema_http_status": (
                            schema_status
                        ),
                        "json_object_http_status": (
                            object_status
                        ),
                        "json_schema_request_accepted": False,
                        "json_object_request_accepted": False,
                    },
                    error_code=self._http_error_code(
                        object_status
                    ),
                )

            object_content = self._assistant_content(
                object_data
            )

            if object_content is None:
                return ProbeResult(
                    name="structured_output",
                    status=ResultStatus.FAIL,
                    support=SupportStatus.UNSUPPORTED,
                    summary=(
                        "json_object was accepted but did "
                        "not return valid assistant content."
                    ),
                    metrics={
                        "total_latency_ms": self._elapsed_ms(
                            start
                        ),
                        "request_count": 2,
                    },
                    evidence={
                        "model": self.model,
                        "outcome": (
                            "invalid_implementation"
                        ),
                        "json_schema_http_status": (
                            schema_status
                        ),
                        "json_object_http_status": (
                            object_status
                        ),
                        "json_schema_request_accepted": False,
                        "json_object_request_accepted": True,
                    },
                    error_code=(
                        "STRUCTURED_OUTPUT_INVALID"
                    ),
                )

            try:
                object_value = json.loads(
                    object_content
                )
            except (
                ValueError,
                UnicodeError,
                RecursionError,
            ):
                return ProbeResult(
                    name="structured_output",
                    status=ResultStatus.FAIL,
                    support=SupportStatus.UNSUPPORTED,
                    summary=(
                        "json_object was accepted but "
                        "returned invalid JSON."
                    ),
                    metrics={
                        "total_latency_ms": self._elapsed_ms(
                            start
                        ),
                        "request_count": 2,
                    },
                    evidence={
                        "model": self.model,
                        "outcome": (
                            "invalid_implementation"
                        ),
                        "json_schema_http_status": (
                            schema_status
                        ),
                        "json_object_http_status": (
                            object_status
                        ),
                        "json_schema_request_accepted": False,
                        "json_object_request_accepted": True,
                    },
                    error_code=(
                        "STRUCTURED_OUTPUT_INVALID"
                    ),
                )

            if not isinstance(
                object_value,
                dict,
            ):
                return ProbeResult(
                    name="structured_output",
                    status=ResultStatus.FAIL,
                    support=SupportStatus.UNSUPPORTED,
                    summary=(
                        "json_object was accepted but "
                        "did not return a JSON object."
                    ),
                    metrics={
                        "total_latency_ms": self._elapsed_ms(
                            start
                        ),
                        "request_count": 2,
                    },
                    evidence={
                        "model": self.model,
                        "outcome": (
                            "invalid_implementation"
                        ),
                        "json_schema_http_status": (
                            schema_status
                        ),
                        "json_object_http_status": (
                            object_status
                        ),
                        "json_schema_request_accepted": False,
                        "json_object_request_accepted": True,
                    },
                    error_code=(
                        "STRUCTURED_OUTPUT_INVALID"
                    ),
                )

            return ProbeResult(
                name="structured_output",
                status=ResultStatus.PARTIAL,
                support=SupportStatus.UNSUPPORTED,
                summary=(
                    "Strict json_schema is unsupported, "
                    "but json_object mode is supported."
                ),
                metrics={
                    "total_latency_ms": self._elapsed_ms(
                        start
                    ),
                    "request_count": 2,
                },
                evidence={
                    "model": self.model,
                    "outcome": "json_object_only",
                    "json_schema_http_status": (
                        schema_status
                    ),
                    "json_object_http_status": (
                        object_status
                    ),
                    "json_schema_request_accepted": False,
                    "json_object_request_accepted": True,
                },
                error_code="FEATURE_UNSUPPORTED",
            )

        # -------------------------------------------------
        # json_schema was accepted.
        # It must now produce valid JSON that passes the
        # actual local JSON Schema validator.
        # -------------------------------------------------

        content = self._assistant_content(
            schema_data
        )

        if content is None:
            return self._invalid_implementation(
                start=start,
                request_count=1,
                json_schema_http_status=(
                    schema_status
                ),
            )

        try:
            structured_value = json.loads(
                content
            )

        except (
            ValueError,
            UnicodeError,
            RecursionError,
        ):
            return self._invalid_implementation(
                start=start,
                request_count=1,
                json_schema_http_status=(
                    schema_status
                ),
            )

        try:
            self._validator.validate(
                structured_value
            )

        except ValidationError:
            return self._invalid_implementation(
                start=start,
                request_count=1,
                json_schema_http_status=(
                    schema_status
                ),
            )

        return ProbeResult(
            name="structured_output",
            status=ResultStatus.PASS,
            support=SupportStatus.SUPPORTED,
            summary=(
                "Strict json_schema Structured Output "
                "passed JSON Schema validation."
            ),
            metrics={
                "total_latency_ms": self._elapsed_ms(
                    start
                ),
                "request_count": 1,
            },
            evidence={
                "model": self.model,
                "outcome": "supported",
                "json_schema_http_status": (
                    schema_status
                ),
                "json_schema_request_accepted": True,
                "schema_validation_passed": True,
            },
        )