"""Unified OpenAI-compatible mock provider."""

import json

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