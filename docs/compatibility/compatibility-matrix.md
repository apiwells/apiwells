# ApiWells Model Compatibility Matrix

This matrix summarizes real endpoint compatibility validation performed
with ApiWells Endpoint Doctor.

Results represent observed behavior for the specific Provider,
Endpoint, Model and test date shown below.

They should not be interpreted as permanent guarantees of provider or
model capability.

## Compatibility Matrix

| ID | Provider | Model | Models | Chat | Streaming | Usage | Tool Calling | Structured Output | Overall |
|---|---|---|---|---|---|---|---|---|---|
| MODEL-0001 | DeepSeek Official | `deepseek-flash` | PASS | PASS | PASS | PASS | PARTIAL / UNKNOWN | FAIL / UNKNOWN | PARTIAL |
| MODEL-0002 | Alibaba Cloud Model Studio | `qwen3.7-plus` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| MODEL-0003 | OpenRouter | `inclusionai/ling-3.0-flash-fin:free` | PASS | PASS | PASS | PASS | PARTIAL / UNKNOWN | FAIL / UNKNOWN | PARTIAL |

## Test Metadata

| ID | Endpoint Type | Test Date | ApiWells Version |
|---|---|---|---|
| MODEL-0001 | Official API | 2026-09-24 | 0.1.0 (v0.2 development build) |
| MODEL-0002 | Official Workspace API | 2026-09-27 | 0.1.0 (v0.2 development build) |
| MODEL-0003 | OpenAI-compatible Aggregator | 2026-09-27 | 0.1.0 (v0.2 development build) |

## Result Definitions

### PASS

The tested capability completed successfully and satisfied the
Endpoint Doctor validation criteria.

### PARTIAL

The capability was partially observed or the request was accepted, but
the complete validation criteria were not satisfied.

### FAIL

The tested validation path failed to satisfy the required criteria.

A FAIL result should be interpreted together with its Support status.

### SUPPORTED

Runtime evidence was sufficient to confirm support for the tested
capability.

### UNSUPPORTED

Runtime evidence was sufficient to establish that the tested capability
is not supported.

### UNKNOWN

Runtime evidence was insufficient to determine whether the capability
is supported or unsupported.

### AVAILABLE

Provider-reported Usage data was returned and parsed successfully.

## Interpretation Notes

- Results describe observed runtime behavior at the recorded test date.
- Provider and model behavior may change over time.
- `FAIL / UNKNOWN` does not mean that a capability is permanently
  unsupported.
- `PARTIAL / UNKNOWN` does not mean that a capability is unsupported.
- Tool Calling is marked PASS only when the complete Tool Call → local
  execution → Tool result → second request → final response round trip
  is validated.
- Structured Output is marked PASS only when the returned output
  successfully passes JSON Schema validation.
- Usage values are based only on provider-reported data and are not
  locally estimated.
- Individual Model Compatibility Records contain the detailed runtime
  evidence behind each matrix entry.

## Detailed Records

- `model0001-deepseek-flash.md`
- `model0002-alibaba-qwen37-plus.md`
- `model0003-openrouter-ling30-flash-fin.md`