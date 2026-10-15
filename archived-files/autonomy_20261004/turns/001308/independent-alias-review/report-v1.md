**PASS — scoped engineering review of the exact repair.** No blocking repair defect found. The legacy fixture remains **FAIL**; production and scientific gates remain **OPEN**. This does not authorize release, adoption or node completion. Root remains sole coordinator.

Base `e4914cb4baf91bbb66f91e25584652eb273b8904` → `0b97d569a50032f62f719b1c8bc61323eaeaecb7`; tree `14b1d23acfea0a2e66d11b765a294ae484e9f2ad`. Worktree clean before and after. Four-file diff only; patch SHA256 `69d79d8b9c0b1640c60807b1325312aa0e515e65562bd6eef522508cc726a8db`. No source edits or commits.

**F1 PASS — Exact committed scope.** HEAD and inspected working bytes match 0b97d569a50032f62f719b1c8bc61323eaeaecb7, tree 14b1d23acfea0a2e66d11b765a294ae484e9f2ad. Four changed files only; clean worktree before and after; git diff --check passed. Full-index patch matches prior repair hash.
Evidence: `scripts/qd_ed_n36_source.py`, `scripts/test_n36_generated_import.py`, `tests/test_n36_frozen_alias.py`, `tests/test_n36_importlib_alias.py`.

**F2 PASS — Closed two-pair live identity proof.** Only importlib._bootstrap -> _frozen_importlib and importlib._bootstrap_external -> _frozen_importlib_external are accepted. Producer requires sys.modules alias/canonical object identity, importlib attribute identity, public name/package, canonical frozen spec name/origin, both FrozenImporter loaders, _imp.is_frozen, canonical interpreter-relative lexical file and equal path/hash inventory records. Existing os.path live check supplies current process and interpreter identity. No equal-record fallback or extensible alias table.
Evidence: `scripts/qd_ed_n36_source.py:144`, `scripts/qd_ed_n36_source.py:150`, `scripts/qd_ed_n36_source.py:178`.

**F3 PASS — Retained receipt consumer and external binding.** Exact two-claim coverage is required. Expected claim equality plus strict True identity checks reject integer boolean substitutions. Canonical frozen names and both alias/canonical runtime inventory rows are mandatory. Existing verifier requires matching interpreter and exact context/runtime_closure/process/phase binding across external expectation and receipts. Retained claims attest prior live identity; consumer does not infer historic object identity from equal hashes. Missing historical proofs remain rejected. The outer worker supplies independently bound expectations; this CPU fixture does not establish those production anchors.
Evidence: `scripts/qd_ed_n36_source.py:111`, `scripts/qd_ed_n36_source.py:203`, `scripts/qd_ed_n36_worker.py:297`, `scripts/qd_ed_n36_worker.py:355`.

**F4 PASS — Canonical frozen rows and ordinary execution audits intact.** Frozen inventory still appends spec.name then sorts/deduplicates; no public alias is added as frozen. Both canonical names and all four ordinary alias/canonical inventory records are present in reproduced evidence. The consumer adds only the two proved names to existing os.path exemption. Arbitrary equal-record aliases and missing ordinary executable evidence are rejected. Bootstrap checks, startup coverage, required source coverage and generated-origin joins are unchanged. Producer/consumer test no longer catches the full verification error or filters observed modules. All 1299 producer ordinary rows reach both live and post-exit consumers.
Evidence: `scripts/qd_ed_n36_source.py:267`, `scripts/qd_ed_n36_source.py:319`, `scripts/test_n36_generated_import.py:115`, `scripts/test_n36_generated_import.py:152`.

**F5 PASS — Generated provenance unchanged.** Bootstrap, generated admission, runtime source helper and worker are byte-identical to base. Prospective fixed generated content hash, owner/template execution and provenance checks remain. Eleven live generated rejection cases and six retained generated mutations pass. Post-exit consumer passes after generated temporary source is removed. No runtime manifest rebuilt or production provenance reconstructed.
Evidence: `scripts/qd_ed_n36_bootstrap.py`, `scripts/qd_ed_n36_generated.py`, `scripts/qd_ed_n34_source.py`, `scripts/qd_ed_n36_worker.py`, `scripts/test_n36_generated_import.py:135`.

**F6 PASS — Bounded mutation and unsuppressed CPU evidence.** 132 passed, 1 deselected in the primary run. Includes 36 importlib live mutations, 54 retained mutations, 30 complete-consumer alias mutations, two arbitrary equal-record aliases, generated provenance negatives and os.path regressions. Consumer runs in child without suppression and again in parent after exit. Inspectable full receipt has 1299 ordinary rows, 1264 compiled rows and three startup source rows. Test-only closure has 2521 records because it additionally inventories executed sources under .cpu_test_source names; not every closure row is a live module. No claim of production inventory completeness.
Evidence: `tests/test_n36_importlib_alias.py`, `tests/test_n36_frozen_alias.py`, `scripts/test_n36_generated_import.py`.

**F7 FAIL — Legacy bootstrap fixture remains broken; bounded exclusion justified with coverage limitation.** Targeted rerun reproduced failure at tests/test_n36_frozen_alias.py:182: empty stdout instead of READY. Source explains the failure: temporary alias_child module is supplied only by PYTHONPATH, while command uses -I and bootstrap constructs explicit approved search paths. Child stderr was not surfaced by this fixture, so precise import-error text is inferred from source, not claimed as observed. Exclusion is justified for the closed-alias engineering verdict: real isolated producer/post-exit consumer and negative binding checks cover the repair. It is not justified as full-suite or equivalent independent-handoff coverage. The excluded test alone captures child process identity from parent /proc before G and hashes actual context/runtime files; replacement reads child-returned binding with c/d placeholder hashes. Existing unit test still checks incomplete after coverage, but the replacement is no production before/after worker proof. Legacy test is unchanged in this diff; this is a known fixture gap, not a discovered repair regression.
Evidence: `tests/test_n36_frozen_alias.py:139`, `tests/test_n36_frozen_alias.py:179`, `scripts/qd_ed_n36_source.py:25`, `scripts/qd_ed_n36_bootstrap.py:77`, `scripts/test_n36_generated_import.py:94`.

**Exact reviewer tests.** Both runs used the worktree above, two-thread environment, empty CUDA visibility, disabled bytecode/cache writes and resolved TMPDIR inside this output directory.

```text
{
  "CUDA_VISIBLE_DEVICES": "",
  "OMP_NUM_THREADS": "2",
  "MKL_NUM_THREADS": "2",
  "OPENBLAS_NUM_THREADS": "2",
  "NUMEXPR_NUM_THREADS": "2",
  "PYTHONDONTWRITEBYTECODE": "1",
  "TMPDIR": "/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001308/independent-alias-review/tmp"
}
```

Run 1: exit `0`, wall **18.940689s**, result `132 passed, 1 deselected in 18.17s`.

```bash
/home/hynx/miniconda3/envs/vla-pilot/bin/python -B -m pytest -p no:cacheprovider -q -s tests/test_n36_importlib_alias.py tests/test_n36_frozen_alias.py scripts/test_n36_generated_import.py -k 'not fresh_source_bootstrap_process_receipt' --basetemp=/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001308/independent-alias-review/pytest-review
```

Run 2: exit `1`, wall **12.754428s**, result `1 failed, 91 passed in 11.97s`.

```bash
/home/hynx/miniconda3/envs/vla-pilot/bin/python -B -m pytest -p no:cacheprovider -q -s tests/test_n36_importlib_alias.py tests/test_n36_frozen_alias.py::test_fresh_source_bootstrap_process_receipt --basetemp=/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001308/independent-alias-review/pytest-legacy
```

Cumulative reviewer test wall **31.695117s / 180s**. The legacy diagnostic command also reselected 91 importlib cases; this is included in time and results. Prior repair tests used 50.180080s; combined prior/reviewer time is 81.875197s. Exact stdout/stderr and start times are in the test JSON artifacts and report JSON.

**Preserved history.** Prior run 1: 91 passed, 1 failed (12.605813s): noncanonical symlink-spelled TMPDIR rejected by the existing path audit. Prior runs 2/3: 132 passed, 1 deselected (18.654173s / 18.920094s), after resolving TMPDIR without weakening the audit. The legacy test was excluded, not certified, in those prior runs. This review independently reproduced its pre-READY failure and retains that result. Original evidence was not rewritten.

**Separate unresolved gates.**

- G1 OPEN — Independent parent anchor CPU regression: Restore an admissible test harness for actual file-reference hashes, parent-captured PID/start ticks/boot ID and pre-receipt handoff; include both runtime_before and runtime_after positive cases. Do not relax isolated path admission.
- G2 OPEN — Production runtime/source closure: No production closure was rebuilt, opened for provenance reconstruction, or certified. Fresh coordinator-authorized frozen closure must bind the exact prospective sources/runtime and complete production required_after set.
- G3 OPEN — Production worker before/after: CPU fixture imports worker helpers but never runs production worker lifecycle/consumer. Immutable observations, independently anchored process identity, loaded_before/after worker identity equality, execution monotonicity, generated before/after equality, Main execution and full required_after remain unproved by this review. The corresponding checks are present in unchanged worker code.
- G4 OPEN — Scientific, release and adoption: Scientific goal remains unproven. No score, formal validation, adoption, promotion, release or node-completion authority follows from engineering PASS. Root remains sole coordinator.

**Smallest next bounded step.** Coordinator may authorize a CPU-only fixture repair restoring an admissible isolated child and parent-anchored actual context/runtime hashes plus process handoff, then test both phases within a fresh bounded budget. Preserve failed/excluded history. Production closure and lifecycle gates remain separate; no manifest rebuild or release as part of that fixture task.

**Source hashes.**

| File | SHA256 |
| --- | --- |
| `scripts/qd_ed_n36_source.py` | `dc11451c64d24f8c3d74fb2ed63ac98e96b38760253879a9d90f874e03854497` |
| `scripts/test_n36_generated_import.py` | `30cd24efe3545eda9179f71d94e6df231a8e0c603ea70309227f6e821ca8ef0a` |
| `tests/test_n36_frozen_alias.py` | `2ae6a3405b4af5f1df71e4bc066f70aef64f695cc8ece08044a41e5b344d5b94` |
| `tests/test_n36_importlib_alias.py` | `e454d8bc6200ea453829a40298ccbcc66c11b75d14cf38c60c81d0ce03942679` |
| `scripts/qd_ed_n36_bootstrap.py` | `b58430c8d7381e13791ad62cc00ce8cb11d7c344192df9729f0d4bdbc306fb64` |
| `scripts/qd_ed_n36_generated.py` | `e1f43e04e4afabba62b81468d8bf68da6cd66d99f3bc074a703ef7bc83d5e523` |
| `scripts/qd_ed_n34_source.py` | `be71a7cc706915c7466b641a68d6ece2689857668baf74fa2a58aa8181ca70b4` |
| `scripts/qd_ed_n36_worker.py` | `f719b22fe54c4beb4ef908040cc130efca7c28ce46fad68243745ac46cda5726` |

**Artifact hashes.** Full absolute paths and byte counts are in JSON; original and reproduced receipts are separately identified.

| Artifact | SHA256 |
| --- | --- |
| `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001308/independent-alias-review/authority-v1.json` | `651591875829db52fcc7553007a8cceb98fee30d85093aab0d8e9e99f9b372fd` |
| `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001306/frozen-alias-repair/report-v1.json` | `52ce6d4547d1a9716efaba13b67c13d67e688eb6b63e99b2badc7cad238d70a0` |
| `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001306/frozen-alias-repair/report-v1.md` | `3446775b2c326e57d6f4b21cc73ba474300a0258ff245b5c08ee7258326380aa` |
| `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001306/frozen-alias-repair/tests-1.json` | `c7a051b532fa52a2faf73a685f614be23e8e4401e2d619fe32c35cc5cafe358c` |
| `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001306/frozen-alias-repair/tests-2.json` | `fe98a10ff3141d44bf92c231d2e22e7e0eeb2c7cd05e5c825611960e8c338ae8` |
| `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001306/frozen-alias-repair/tests-3.json` | `4c3e0eb076eda235a8b236733a08f1a5692e94694d4871ca74200cd01d53ee4c` |
| `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001306/frozen-alias-repair/pytest-3/test_real_bootstrap_and_retain0/cpu-receipts.json` | `326e9c9a06a9fd9d8cb6f7e8df564510df6de1e609804855206154051045163a` |
| `reviewed-diff.patch` | `69d79d8b9c0b1640c60807b1325312aa0e515e65562bd6eef522508cc726a8db` |
| `inspection-evidence.json` | `8caf42f791dd1bab99fd104abb455fb89bc57502b842002bf04190004a9ffbcd` |
| `receipt-inspection.json` | `51838fd308479bb33fe39ad0300e3a1ff7b0235417f329e010409941b44440c0` |
| `tests-review.json` | `d27eac15cc11cb9117c611e06fb4371e2e0fdfe897ec13b060a7191c6133dd26` |
| `tests-legacy.json` | `0581006413b24e2e4fbadeafbf3baf7a53dff8db6d6acfda621ee67714f58cae` |
| `pytest-review/test_real_bootstrap_and_retain0/cpu-receipts.json` | `a6d169d15bebc6ae10c4c21c3922baec4be8398b494c8ca329fd52797b18ab41` |
| `write-report.py` | `14b14d8c7992274688880bdba90e351f080bd221bf6b892b44990aa33f75299d` |

Conservative elapsed time from authority creation: 193.739s / 900s at report generation. All writes remained in the authorized output directory. No forbidden operations, external model/provider calls or child agents. Scientific goal remains unproven. Review stops here.
