import hashlib
import json
from pathlib import Path
import subprocess

W = Path(__file__).resolve().parent / 'implementation'
P = W.parent
commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip()
files = subprocess.check_output(['git','diff-tree','--no-commit-id','--name-only','-r','HEAD'],cwd=W,text=True).splitlines()
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
commands = {
 'regression': 'OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest tests/test_qd_actuator_clipped_quality.py tests/test_qd_executed_quality.py tests/test_qd_executed_feedback.py tests/test_qd_lift_quality.py tests/test_qd_hold_lift_quality.py tests/test_decision_evidence_audit.py tests/test_eds_eval_metrics.py tests/test_qd_ed_final_runner.py -q',
 'native': "OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest tests/test_rdt_steer.py -k 'n23 or n22_hold_condition or n21_positive_lift or n20_exact_profile' -q --basetemp=../cpu-native-reproduction-new-directory",
 'focused_n23': "OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest tests/test_qd_actuator_clipped_quality.py tests/test_rdt_steer.py -k 'n23 or native_clip or no_clip or native_invalid or actual_static or bound_context or nonzero_target' -q --basetemp=../cpu-n23-focused-reproduction-new-directory",
 'boundary': 'OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python ../cpu-gpu-boundary-readonly-v1.py',
}
fixtures=[]
for i in range(6):
 f=P/'cpu-native-final-v1'/f'test_n23_full_native_cpu_loop_{i}'/'N23'
 audit=json.loads((f/'audit-report.json').read_text())
 metric=json.loads((f/'metrics.json').read_text())
 row={'path':str(f),'case':['valid_fp32','valid_bf16','unclipped_quality_fp32','unclipped_quality_bf16','wrong_bounds_fp32','wrong_bounds_bf16'][i],
      'accepted':audit['accepted'],'errors':audit['errors'],'audit':audit.get('n23_actuator_clipped_quality_audit'),
      'insertions':sum(metric['qd_archive_insertions_by_iter']), 'replacements':sum(metric['qd_archive_replacements_by_iter']),
      'quality_overhead_seconds':metric['qd_actuator_overhead_seconds'],
      'audit_report_sha256':digest(f/'audit-report.json')}
 if i < 2:
  c=json.loads((f.parent/'compute-comparison.json').read_text())
  row['comparison']=c
  row['final_choice_changed']=c[0]['final']!=c[1]['final']
 fixtures.append(row)
boundary=json.loads((P/'cpu-gpu-boundary-readonly-v1.json').read_text())
result={'schema':'n23-cpu-implementation-report-v1','status':'CONDITIONAL_BACKEND_NOT_READY','commit':commit,
        'branch':'codex/rdt-qd-ed-n23-clipped-quality-20260930','base':'60425750c41c8a46e1102e02e2e4e4d2f97fb242',
        'worktree':str(W),'tests':{'regression_passed':205,'native_loop_and_early_gate_passed':20,'unique_total_passed':225,
        'latest_auditor_replay':json.loads((P/'cpu-auditor-recheck-v1.json').read_text()),'commands':commands},
        'files':{f:digest(W/f) for f in files},'fixtures':fixtures,'backend_boundary':boundary,
        'protocol_sha256':digest(P/'protocol-cpu-v1.md'),
        'preserved_logs':{f.name:digest(f) for f in sorted(P.glob('cpu-*.log'))},
        'additional_artifacts':{name:digest(P/name) for name in ['cpu-call-count-clarification-v1.md','cpu-gpu-boundary-readonly-v1.py','cpu-gpu-boundary-readonly-v1.json','cpu-auditor-recheck-v1.json']},
        'scope':{'gpu_used':False,'simulator_used':False,'provider_service_used':False,'owning_study_changed':False,'state_ledger_tree_changed':False,'runtime_release':False}}
