"""Unified OpenAI-compatible mock provider."""

import json
import time

from werkzeug.wrappers import Response

from .responses import (
    chat_response,
    models_response,
    streaming_response,
    structured_response,
    tool_call_response,
    tool_final_response,
)


def _json_response(
    payload: dict,
    status: int = 200,
) -> Response:
    return Response(
        json.dumps(payload),
        status=status,
        content_type="application/json",
    )


def _chat_completions_handler(request):
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return _json_response(
            {
                "error": {
                    "message": "invalid JSON request"
                }
            },
            status=400,
        )

    # 1. Streaming
    if payload.get("stream") is True:
        return Response(
            streaming_response(),
            status=200,
            content_type="text/event-stream",
        )

    # 2. Structured Output
    response_format = payload.get(
        "response_format"
    )

    if isinstance(response_format, dict):
        return _json_response(
            structured_response()
        )

    # 3. Tool Calling
    if "tools" in payload:
        messages = payload.get(
            "messages",
            [],
        )

        is_second_tool_request = any(
            isinstance(message, dict)
            and message.get("role") == "tool"
            for message in messages
        )

        if is_second_tool_request:
            return _json_response(
                tool_final_response()
            )

        return _json_response(
            tool_call_response()
        )

    # 4. Normal non-stream Chat
    return _json_response(
        chat_response()
    )


def register_happy_path_routes(httpserver):
    """Register the ED-030 happy-path provider."""

    httpserver.expect_request(
        "/v1/models",
        method="GET",
    ).respond_with_json(
        models_response()
    )

    httpserver.expect_request(
        "/v1/chat/completions",
        method="POST",
    ).respond_with_handler(
        _chat_completions_handler
    )


def register_http_error_route(
    httpserver,
    *,
    status_code: int,
    message: str,
):
    """Return one HTTP error for chat completions."""

    state = {
        "request_count": 0,
    }

    def handler(request):
        state["request_count"] += 1

        return _json_response(
            {
                "error": {
                    "message": message,
                }
            },
            status=status_code,
        )

    httpserver.expect_request(
        "/v1/chat/completions",
        method="POST",
    ).respond_with_handler(
        handler
    )

    return state


def register_invalid_json_route(httpserver):
    """Return HTTP 200 with a non-JSON body."""

    httpserver.expect_request(
        "/v1/chat/completions",
        method="POST",
    ).respond_with_handler(
        lambda request: Response(
            "<html>not-json</html>",
            status=200,
            content_type="application/json",
        )
    )


def register_broken_sse_route(httpserver):
    """Return malformed JSON inside a valid SSE response."""

    body = (
        "data: {not-json}\n\n"
        "data: [DONE]\n\n"
    )

    httpserver.expect_request(
        "/v1/chat/completions",
        method="POST",
    ).respond_with_handler(
        lambda request: Response(
            body,
            status=200,
            content_type="text/event-stream",
        )
    )


def register_tool_unsupported_route(httpserver):
    """Model answers normally instead of issuing a tool call."""

    def handler(request):
        return _json_response(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "42",
                        }
                    }
                ]
            }
        )

    httpserver.expect_request(
        "/v1/chat/completions",
        method="POST",
    ).respond_with_handler(
        handler
    )


def register_structured_json_object_only_route(
    httpserver,
):
    """
    Reject json_schema explicitly but accept json_object.

    This represents a partially compatible provider.
    """

    state = {
        "request_count": 0,
    }

    def handler(request):
        state["request_count"] += 1

        payload = request.get_json(
            silent=True
        ) or {}

        response_format = payload.get(
            "response_format",
            {},
        )

        format_type = response_format.get(
            "type"
        )

        if format_type == "json_schema":
            return _json_response(
                {
                    "error": {
                        "message": (
                            "response_format type "
                            "json_schema is not supported"
                        )
                    }
                },
                status=400,
            )

        if format_type == "json_object":
            return _json_response(
                structured_response()
            )

        return _json_response(
            {
                "error": {
                    "message": (
                        "unexpected response_format"
                    )
                }
            },
            status=400,
        )

    httpserver.expect_request(
        "/v1/chat/completions",
        method="POST",
    ).respond_with_handler(
        handler
    )

    return state


