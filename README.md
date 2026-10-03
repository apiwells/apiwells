# ApiWells

ApiWells is the Python package and CLI for ApiWells developer tooling.
Its current public capability, Endpoint Doctor, is a Local-First CLI for
diagnosing OpenAI-compatible model API endpoints from your machine. Endpoint
Doctor checks connectivity and protocol capabilities; it does not score model
quality. Python 3.10+ is required.

Runtime dependencies include `jsonschema` for Structured Output validation.

## Install

Install the latest release from PyPI:

```sh
python -m pip install --upgrade apiwells
apiwells --version
```

`apiwells --version` reports the installed package version.

Install this local checkout with:

```sh
python -m pip install .
```

## Basic Doctor

Set `APIWELLS_API_KEY` using your shell's secret-input mechanism. Do not put a
real key in a command, screenshot, issue or repository. Use `--api-key-env NAME`
to select another environment variable.

```sh
apiwells doctor --base-url https://YOUR-API-HOST/v1
apiwells doctor --base-url https://YOUR-API-HOST/v1 --v2-json
```

Basic is the default mode: **URL → DNS → TLS → HTTP → Authentication → /models**.
It sends no inference request. HTTP, authentication and model-list checks share
one GET to `BASE/models`. An empty model list can pass the response-shape check;
a model list alone does not prove inference works.

Supply the exact API base: `/v1` is not added automatically. For a gateway with
`/openai/v1`, include that prefix. Do not supply the full `/models` or
`/chat/completions` URL.

For a local unauthenticated development server:

```sh
apiwells doctor --base-url http://127.0.0.1:3000/v1 --anonymous
```

## Deep Doctor

```sh
apiwells doctor --base-url https://YOUR-API-HOST/v1 --deep --model YOUR-MODEL-ID
apiwells doctor --base-url https://YOUR-API-HOST/v1 --deep --model YOUR-MODEL-ID --v2-json
```

Deep requires an explicit, nonempty model ID and follows:
**Basic → Chat → Streaming/SSE → Usage → Tool Calling → Structured Output**.
Usage is extracted from Chat and Streaming responses, not a separate request.
Capability probes run only after Basic passes and the requested model is found.

Deep makes multiple potentially billable inference requests:

- Chat validates a nonempty assistant text response.
- Streaming validates SSE framing, output and terminal `[DONE]`; it reports
  TTFT and total latency. TTFT is measured from request start to the first valid
  model-output event. HTTP headers, keepalive, role-only, empty and metadata-only
  events do not count.
- Usage contains provider-reported token counts only. Missing values remain
  unavailable or null; ApiWells never estimates them.
- Tool Calling must complete a full round trip: tool call, validated arguments,
  local diagnostic tool execution, tool result, second request and a final
  response using that result. Merely accepting `tools` is insufficient.
- Structured Output must return JSON that passes the requested JSON Schema.
  An explicit rejection of `json_schema` as unsupported can trigger one
  additional, potentially billable `json_object` sub-test. JSON-object-only
  success does not certify strict JSON Schema support.

There are no hidden billable retries or fallback models. The Tool Calling
second request and conditional Structured Output sub-test are diagnostic steps,
with request counts included in their results. `--max-tokens` controls applicable
generation budgets and is not a guaranteed total cost ceiling; diagnostic
sub-tests may use bounded request parameters. Provider support varies; not every
endpoint supports every capability.

## Legacy chat compatibility

```sh
apiwells doctor --base-url https://YOUR-API-HOST/v1 --chat --model YOUR-MODEL-ID --json
```

Legacy `--chat` remains a single, opt-in, potentially billable non-streaming
request to `BASE/chat/completions`, with `Reply OK.` and default `max_tokens=8`.
A pass requires nonempty assistant text, not exactly `OK`. Use `--max-tokens 32`
to change the budget; some models need more output tokens. It performs no
automatic retry or fallback model selection. `--chat` and `--deep` are mutually
exclusive.

## Results and timing

Probe execution status (`PASS`, `FAIL`, `PARTIAL`) is separate from capability
support (`SUPPORTED`, `UNSUPPORTED`, `UNKNOWN`, `NOT_APPLICABLE`). A failed or
partial probe with unknown support does not establish that a capability is
unsupported. Core failures make the overall result FAIL; non-passing
Streaming, Tool Calling or Structured Output probes make it PARTIAL when core
checks pass.

The exit-code contract remains:

| Code | Meaning |
|---|---|
| `0` | Selected check / overall diagnostics passed |
| `1` | Endpoint diagnostics did not pass, including an overall PARTIAL |
| `2` | Local usage or configuration error |

For Basic/Deep, `--v2-json` writes a versioned JSON report with
`schema_version: "1"`, `apiwells_version`, `overall_status` and `probes`.
Each probe includes status, support, summary, metrics, evidence and error code.
The report schema version is independent of the package version.
`--json` retains the compatibility report with `ok`; legacy `--chat --json`
retains its single-check report. Use `--json`, not `--v2-json`, for legacy chat.
Completed checks produce one JSON object on stdout; usage/configuration errors
go to stderr and do not produce a JSON report.

Error codes distinguish configuration, DNS/TLS/connectivity/timeout, HTTP/auth,
JSON/schema, SSE/interruption and capability validation failures. They are
diagnostic evidence, not definitive root-cause conclusions.

`--timeout 15` is a socket-operation timeout, not an overall deadline. Client
TTFT and total latency include transport effects and are not server-only
inference timings. Legacy `elapsed_ms` is request/response elapsed time, not
streaming TTFT.

## Security and boundaries

- Local-First execution; no telemetry or hidden upload of prompts, responses or
  usage. Requested diagnostic traffic goes to the endpoint you select.
- API keys and Authorization header values must not be printed. Centralized
  redaction protects console/JSON reports and error paths; raw provider bodies
  are not dumped into reports. Review reports before sharing.
- HTTPS certificate verification stays enabled. Remote HTTP requires
  `--allow-http`; literal loopback addresses and localhost are allowed for
  development.
- All redirects, including same-host redirects, are blocked so credentials are
  not forwarded to redirect destinations.
- Environment proxies are ignored unless `--use-env-proxy` is supplied.
- Test only endpoints you are authorized to test. Private/local destinations are
  intentionally allowed; this CLI is not an unrestricted server-side URL fetcher.

See [Security](https://github.com/apiwells/apiwells/blob/main/SECURITY.md) for handling and reporting guidance.

## Compatibility and development

[Compatibility](https://github.com/apiwells/apiwells/blob/main/docs/COMPATIBILITY.md) indexes three point-in-time ED-031 live
certification records. These establish observed endpoint behavior, not
universal provider support or model quality.

[The release-facing specification](https://github.com/apiwells/apiwells/blob/main/docs/V0.2_SPEC.md) summarizes the frozen
v0.2 scope. Benchmark, scoring/ranking, recommendations, cost optimization,
Router, Gateway, long-term Monitoring, Web Dashboard, SaaS accounts, cloud
telemetry and complete Responses API coverage are outside that scope.

For test coverage and the observed QA harness dependencies, see
[the test plan](https://github.com/apiwells/apiwells/blob/main/docs/TEST_PLAN.md). With the test harness installed, run:

```sh
python -m pytest tests -q
```

See [the release checklist](https://github.com/apiwells/apiwells/blob/main/docs/RELEASE_CHECKLIST.md) for release evidence,
and [the changelog](https://github.com/apiwells/apiwells/blob/main/CHANGELOG.md) for version history and changes.
License: MIT.