(P/'cpu-implementation-report-v1.json').write_text(json.dumps(result,indent=2)+'\n')
assert result['protocol_sha256']=='e38d4c6825cca743539282818e8b49168c1910cf688720bd1901b7405ab8cf67'
rows='\n'.join(f"| {r['case']} | {'accepted' if r['accepted'] else 'rejected as intended'} | {r['audit']['score_batches_verified'] if r['audit'] else 0} | {', '.join(r['errors']) or 'none'} |" for r in fixtures)
text=f'''# N23 CPU implementation report

Status: **CONDITIONAL_BACKEND_NOT_READY**. Scientific source commit `{commit}` on `{result['branch']}`, based on `{result['base']}`. No GPU release is justified by this report. N22 and its owning source/runtime were not changed.

## Implemented scope

The N7-derived profile adds only `qd_quality_mode=actuator_clipped_provider_v1`. It clips each candidate's first eight translation commands componentwise to [-1,1] in a separate internal native 0.01 multiply/cumsum/add view, then uses only t1..t7 with weights [1,1,1,1,3,3,3]/13 and the original native norm/square and FP32 weight/storage behavior. Candidates without clipping in the scored first seven actions retain the already-computed raw tensor value byte-for-byte, including signed zero. The t8 value cannot trigger a quality change. No lift/hold, Q8 objective, descriptor, N5 eligibility, external provider/projector or deployed-action modification is included.

The opt-in contract snapshots the actual applicable controller's static bounds, shape/type, OSC_POSE fixed/delta semantics, controller method source paths/hashes, and process/adapter/wrapper/environment/controller/task/episode/reset identities. Source functions and static limits are read; no controller dynamics, object/contact/success state, stepping, resetting or rendering is requested. The passive reset-generation increment only activates after an N23 snapshot. Metadata/provider/reset drift fails closed. The Stage selected reward uses the original raw channel and the existing archive spread definition; archive/parent/terminal action-quality associations retain both raw and effective values.

The independent auditor reconstructs projection and quality without importing the N23 production helper, checks static metadata/native source links, and retains existing descriptor/selector/Stage/action audits. It shares the existing bounded provider-template recognizer solely for target0 source identity. The CPU runner profile expansion is closed to this exact N7 delta; no N23 plan admission, scheduler, budget or protected-set path was added.

## CPU verification and counters

- 205 unit/regression tests pass; 20 guided-loop/early-rejection tests pass, for **225 unique test cases**. This includes new N23 tests and old N20/N21/N22 and provider/feedback/auditor/metrics/runner regressions. The latest source-level auditor was also replayed over all six retained N23 native fixtures.
- Accepted FP32 and BF16 fixtures each independently verify **176 candidates / 11 canonical score batches**, with 160 clipped-prefix candidates and 10 changed-ranking batches. Both change the final selected candidate versus paired N7. N23 archive insertions/replacements are FP32 10/16 and BF16 11/13, showing active archive and ED search, not a final-only synthetic helper test.
- Both pairs use 176 external provider returns, 16 stub-model forwards / 256 model rows, 25 decoder calls and **347 population-projector invocations at identical existing caller sites**. The scored candidate domain is 176 in both. The unchanged archive diagnostic processes an outcome-dependent number of occupied cells: FP32 total adapter projection rows are N7 1949 versus N23 1948; BF16 1949 versus 1949. `cpu-call-count-clarification-v1.md` identifies the exact existing caller and preserves this exception to global row-count parity.
- Additional N23 quality overhead is timed in `qd_actuator_overhead_seconds` (CPU fixtures approximately {fixtures[0]['quality_overhead_seconds']:.3f}s FP32 / {fixtures[1]['quality_overhead_seconds']:.3f}s BF16). Its scope includes static snapshot/validation and internal tensor operations, not native evidence/origin-copy timing. Origin capture reuses the existing projection read, at 176 × 3 native source elements per guided chunk; canonical raw/action association clones are also retained. These and archive-dependent diagnostics belong in total episode wall cost. No GPU timing claim is made.

| Fixture | Verdict | Verified N23 batches before completion/rejection | Error |
|---|---|---:|---|
{rows}

Fixtures use CPU model/controller stubs and AST-extracted installed static controller methods plus the unchanged production adapter projector. Controller methods are never executed and no robosuite/MuJoCo instance is constructed. They establish implementation plumbing and CPU arithmetic, not current live controller metadata, GPU equivalence, real-environment behavior or success rate.

## Actual-GPU evidence boundary: release blocker

Root explicitly authorized read-only reuse of the existing N17/N7 task0/task9 and N21 task0 exposed paths. `cpu-gpu-boundary-readonly-v1.py` verified all **6139 saved bundle hashes** and checked **407 canonical batches / 6512 candidates**, without a simulator, provider or GPU call. On recorded GPU-native BF16 projections, CPU seven-point raw-quality reconstruction differs from the saved raw aggregate in **12/2992, 2/704, 8/2816** candidates respectively; maximum absolute differences are **0.00048828125, 0.0001220703125, 0.00048828125**. CPU raw projection reconstruction differs for **2725/2992, 624/704, 2369/2816** paths, with maxima **3.90625, 1.953125, 3.90625 mm**. CUDA remains uninitialized.

These are preserved numerical mismatches, not toleranced successes or N23 outcomes. The strict current CPU auditor would reject genuine GPU-native evidence; a passing CPU fixture is insufficient. The execution-device helper's raw-projection equality also needs a future check of exact operation order/layout on the assigned backend. This report does not resolve whether reduction order, layout or other native backend details explain each mismatch. No unexplained tolerance, altered projector, FP64 production substitution, or relaxed old-mode gate was added. Root requested the prototype be frozen with this blocker before a separately reviewed, metered backend contract/preflight.

The previously bounded FP64 fixed-pool ranking screen is descriptive evidence only; it changed a saved choice on a successful path. N2/N3 historical failures caution that geometry-error or ranking improvements do not establish task success. This implementation deliberately leaves raw descriptors and eligibility unchanged. Historical controller bounds were not recorded and cannot be inferred retroactively; the new snapshot is prospective.

## Reproduction and provenance

Run from `implementation` with the vla-pilot Python. Do not reuse a pytest `--basetemp` path containing preserved artifacts, since pytest clears that directory.

```bash
{commands['regression']}
{commands['native']}
```

The compact machine report `cpu-implementation-report-v1.json` gives exact source/profile/protocol hashes, commands, audit counters, fixture paths and log hashes. Root-owned CPU protocol bytes remain unchanged, SHA256 `{result['protocol_sha256']}`; byte-identical protocol/declaration/reference copies are committed under `experiments/iteration_023_actuator_clipped_quality`.

Preserved failures: `cpu-unit-first-v1.log` (AST fixture metaclass setup), `cpu-native-first-v1.log` (fixture type annotations), `cpu-native-second-v1.log` (new-mode audit admission omitted), `cpu-native-third-v1.log` (overly broad global diagnostic-row equality assertion). Subsequent passing logs and complete rejection fixtures are retained separately. All artifacts stay under this N23 variant directory. The three historical evidence paths were read-only; no owning study, state, ledger, Arbor tree, budget or active experiment source was changed.
'''
(P/'cpu-implementation-report-v1.md').write_text(text)
print(json.dumps({'commit':commit,'status':result['status'],'tests':225,'protocol_sha256':result['protocol_sha256'],'report':str(P/'cpu-implementation-report-v1.md')}))
