"""Configuration validation for Endpoint Doctor."""

import ipaddress
import urllib.parse


def normalize_endpoint(base: str, allow_http: bool = False) -> str:
    """Validate and normalize an OpenAI-compatible API base URL."""

    if not base or any(ord(c) <= 32 or ord(c) == 127 for c in base):
        raise ValueError(
            "Base URL must not contain whitespace/control characters."
        )

    parsed = urllib.parse.urlsplit(base)

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError(
            "Use an absolute http(s) API base URL ending in /v1 if required."
        )

    if (
        parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Do not put credentials, query strings or fragments in the base URL."
        )

    try:
        parsed.port
        local = ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        local = parsed.hostname == "localhost"

        # Accessing .port separately also validates malformed ports.
        parsed.port

    if parsed.scheme == "http" and not local and not allow_http:
        raise ValueError(
            "Remote HTTP is unencrypted; use HTTPS or explicitly --allow-http."
        )

    path = parsed.path.rstrip("/")

    if path.endswith(("/models", "/chat/completions")):
        raise ValueError(
            "Supply the API base, not the /models or /chat/completions endpoint."
        )

    return urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            path,
            "",
            "",
        )
    )