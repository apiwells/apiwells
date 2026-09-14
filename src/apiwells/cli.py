"""Dependency-free, single-request endpoint diagnostics."""
import argparse
import http.client
import ipaddress
import json
import math
import os
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

from . import __version__

LIMIT = 2 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def endpoint(base, allow_http=False):
    if not base or any(ord(c) <= 32 or ord(c) == 127 for c in base):
        raise ValueError("Base URL must not contain whitespace/control characters.")
    p = urllib.parse.urlsplit(base)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError("Use an absolute http(s) API base URL ending in /v1 if required.")
    if p.username is not None or p.password is not None or p.query or p.fragment:
        raise ValueError("Do not put credentials, query strings or fragments in the base URL.")
    try:
        p.port
        local = ipaddress.ip_address(p.hostname).is_loopback
    except ValueError:
        local = p.hostname == "localhost"
        # Validate malformed ports separately from non-IP hostnames.
        p.port
    if p.scheme == "http" and not local and not allow_http:
        raise ValueError("Remote HTTP is unencrypted; use HTTPS or explicitly --allow-http.")
    path = p.path.rstrip("/")
    if path.endswith(("/models", "/chat/completions")):
        raise ValueError("Supply the API base, not the /models or /chat/completions endpoint.")
    return urllib.parse.urlunsplit((p.scheme, p.netloc, path, "", ""))


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


def diagnose(base_url, key="", model=None, timeout=15.0, max_tokens=8,
             allow_http=False, use_env_proxy=False):
    """Return a sanitized report. Raises ValueError for invalid local configuration."""
    base = endpoint(base_url, allow_http)
    if not math.isfinite(timeout) or timeout <= 0 or timeout > 300:
        raise ValueError("Timeout must be finite and in (0, 300] seconds.")
    if not isinstance(max_tokens, int) or not 1 <= max_tokens <= 4096:
        raise ValueError("max-tokens must be an integer from 1 to 4096.")
    if any(ord(c) < 33 or ord(c) > 126 for c in key):
        raise ValueError("API key must contain printable ASCII without spaces.")
    if model is not None and (not isinstance(model, str) or not model.strip()):
        raise ValueError("A nonempty model is required for a chat check.")
    kind = "chat" if model is not None else "models"
    route = "/chat/completions" if model is not None else "/models"
    headers = {"Accept": "application/json", "User-Agent": "apiwells/" + __version__}
    if key:
        headers["Authorization"] = "Bearer " + key
    body = None
    if model is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps({"model": model, "messages": [{"role": "user", "content": "Reply OK."}],
                           "max_tokens": max_tokens, "stream": False}).encode()
    req = urllib.request.Request(base + route, data=body, headers=headers)
    # No redirects, .netrc authentication, retries or implicit environment proxy.
    opener = urllib.request.build_opener(NoRedirect(), urllib.request.ProxyHandler(
        None if use_env_proxy else {}))
    report = {"schema_version": 1, "version": __version__, "check": kind,
              "ok": False, "http_status": None, "category": "network", "elapsed_ms": 0}
    start = time.monotonic()
    try:
        try:
            response = opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            report["http_status"] = response.code
            if not 200 <= response.code < 300:
                report["category"], report["hint"] = hint(response.code)
                return report
            raw = response.read(LIMIT + 1)
        if len(raw) > LIMIT:
            report.update(category="response_too_large", hint="Response exceeded the 2 MiB limit.")
            return report
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError, RecursionError):
            report.update(category="invalid_json", hint="Expected JSON; check for an HTML login or proxy page.")
            return report
        valid = False
        if isinstance(data, dict) and "error" not in data:
            if kind == "models":
                items = data.get("data")
                valid = isinstance(items, list) and all(
                    isinstance(x, dict) and isinstance(x.get("id"), str) and bool(x["id"])
                    for x in items)
                if valid:
                    report["model_count"] = len(items)
            else:
                choices = data.get("choices")
                if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                    message = choices[0].get("message")
                    valid = (isinstance(message, dict) and message.get("role") == "assistant"
                             and isinstance(message.get("content"), str) and bool(message["content"].strip()))
        report.update(ok=valid, category="ok" if valid else "unexpected_schema",
                      hint=("Minimal response check passed; this is not a full compatibility or quality certification."
                            if valid else "Expected models data or nonempty assistant text. Inspect upstream protocol/model support."))
        return report
    except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
        reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
        category = "network"
        if isinstance(reason, (TimeoutError, socket.timeout)):
            category = "timeout"
        elif isinstance(reason, ssl.SSLError):
            category = "tls"
        elif isinstance(reason, socket.gaierror):
            category = "dns"
        report.update(category=category, hint="Check DNS, certificate trust, connectivity and timeout. Raw errors are omitted to protect credentials.")
        return report
    finally:
        report["elapsed_ms"] = round((time.monotonic() - start) * 1000, 2)


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
