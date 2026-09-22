"""Dependency-free, single-request endpoint diagnostics."""
import argparse
import json
import math
import os
import time


from . import __version__
from .config import normalize_endpoint
from .models import ResultStatus
from .probes import ChatProbe, ModelsProbe
from .reporting import (
    redact_probe_result,
    redact_value,
)

endpoint = normalize_endpoint


def hint(status):
    if 300 <= status < 400:
        return "redirect", "Redirect blocked. Verify the final API base URL."
    return {
        400: ("bad_request", "Check model support and request parameters."),
        401: ("authentication", "Check API key validity and the intended endpoint."),
        403: ("forbidden", "Check permissions, IP policy and gateway/WAF rules."),
        404: ("not_found", "Check base path and model name; this does not prove the service is offline."),
        405: ("method_not_allowed", "Check route and protocol compatibility."),
        429: ("rate_or_quota", "Check rate limits, quota and account balance; status alone cannot distinguish them."),
    }.get(status, ("server_error" if status >= 500 else "http_error", "Inspect gateway/upstream logs for this request."))


def _legacy_report_from_probe(result, kind):
    """Translate a v0.2 ProbeResult into the v0.1 diagnose() dict contract."""

    http_status = result.evidence.get(
        "http_status"
    )

    report = {
        "schema_version": 1,
        "version": __version__,
        "check": kind,
        "ok": result.status is ResultStatus.PASS,
        "http_status": http_status,
        "category": "network",
        "elapsed_ms": 0,
    }

    if result.status is ResultStatus.PASS:
        report["category"] = "ok"
        report["hint"] = (
            "Minimal response check passed; this is not a "
            "full compatibility or quality certification."
        )

        if kind == "models":
            model_count = result.metrics.get(
                "model_count"
            )

            if model_count is not None:
                report["model_count"] = (
                    model_count
                )

        return report

    if result.evidence.get(
        "response_too_large"
    ):
        report["category"] = (
            "response_too_large"
        )

        report["hint"] = (
            "Response exceeded the 2 MiB limit."
        )

        return report

    if result.error_code == "INVALID_JSON":
        report["category"] = "invalid_json"

        report["hint"] = (
            "Expected JSON; check for an HTML "
            "login or proxy page."
        )

        return report

    if result.error_code == "INVALID_SCHEMA":
        report["category"] = (
            "unexpected_schema"
        )

        report["hint"] = (
            "Expected models data or nonempty "
            "assistant text. Inspect upstream "
            "protocol/model support."
        )

        return report

    if (
        isinstance(http_status, int)
        and not 200 <= http_status < 300
    ):
        (
            report["category"],
            report["hint"],
        ) = hint(http_status)

        return report

    network_categories = {
        "DNS_ERROR": "dns",
        "TLS_ERROR": "tls",
        "TIMEOUT": "timeout",
        "CONNECTION_ERROR": "network",
    }

    if result.error_code in network_categories:
        report["category"] = (
            network_categories[
                result.error_code
            ]
        )

        report["hint"] = (
            "Check DNS, certificate trust, "
            "connectivity and timeout. Raw errors "
            "are omitted to protect credentials."
        )

        return report

    # Preserve v0.1 failure semantics for a structurally
    # incomplete or PARTIAL successful HTTP response.
    report["category"] = "unexpected_schema"

    report["hint"] = (
        "Expected models data or nonempty "
        "assistant text. Inspect upstream "
        "protocol/model support."
    )

    return report


def diagnose(
    base_url,
    key="",
    model=None,
    timeout=15.0,
    max_tokens=8,
    allow_http=False,
    use_env_proxy=False,
):
    """Return the legacy sanitized report using v0.2 probes."""

    base = endpoint(
        base_url,
        allow_http,
    )

    if (
        not math.isfinite(timeout)
        or timeout <= 0
        or timeout > 300
    ):
        raise ValueError(
            "Timeout must be finite and in "
            "(0, 300] seconds."
        )

    if (
        not isinstance(max_tokens, int)
        or not 1 <= max_tokens <= 4096
    ):
        raise ValueError(
            "max-tokens must be an integer "
            "from 1 to 4096."
        )

    if any(
        ord(c) < 33 or ord(c) > 126
        for c in key
    ):
        raise ValueError(
            "API key must contain printable "
            "ASCII without spaces."
        )

    if model is not None and (
        not isinstance(model, str)
        or not model.strip()
    ):
        raise ValueError(
            "A nonempty model is required "
            "for a chat check."
        )

    start = time.monotonic()

    if model is None:
        result = ModelsProbe(
            base_url=base,
            key=key,
            timeout=timeout,
            use_env_proxy=use_env_proxy,
        ).run()

        safe_result = redact_probe_result(
            result,
            secrets=(key,),
        )

        report = _legacy_report_from_probe(
            safe_result,
            "models",
        )

    else:
        result = ChatProbe(
            base_url=base,
            model=model,
            key=key,
            timeout=timeout,
            max_tokens=max_tokens,
            use_env_proxy=use_env_proxy,
        ).run()

        safe_result = redact_probe_result(
            result,
            secrets=(key,),
        )

        report = _legacy_report_from_probe(
            safe_result,
            "chat",
        )

    report["elapsed_ms"] = round(
        (time.monotonic() - start) * 1000,
        2,
    )

    return redact_value(
        report,
        secrets=(key,),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="ApiWells Endpoint Doctor: one diagnostic request, no retries.")
    parser.add_argument("--version", action="version", version="apiwells " + __version__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("doctor", help="Check an OpenAI-compatible API base")
    p.add_argument("--base-url", required=True, help="Exact API base, e.g. https://host.example/v1; no automatic /v1")
    p.add_argument("--api-key-env", default="APIWELLS_API_KEY", help="Environment variable containing the key")
    p.add_argument("--anonymous", action="store_true", help="Send no authentication header")
    p.add_argument("--chat", action="store_true", help="Opt into one potentially billable chat request")
    p.add_argument("--model", help="Exact model ID; required with --chat")
    p.add_argument("--max-tokens", type=int, default=8)
    p.add_argument("--timeout", type=float, default=15, help="Socket operation timeout in seconds, not total wall-clock deadline")
    p.add_argument("--allow-http", action="store_true", help="Explicitly allow unencrypted remote HTTP")
    p.add_argument("--use-env-proxy", action="store_true", help="Opt into system/environment proxy settings")
    p.add_argument("--json", action="store_true", help="Print sanitized JSON to stdout")
    args = parser.parse_args(argv)
    if args.chat != (args.model is not None):
        p.error("Use --chat and --model together.")
    key = "" if args.anonymous else os.environ.get(args.api_key_env, "")
    if not args.anonymous and not key:
        p.error("API key environment variable is missing/empty; set it or use --anonymous.")
    try:
        result = diagnose(args.base_url, key, args.model, args.timeout, args.max_tokens,
                          args.allow_http, args.use_env_proxy)
    except (ValueError, UnicodeError):
        p.error("Invalid configuration. Check URL, port, HTTPS, key characters, model, timeout and token limit.")
    if args.json:
        print(json.dumps(result, ensure_ascii=True, allow_nan=False))
    else:
        print("{} {} HTTP={} {:.2f}ms [{}]".format(
            "PASS" if result["ok"] else "FAIL", result["check"],
            result["http_status"], result["elapsed_ms"], result["category"]))
        print(result["hint"])
        if "model_count" in result:
            print("Models returned:", result["model_count"])
    return 0 if result["ok"] else 1
