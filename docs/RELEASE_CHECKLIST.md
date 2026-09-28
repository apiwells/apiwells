# v0.2 Release Checklist

Repository release-facing scope reference: [V0.2_SPEC.md](V0.2_SPEC.md), derived
from the project-level frozen engineering baseline maintained outside the
repository release artifacts.

A checked evidence item applies only to its recorded development build/environment,
not automatically to a future RC or final artifact. Unverified work stays unchecked.

Current baseline: branch `feature/v0.2-diagnostics`, starting commit
`f63de41`, package/CLI **0.1.0 (v0.2 development build)**.
v0.2.0 has not been released.

## Completed development-build evidence

- [x] ED-031 real endpoint/provider live validation: **CLOSED / PASS**.
  The [compatibility index](COMPATIBILITY.md) links the authoritative matrix
  and MODEL-0001, MODEL-0002 and MODEL-0003 records.
- [x] ED-032 Windows clean-install test: **CLOSED / PASS**.
- [x] Local wheel + sdist build: **PASS**.
- [x] Windows Basic real endpoint smoke: **PASS**.
- [x] Windows clean-wheel integration suite: **43 passed**.
- [x] Windows critical Deep smoke: **PASS**.
- [x] No secret leak observed in the recorded validation.

The ED-032 outcomes above are carried forward from the supplied ED-033
acceptance baseline; they are not newly executed ED-033 checks. They do not
replace or overwrite ED-031 compatibility measurements. Historical
[0.1.0 validation](releases/0.1.0/VALIDATION.md) remains separate evidence, not
v0.2 RC acceptance.

## Frozen Scope gates (section 46)

| Gate | Required evidence | Current release disposition |
|---|---|---|
| A — Baseline | v0.1 regression tests, editable install, CLI smoke, clean baseline | Historical gate evidence must be included in final release review; no new PASS claimed here |
| B — Core Architecture | Unified ProbeResult; runner independent of console; reporters do not send HTTP | Implementation described in the spec; final gate acceptance remains to be recorded |
| C — Functional | Success, unsupported and failure paths for Models, Chat, Streaming, Tools and Structured Output | Test plan covers these paths; complete release validation evidence remains pending |
| D — Security | Secret Leak Test passes; any complete credential leak blocks release | No leak observed in accepted validation; retain the dedicated release test evidence before final acceptance |
| E — Real Providers | At least 3 independent providers/endpoints covering 3–5 Chinese models | PASS: closed ED-031 records |
| F — Package | Build wheel + sdist and clean install | PASS for the development build via ED-032; RC/final artifact acceptance remains pending |
| G — Release Documentation | README, CHANGELOG, SECURITY and the four release documents | PASS — ED-033 documentation reviewed and accepted |

## Documentation acceptance (ED-033)

- [x] Reconcile the release-facing specification/checklist with the supplied
  frozen specification and current CLI compatibility behavior.
- [x] Reviewer acceptance of README, changelog, security guidance, specification,
  test plan, compatibility index and this checklist (Gate G): PASS.

TESTENV-01: the observed Windows harness used pytest **9.1.1**,
pytest-httpserver **1.1.5** and Werkzeug **3.1.8**. These are test dependencies,
not ApiWells runtime dependencies. See [TEST_PLAN.md](TEST_PLAN.md).
No new dev-dependency packaging mechanism is selected in ED-033.

## Remaining formal release gates

- [ ] Complete remaining required release validation under the frozen scope:
  unit, mock integration, Secret Leak Test and any outstanding platform/Python
  coverage; retain evidence tied to the release candidate.
- [ ] Complete macOS and Linux installation, `--version`, `--help`, Basic smoke
  and mock-suite validation required by section 38.
- [ ] Verify the minimal CI checks: unit tests, mock integration, wheel/sdist build
  and package verification; live provider tests stay separately controlled.
- [ ] Synchronize production version declarations to **0.2.0** in both
  `pyproject.toml` and `src/apiwells/__init__.py` before formal RC/final artifacts.
- [ ] Build and identify the formal **RC artifact**; validate metadata and
  preserve artifact hashes and provenance.
- [ ] Complete **TestPyPI** publication/installation validation.
- [ ] Complete **RC clean-install acceptance** against the actual RC artifact.
- [ ] Review all required release evidence and approve the final release.
- [ ] Publish the final **PyPI 0.2.0 release**.
- [ ] Complete **post-release PyPI clean-install smoke**, including the frozen
  onboarding target of a first Basic check within about five minutes.

VERSION-01: both version declarations remain 0.1.0 in ED-033. Whether to refactor
to a single version source is undecided. Closed ED-031/ED-032 work is not
reopened by these future artifact-specific gates. This checklist does not
authorize publishing.
