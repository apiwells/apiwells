# Model Compatibility Record — Ling 3.0 Flash Fin via OpenRouter

## Overview

| Field | Value |
|---|---|
| Record ID | MODEL-0003 |
| Provider | OpenRouter |
| Endpoint Type | OpenAI-compatible Aggregator |
| Endpoint | `https://openrouter.ai/api/v1` |
| Model | `inclusionai/ling-3.0-flash-fin:free` |
| Protocol | OpenAI-compatible Chat Completions |
| Test Date | 2026-09-27 |
| ApiWells Version | 0.1.0 (v0.2 development build) |
| Overall | PARTIAL |

## Compatibility

| Capability | Status | Support |
|---|---|---|
| Connectivity | PASS | — |
| Authentication | PASS | SUPPORTED |
| Models | PASS | SUPPORTED |
| Chat Completions | PASS | SUPPORTED |
| Streaming / SSE | PASS | SUPPORTED |
| Usage | PASS | AVAILABLE |
| Tool Calling | PARTIAL | UNKNOWN |
| Structured Output | FAIL | UNKNOWN |

## Models

- HTTP status: 200
- Models returned: 458
- Target model found: yes

## Connectivity

| Metric | Value |
|---|---|
| TLS status | PASS |
| TLS version | TLSv1.3 |
| Cipher | `TLS_AES_256_GCM_SHA384` |
| TLS latency | 2578 ms |

## Chat Completions

| Metric | Value |
|---|---:|
| Status | PASS |
| HTTP status | 200 |
| Total latency | 4594 ms |
| Usage available | yes |
| Prompt tokens | 23 |
| Completion tokens | 325 |
| Total tokens | 348 |

## Streaming

| Metric | Value |
|---|---:|
| Status | PASS |
| Content-Type | `text/event-stream` |
| Model output received | yes |
| Terminal `[DONE]` received | yes |
| TTFT | 4641 ms |
| Total latency | 4641 ms |
| Chunk count | 132 |
| Usage available | yes |
| Prompt tokens | 23 |
| Completion tokens | 298 |
| Total tokens | 321 |

## Tool Calling

- Status: PARTIAL
- Support: UNKNOWN
- First request HTTP status: 200
- Tool call observed: no
- Request count: 1
- Round trip completed: no

The Tool Calling request was accepted, but no Tool Call was emitted
during the compatibility test.

This result does not establish that the model or endpoint lacks Tool
Calling support. It means that the complete required Tool Calling
round trip was not observed during this test.

## Structured Output

- Status: FAIL
- Support: UNKNOWN
- `json_schema` HTTP status: 400
- `json_schema` request accepted: no

The runtime response did not provide sufficient evidence to classify
strict JSON Schema Structured Output as definitively unsupported.

## Summary

`inclusionai/ling-3.0-flash-fin:free` successfully passed Models,
Chat Completions, Streaming and Usage validation through OpenRouter.

Tool Calling is recorded as `PARTIAL / UNKNOWN` because no Tool Call
was observed during the test.

Strict JSON Schema Structured Output is recorded as `FAIL / UNKNOWN`
because the request was rejected without sufficient runtime evidence
to establish definitive lack of support.