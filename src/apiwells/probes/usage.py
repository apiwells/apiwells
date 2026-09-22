"""Usage extraction helpers for OpenAI-compatible responses."""

from dataclasses import dataclass


@dataclass(frozen=True)
class UsageObservation:
    """Normalized token usage returned by a provider."""

    available: bool
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    @property
    def complete(self) -> bool:
        """Return whether all standard token fields are available."""

        return (
            self.prompt_tokens is not None
            and self.completion_tokens is not None
            and self.total_tokens is not None
        )

    def as_metrics(self) -> dict[str, bool | int | None]:
        """Return normalized fields suitable for ProbeResult.metrics."""

        return {
            "usage_available": self.available,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


def _token_count(value: object) -> int | None:
    """Accept only nonnegative integer token counts."""

    if isinstance(value, bool):
        return None

    if not isinstance(value, int):
        return None

    if value < 0:
        return None

    return value


def extract_usage(payload: object) -> UsageObservation:
    """Extract standard usage fields without estimating missing values."""

    if not isinstance(payload, dict):
        return UsageObservation(
            available=False
        )

    usage = payload.get("usage")

    if not isinstance(usage, dict):
        return UsageObservation(
            available=False
        )

    prompt_tokens = _token_count(
        usage.get("prompt_tokens")
    )

    completion_tokens = _token_count(
        usage.get("completion_tokens")
    )

    total_tokens = _token_count(
        usage.get("total_tokens")
    )

    available = any(
        value is not None
        for value in (
            prompt_tokens,
            completion_tokens,
            total_tokens,
        )
    )

    return UsageObservation(
        available=available,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )