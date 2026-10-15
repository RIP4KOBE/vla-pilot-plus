# N25 named infrastructure continuation: CPU delivery

Status: **CPU_PREPARATION_COMPLETE / ONLINE_CLOSED**. Final isolated commit `6f796358aa84d53e9c8a04859f7d19352c9db7fe` on `codex/n25-infrastructure-continuation`; protocol precommit `57f015c`. No actual history seal, integration, budget adoption, runtime proof read or GPU dispatch occurred. N25 original INVALID, N25 validation and N26 preparation remain unchanged. This administrative continuation is not an algorithm revision or a measured efficacy result.

## Source boundary

The source manifest contains271 files, internal digest `702bfd450b2de2df9a3b3b0a2117801528f0c761d949a0d94d276047d848fc7f`. All255 original files outside runner/worker are byte-identical to5a. Whole-file reverse patches reproduce both original files exactly; the only changed existing functions are `runner.metered_support`, `runner.check_budget`, `runner.check_retry`, and `worker.validate_context`. Original `run_plan`, command construction, process deadline/cleanup, `run_worker`, `verify_receipt`, scientific/native/RDT/provider/Stage code, profiles, and single-timeout classifier are unchanged. Eight new operational modules, two synthetic-test files and four source documents close the additional source list. `source-reverse-bridge-cpu-v1.json` is byte evidence only; root must construct the actual history-bound bridge after sealing.

## Implemented behavior

The new versioned cohort carries exactly18 root-attested accepted cells without native tensor replay, new reservations or execution. It permits22 remaining rows in original order: one exact named task4/N23 retry in recovery, followed by untouched indices19..39. Any new invalidity stops; there is no additional pure-timeout retry or resume. All19 original attempts, the literal failed terminal, six unknown-token calls and unmeasured native/safety/causal Unknowns remain visible. Original22 local GPU hours include the old8201.788167113322 seconds. Capacity checks preserve494/100 and all buckets/protected reserves, require5 baseline+16 development+1 recovery slots at entry, and1840seconds before every dispatch. No new preflight is added.

The metadata sealer is restricted to at most512 inventoried JSON/JSONL/text files,16MiB per file and128MiB total. It checks size before bounded allocation and caches each payload. Receipt evidence-index digests may contain thousands of tensor refs; no tensor is opened or rehashed. Public Stage projection is checked against all43 recorded calls, exact six failed identities, observed180-second timing, event/item categories and cleanup order. The root's public projection and original metered/root-attested native acceptance are explicitly trusted attestations, not a fresh native audit. Two absent failed-attempt audit files remain typed absences; late files or links fail.

The successor report distinguishes original INVALID from logical-cohort disposition, imports/new cells, every charged attempt and partial costs. Status/journal disagreement stays INVALID while retaining valid journal evidence. Independent terminal review recomputes gates/counts/costs from metadata rather than calling the result analyzer, rejects duplicate attempt IDs before dictionary comparison, and checks process cleanup for every newly dispatched attempt including an invalid final attempt. Reserved→aborted without dispatch records explicit process absence. Missing process evidence after dispatch blocks root reconstruction rather than inventing a PID. The reviewer writes a separate immutable root review; optional missing-result repair is explicitly a writer, not an accepted review.

## CPU evidence and preserved failures

113 distinct synthetic tests have final passing evidence across necessary targeted runs; this is not a claim of one113-test final rerun.

| Run | Outcome | Guard | Explanation |
|---|---|---|---|
| focused-v1 |66 pass,3 fail;54.92s|0 blocks|Implementation lacked creation of the strictly constrained status directory in direct `execute`. Fixed and all3 cases passed v2. |
| focused-v2 |93 pass,3 fail;76.33s|3 denied reads|Mocked PID999999999 triggered unstubbed `/proc/999999999/stat` reads. Guard blocked all three before content; fixed the synthetic fixture, not the guard. |
| focused-v3 |28 pass,81 deselected;22.37s|0 blocks|Affected real `run_plan` composition, independent review,255-file/reverse bridge, and finite adoption gates. |
| focused-v4 |15 pass,98 deselected;14.30s|0 blocks|Final duplicate-cost, all-dispatched cleanup, missing-process and undispatched-absence checks plus normal/reject/futility/invalid review. |

Every run recorded CUDA uninitialized, two CPU threads and two interop threads. No real experiment/protected payload was read; no API/model/simulator or GPU was invoked. The allowed static source, source manifest, root protocol and sanitized public interface supplement were the only non-synthetic inputs. All failed logs are preserved. The inventory draft and actual public Stage projection were not read or executed during these tests.

A reproducible focused command from the isolated implementation (use a new unused basetemp/log name) is:

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python -B - <<'PYTEST'
import runpy, sys
from pathlib import Path
h = Path.cwd().parent / 'infrastructure-continuation-preparation-v1'
runpy.run_path(str(h / 'cpu_guard_v1.py'))
import pytest
sys.exit(pytest.main(['-q', '-p', 'no:cacheprovider', '--basetemp', str(h / 'tmp' / 'pytest-root-review-new'), 'tests/test_qd_ed_n25_cont.py', '-k', 'independent_existing_terminal_review']))
PYTEST
```

## Root handoff and limitations

Exact schemas, paths, CLI order and attestation limits are in `experiments/qd_ed_n25_continuation/controller-contract-v1.md`. The eight JSON files under `disabled-templates-v1/` have explicit `executable=false`, `gpu_authorized=false` and unresolved refs; they are templates, not release artifacts. Root's already disabled metadata-input draft can remain immutable; create a separately reviewed authorized inventory using this stable schema. No additional actual input category was introduced by final tests.

Required order remains: root source/log review → new reviewed metadata inventory → actual sealer under intact old5a → seal review → exact source integration → administrative bridge/source/runtime/resource/budget review and finite authority → one immutable22-row plan → inspect all commands → explicit single launch. The controller records its measured PID/boot/ticks itself. After closure, root runs the independent terminal reviewer under the controller/runner locks. No source-embedded future seal/proof hash creates a circular freeze.

Actual metadata, runtime alias behavior, live capacity and exclusive GPU7 admission remain root verification tasks. Historical absent native gates are never certified; all new attempts must pass the unchanged full audit. Any resulting logical promotion/rejection still requires a separately reviewed adapter for prebuilt N25 validation or N26 admission. Neither downstream preparation is activated by this delivery.
