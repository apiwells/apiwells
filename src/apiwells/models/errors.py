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

def classify_http_status(
    http_status: int | None,
) -> str | None:
    if http_status is None:
        return None

    if 300 <= http_status < 400:
        return "HTTP_REDIRECT"

    if http_status == 401:
        return "AUTH_INVALID"

    if http_status == 403:
        return "PERMISSION_DENIED"

    if http_status == 404:
        return "NOT_FOUND"

    if http_status == 429:
        return "RATE_LIMITED"

    if 500 <= http_status < 600:
        return "UPSTREAM_5XX"

    return None