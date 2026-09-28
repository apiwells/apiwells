# Model Compatibility Record — DeepSeek Flash

## Overview

| Field | Value |
|---|---|
| Record ID | MODEL-0001 |
| Provider | DeepSeek Official |
| Endpoint | `https://api.deepseek.com` |
| Model | `deepseek-flash` |
| Protocol | OpenAI-compatible Chat Completions |
| Test Date | 2026-09-24 |
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
- Models returned: 2
- Target model found: yes

## Chat Completions

| Metric | Value |
|---|---:|
| Status | PASS |
| HTTP status | 200 |
| Total latency | 969 ms |
| Usage available | yes |
| Prompt tokens | 33 |
| Completion tokens | 34 |
| Total tokens | 67 |

## Streaming

| Metric | Value |
|---|---:|
| Status | PASS |
| Content-Type | `text/event-stream; charset=utf-8` |
| Model output received | yes |
| Terminal `[DONE]` received | yes |
| TTFT | 953 ms |
| Total latency | 1094 ms |
| Chunk count | 58 |
| Usage available | yes |
| Prompt tokens | 33 |
| Completion tokens | 57 |
| Total tokens | 90 |

## Tool Calling

- Status: PARTIAL
- Support: UNKNOWN
- First request HTTP status: 200
- Tool call observed: no
- Round trip completed: no

The Tool Calling request was accepted, but no Tool Call was emitted
during the default compatibility test.

This result does not establish that the model lacks Tool Calling
support.

An additional controlled validation successfully completed a full
two-request Tool Calling round trip. This supporting observation does
not override the default compatibility result above.

## Structured Output

- Status: FAIL
- Support: UNKNOWN
- `json_schema` HTTP status: 400
- `json_schema` request accepted: no

The runtime response did not provide sufficient evidence to classify
strict JSON Schema Structured Output as definitively unsupported.

## Summary

`deepseek-flash` successfully passed Models, Chat Completions,
Streaming and Usage validation.

Tool Calling is recorded as `PARTIAL / UNKNOWN` because the full
required Tool Calling round trip was not observed during the default
test.

Strict JSON Schema Structured Output is recorded as `FAIL / UNKNOWN`
because the request was rejected without sufficient runtime evidence
to establish definitive lack of support.