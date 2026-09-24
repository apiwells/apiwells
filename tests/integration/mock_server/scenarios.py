"""Named failure scenarios used by ED-030 integration tests."""

from enum import Enum


class MockScenario(str, Enum):
    NORMAL = "normal"

    AUTH_INVALID = "auth_invalid"
    PERMISSION_DENIED = "permission_denied"
    RATE_LIMITED = "rate_limited"
    UPSTREAM_5XX = "upstream_5xx"

    INVALID_JSON = "invalid_json"
    BROKEN_SSE = "broken_sse"

    TOOL_UNSUPPORTED = "tool_unsupported"

    STRUCTURED_JSON_OBJECT_ONLY = (
        "structured_json_object_only"
    )