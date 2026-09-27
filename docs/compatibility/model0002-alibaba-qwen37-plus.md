# Model Compatibility Record — Qwen3.7 Plus

## Overview

| Field | Value |
|---|---|
| Record ID | MODEL-0002 |
| Provider | Alibaba Cloud Model Studio |
| Region | Beijing |
| Endpoint | `https://<workspace-id>.cn-beijing.maas.aliyuncs.com/compatible-mode/v1` |
| Model | `qwen3.7-plus` |
| Protocol | OpenAI-compatible Chat Completions |
| Test Date | 2026-09-27 |
| ApiWells Version | 0.1.0 (v0.2 development build) |
| Overall | PASS |

## Compatibility

| Capability | Status | Support |
|---|---|---|
| Connectivity | PASS | — |
| Authentication | PASS | SUPPORTED |
| Models | PASS | SUPPORTED |
| Chat Completions | PASS | SUPPORTED |
| Streaming / SSE | PASS | SUPPORTED |
| Usage | PASS | AVAILABLE |
| Tool Calling | PASS | SUPPORTED |
| Structured Output | PASS | SUPPORTED |

## Models

- HTTP status: 200
- Models returned: 261
- Target model found: yes

## Chat Completions

| Metric | Value |
|---|---:|
| Status | PASS |
| HTTP status | 200 |
| Total latency | 2766 ms |
| Usage available | yes |
| Prompt tokens | 13 |
| Completion tokens | 130 |
| Total tokens | 143 |

## Streaming

| Metric | Value |
|---|---:|
| Status | PASS |
| Content-Type | `text/event-stream; charset=utf-8` |
| Model output received | yes |
| Terminal `[DONE]` received | yes |
| TTFT | 703 ms |
| Total latency | 2671 ms |
| Chunk count | 37 |
| Usage available | yes |
| Prompt tokens | 13 |
| Completion tokens | 116 |
| Total tokens | 129 |

## Tool Calling

- Status: PASS
- Support: SUPPORTED
- First request HTTP status: 200
- Second request HTTP status: 200
- Request count: 2
- Tool: `get_diagnostic_value`
- Round trip completed: yes

The model successfully completed the full Tool Calling validation flow:

Tool Call → local Tool execution → Tool result → second request →
final model response.

## Structured Output

- Status: PASS
- Support: SUPPORTED
- `json_schema` HTTP status: 200
- `json_schema` request accepted: yes
- JSON Schema validation passed: yes

The returned structured response successfully passed strict JSON Schema
validation.

## Summary

`qwen3.7-plus` passed every capability tested in this compatibility
record.

The endpoint successfully completed:

- Models discovery;
- non-stream Chat Completions;
- SSE Streaming;
- provider-reported Usage extraction;
- full two-request Tool Calling;
- strict JSON Schema Structured Output validation.