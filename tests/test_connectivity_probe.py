import socket
import ssl
import unittest
from unittest.mock import MagicMock, patch

from apiwells.transport import ObservedHTTP
from apiwells.models import ResultStatus, SupportStatus
from apiwells.probes import DNSProbe, TLSProbe, URLProbe, HTTPProbe, AuthProbe
from apiwells.runner import DoctorRunner


class URLProbeTests(unittest.TestCase):
    def test_valid_url_passes(self):
        result = URLProbe(
            "https://example.com/v1/"
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.PASS,
        )

        self.assertEqual(
            result.support,
            SupportStatus.NOT_APPLICABLE,
        )

        self.assertEqual(
            result.evidence["scheme"],
            "https",
        )

        self.assertEqual(
            result.evidence["host"],
            "example.com",
        )

        self.assertEqual(
            result.evidence["path"],
            "/v1",
        )

    def test_invalid_url_fails(self):
        result = URLProbe(
            "ftp://example.com"
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            result.error_code,
            "INVALID_URL",
        )

    def test_remote_http_requires_explicit_opt_in(self):
        result = URLProbe(
            "http://example.com/v1"
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.FAIL,
        )

        allowed = URLProbe(
            "http://example.com/v1",
            allow_http=True,
        ).run()

        self.assertEqual(
            allowed.status,
            ResultStatus.PASS,
        )


class DNSProbeTests(unittest.TestCase):
    def test_dns_success(self):
        fake_result = [
            (
                2,
                1,
                6,
                "",
                ("203.0.113.10", 443),
            ),
            (
                2,
                1,
                6,
                "",
                ("203.0.113.11", 443),
            ),
        ]

        with patch(
            "apiwells.probes.connectivity.socket.getaddrinfo",
            return_value=fake_result,
        ):
            result = DNSProbe(
                "https://example.com/v1"
            ).run()

        self.assertEqual(
            result.status,
            ResultStatus.PASS,
        )

        self.assertEqual(
            result.support,
            SupportStatus.NOT_APPLICABLE,
        )

        self.assertEqual(
            result.evidence["host"],
            "example.com",
        )

        self.assertEqual(
            result.evidence["address_count"],
            2,
        )

    def test_dns_failure(self):
        with patch(
            "apiwells.probes.connectivity.socket.getaddrinfo",
            side_effect=__import__("socket").gaierror(),
        ):
            result = DNSProbe(
                "https://does-not-exist.example/v1"
            ).run()

        self.assertEqual(
            result.status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            result.error_code,
            "DNS_ERROR",
        )

    def test_dns_uses_explicit_port(self):
        with patch(
            "apiwells.probes.connectivity.socket.getaddrinfo",
            return_value=[
                (
                    2,
                    1,
                    6,
                    "",
                    ("127.0.0.1", 8443),
                )
            ],
        ) as mocked:
            DNSProbe(
                "https://example.com:8443/v1"
            ).run()

        mocked.assert_called_once_with(
            "example.com",
            8443,
            type=__import__("socket").SOCK_STREAM,
        )

    def test_url_and_dns_run_under_doctor_runner(self):
        fake_result = [
            (
                2,
                1,
                6,
                "",
                ("203.0.113.10", 443),
            )
        ]

        with patch(
            "apiwells.probes.connectivity.socket.getaddrinfo",
            return_value=fake_result,
        ):
            runner = DoctorRunner(
                [
                    URLProbe(
                        "https://example.com/v1"
                    ),
                    DNSProbe(
                        "https://example.com/v1"
                    ),
                ]
            )

            results = runner.run()

        self.assertEqual(
            [result.name for result in results],
            ["url", "dns"],
        )

        self.assertEqual(
            results[0].status,
            ResultStatus.PASS,
        )

        self.assertEqual(
            results[1].status,
            ResultStatus.PASS,
        )


