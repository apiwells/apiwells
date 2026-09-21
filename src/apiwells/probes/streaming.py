"""SSE parsing primitives for OpenAI-compatible streaming probes."""

from dataclasses import dataclass


class SSEParseError(ValueError):
    """Raised when an SSE stream cannot be parsed safely."""


@dataclass(frozen=True)
class SSEEvent:
    """One complete Server-Sent Event."""

    data: str


class SSEParser:
    """Incrementally parse SSE framing one line at a time."""

    def __init__(self) -> None:
        self._data_lines: list[str] = []

    @property
    def has_pending_event(self) -> bool:
        """Return whether data exists without a terminating event boundary."""

        return bool(self._data_lines)

    def feed_line(
        self,
        raw_line: bytes | str,
    ) -> SSEEvent | None:
        """Consume one SSE line and emit an event at a blank-line boundary."""

        if isinstance(raw_line, bytes):
            try:
                line = raw_line.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise SSEParseError(
                    "SSE stream was not valid UTF-8."
                ) from exc

        elif isinstance(raw_line, str):
            line = raw_line

        else:
            raise TypeError(
                "SSEParser.feed_line() requires bytes or str."
            )

        # HTTPResponse.readline() normally keeps the line ending.
        # Remove only transport line endings, not other whitespace.
        if line.endswith("\n"):
            line = line[:-1]

        if line.endswith("\r"):
            line = line[:-1]

        # In SSE, a blank line terminates the current event.
        if line == "":
            if not self._data_lines:
                return None

            event = SSEEvent(
                data="\n".join(self._data_lines)
            )

            self._data_lines.clear()

            return event

        # SSE comments are commonly used as keepalive messages.
        if line.startswith(":"):
            return None

        field, separator, value = line.partition(":")

        # Per SSE syntax, one optional space after ":" is ignored.
        if separator and value.startswith(" "):
            value = value[1:]

        # Endpoint Doctor only needs data fields for this probe.
        # event:, id:, retry:, and unknown fields are ignored.
        if field == "data":
            self._data_lines.append(
                value if separator else ""
            )

        return None