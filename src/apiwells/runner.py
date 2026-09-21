"""Probe orchestration for Endpoint Doctor."""

from typing import Iterable, Protocol

from .models import ProbeResult


class Probe(Protocol):
    """Minimal interface implemented by diagnostic probes."""

    def run(self) -> ProbeResult:
        ...


class DoctorRunner:
    """Run diagnostic probes in order and collect structured results."""

    def __init__(self, probes: Iterable[Probe]) -> None:
        self._probes = tuple(probes)

    def run(self) -> list[ProbeResult]:
        results: list[ProbeResult] = []

        for probe in self._probes:
            result = probe.run()

            if not isinstance(result, ProbeResult):
                raise TypeError(
                    "Probe.run() must return a ProbeResult."
                )

            results.append(result)

        return results