class TLSProbeTests(unittest.TestCase):
    def test_https_tls_success(self):
        raw_socket = MagicMock()
        raw_socket.__enter__.return_value = raw_socket

        tls_socket = MagicMock()
        tls_socket.__enter__.return_value = tls_socket
        tls_socket.version.return_value = "TLSv1.3"
        tls_socket.cipher.return_value = (
            "TLS_AES_256_GCM_SHA384",
            "TLSv1.3",
            256,
        )

        context = MagicMock()
        context.wrap_socket.return_value = tls_socket

        with patch(
            "apiwells.probes.connectivity.ssl.create_default_context",
            return_value=context,
        ), patch(
            "apiwells.probes.connectivity.socket.create_connection",
            return_value=raw_socket,
        ) as connect:
            result = TLSProbe(
                "https://example.com/v1",
                timeout=1,
            ).run()

        self.assertEqual(
            result.status,
            ResultStatus.PASS,
        )

        self.assertEqual(
            result.support,
            SupportStatus.NOT_APPLICABLE,
        )

        self.assertEqual(
            result.evidence["tls_version"],
            "TLSv1.3",
        )

        self.assertEqual(
            result.evidence["cipher"],
            "TLS_AES_256_GCM_SHA384",
        )

        connect.assert_called_once_with(
            ("example.com", 443),
            timeout=1,
        )

        context.wrap_socket.assert_called_once_with(
            raw_socket,
            server_hostname="example.com",
        )

    def test_http_tls_is_not_applicable(self):
        result = TLSProbe(
            "http://127.0.0.1:8000/v1"
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.PASS,
        )

        self.assertEqual(
            result.support,
            SupportStatus.NOT_APPLICABLE,
        )

        self.assertFalse(
            result.evidence["tls_applicable"]
        )

    def test_certificate_verification_failure(self):
        raw_socket = MagicMock()
        raw_socket.__enter__.return_value = raw_socket

        context = MagicMock()
        context.wrap_socket.side_effect = (
            ssl.SSLCertVerificationError(
                1,
                "certificate verify failed",
            )
        )

        with patch(
            "apiwells.probes.connectivity.ssl.create_default_context",
            return_value=context,
        ), patch(
            "apiwells.probes.connectivity.socket.create_connection",
            return_value=raw_socket,
        ):
            result = TLSProbe(
                "https://example.com/v1"
            ).run()

        self.assertEqual(
            result.status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            result.error_code,
            "TLS_ERROR",
        )

        self.assertEqual(
            result.evidence["failure_kind"],
            "certificate_verification",
        )

    def test_tls_handshake_failure(self):
        raw_socket = MagicMock()
        raw_socket.__enter__.return_value = raw_socket

        context = MagicMock()
        context.wrap_socket.side_effect = ssl.SSLError(
            1,
            "handshake failure",
        )

        with patch(
            "apiwells.probes.connectivity.ssl.create_default_context",
            return_value=context,
        ), patch(
            "apiwells.probes.connectivity.socket.create_connection",
            return_value=raw_socket,
        ):
            result = TLSProbe(
                "https://example.com/v1"
            ).run()

        self.assertEqual(
            result.status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            result.error_code,
            "TLS_ERROR",
        )

        self.assertEqual(
            result.evidence["failure_kind"],
            "handshake",
        )

    def test_tls_timeout_is_distinct(self):
        with patch(
            "apiwells.probes.connectivity.socket.create_connection",
            side_effect=socket.timeout(),
        ):
            result = TLSProbe(
                "https://example.com/v1",
                timeout=1,
            ).run()

        self.assertEqual(
            result.status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            result.error_code,
            "TIMEOUT",
        )

    def test_tls_probe_runs_under_doctor_runner(self):
        raw_socket = MagicMock()
        raw_socket.__enter__.return_value = raw_socket

        tls_socket = MagicMock()
        tls_socket.__enter__.return_value = tls_socket
        tls_socket.version.return_value = "TLSv1.3"
        tls_socket.cipher.return_value = (
            "TLS_AES_256_GCM_SHA384",
            "TLSv1.3",
            256,
        )

        context = MagicMock()
        context.wrap_socket.return_value = tls_socket

        with patch(
            "apiwells.probes.connectivity.ssl.create_default_context",
            return_value=context,
        ), patch(
            "apiwells.probes.connectivity.socket.create_connection",
            return_value=raw_socket,
        ):
            runner = DoctorRunner(
                [
                    TLSProbe(
                        "https://example.com/v1"
                    )
                ]
            )

            results = runner.run()

        self.assertEqual(
            len(results),
            1,
        )

        self.assertEqual(
            results[0].name,
            "tls",
        )

        self.assertEqual(
            results[0].status,
            ResultStatus.PASS,
        )


