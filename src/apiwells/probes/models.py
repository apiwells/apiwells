"""Probe for the OpenAI-compatible /models endpoint."""

import json
import urllib.request

from .. import __version__
from ..models import ProbeResult, ResultStatus, SupportStatus
from ..transport import HTTPObservation


RESPONSE_LIMIT = 2 * 1024 * 1024


def build_models_observation(
    base_url: str,
    key: str = "",
    timeout: float = 15.0,
    use_env_proxy: bool = False,
) -> HTTPObservation:
    """Prepare one shared GET /models HTTP observation."""

    headers = {
        "Accept": "application/json",
        "User-Agent": "apiwells/" + __version__,
    }

    if key:
        headers["Authorization"] = "Bearer " + key

    request = urllib.request.Request(
        base_url.rstrip("/") + "/models",
        headers=headers,
    )

    return HTTPObservation(
        request,
        timeout=timeout,
        use_env_proxy=use_env_proxy,
        response_limit=RESPONSE_LIMIT,
    )


class ModelsProbe:
    """Validate the /models endpoint and its core response structure."""

    def __init__(
        self,
        base_url: str | None = None,
        key: str = "",
        timeout: float = 15.0,
        expected_model: str | None = None,
        use_env_proxy: bool = False,
        observation: HTTPObservation | None = None,
    ) -> None:
        if observation is not None and base_url is not None:
            raise ValueError(
                "Provide either base_url or observation, not both."
            )

        if observation is None:
            if not isinstance(base_url, str) or not base_url.strip():
                raise ValueError(
                    "ModelsProbe requires base_url when no observation is provided."
                )

            observation = build_models_observation(
                base_url=base_url,
                key=key,
                timeout=timeout,
                use_env_proxy=use_env_proxy,
            )

        self.observation = observation
        self.expected_model = expected_model

    def run(self) -> ProbeResult:
        observed = self.observation.collect()

        latency_ms = observed.elapsed_ms

        if observed.error_code is not None:
            return ProbeResult(
                name="models",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary=(
                    "Models request failed before "
                    "a valid HTTP response was received."
                ),
                metrics={
                    "latency_ms": latency_ms,
                },
                error_code=observed.error_code,
            )

        http_status = observed.http_status

        if http_status is None:
            return ProbeResult(
                name="models",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary="Models request produced no HTTP status.",
                metrics={
                    "latency_ms": latency_ms,
                },
                error_code="CONNECTION_ERROR",
            )

        if not 200 <= http_status < 300:
            return ProbeResult(
                name="models",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary=(
                    f"Models request returned HTTP {http_status}."
                ),
                metrics={
                    "latency_ms": latency_ms,
                },
                evidence={
                    "http_status": http_status,
                },
            )

        if observed.response_too_large:
            return ProbeResult(
                name="models",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary="Models response exceeded the allowed size.",
                metrics={
                    "latency_ms": latency_ms,
                },
                evidence={
                    "http_status": http_status,
                    "response_too_large": True,
                },
            )

        try:
            data = json.loads(observed.body)
        except (ValueError, UnicodeError, RecursionError):
            return ProbeResult(
                name="models",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary="Models response was not valid JSON.",
                metrics={
                    "latency_ms": latency_ms,
                },
                evidence={
                    "http_status": http_status,
                },
                error_code="INVALID_JSON",
            )

        if not isinstance(data, dict) or "error" in data:
            return ProbeResult(
                name="models",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary=(
                    "Models response did not contain "
                    "the expected object structure."
                ),
                metrics={
                    "latency_ms": latency_ms,
                },
                evidence={
                    "http_status": http_status,
                },
                error_code="INVALID_SCHEMA",
            )

        items = data.get("data")

        if not isinstance(items, list):
            return ProbeResult(
                name="models",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary=(
                    "Models response did not contain "
                    "a valid data list."
                ),
                metrics={
                    "latency_ms": latency_ms,
                },
                evidence={
                    "http_status": http_status,
                },
                error_code="INVALID_SCHEMA",
            )

        valid_model_ids = []
        invalid_entries = 0

        for item in items:
            if (
                isinstance(item, dict)
                and isinstance(item.get("id"), str)
                and bool(item["id"])
            ):
                valid_model_ids.append(
                    item["id"]
                )
            else:
                invalid_entries += 1

        if items and not valid_model_ids:
            return ProbeResult(
                name="models",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary=(
                    "Models data list contained "
                    "no valid model entries."
                ),
                metrics={
                    "latency_ms": latency_ms,
                    "model_count": 0,
                },
                evidence={
                    "http_status": http_status,
                    "invalid_model_entries": invalid_entries,
                },
                error_code="INVALID_SCHEMA",
            )

        status = (
            ResultStatus.PARTIAL
            if invalid_entries
            else ResultStatus.PASS
        )

        summary = (
            "Models endpoint returned a valid model list."
        )

        evidence = {
            "http_status": http_status,
            "invalid_model_entries": invalid_entries,
        }

        if self.expected_model is not None:
            model_found = (
                self.expected_model
                in valid_model_ids
            )

            evidence[
                "target_model_found"
            ] = model_found

            if not model_found:
                status = ResultStatus.PARTIAL
                summary = (
                    "Models endpoint returned a valid "
                    "model list, but the requested "
                    "model was not found."
                )

        return ProbeResult(
            name="models",
            status=status,
            support=SupportStatus.SUPPORTED,
            summary=summary,
            metrics={
                "latency_ms": latency_ms,
                "model_count": len(
                    valid_model_ids
                ),
            },
            evidence=evidence,
        )