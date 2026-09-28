# v0.2.0 Release Checklist

Release date: **2026-09-28**

Release status: **CLOSED / PASS**

Release source: `cac558b543336f42d17b8db99bfacd6e53d1e5dd`

Release tag: `v0.2.0` (annotated)

Production package: `apiwells==0.2.0`

Public release-facing specification: [V0.2_SPEC.md](V0.2_SPEC.md).

This completed release record reflects the acceptance evidence established
during ED-034, ED-035 and the post-release production acceptance. ED-036 only
reconciles the repository documentation with those already-confirmed results;
it does not represent a new build, publication or execution of acceptance tests.

## Canonical final artifacts

| Artifact | Filename |
|---|---|
| Wheel | `apiwells-0.2.0-py3-none-any.whl` |
| sdist | `apiwells-0.2.0.tar.gz` |

Wheel SHA256:

```text
AC346E77ADA9B376420BD9F3B83FDA1CAB2CFD89F80598A5937162F1EDF03168
```

sdist SHA256:

```text
CBD4D357E2DE397951B35D499A12AC89C3002F34E614634A1BFF12ECE35C32A3
```

These identify the canonical final release artifacts. The release source,
annotated tag and published artifacts are unchanged by this documentation pass.

## Completed release checklist

- [x] Frozen scope validation.
- [x] Package and CLI version synchronized to **0.2.0**.
- [x] Unit tests.
- [x] Mock integration tests.
- [x] Secret leak validation.
- [x] ED-031 real-provider compatibility evidence: **CLOSED / PASS**.
- [x] ED-033 release documentation reviewed and accepted.
- [x] ED-034 Windows formal RC acceptance.
- [x] Wheel build.
- [x] sdist build.
- [x] `twine check`.
- [x] TestPyPI publication.
- [x] TestPyPI artifact identity.
- [x] TestPyPI clean install.
- [x] TestPyPI Basic smoke.
- [x] Cross-platform CI — Ubuntu: **PASS**.
- [x] Cross-platform CI — Windows: **PASS**.
- [x] Cross-platform CI — macOS: **PASS**.
- [x] Annotated `v0.2.0` tag created and pushed.
- [x] ED-035 production PyPI publication.
- [x] Production PyPI artifact identity.
- [x] Fresh production PyPI clean install.
- [x] `apiwells --version`: **PASS**, reports `apiwells 0.2.0`.
- [x] `apiwells --help`: **PASS**.
- [x] `apiwells doctor --help`: **PASS**.
- [x] `pip check`: **PASS**.
- [x] Production real-provider Basic smoke: **PASS**.
- [x] v2 JSON contract: **PASS**.
- [x] Secret not present in stdout/stderr.
- [x] Temporary API key removed after testing.
- [x] ≤5 minute onboarding target: **PASS**.
- [x] Final release: **CLOSED / PASS**.

## Evidence boundaries

Cross-platform CI PASS is not macOS/Linux real-provider live-validation PASS.
The production Basic smoke establishes the recorded Basic checks, not every
Deep capability on every provider. The release record makes no claim that
every Python version was tested or every provider capability passed.

ED-031 compatibility results remain point-in-time evidence for their original
endpoint, model, build and test date. Later production smoke and CI results
do not replace those observations.

## Historical evidence preserved

- **ED-031 — CLOSED / PASS:** the [compatibility index](COMPATIBILITY.md) links
  the authoritative matrix and MODEL-0001, MODEL-0002 and MODEL-0003 records.
  Their original build versions, dates, metrics and PASS/PARTIAL results remain
  unchanged.
- **ED-032 — CLOSED / PASS:** local wheel + sdist build PASS, Windows Basic
  real-endpoint smoke PASS, clean-wheel integration **43 passed**, critical
  Deep smoke PASS and no secret leak observed. These are historical Windows
  acceptance results, separate from ED-034 RC and production PyPI acceptance.
- **TESTENV-01:** the observed ED-032 Windows harness used pytest **9.1.1**,
  pytest-httpserver **1.1.5** and Werkzeug **3.1.8**. These are test dependencies,
  not ApiWells runtime dependencies. See [TEST_PLAN.md](TEST_PLAN.md).
- [0.1.0 validation](releases/0.1.0/VALIDATION.md) remains historical evidence for
  that release; it is not relabeled as v0.2.0 acceptance.

VERSION-01 was completed by synchronizing both version declarations to 0.2.0
before the formal release. No version bump or version-source refactor is part
of ED-036. ED-031 and ED-032 remain closed.
