"""HTTP transport policy for Endpoint Doctor."""

import http.client
import socket
import ssl
import time
import urllib.error
import urllib.request

from dataclasses import dataclass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Expose redirects to the caller instead of following them."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def build_opener(use_env_proxy: bool = False):
    """Build an opener with Endpoint Doctor's transport policy."""

    proxies = None if use_env_proxy else {}

    return urllib.request.build_opener(
        NoRedirect(),
        urllib.request.ProxyHandler(proxies),
    )


def open_request(request, timeout: float, use_env_proxy: bool = False):
    """Open exactly one HTTP request without retries or redirects."""

    opener = build_opener(use_env_proxy=use_env_proxy)

    try:
        return opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        # HTTPError is also response-like and carries status/headers/body.
        # Returning it lets probes inspect 3xx/4xx/5xx explicitly.
        return exc


DEFAULT_RESPONSE_LIMIT = 2 * 1024 * 1024


@dataclass(frozen=True)
class ObservedHTTP:
    """Sanitized result of one HTTP exchange."""

    http_status: int | None
    body: bytes
    elapsed_ms: float
    error_code: str | None = None
    response_too_large: bool = False
    redirected: bool = False


def observe_request(
    request,
    timeout: float,
    use_env_proxy: bool = False,
    response_limit: int = DEFAULT_RESPONSE_LIMIT,
) -> ObservedHTTP:
    """Execute and fully observe one HTTP request."""

    start = time.monotonic()

    try:
        response = open_request(
            request,
            timeout=timeout,
            use_env_proxy=use_env_proxy,
        )

        with response:
            http_status = response.code

            raw = response.read(
                response_limit + 1
            )

        too_large = len(raw) > response_limit

        return ObservedHTTP(
            http_status=http_status,
            body=b"" if too_large else raw,
            elapsed_ms=round(
                (time.monotonic() - start) * 1000,
                2,
            ),
            response_too_large=too_large,
            redirected=300 <= http_status < 400,
        )

    except (
        urllib.error.URLError,
        OSError,
        http.client.HTTPException,
    ) as exc:
        reason = (
            exc.reason
            if isinstance(exc, urllib.error.URLError)
            else exc
        )

        if isinstance(
            reason,
            (TimeoutError, socket.timeout),
        ):
            error_code = "TIMEOUT"

        elif isinstance(reason, ssl.SSLError):
            error_code = "TLS_ERROR"

        elif isinstance(reason, socket.gaierror):
            error_code = "DNS_ERROR"

        else:
            error_code = "CONNECTION_ERROR"

        return ObservedHTTP(
            http_status=None,
            body=b"",
            elapsed_ms=round(
                (time.monotonic() - start) * 1000,
                2,
            ),
            error_code=error_code,
        )


class HTTPObservation:
    """Lazily execute one HTTP request and cache its observation."""

    def __init__(
        self,
        request,
        timeout: float,
        use_env_proxy: bool = False,
        response_limit: int = DEFAULT_RESPONSE_LIMIT,
    ) -> None:
        self._request = request
        self._timeout = timeout
        self._use_env_proxy = use_env_proxy
        self._response_limit = response_limit
        self._result: ObservedHTTP | None = None

    def collect(self) -> ObservedHTTP:
        if self._result is None:
            self._result = observe_request(
                self._request,
                timeout=self._timeout,
                use_env_proxy=self._use_env_proxy,
                response_limit=self._response_limit,
            )

        return self._result