def register_basic_flow_routes(httpserver):
    """Register routes for the ED-030.2 Basic full-flow test.

    The returned state allows the integration test to prove that
    Basic mode performs exactly one /models request and does not
    execute any billable chat/capability request.
    """

    state = {
        "models_request_count": 0,
        "chat_request_count": 0,
    }

    def models_handler(request):
        state["models_request_count"] += 1

        return _json_response(
            models_response()
        )

    def unexpected_chat_handler(request):
        state["chat_request_count"] += 1

        return _json_response(
            {
                "error": {
                    "message": (
                        "Basic diagnostics must not execute "
                        "chat completions."
                    )
                }
            },
            status=500,
        )

    httpserver.expect_request(
        "/v1/models",
        method="GET",
    ).respond_with_handler(
        models_handler
    )

    httpserver.expect_request(
        "/v1/chat/completions",
        method="POST",
    ).respond_with_handler(
        unexpected_chat_handler
    )

    return state


def register_basic_auth_failure_routes(httpserver):
    """Return HTTP 401 from /models for Basic full-flow testing."""

    state = {
        "models_request_count": 0,
        "chat_request_count": 0,
    }

    def models_handler(request):
        state["models_request_count"] += 1

        return _json_response(
            {
                "error": {
                    "message": "invalid API key",
                }
            },
            status=401,
        )

    def unexpected_chat_handler(request):
        state["chat_request_count"] += 1

        return _json_response(
            {
                "error": {
                    "message": (
                        "Basic diagnostics must not execute "
                        "chat completions."
                    )
                }
            },
            status=500,
        )

    httpserver.expect_request(
        "/v1/models",
        method="GET",
    ).respond_with_handler(
        models_handler
    )

    httpserver.expect_request(
        "/v1/chat/completions",
        method="POST",
    ).respond_with_handler(
        unexpected_chat_handler
    )

    return state


def register_basic_invalid_json_routes(httpserver):
    """Return HTTP 200 with an invalid /models JSON body."""

    state = {
        "models_request_count": 0,
        "chat_request_count": 0,
    }

    def models_handler(request):
        state["models_request_count"] += 1

        return Response(
            "<html>not-json</html>",
            status=200,
            content_type="application/json",
        )

    def unexpected_chat_handler(request):
        state["chat_request_count"] += 1

        return _json_response(
            {
                "error": {
                    "message": (
                        "Basic diagnostics must not execute "
                        "chat completions."
                    )
                }
            },
            status=500,
        )

    httpserver.expect_request(
        "/v1/models",
        method="GET",
    ).respond_with_handler(
        models_handler
    )

    httpserver.expect_request(
        "/v1/chat/completions",
        method="POST",
    ).respond_with_handler(
        unexpected_chat_handler
    )

    return state


def register_deep_flow_routes(httpserver):
    """Register and observe the Deep happy path."""

    state = {
        "models_request_count": 0,
        "chat_request_count": 0,
        "streaming_request_count": 0,
        "tool_first_request_count": 0,
        "tool_second_request_count": 0,
        "structured_request_count": 0,
        "authorization_headers": [],
    }

    def models_handler(request):
        state["models_request_count"] += 1
        state["authorization_headers"].append(
            request.headers.get(
                "Authorization"
            )
        )

        return _json_response(
            models_response()
        )

    def chat_handler(request):
        state["authorization_headers"].append(
            request.headers.get(
                "Authorization"
            )
        )
        payload = request.get_json(
            silent=True
        ) or {}

        if payload.get("stream") is True:
            state[
                "streaming_request_count"
            ] += 1

        elif isinstance(
            payload.get("response_format"),
            dict,
        ):
            state[
                "structured_request_count"
            ] += 1

        elif "tools" in payload:
            messages = payload.get(
                "messages",
                [],
            )

            is_second_request = any(
                isinstance(message, dict)
                and message.get("role") == "tool"
                for message in messages
            )

            if is_second_request:
                state[
                    "tool_second_request_count"
                ] += 1
            else:
                state[
                    "tool_first_request_count"
                ] += 1

        else:
            state[
                "chat_request_count"
            ] += 1

        return _chat_completions_handler(
            request
        )

    httpserver.expect_request(
        "/v1/models",
        method="GET",
    ).respond_with_handler(
        models_handler
    )

    httpserver.expect_request(
        "/v1/chat/completions",
        method="POST",
    ).respond_with_handler(
        chat_handler
    )

    return state


