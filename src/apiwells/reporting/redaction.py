"""Central secret redaction for Endpoint Doctor reporting."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any, Iterable

from ..models import ProbeResult


REDACTED = "[REDACTED]"


_BEARER_PATTERN = re.compile(
    r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"
)

_HEADER_SECRET_PATTERN = re.compile(
    r"(?im)\b("
    r"authorization|"
    r"x-api-key|"
    r"api-key"
    r")\s*:\s*([^\r\n]+)"
)

_QUERY_SECRET_PATTERN = re.compile(
    r"(?i)"
    r"([?&](?:"
    r"api[_-]?key|"
    r"access[_-]?token|"
    r"token|"
    r"authorization"
    r")=)"
    r"([^&#\s]+)"
)

_COMMON_KEY_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])"
    r"sk-[A-Za-z0-9._-]{8,}"
)


def _normalize_secrets(
    secrets: Iterable[str],
) -> tuple[str, ...]:
    """Return unique nonempty secrets, longest first."""

    values = {
        secret
        for secret in secrets
        if isinstance(secret, str) and secret
    }

    return tuple(
        sorted(
            values,
            key=len,
            reverse=True,
        )
    )


def redact_text(
    text: str,
    *,
    secrets: Iterable[str] = (),
) -> str:
    """Redact secrets from a reporting string."""

    if not isinstance(text, str):
        raise TypeError(
            "redact_text() requires a string."
        )

    normalized = _normalize_secrets(secrets)
    redacted = text

    # Exact runtime secrets are the strongest protection.
    # Provider keys do not all use recognizable prefixes.
    for secret in normalized:
        redacted = redacted.replace(
            secret,
            REDACTED,
        )

    redacted = _HEADER_SECRET_PATTERN.sub(
        lambda match: (
            f"{match.group(1)}: {REDACTED}"
        ),
        redacted,
    )

    redacted = _BEARER_PATTERN.sub(
        f"Bearer {REDACTED}",
        redacted,
    )

    redacted = _QUERY_SECRET_PATTERN.sub(
        lambda match: (
            f"{match.group(1)}{REDACTED}"
        ),
        redacted,
    )

    redacted = _COMMON_KEY_PATTERN.sub(
        REDACTED,
        redacted,
    )

    return redacted


def _redact_value(
    value: Any,
    *,
    secrets: tuple[str, ...],
) -> Any:
    """Recursive implementation using normalized secrets."""

    if isinstance(value, str):
        return redact_text(
            value,
            secrets=secrets,
        )

    if isinstance(value, bytes):
        return redact_text(
            value.decode(
                "utf-8",
                errors="replace",
            ),
            secrets=secrets,
        )

    if isinstance(value, BaseException):
        return redact_text(
            str(value),
            secrets=secrets,
        )

    if isinstance(value, dict):
        return {
            _redact_value(
                key,
                secrets=secrets,
            ): _redact_value(
                item,
                secrets=secrets,
            )
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            _redact_value(
                item,
                secrets=secrets,
            )
            for item in value
        ]

    if isinstance(value, tuple):
        return tuple(
            _redact_value(
                item,
                secrets=secrets,
            )
            for item in value
        )

    if isinstance(value, set):
        return {
            _redact_value(
                item,
                secrets=secrets,
            )
            for item in value
        }

    return value


def redact_value(
    value: Any,
    *,
    secrets: Iterable[str] = (),
) -> Any:
    """Recursively redact values intended for reporting."""

    return _redact_value(
        value,
        secrets=_normalize_secrets(secrets),
    )


def redact_probe_result(
    result: ProbeResult,
    *,
    secrets: Iterable[str] = (),
) -> ProbeResult:
    """Return a redacted copy of a ProbeResult."""

    if not isinstance(result, ProbeResult):
        raise TypeError(
            "redact_probe_result() requires a ProbeResult."
        )

    normalized = _normalize_secrets(secrets)

    return replace(
        result,
        summary=redact_text(
            result.summary,
            secrets=normalized,
        ),
        metrics=_redact_value(
            result.metrics,
            secrets=normalized,
        ),
        evidence=_redact_value(
            result.evidence,
            secrets=normalized,
        ),
    )