class StaticObservation:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def collect(self):
        self.calls += 1
        return self.result


class HTTPProbeTests(unittest.TestCase):
    def test_http_200_passes(self):
        observation = StaticObservation(
            ObservedHTTP(
                http_status=200,
                body=b"",
                elapsed_ms=12.5,
            )
        )

        result = HTTPProbe(
            observation
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.PASS,
        )

        self.assertEqual(
            result.support,
            SupportStatus.NOT_APPLICABLE,
        )

        self.assertEqual(
            result.evidence["http_status"],
            200,
        )

    def test_http_500_still_proves_http_connectivity(self):
        observation = StaticObservation(
            ObservedHTTP(
                http_status=500,
                body=b"",
                elapsed_ms=10.0,
            )
        )

        result = HTTPProbe(
            observation
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.PASS,
        )

        self.assertEqual(
            result.evidence["http_status"],
            500,
        )

    def test_http_redirect_is_partial(self):
        observation = StaticObservation(
            ObservedHTTP(
                http_status=302,
                body=b"",
                elapsed_ms=8.0,
                redirected=True,
            )
        )

        result = HTTPProbe(
            observation
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.PARTIAL,
        )

        self.assertEqual(
            result.error_code,
            "HTTP_REDIRECT",
        )

    def test_http_timeout_fails(self):
        observation = StaticObservation(
            ObservedHTTP(
                http_status=None,
                body=b"",
                elapsed_ms=1000.0,
                error_code="TIMEOUT",
            )
        )

        result = HTTPProbe(
            observation
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            result.error_code,
            "TIMEOUT",
        )


class AuthProbeTests(unittest.TestCase):
    def test_auth_2xx_passes(self):
        observation = StaticObservation(
            ObservedHTTP(
                http_status=200,
                body=b"",
                elapsed_ms=10.0,
            )
        )

        result = AuthProbe(
            observation
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.PASS,
        )

        self.assertEqual(
            result.support,
            SupportStatus.SUPPORTED,
        )

    def test_auth_401_is_auth_invalid(self):
        observation = StaticObservation(
            ObservedHTTP(
                http_status=401,
                body=b"",
                elapsed_ms=10.0,
            )
        )

        result = AuthProbe(
            observation
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            result.error_code,
            "AUTH_INVALID",
        )

        self.assertEqual(
            result.support,
            SupportStatus.UNKNOWN,
        )

    def test_auth_403_is_permission_denied(self):
        observation = StaticObservation(
            ObservedHTTP(
                http_status=403,
                body=b"",
                elapsed_ms=10.0,
            )
        )

        result = AuthProbe(
            observation
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.FAIL,
        )

        self.assertEqual(
            result.error_code,
            "PERMISSION_DENIED",
        )

    def test_auth_other_status_is_unknown_partial(self):
        observation = StaticObservation(
            ObservedHTTP(
                http_status=500,
                body=b"",
                elapsed_ms=10.0,
            )
        )

        result = AuthProbe(
            observation
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.PARTIAL,
        )

        self.assertEqual(
            result.support,
            SupportStatus.UNKNOWN,
        )

    def test_anonymous_mode_is_not_applicable(self):
        observation = StaticObservation(
            ObservedHTTP(
                http_status=401,
                body=b"",
                elapsed_ms=10.0,
            )
        )

        result = AuthProbe(
            observation,
            authentication_requested=False,
        ).run()

        self.assertEqual(
            result.status,
            ResultStatus.PASS,
        )

        self.assertEqual(
            result.support,
            SupportStatus.NOT_APPLICABLE,
        )

        self.assertEqual(
            observation.calls,
            0,
        )


class SharedObservationTests(unittest.TestCase):
    def test_http_and_auth_share_observation_result(self):
        observation = StaticObservation(
            ObservedHTTP(
                http_status=200,
                body=b"",
                elapsed_ms=10.0,
            )
        )

        runner = DoctorRunner(
            [
                HTTPProbe(observation),
                AuthProbe(observation),
            ]
        )

        results = runner.run()

        self.assertEqual(
            [result.name for result in results],
            ["http", "auth"],
        )

        self.assertEqual(
            results[0].status,
            ResultStatus.PASS,
        )

        self.assertEqual(
            results[1].status,
            ResultStatus.PASS,
        )


if __name__ == "__main__":
    unittest.main()