def register_basic_secret_error_routes(
    httpserver,
    *,
    status_code: int,
    secret: str,
):
    """Return a /models error body that deliberately echoes the secret."""

    state = {
        "models_request_count": 0,
        "chat_request_count": 0,
        "authorization": None,
    }

    def models_handler(request):
        state["models_request_count"] += 1

        state["authorization"] = (
            request.headers.get(
                "Authorization"
            )
        )

        return _json_response(
            {
                "error": {
                    "message": (
                        "provider echoed credential "
                        + secret
                    )
                }
            },
            status=status_code,
        )

    def unexpected_chat_handler(request):
        state["chat_request_count"] += 1

        return _json_response(
            {
                "error": {
                    "message": (
                        "Basic diagnostics must not "
                        "execute chat completions."
                    )
                }
            },
            status=500,
        )

    httpserver.expect_request(
        "/v1/models",
        method="GET",
    ).respond_with_handler(
        models_handler
    )

    httpserver.expect_request(
        "/v1/chat/completions",
        method="POST",
    ).respond_with_handler(
        unexpected_chat_handler
    )

    return state


def register_basic_secret_invalid_json_routes(
    httpserver,
    *,
    secret: str,
):
    """Return HTTP 200 with invalid JSON containing the secret."""

    state = {
        "models_request_count": 0,
        "chat_request_count": 0,
        "authorization": None,
    }

    def models_handler(request):
        state["models_request_count"] += 1

        state["authorization"] = (
            request.headers.get(
                "Authorization"
            )
        )

        return Response(
            (
                "not-json provider-body "
                + secret
            ),
            status=200,
            content_type="application/json",
        )

    def unexpected_chat_handler(request):
        state["chat_request_count"] += 1

        return _json_response(
            {
                "error": {
                    "message": "unexpected chat"
                }
            },
            status=500,
        )

    httpserver.expect_request(
        "/v1/models",
        method="GET",
    ).respond_with_handler(
        models_handler
    )

    httpserver.expect_request(
        "/v1/chat/completions",
        method="POST",
    ).respond_with_handler(
        unexpected_chat_handler
    )

    return state


def register_basic_timeout_routes(
    httpserver,
    *,
    delay: float = 0.2,
):
    """Delay /models long enough to trigger the Doctor timeout."""

    state = {
        "models_request_count": 0,
        "chat_request_count": 0,
    }

    def models_handler(request):
        state["models_request_count"] += 1

        time.sleep(delay)

        return _json_response(
            models_response()
        )

    def unexpected_chat_handler(request):
        state["chat_request_count"] += 1

        return _json_response(
            {
                "error": {
                    "message": "unexpected chat"
                }
            },
            status=500,
        )

    httpserver.expect_request(
        "/v1/models",
        method="GET",
    ).respond_with_handler(
        models_handler
    )

    httpserver.expect_request(
        "/v1/chat/completions",
        method="POST",
    ).respond_with_handler(
        unexpected_chat_handler
    )

    return state


def register_models_status_route(
    httpserver,
    *,
    status_code: int,
):
    """Return a controlled HTTP status from /v1/models."""

    state = {
        "models_request_count": 0,
        "redirect_target_count": 0,
    }

    def models_handler(request):
        state["models_request_count"] += 1

        headers = {}

        if 300 <= status_code < 400:
            headers["Location"] = (
                "/v1/redirect-target"
            )

        return Response(
            json.dumps(
                {
                    "error": {
                        "message": (
                            "mock models status "
                            f"{status_code}"
                        )
                    }
                }
            ),
            status=status_code,
            content_type="application/json",
            headers=headers,
        )

    def redirect_target_handler(request):
        state["redirect_target_count"] += 1

        return _json_response(
            models_response()
        )

    httpserver.expect_request(
        "/v1/models",
        method="GET",
    ).respond_with_handler(
        models_handler
    )

    if 300 <= status_code < 400:
        httpserver.expect_request(
            "/v1/redirect-target",
            method="GET",
        ).respond_with_handler(
            redirect_target_handler
        )

    return state


def register_invalid_tool_arguments_route(
    httpserver,
):
    """Return a tool call whose arguments violate the tool schema."""

    state = {
        "request_count": 0,
    }

    def handler(request):
        state["request_count"] += 1

        return _json_response(
            {
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
                                        "name": "add_numbers",
                                        "arguments": (
                                            '{"a":17}'
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        )

    httpserver.expect_request(
        "/v1/chat/completions",
        method="POST",
    ).respond_with_handler(
        handler
    )

    return state


def register_invalid_structured_schema_route(
    httpserver,
):
    """Accept json_schema but return content that violates it."""

    state = {
        "request_count": 0,
    }

    def handler(request):
        state["request_count"] += 1

        return _json_response(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": (
                                '{"name":"diagnostic",'
                                '"value":"42"}'
                            ),
                        }
                    }
                ]
            }
        )

    httpserver.expect_request(
        "/v1/chat/completions",
        method="POST",
    ).respond_with_handler(
        handler
    )

    return state