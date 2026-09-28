"""Human-readable console reporting for Endpoint Doctor."""

from collections.abc import Iterable

from .. import __version__
from ..models import (
    ProbeResult,
    ResultStatus,
    SupportStatus,
)
from .aggregation import aggregate_overall_status
from .redaction import redact_probe_result


_DISPLAY_NAMES = {
    "url": "URL",
    "dns": "DNS",
    "tls": "TLS",
    "http": "HTTP",
    "auth": "Authentication",
    "models": "/models",
    "chat": "Chat Completions",
    "streaming": "Streaming",
    "tool_calling": "Tool Calling",
    "structured_output": "Structured Output",
}


_ERROR_HINTS = {
    "CONFIG_ERROR": (
        "Check the Endpoint Doctor configuration and command arguments."
    ),
    "INVALID_URL": (
        "Check the base URL, scheme, hostname, port, and path."
    ),
    "DNS_ERROR": (
        "Check the hostname and local DNS/network configuration."
    ),
    "TLS_ERROR": (
        "Check certificate validity, hostname matching, and trust chain."
    ),
    "CONNECTION_ERROR": (
        "Check network reachability, firewall rules, and endpoint availability."
    ),
    "TIMEOUT": (
        "Check endpoint responsiveness, network latency, and timeout settings."
    ),
    "HTTP_REDIRECT": (
        "Check that the configured base URL is the final API endpoint."
    ),
    "NOT_FOUND": (
        "Check the API base path, route, and requested model."
    ),
    "RATE_LIMITED": (
        "Check provider rate limits, quota, and account capacity."
    ),
    "UPSTREAM_5XX": (
        "Check the upstream provider or gateway for a server-side failure."
    ),
    "AUTH_INVALID": (
        "Check that the API key is valid and uses the expected "
        "Authorization scheme."
    ),
    "PERMISSION_DENIED": (
        "Check API key permissions, model access, IP policy, and gateway rules."
    ),
    "INVALID_JSON": (
        "Check whether the endpoint returned HTML or another non-JSON response."
    ),
    "INVALID_SCHEMA": (
        "Check the endpoint response structure and OpenAI-compatible schema."
    ),
    "SSE_INVALID": (
        "Check the streaming response Content-Type and SSE event format."
    ),
    "STREAM_INTERRUPTED": (
        "Check the provider or network for an interrupted streaming response."
    ),
    "FEATURE_UNSUPPORTED": (
        "Check whether the selected model supports this capability."
    ),
    "TOOL_CALL_INVALID": (
        "Check tool-call arguments, schema, and round-trip protocol behavior."
    ),
    "STRUCTURED_OUTPUT_INVALID": (
        "Check Structured Output support and returned JSON Schema compliance."
    ),
    "RESPONSE_TOO_LARGE": (
        "Check whether the endpoint response exceeds the Doctor safety limit."
    ),
    "INTERNAL_ERROR": (
        "Retry after verifying the local installation; "
        "sensitive internal details are intentionally suppressed."
    ),
}


def _display_name(name: str) -> str:
    """Return a stable human label without hiding unknown probes."""

    return _DISPLAY_NAMES.get(name, name)


def _render_probe_line(result: ProbeResult) -> str:
    """Render one probe's primary status line."""

    line = (
        f"{_display_name(result.name):<22} "
        f"{result.status.value}"
    )

    if result.support is not SupportStatus.NOT_APPLICABLE:
        line += f" / {result.support.value}"

    return line


def render_console_report(
    results: Iterable[ProbeResult],
    *,
    secrets: Iterable[str] = (),
) -> str:
    """Render a safe human-readable Endpoint Doctor report."""

    probe_results = tuple(results)

    if not probe_results:
        raise ValueError(
            "Cannot render a console report from an empty result collection."
        )

    safe_results = tuple(
        redact_probe_result(
            result,
            secrets=secrets,
        )
        for result in probe_results
    )

    overall_status = aggregate_overall_status(
        safe_results
    )

    lines = [
        f"ApiWells Endpoint Doctor {__version__}",
        "",
    ]

    for result in safe_results:
        lines.append(
            _render_probe_line(result)
        )

        if result.status is not ResultStatus.PASS:
            lines.append(
                f"  {result.summary}"
            )

        http_status = result.evidence.get(
            "http_status"
        )

        if (
            result.status is not ResultStatus.PASS
            and isinstance(http_status, int)
        ):
            lines.append(
                f"  HTTP {http_status}"
            )

        if result.error_code is not None:
            lines.append(
                f"  Error: {result.error_code}"
            )

            hint = _ERROR_HINTS.get(
                result.error_code
            )

            if hint is not None:
                lines.append(
                    f"  Check: {hint}"
                )

    lines.extend(
        [
            "",
            f"Overall               {overall_status.value}",
        ]
    )

    return "\n".join(lines)