# Changelog

## Unreleased — v0.2 development

The package and CLI remain at 0.1.0 (v0.2 development build); v0.2.0 has not
been released.

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
  and remaining release gates.

## 0.1.0
- Add a single-request models endpoint check and opt-in text chat smoke check.
- Add HTTP/network failure categories, response shape checks and sanitized JSON.
- Disable redirects, retries and implicit environment proxy use.
