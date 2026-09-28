# Changelog

## Unreleased

No unreleased changes are recorded yet.

## 0.2.1 — 2026-09-28

- Correct the PyPI-facing README and package metadata.
- Make the README and v0.2 specification patch-version-neutral.
- Add verified repository and issue project URLs.
- Replace repository-relative README documentation links with PyPI-safe
  absolute GitHub links.
- No runtime diagnostic behavior changes.

## 0.2.0 — 2026-09-28

- Add Basic connectivity/authentication/models diagnostics and explicit-model
  Deep capability diagnostics while retaining legacy `--chat` behavior.
- Validate Streaming/SSE and report client TTFT and total latency.
- Parse provider-reported Usage without estimating missing token counts.
- Validate Tool Calling through the complete local-tool/two-request round trip.
- Validate Structured Output against JSON Schema, distinguishing strict schema
  support from JSON-object-only behavior.
- Separate probe execution status from capability support.
- Add a shared error taxonomy and centralized secret redaction.
- Add versioned structured JSON reporting alongside compatibility reports.
- Validate live endpoint compatibility with three preserved ED-031 records;
  results remain point-in-time observations, including partial capabilities.
- Validate local wheel/sdist packaging and Windows clean installation, including
  Basic and critical Deep smoke checks and 43 clean-wheel integration tests.
- Document Local-First/no-telemetry behavior, security boundaries, test coverage
  and completed release validation.
- Complete RC/TestPyPI acceptance and cross-platform CI on Ubuntu, Windows and
  macOS; publish to production PyPI and verify artifact identity, clean
  installation, CLI/JSON contracts, real-provider Basic smoke, secret safety
  and the five-minute onboarding target.

## 0.1.0
- Add a single-request models endpoint check and opt-in text chat smoke check.
- Add HTTP/network failure categories, response shape checks and sanitized JSON.
- Disable redirects, retries and implicit environment proxy use.
