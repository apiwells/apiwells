# v0.2 Test Plan

This plan describes validation methods and historical release evidence for the
frozen Endpoint Doctor v0.2.0 scope in [V0.2_SPEC.md](V0.2_SPEC.md). The final
release was completed on **2026-09-28**, with status **CLOSED / PASS**. See
[the release checklist](RELEASE_CHECKLIST.md) for the completed acceptance
record. ED-031 and ED-032 remain closed; this documentation reconciliation
does not rerun or reopen them.

## 1. Unit testing

Keep unit tests offline. Use the tests under `tests/` to cover:

| Area | Required checks |
|---|---|
| URL/configuration | Exact base path, schemes, host/port, credentials/query/fragment rejection, loopback versus remote HTTP, key characters, model requirement, token/timeout bounds |
| ProbeResult | Required fields, allowed status/support enums and error codes, ordered probe collection |
| Status/support | Execution outcome separate from support; core failure versus capability PARTIAL aggregation; unknown support is not unsupported |
| Redaction | Exact runtime secrets, bearer/header/query patterns, nested values, summaries, metrics and evidence |
| Error classification | DNS, TLS, connection, timeout, redirect, authentication, permissions, quota/rate, upstream, parsing and capability errors |
| JSON parsing | Valid and malformed JSON, invalid response shapes, non-JSON HTTP 200 responses, bounded response reads |
| SSE parsing | LF/CRLF, multiline data, comments, UTF-8, event boundaries, malformed JSON, broken/pending events, missing DONE and interrupted streams |
| TTFT/latency | Measure from request start to the first valid model-output event; HTTP headers, keepalive, role-only, empty and metadata-only events do not count; total latency remains distinct |
| Tool Calling | Correct tool name/ID, arguments JSON and schema, diagnostic challenge, local execution, tool-result linkage, second request and final response using the runtime tool result |
| Structured Output | Strict JSON Schema success, malformed JSON, wrong types/extra properties, explicit unsupported detection, json_object-only result distinct from schema support |
| Usage | Provider-reported nonnegative integer fields, partial/missing/invalid fields, streaming merge, no estimated counts or derived missing totals |
| Reporters | Console, versioned JSON and legacy compatibility output; schema/package versions, fields/order, aggregation, secret safety, stdout/stderr and exit codes |

## 2. Mock integration testing

Use `tests/integration/` with the local HTTP mock server. Validate Basic and
Deep end to end, CLI flag combinations, legacy `--chat` (including the default
`max_tokens=8`), console/JSON agreement and the exit-code contract.

Exercise successful and failed authentication, missing requested model,
301/302 redirects, 400/401/403/404/429/500/502/503 responses, invalid JSON/schema, broken and interrupted
SSE, invalid tool arguments, full tool round trips and Structured Output
outcomes. Verify that Deep stops before billable probes when Basic does not
pass. Check redirect blocking and request counts: no hidden billable retry;
only the documented Tool Calling second request and conditional
`json_object` sub-test may add their respective requests.

With a prepared development/test environment:

```sh
python -m pytest tests -q
python -m pytest tests/integration -q
```

The first command includes the integration suite. The second is the focused
integration command, including for clean-wheel acceptance when package imports
are verified to resolve to the installed wheel.

## 3. Secret Leak Test

Use synthetic canary credentials, never live keys in fixtures. Inject them into
provider echoes, errors, headers, nested evidence, malformed responses and
unexpected exceptions. Check captured stdout, stderr, logs, tracebacks, console reports, both
JSON paths and serialized results for credential leakage or raw traceback/body
exposure. Exercise full Basic, Deep and legacy paths, including timeout and
interrupted-stream failures. Search captured outputs and generated test artifacts for complete canary secrets;
any leak blocks release. Preserve only sanitized evidence.

## 4. Real Endpoint Certification

The frozen minimum is three independent providers/endpoints covering three to
five Chinese models. Record provider, exact endpoint/model, date, package/build version, environment,
configuration, per-capability status/support, safe evidence and client timings.
Validate Models, Chat, SSE/TTFT, provider-reported Usage, Tool Calling's full
round trip and strict JSON Schema output. Preserve FAIL/PARTIAL/UNKNOWN
observations without turning them into permanent provider claims.

