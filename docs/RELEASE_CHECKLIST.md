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

## v0.2.1 Patch Release

Release type: **Documentation / Package Metadata Correction**

Release date: **2026-09-28 (America/New_York)**. Production uploads completed
at **2026-09-29 00:06:48-49 UTC**.

Release status: **CLOSED / PASS**

Release source: `74ad97a83ff4580590d050fc3b32c86aa7130940`

Release tag: `v0.2.1` (annotated; remains on the release source commit)

Production package: `apiwells==0.2.1`

Scope: runtime diagnostic behavior is unchanged. The only runtime source
difference from v0.2.0 is package version identity. Runtime dependencies,
tests, CLI arguments and JSON contracts are unchanged. ED-037A separately
made CI package checks version-neutral; that is release engineering only.

### v0.2.1 canonical artifacts

| Artifact | Filename | Size |
|---|---|---:|
| Wheel | `apiwells-0.2.1-py3-none-any.whl` | 40,897 bytes |
| sdist | `apiwells-0.2.1.tar.gz` | 84,236 bytes |

Wheel SHA256:

`AE3B6376B1E2D4CE2DDA8A36F91094E3961D08320B457BD09986BCF1B8CDBD1D`

sdist SHA256:

`812AB655BA983A4407CC7238365F677B5CF7D90E81958720960A29BFBECD811D`

Canonical artifacts were built once from the frozen source. Local artifacts,
TestPyPI 0.2.1 and Production PyPI 0.2.1 have identical hashes. No canonical
artifact was rebuilt after TestPyPI acceptance.

### v0.2.1 completed release checklist

- [x] Package and CLI version synchronized to **0.2.1**.
- [x] README is patch-version-neutral.
- [x] README documentation links are absolute, PyPI-safe GitHub URLs.
- [x] Repository and Issues project URLs verified publicly accessible.
- [x] v0.2 specification is patch-version-neutral; frozen scope preserved.
- [x] Full local regression: **290 passed, 59 subtests passed**.
- [x] Focused integration regression: **43 passed**; local `pip check` PASS.
- [x] Runtime code equivalence to v0.2.0 except version identity.
- [x] Release branch CI: Ubuntu / Windows / macOS PASS.
- [x] Release-source main CI: Ubuntu / Windows / macOS PASS.
- [x] Canonical wheel and sdist build.
- [x] `twine check --strict`: both artifacts PASS.
- [x] Artifact metadata, README and runtime byte-equivalence inspection.
- [x] TestPyPI 0.2.1 publication.
- [x] TestPyPI artifact identity.
- [x] TestPyPI metadata / description / project URLs.
- [x] TestPyPI fresh clean install and CLI / `pip check`.
- [x] Downloaded TestPyPI wheel hash matches the canonical wheel.
- [x] Annotated `v0.2.1` tag created and pushed.
- [x] Tag CI: Ubuntu / Windows / macOS PASS.
- [x] Production PyPI publication.
- [x] Production artifact identity.
- [x] Production metadata / description / project URLs.
- [x] Production fresh install: second fresh-environment attempt PASS.
- [x] `apiwells --version`: **apiwells 0.2.1**.
- [x] `apiwells --help`.
- [x] `apiwells doctor --help`.
- [x] Production `pip check`: **No broken requirements found.**
- [x] Production real-provider Basic smoke: Alibaba Cloud Model Studio PASS.
- [x] v2 JSON contract.
- [x] Secret safety: actual key absent from stdout and stderr.
- [x] Temporary `APIWELLS_TEST_KEY` removed; subsequent environment check false.
- [x] ED-037 final release: **CLOSED / PASS**.

### v0.2.1 CI evidence

All jobs below used Python 3.12. These are CI results, not macOS/Linux
real-provider certification.

| Gate | Ubuntu | Windows | macOS | Evidence |
|---|---|---|---|---|
| ED-037A branch | PASS | PASS | PASS | [Run 36451428904](https://github.com/apiwells/apiwells/actions/runs/36451428904) |
| ED-037A main | PASS | PASS | PASS | [Run 36452855523](https://github.com/apiwells/apiwells/actions/runs/36452855523) |
| v0.2.1 release branch | PASS | PASS | PASS | [Run 36499257866](https://github.com/apiwells/apiwells/actions/runs/36499257866) |
| v0.2.1 release-source main | PASS | PASS | PASS | [Run 36499636095](https://github.com/apiwells/apiwells/actions/runs/36499636095) |
| v0.2.1 tag | PASS | PASS | PASS | [Run 36501015258](https://github.com/apiwells/apiwells/actions/runs/36501015258) |

ED-037A branch/main were first confirmed through human review of GitHub Actions
UI and subsequently verified through the public Actions API. The release
branch, release-source main and tag results were read through the Actions API.
The final documentation commit's CI result is recorded in the release handoff.

### Production propagation observation

**First clean-install attempt: FAIL.** Immediately after publication, pip's
normal Production index resolution listed only 0.1.0 and 0.2.0 and returned
`No matching distribution found for apiwells==0.2.1`. Acceptance stopped at
that gate. No upload, rebuild, retag or version change was used to bypass it.

Subsequent direct Production JSON and Simple Index checks showed the 0.2.1
wheel and sdist with the canonical hashes. A second, entirely fresh Windows
environment using **Python 3.12.13** first ran `pip index versions apiwells`
against `https://pypi.org/simple/` and confirmed latest **0.2.1**, then installed
`apiwells==0.2.1` through the normal index with `--no-cache-dir`.

**Second fresh-environment acceptance: PASS.** Import identity came from that
environment's `site-packages`, not the source checkout. CLI checks and
`pip check` passed. The first attempt remains historical release evidence.

The observed sequence is consistent with publication/index propagation timing,
but the release record does not claim a definitive root cause.

### v0.2.1 production Basic and secret-safety evidence

Only Basic console and Basic `--v2-json` checks were run against the previously
validated Alibaba Cloud Model Studio endpoint. URL, DNS, TLS and HTTP were
PASS; Authentication and /models were PASS / SUPPORTED; overall was PASS.

Both commands exited **0**, with **0 stderr bytes**. The JSON report had
`schema_version: "1"`, `apiwells_version: "0.2.1"`, `overall_status: "PASS"` and
six ordered probes: `url`, `dns`, `tls`, `http`, `auth`, `models`.

Raw stdout/stderr were captured as bytes. Exact-key checks found no actual API
key in either output for either command. The temporary key environment
variable was removed after testing, and its absence was verified.

No Deep recertification was required because runtime diagnostic source remained
equivalent to v0.2.0 except version identity. No paid Deep certification was
rerun. ED-031 historical compatibility evidence was not modified. TestPyPI
0.2.0, Production PyPI 0.2.0 and the v0.2.0 tag were not modified.

This documentation closeout follows the release source on main; it does not
move the v0.2.1 tag or change any published artifact.
