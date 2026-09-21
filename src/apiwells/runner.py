"""Probe orchestration for Endpoint Doctor."""

from typing import Iterable, Protocol

from .config import normalize_endpoint
from .models import ProbeResult, ResultStatus
from .probes import (
    AuthProbe,
    DNSProbe,
    HTTPProbe,
    ModelsProbe,
    TLSProbe,
    URLProbe,
)
from .probes.models import build_models_observation


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


def run_basic_diagnostics(
    base_url: str,
    key: str = "",
    timeout: float = 15.0,
    allow_http: bool = False,
    use_env_proxy: bool = False,
    authentication_requested: bool = True,
    expected_model: str | None = None,
) -> list[ProbeResult]:
    """Run the non-billable Basic Doctor diagnostic chain."""

    url_result = URLProbe(
        base_url,
        allow_http=allow_http,
    ).run()

    if url_result.status is ResultStatus.FAIL:
        return [url_result]

    normalized_base = normalize_endpoint(
        base_url,
        allow_http=allow_http,
    )

    models_observation = build_models_observation(
        normalized_base,
        key=key,
        timeout=timeout,
        use_env_proxy=use_env_proxy,
    )

    runner = DoctorRunner(
        [
            DNSProbe(
                normalized_base
            ),
            TLSProbe(
                normalized_base,
                timeout=timeout,
            ),
            HTTPProbe(
                models_observation
            ),
            AuthProbe(
                models_observation,
                authentication_requested=authentication_requested,
            ),
            ModelsProbe(
                observation=models_observation,
                expected_model=expected_model,
            ),
        ]
    )

    return [
        url_result,
        *runner.run(),
    ]