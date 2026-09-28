# Security

ApiWells Endpoint Doctor runs locally against endpoints chosen by the user.
It is Local-First, with no telemetry by default and no hidden upload of prompts,
responses or usage. Requested diagnostic prompts and tool results are sent to
the selected provider; local execution does not prevent that provider from
receiving or processing the requests.

## Credentials and reports

API keys and Authorization header values must not be printed, committed or
included in issues, screenshots or shared logs. Supply keys through an
environment variable, using a shell's secret-input mechanism.

Centralized redaction removes known runtime secrets and recognized credential
patterns from report summaries, metrics, evidence and nested values. Error
handling suppresses raw sensitive exceptions; console and JSON reporters use
sanitized results rather than dumping raw provider response bodies.
Review reports before sharing, and remove any sensitive endpoint, account or
business information that is not a credential pattern.

## Transport and responsibility

HTTPS certificate verification remains enabled. All redirects, including
same-host redirects, are blocked; credentials are not forwarded to redirect
destinations. Verify the destination before testing. Environment proxies are
used only with explicit `--use-env-proxy` opt-in.

Remote unencrypted HTTP requires `--allow-http`; localhost and literal loopback
addresses are allowed for development. Use HTTPS when transmitting credentials.

Only test endpoints you are authorized to test. You are responsible for
endpoint selection, credentials, provider permissions and potentially billable
Deep or legacy chat requests. Local/private addresses are intentionally allowed;
do not expose the CLI as an unrestricted server-side URL-fetching service.

## Reporting a security issue

Security contact information will be published when an official channel is
established. Do not publish live credentials or sensitive response bodies in a
public report. No dedicated security address or response SLA is currently
specified here.
