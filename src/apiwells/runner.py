"""Probe orchestration for Endpoint Doctor."""

from typing import Iterable, Protocol

from .config import normalize_endpoint
from .models import ProbeResult, ResultStatus
from .probes import (
    AuthProbe,
    ChatProbe,
    DNSProbe,
    HTTPProbe,
    ModelsProbe,
    StreamingProbe,
    StructuredOutputProbe,
    TLSProbe,
    URLProbe,
    ToolCallingProbe,
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


def run_deep_diagnostics(
    base_url: str,
    model: str,
    key: str = "",
    timeout: float = 15.0,
    max_tokens: int = 512,
    allow_http: bool = False,
    use_env_proxy: bool = False,
    authentication_requested: bool = True,
) -> list[ProbeResult]:
    """Run the currently implemented Deep Doctor diagnostic chain.

    During staged v0.2 development this currently extends Basic Doctor
    with non-stream Chat and Streaming probes. It is not yet exposed as
    the final CLI Deep Mode.
    """

    if not isinstance(model, str) or not model.strip():
        raise ValueError(
            "Deep diagnostics require a nonempty model."
        )

    basic_results = run_basic_diagnostics(
        base_url=base_url,
        key=key,
        timeout=timeout,
        allow_http=allow_http,
        use_env_proxy=use_env_proxy,
        authentication_requested=authentication_requested,
        expected_model=model,
    )

    # Billable probes must not run when the non-billable Basic chain
    # has not established a sufficiently healthy endpoint.
    if any(
        result.status is not ResultStatus.PASS
        for result in basic_results
    ):
        return basic_results

    models_result = next(
        (
            result
            for result in basic_results
            if result.name == "models"
        ),
        None,
    )

    # Be defensive even if ModelsProbe currently represents a missing
    # requested model as PASS/PARTIAL differently in the future.
    if (
        models_result is not None
        and models_result.evidence.get(
            "target_model_found"
        )
        is False
    ):
        return basic_results

    normalized_base = normalize_endpoint(
        base_url,
        allow_http=allow_http,
    )

    deep_runner = DoctorRunner(
        [
            ChatProbe(
                base_url=normalized_base,
                model=model,
                key=key,
                timeout=timeout,
                max_tokens=max_tokens,
                use_env_proxy=use_env_proxy,
            ),
            StreamingProbe(
                base_url=normalized_base,
                model=model,
                key=key,
                timeout=timeout,
                max_tokens=max_tokens,
                use_env_proxy=use_env_proxy,
            ),
            ToolCallingProbe(
                base_url=normalized_base,
                model=model,
                key=key,
                timeout=timeout,
                use_env_proxy=use_env_proxy,
            ),
            StructuredOutputProbe(
                base_url=normalized_base,
                model=model,
                key=key,
                timeout=timeout,
                max_tokens=max_tokens,
                use_env_proxy=use_env_proxy,
            ),
        ]
    )

    return [
        *basic_results,
        *deep_runner.run(),
    ]