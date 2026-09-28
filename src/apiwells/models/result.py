"""Core result types shared by Endpoint Doctor probes."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .errors import ERROR_CODES

class ResultStatus(str, Enum):
    """Execution outcome of a probe."""

    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"


class SupportStatus(str, Enum):
    """Capability support reported by a probe."""

    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass
class ProbeResult:
    """Structured result returned by one diagnostic probe."""

    name: str
    status: ResultStatus
    support: SupportStatus
    summary: str
    metrics: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("ProbeResult.name must be a nonempty string.")

        if not isinstance(self.summary, str) or not self.summary.strip():
            raise ValueError("ProbeResult.summary must be a nonempty string.")

        if not isinstance(self.status, ResultStatus):
            raise TypeError("ProbeResult.status must be a ResultStatus.")

        if not isinstance(self.support, SupportStatus):
            raise TypeError("ProbeResult.support must be a SupportStatus.")
        if (
            self.error_code is not None
            and self.error_code not in ERROR_CODES
        ):
            raise ValueError(
                f"Unknown error_code: {self.error_code}"
            )