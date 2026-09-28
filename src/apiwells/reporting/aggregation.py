"""Overall status aggregation for Endpoint Doctor reports."""

from collections.abc import Iterable

from ..models import ProbeResult, ResultStatus


_CAPABILITY_PROBES = frozenset(
    {
        "streaming",
        "tool_calling",
        "structured_output",
    }
)


def aggregate_overall_status(
    results: Iterable[ProbeResult],
) -> ResultStatus:
    """Aggregate probe results without conflating health and capability.

    Rules:
    - All PASS -> PASS.
    - A FAIL in a core/unknown probe -> FAIL.
    - A non-PASS capability result -> PARTIAL.
    - Any remaining PARTIAL result -> PARTIAL.
    """

    probe_results = tuple(results)

    if not probe_results:
        raise ValueError(
            "Cannot aggregate an empty probe result collection."
        )

    for result in probe_results:
        if not isinstance(result, ProbeResult):
            raise TypeError(
                "Overall status aggregation requires ProbeResult values."
            )

    for result in probe_results:
        if (
            result.status is ResultStatus.FAIL
            and result.name not in _CAPABILITY_PROBES
        ):
            return ResultStatus.FAIL

    if any(
        result.status is not ResultStatus.PASS
        for result in probe_results
    ):
        return ResultStatus.PARTIAL

    return ResultStatus.PASS