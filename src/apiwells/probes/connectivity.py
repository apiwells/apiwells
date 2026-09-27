"""Connectivity probes for Endpoint Doctor."""

import http.client
import socket
import ssl
import time
import urllib.parse

from ..config import normalize_endpoint
from ..transport import HTTPObservation, verify_tls
from ..models import ProbeResult, ResultStatus, SupportStatus


class URLProbe:
    """Validate and normalize the configured API base URL."""

    def __init__(
        self,
        base_url: str,
        allow_http: bool = False,
    ) -> None:
        self.base_url = base_url
        self.allow_http = allow_http

    def run(self) -> ProbeResult:
        try:
            normalized = normalize_endpoint(
                self.base_url,
                allow_http=self.allow_http,
            )
        except (ValueError, UnicodeError):
            return ProbeResult(
                name="url",
                status=ResultStatus.FAIL,
                support=SupportStatus.NOT_APPLICABLE,
                summary="API base URL configuration is invalid.",
                error_code="INVALID_URL",
            )

        parsed = urllib.parse.urlsplit(normalized)

        return ProbeResult(
            name="url",
            status=ResultStatus.PASS,
            support=SupportStatus.NOT_APPLICABLE,
            summary="API base URL is valid.",
            evidence={
                "scheme": parsed.scheme,
                "host": parsed.hostname,
                "port": parsed.port,
                "path": parsed.path,
            },
        )


class DNSProbe:
    """Resolve the endpoint hostname using the operating system resolver."""

    def __init__(
        self,
        base_url: str,
    ) -> None:
        self.base_url = base_url

    @staticmethod
    def _elapsed_ms(start: float) -> float:
        return round(
            (time.monotonic() - start) * 1000,
            2,
        )

    def run(self) -> ProbeResult:
        parsed = urllib.parse.urlsplit(
            self.base_url
        )

        host = parsed.hostname

        if not host:
            return ProbeResult(
                name="dns",
                status=ResultStatus.FAIL,
                support=SupportStatus.NOT_APPLICABLE,
                summary="DNS resolution could not start because the endpoint has no hostname.",
                error_code="CONFIG_ERROR",
            )

        port = parsed.port

        if port is None:
            if parsed.scheme == "https":
                port = 443
            elif parsed.scheme == "http":
                port = 80
            else:
                return ProbeResult(
                    name="dns",
                    status=ResultStatus.FAIL,
                    support=SupportStatus.NOT_APPLICABLE,
                    summary="DNS resolution could not determine a network service port.",
                    error_code="CONFIG_ERROR",
                )

        start = time.monotonic()

        try:
            addresses = socket.getaddrinfo(
                host,
                port,
                type=socket.SOCK_STREAM,
            )

        except socket.gaierror:
            return ProbeResult(
                name="dns",
                status=ResultStatus.FAIL,
                support=SupportStatus.NOT_APPLICABLE,
                summary="DNS resolution failed for the endpoint hostname.",
                metrics={
                    "latency_ms": self._elapsed_ms(start),
                },
                evidence={
                    "host": host,
                },
                error_code="DNS_ERROR",
            )

        except OSError:
            return ProbeResult(
                name="dns",
                status=ResultStatus.FAIL,
                support=SupportStatus.NOT_APPLICABLE,
                summary="The operating system resolver could not complete DNS resolution.",
                metrics={
                    "latency_ms": self._elapsed_ms(start),
                },
                evidence={
                    "host": host,
                },
                error_code="DNS_ERROR",
            )

        resolved_addresses = sorted(
            {
                item[4][0]
                for item in addresses
                if item[4]
            }
        )

        if not resolved_addresses:
            return ProbeResult(
                name="dns",
                status=ResultStatus.FAIL,
                support=SupportStatus.NOT_APPLICABLE,
                summary="DNS resolution returned no usable addresses.",
                metrics={
                    "latency_ms": self._elapsed_ms(start),
                },
                evidence={
                    "host": host,
                },
                error_code="DNS_ERROR",
            )

        return ProbeResult(
            name="dns",
            status=ResultStatus.PASS,
            support=SupportStatus.NOT_APPLICABLE,
            summary="DNS resolution succeeded.",
            metrics={
                "latency_ms": self._elapsed_ms(start),
            },
            evidence={
                "host": host,
                "address_count": len(
                    resolved_addresses
                ),
                "addresses": resolved_addresses,
            },
        )


