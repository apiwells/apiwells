# ApiWells Endpoint Doctor

A small, dependency-free CLI that checks an OpenAI-compatible model API from
your machine. Useful when onboarding a gateway customer or checking a deployment.
Python 3.10+. Initial alpha release; not a full SDK or a service monitor.

## Install

After the release is published to PyPI:

```sh
python -m pip install apiwells
apiwells --version
```

For an unpublished local checkout: `python -m pip install .`

## Check a model API

Set `APIWELLS_API_KEY` in your environment using your shell's secret-input
mechanism. Do not put a real key in a command, screenshot, issue or repository.

```sh
apiwells doctor --base-url https://YOUR-API-HOST/v1
apiwells doctor --base-url https://YOUR-API-HOST/v1 --json
```

Replace the host with your actual API base. `/v1` is **not** added automatically.
For a gateway using `/openai/v1`, supply that exact prefix. Do not supply the
full `/models` or `/chat/completions` URL. This command sends one GET to
`BASE/models`; it checks JSON `data` entries for nonempty string model IDs.
An empty model list passes the shape check and reports `model_count: 0`.
A model list does not prove that inference works or is available to this key.

For one potentially billable inference request, opt in explicitly:

```sh
apiwells doctor --base-url https://YOUR-API-HOST/v1 --chat --model YOUR-MODEL-ID
```

This sends `Reply OK.` to `BASE/chat/completions`, with `stream: false` and
`max_tokens: 8`. A pass means a nonempty assistant text response was returned;
it does not require exactly `OK`. Some reasoning models require a different
parameter or larger output budget; this release does not support those variants.
`--max-tokens 32` increases the budget, not a guaranteed cost ceiling.
There are no automatic retries or fallback models.

For a local unauthenticated development server:

```sh
apiwells doctor --base-url http://127.0.0.1:3000/v1 --anonymous
```

Use `--api-key-env NAME` to select another environment variable.
`--timeout 15` is a socket-operation timeout, not an overall deadline; DNS or
slow continuous delivery may make total runtime longer. `elapsed_ms` measures
this client's request/response time, not server inference time or streaming TTFT.

## Results

Exit codes: `0` minimal check passed, `1` endpoint check failed, `2` local usage
or configuration error. `--json` writes one JSON object to stdout for completed
checks; usage errors go to stderr and do not produce a JSON report.

HTTP categories include authentication (401), forbidden (403), not_found (404),
rate_or_quota (429), server_error (5xx), and redirect (3xx). These are diagnostic
hints, not definitive root-cause identification. Transport categories include
network, DNS, TLS and timeout. HTTP 200 with HTML, malformed JSON or an invalid
response shape fails. Response reading is capped at 2 MiB plus one sentinel byte.

## Security and limitations

- Keys are sent only to the supplied endpoint. Verify the host before running.
- HTTPS certificate verification stays enabled. Remote HTTP requires `--allow-http`;
  literal loopback addresses and localhost are allowed for development.
- Redirects are blocked, including same-host redirects.
- No telemetry, files, raw response bodies, model IDs, URL or keys in reports.
- Proxy settings are ignored unless `--use-env-proxy` is explicitly supplied.
- This is a local CLI for endpoints you may test. Do not expose it as an unrestricted
  server-side URL-fetching service: private/local destinations are intentionally allowed.
- No streaming, embeddings, images, tool calling, Responses API, native Anthropic
  or native Gemini protocol coverage in this version.
- No live provider integration has been certified by the bundled local tests.

## Development

```sh
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m unittest discover -s tests -v
python -m pip install build twine
python -m build
python -m twine check --strict dist/*
```

See `docs/PUBLISH_ZH.md` for the release walkthrough, sources and maintenance
plan. License: MIT. Public source URL and maintainer contact can be added to
project metadata once their real identities are confirmed; no fictitious links
or authors are included.
