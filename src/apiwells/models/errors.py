"""Error codes used by Endpoint Doctor diagnostics."""

ERROR_CODES = frozenset(
    {
        "CONFIG_ERROR",
        "INVALID_URL",

        "DNS_ERROR",
        "TLS_ERROR",
        "CONNECTION_ERROR",
        "TIMEOUT",

        "HTTP_REDIRECT",
        "NOT_FOUND",
        "RATE_LIMITED",
        "UPSTREAM_5XX",

        "AUTH_INVALID",
        "PERMISSION_DENIED",

        "INVALID_JSON",
        "INVALID_SCHEMA",

        "SSE_INVALID",
        "STREAM_INTERRUPTED",

        "FEATURE_UNSUPPORTED",

        "TOOL_CALL_INVALID",
        "STRUCTURED_OUTPUT_INVALID",

        "RESPONSE_TOO_LARGE",

        "INTERNAL_ERROR",
    }
)