ED-031 is **CLOSED / PASS**. The three certified records and matrix linked from
[COMPATIBILITY.md](COMPATIBILITY.md) are authoritative historical evidence.
Do not overwrite them or replace their measurements with clean-install smoke
timings. Provider capability outcomes need not all be PASS for a valid record.

## 5. Packaging / clean-install testing

Build local wheel and sdist, check distribution metadata, install the wheel
into a clean environment, and verify imports resolve to that environment's
site-packages rather than the checkout. Check package/CLI version agreement,
entry points, dependency consistency, Basic real endpoint smoke, the mock
integration suite and critical Deep smoke. Preserve artifact identity and
sanitized command/results evidence.

ED-032 Windows clean-install testing is **CLOSED / PASS**. The supplied ED-032
acceptance evidence records local wheel + sdist build PASS, Windows Basic real
endpoint smoke PASS, clean-wheel integration **43 passed**, critical Deep smoke
PASS and no secret leak observed. These remain historical ED-032 observations,
separate from the subsequent formal RC and production-install acceptance.

### TESTENV-01: observed Windows QA harness

| Test dependency | Observed version |
|---|---|
| pytest | 9.1.1 |
| pytest-httpserver | 1.1.5 |
| Werkzeug | 3.1.8 |

These are **test dependencies, not ApiWells runtime dependencies**. They describe
the observed Windows clean-wheel integration environment, not a new supported
dependency matrix. This record does not add them to runtime dependencies or
choose a new dev-dependency packaging or management mechanism.

## 6. Cross-platform testing

The cross-platform validation method covers Windows, macOS and Linux,
including shell entry points, environment-key handling, TLS/proxy behavior,
JSON encoding and exit codes. macOS and Linux checks include installation,
`--version`, `--help`, Basic smoke and the mock suite. Record whether a smoke
test uses a local mock or a real provider. Each platform run records OS, Python
version and the tested artifact. Python must satisfy the declared `>=3.10`
requirement. The Frozen Scope requires the specified Windows/macOS/Linux
validation, not an exhaustive OS × Python-version matrix.

Ubuntu, Windows and macOS CI completed with **PASS**. Windows formal RC
acceptance also completed with **PASS**, separately from historical ED-032
acceptance. Cross-platform CI PASS does not establish macOS/Linux real-provider
live validation. The production real-provider Basic smoke is separate evidence
and does not replace ED-031 capability measurements.

## 7. Release evidence

Keep live provider tests separately controlled and out of ordinary CI by default;
provide credentials through environment variables or managed CI secrets.
Keep unit/mock/secret-test summaries, sanitized compatibility records,
build/metadata checks, artifact hashes and clean-install/platform results tied
to the tested commit and artifact. Record failures and limitations as well as
passes. Both package version declarations were synchronized to **0.2.0** for
the formal release. This documentation pass changes neither version declaration
nor the version-source design.

The following completed evidence was established during the v0.2.0 release
process and post-release production acceptance. ED-036 records that existing
evidence here; these are not new test runs performed by this documentation pass:

| Stage | Completed evidence |
|---|---|
| ED-031 | Point-in-time real-endpoint capability certification; original build versions, dates and PASS/PARTIAL outcomes preserved |
| ED-032 | Windows clean-wheel acceptance, including 43 integration tests and critical Deep smoke |
| ED-034 | Windows formal RC acceptance; wheel/sdist builds and twine check; TestPyPI publication, artifact identity, clean install and Basic smoke |
| Cross-platform CI | Ubuntu, Windows and macOS PASS; not a claim of macOS/Linux real-provider validation |
| ED-035 | Annotated v0.2.0 tag, production PyPI publication and canonical artifact identity PASS |
| Production post-release acceptance | Fresh PyPI install, CLI version/help, doctor help, pip check, real-provider Basic smoke, v2 JSON contract, secret safety, temporary key cleanup and the five-minute onboarding target PASS |

Unit, mock integration and secret leak validation passed as part of the
completed release acceptance. Final release status is **CLOSED / PASS**.
The canonical release source, tag, artifact hashes and completed checklist are
in [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md). Historical compatibility
evidence remains authoritative for its recorded tests and is not overwritten
by later Basic smoke or CI results.
