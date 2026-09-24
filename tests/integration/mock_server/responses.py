"""Reusable happy-path responses for ED-030 mock integration tests."""

import json


def models_response() -> dict:
    return {
        "object": "list",
        "data": [
            {
                "id": "test-model",
                "object": "model",
                "owned_by": "apiwells-test",
            }
        ],
    }


def chat_response() -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "hello from mock",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 5,
            "completion_tokens": 3,
            "total_tokens": 8,
        },
    }


def tool_call_response() -> dict:
    return {
        "id": "chatcmpl-tool-1",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {
                                "name": "add_numbers",
                                "arguments": '{"a":17,"b":25}',
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
    }


def tool_final_response() -> dict:
    return {
        "id": "chatcmpl-tool-2",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "The result is 42.",
                },
                "finish_reason": "stop",
            }
        ],
    }


def structured_response() -> dict:
    return {
        "id": "chatcmpl-structured",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": (
                        '{"name":"diagnostic","value":42}'
                    ),
                },
                "finish_reason": "stop",
            }
        ],
    }


def streaming_response() -> str:
    events = [
        {
            "choices": [
                {
                    "delta": {
                        "role": "assistant",
                    }
                }
            ]
        },
        {
            "choices": [
                {
                    "delta": {
                        "content": "O",
                    }
                }
            ]
        },
        {
            "choices": [],
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 1,
                "total_tokens": 6,
            },
        },
    ]

    body = ""

    for event in events:
        body += (
            "data: "
            + json.dumps(event)
            + "\n\n"
        )

    body += "data: [DONE]\n\n"

    return body