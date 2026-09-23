"""Versioned JSON reporting for Endpoint Doctor."""

from collections.abc import Iterable
from typing import Any

from .. import __version__
from ..models import ProbeResult
from .aggregation import aggregate_overall_status
from .redaction import redact_probe_result


SCHEMA_VERSION = "1"


def _probe_to_dict(
    result: ProbeResult,
) -> dict[str, Any]:
    """Convert one safe ProbeResult into the JSON v1 probe contract."""

    return {
        "name": result.name,
        "status": result.status.value,
        "support": result.support.value,
        "summary": result.summary,
        "metrics": result.metrics,
        "evidence": result.evidence,
        "error_code": result.error_code,
    }


def build_json_report(
    results: Iterable[ProbeResult],
    *,
    secrets: Iterable[str] = (),
) -> dict[str, Any]:
    """Build the Endpoint Doctor JSON report v1.

    The returned object is JSON-serializable and preserves probe order.
    Secrets are redacted before ProbeResult values enter the report.
    """

    probe_results = tuple(results)

    if not probe_results:
        raise ValueError(
            "Cannot build a JSON report from an empty result collection."
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

    return {
        "schema_version": SCHEMA_VERSION,
        "apiwells_version": __version__,
        "overall_status": overall_status.value,
        "probes": [
            _probe_to_dict(result)
            for result in safe_results
        ],
    }