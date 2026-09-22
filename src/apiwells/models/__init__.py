"""Shared data models for ApiWells diagnostics."""

from .errors import ERROR_CODES
from .result import ProbeResult, ResultStatus, SupportStatus

__all__ = [
    "ProbeResult",
    "ResultStatus",
    "SupportStatus",
    "ERROR_CODES",
]