class TLSProbe:
    """Perform a verified TLS handshake with the endpoint."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 15.0,
        use_env_proxy: bool = False,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.use_env_proxy = use_env_proxy

    @staticmethod
    def _elapsed_ms(start: float) -> float:
        return round(
            (time.monotonic() - start) * 1000,
            2,
        )

    def run(self) -> ProbeResult:
        parsed = urllib.parse.urlsplit(
            self.base_url
        )

        host = parsed.hostname

        if not host:
            return ProbeResult(
                name="tls",
                status=ResultStatus.FAIL,
                support=SupportStatus.NOT_APPLICABLE,
                summary="TLS check could not start because the endpoint has no hostname.",
                error_code="CONFIG_ERROR",
            )

        if parsed.scheme == "http":
            return ProbeResult(
                name="tls",
                status=ResultStatus.PASS,
                support=SupportStatus.NOT_APPLICABLE,
                summary="TLS is not applicable to this HTTP endpoint.",
                evidence={
                    "host": host,
                    "tls_applicable": False,
                },
            )

        if parsed.scheme != "https":
            return ProbeResult(
                name="tls",
                status=ResultStatus.FAIL,
                support=SupportStatus.NOT_APPLICABLE,
                summary="TLS check requires an HTTP or HTTPS endpoint.",
                error_code="CONFIG_ERROR",
            )

        port = parsed.port or 443
        start = time.monotonic()

        try:
            if self.use_env_proxy:
                tls_version, cipher = verify_tls(
                    self.base_url,
                    timeout=self.timeout,
                    use_env_proxy=True,
                )
            else:
                context = ssl.create_default_context()

                with socket.create_connection(
                    (host, port),
                    timeout=self.timeout,
                ) as raw_socket:
                    with context.wrap_socket(
                        raw_socket,
                        server_hostname=host,
                    ) as tls_socket:
                        tls_version = tls_socket.version()
                        cipher = tls_socket.cipher()

        except ssl.SSLCertVerificationError as exc:
            message = (
                getattr(exc, "verify_message", None)
                or str(exc)
            ).lower()

            if (
                "hostname mismatch" in message
                or "not valid for" in message
            ):
                failure_kind = "hostname_mismatch"
                summary = (
                    "TLS certificate verification failed because "
                    "the certificate does not match the endpoint hostname."
                )
            else:
                failure_kind = "certificate_verification"
                summary = (
                    "TLS certificate verification failed."
                )

            return ProbeResult(
                name="tls",
                status=ResultStatus.FAIL,
                support=SupportStatus.NOT_APPLICABLE,
                summary=summary,
                metrics={
                    "latency_ms": self._elapsed_ms(start),
                },
                evidence={
                    "host": host,
                    "port": port,
                    "failure_kind": failure_kind,
                },
                error_code="TLS_ERROR",
            )

        except ssl.SSLError:
            return ProbeResult(
                name="tls",
                status=ResultStatus.FAIL,
                support=SupportStatus.NOT_APPLICABLE,
                summary="TLS handshake failed.",
                metrics={
                    "latency_ms": self._elapsed_ms(start),
                },
                evidence={
                    "host": host,
                    "port": port,
                    "failure_kind": "handshake",
                },
                error_code="TLS_ERROR",
            )

        except (socket.timeout, TimeoutError):
            return ProbeResult(
                name="tls",
                status=ResultStatus.FAIL,
                support=SupportStatus.NOT_APPLICABLE,
                summary="Connection timed out before the TLS handshake completed.",
                metrics={
                    "latency_ms": self._elapsed_ms(start),
                },
                evidence={
                    "host": host,
                    "port": port,
                },
                error_code="TIMEOUT",
            )

        except (ValueError, http.client.InvalidURL):
            return ProbeResult(
                name="tls",
                status=ResultStatus.FAIL,
                support=SupportStatus.NOT_APPLICABLE,
                summary="TLS check could not start because the transport configuration is invalid.",
                metrics={
                    "latency_ms": self._elapsed_ms(start),
                },
                evidence={"host": host, "port": port},
                error_code="CONFIG_ERROR",
            )

        except (OSError, http.client.HTTPException):
            return ProbeResult(
                name="tls",
                status=ResultStatus.FAIL,
                support=SupportStatus.NOT_APPLICABLE,
                summary="Network connection failed before the TLS handshake completed.",
                metrics={
                    "latency_ms": self._elapsed_ms(start),
                },
                evidence={
                    "host": host,
                    "port": port,
                },
                error_code="CONNECTION_ERROR",
            )

        cipher_name = (
            cipher[0]
            if cipher
            else None
        )

        return ProbeResult(
            name="tls",
            status=ResultStatus.PASS,
            support=SupportStatus.NOT_APPLICABLE,
            summary="TLS handshake and certificate verification succeeded.",
            metrics={
                "latency_ms": self._elapsed_ms(start),
            },
            evidence={
                "host": host,
                "port": port,
                "tls_applicable": True,
                "tls_version": tls_version,
                "cipher": cipher_name,
            },
        )


class HTTPProbe:
    """Interpret basic HTTP connectivity from a shared observation."""

    def __init__(
        self,
        observation: HTTPObservation,
    ) -> None:
        self.observation = observation

    def run(self) -> ProbeResult:
        observed = self.observation.collect()

        metrics = {
            "latency_ms": observed.elapsed_ms,
        }

        if observed.error_code is not None:
            return ProbeResult(
                name="http",
                status=ResultStatus.FAIL,
                support=SupportStatus.NOT_APPLICABLE,
                summary="No valid HTTP response was received.",
                metrics=metrics,
                error_code=observed.error_code,
            )

        http_status = observed.http_status

        if http_status is None:
            return ProbeResult(
                name="http",
                status=ResultStatus.FAIL,
                support=SupportStatus.NOT_APPLICABLE,
                summary="HTTP observation completed without a status code.",
                metrics=metrics,
                error_code="CONNECTION_ERROR",
            )

        evidence = {
            "http_status": http_status,
        }

        if observed.redirected:
            return ProbeResult(
                name="http",
                status=ResultStatus.PARTIAL,
                support=SupportStatus.NOT_APPLICABLE,
                summary=f"HTTP endpoint returned redirect status {http_status}.",
                metrics=metrics,
                evidence=evidence,
                error_code="HTTP_REDIRECT",
            )

        return ProbeResult(
            name="http",
            status=ResultStatus.PASS,
            support=SupportStatus.NOT_APPLICABLE,
            summary=f"HTTP endpoint responded with status {http_status}.",
            metrics=metrics,
            evidence=evidence,
        )


class AuthProbe:
    """Interpret authentication from a shared HTTP observation."""

    def __init__(
        self,
        observation: HTTPObservation,
        authentication_requested: bool = True,
    ) -> None:
        self.observation = observation
        self.authentication_requested = authentication_requested

    def run(self) -> ProbeResult:
        if not self.authentication_requested:
            return ProbeResult(
                name="auth",
                status=ResultStatus.PASS,
                support=SupportStatus.NOT_APPLICABLE,
                summary="Authentication check was not requested.",
            )

        observed = self.observation.collect()

        metrics = {
            "latency_ms": observed.elapsed_ms,
        }

        if observed.error_code is not None:
            return ProbeResult(
                name="auth",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary="Authentication could not be evaluated because no valid HTTP response was received.",
                metrics=metrics,
                error_code=observed.error_code,
            )

        http_status = observed.http_status

        evidence = {
            "http_status": http_status,
        }

        if http_status is None:
            return ProbeResult(
                name="auth",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary="Authentication could not be evaluated because no HTTP status was available.",
                metrics=metrics,
                evidence=evidence,
                error_code="CONNECTION_ERROR",
            )

        if 200 <= http_status < 300:
            return ProbeResult(
                name="auth",
                status=ResultStatus.PASS,
                support=SupportStatus.SUPPORTED,
                summary="Authentication was accepted by the endpoint.",
                metrics=metrics,
                evidence=evidence,
            )

        if http_status == 401:
            return ProbeResult(
                name="auth",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary="The endpoint rejected authentication with HTTP 401.",
                metrics=metrics,
                evidence=evidence,
                error_code="AUTH_INVALID",
            )

        if http_status == 403:
            return ProbeResult(
                name="auth",
                status=ResultStatus.FAIL,
                support=SupportStatus.UNKNOWN,
                summary="The endpoint denied the request with HTTP 403.",
                metrics=metrics,
                evidence=evidence,
                error_code="PERMISSION_DENIED",
            )

        if observed.redirected:
            return ProbeResult(
                name="auth",
                status=ResultStatus.PARTIAL,
                support=SupportStatus.UNKNOWN,
                summary="Authentication could not be determined because the endpoint redirected the request.",
                metrics=metrics,
                evidence=evidence,
                error_code="HTTP_REDIRECT",
            )

        return ProbeResult(
            name="auth",
            status=ResultStatus.PARTIAL,
            support=SupportStatus.UNKNOWN,
            summary=(
                f"Authentication could not be determined reliably "
                f"from HTTP {http_status}."
            ),
            metrics=metrics,
            evidence=evidence,
        )