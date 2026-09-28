# v0.2 Compatibility

The ED-031 compatibility records below were captured before the package version
was synchronized to 0.2.0. Their recorded package/build versions are preserved
as historical point-in-time evidence and must not be rewritten to match the
later final release version. Endpoint Doctor v0.2.0 was subsequently released
on **2026-09-28**. Production Basic smoke and cross-platform CI do not replace
these historical capability observations.

ED-031 real endpoint/provider live validation is **CLOSED / PASS**. This page is
a release-facing index; the historical
[compatibility matrix](compatibility/compatibility-matrix.md) and individual
records remain the authoritative detailed evidence. An overall PARTIAL record
does not mean that the ED-031 validation work package failed.

| Record | Provider | Model | Test date | ApiWells version | Overall |
|---|---|---|---|---|---|
| [MODEL-0001](compatibility/model0001-deepseek-flash.md) | DeepSeek Official | `deepseek-flash` | 2026-09-24 | 0.1.0 (v0.2 development build) | PARTIAL |
| [MODEL-0002](compatibility/model0002-alibaba-qwen37-plus.md) | Alibaba Cloud Model Studio | `qwen3.7-plus` | 2026-09-27 | 0.1.0 (v0.2 development build) | PASS |
| [MODEL-0003](compatibility/model0003-openrouter-ling30-flash-fin.md) | OpenRouter | `inclusionai/ling-3.0-flash-fin:free` | 2026-09-27 | 0.1.0 (v0.2 development build) | PARTIAL |

## Interpretation

- Results are point-in-time observations for the recorded endpoint, model,
  configuration and date, not permanent provider guarantees.
- Probe execution status and capability support are separate concepts.
  `FAIL / UNKNOWN` does not establish permanent lack of support;
  `PARTIAL / UNKNOWN` does not mean unsupported.
- Tool Calling certification requires the full round trip, and Structured
  Output certification requires successful JSON Schema validation. Request
  acceptance alone is insufficient.
- Some historical records use `AVAILABLE` for Usage. This is a
  compatibility-record-local label meaning provider-reported usage data was
  returned and parsed. It does not add a new ProbeResult support enum; those
  remain `SUPPORTED`, `UNSUPPORTED`, `UNKNOWN` and `NOT_APPLICABLE`.
- Compatibility evidence is not a model-quality Benchmark, ranking or
  recommendation. Timings are observations, not a performance guarantee.

Detailed metrics and qualifications belong to the linked ED-031 records and
are not duplicated here. ED-032 Windows clean-install smoke evidence validates
installation and execution; its metrics do not replace ED-031 measurements.
