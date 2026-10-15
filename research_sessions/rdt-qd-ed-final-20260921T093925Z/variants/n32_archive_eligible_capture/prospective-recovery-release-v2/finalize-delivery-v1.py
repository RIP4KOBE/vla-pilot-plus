"""Seal CPU executor delivery; excludes live executor transport logs."""
import datetime as dt,hashlib,json,subprocess,sys
from pathlib import Path
root=Path.cwd().resolve(); out=root.parent/'prospective-recovery-release-v2'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def put(name,obj):
 p=out/name
 with p.open('x') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')
 return ref(p)
v=json.loads((out/'validation-v1.json').read_text()); plan=json.loads(Path(v['plan']['path']).read_text()); runtime=json.loads(Path(plan['runtime']['path']).read_text())
prefix="env CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 taskset -c 0,1 python "
commands=[]
for script,log in [('prepare-candidates-v1.py','preparation-v1.log'),('verify-entrypoint-v1.py','entrypoint-verification-v1.log')]:
 commands.append({'command':prefix+'../prospective-recovery-release-v2/'+script+' > ../prospective-recovery-release-v2/'+log+' 2>&1',
 'cwd':str(root),'exit_code':0,'script':ref(out/script),'log':ref(out/log)})
commands.append({'command':prefix+'../prospective-recovery-release-v2/finalize-delivery-v1.py','cwd':str(root),'script':ref(out/'finalize-delivery-v1.py'),'purpose':'Seal artifact hashes and verify delivery references; success signaled by final-check-v1.json'})
command_ref=put('validation-commands-v1.json',{'schema':'n32r2-validation-commands-v1','commands':commands,
 'preparatory_reads':['arbor-agent-executor/SKILL.md','applicable ancestor AGENTS.md lookup (none found); user-supplied AGENTS instructions applied','current N32 prepare/contract/release/bridge/worker/runner APIs','root-recovery-release-v1 plan and budget authority','historical release-preparation-v1/verify-draft-v1.py and qd_ed_n31_prepare.py as templates only','root identity and worker-entrypoint review documents'],
 'broad_tests_run':False,'recursive_provenance_rebuild':False})
now=dt.datetime.now(dt.timezone.utc); upper=(now-dt.datetime.fromisoformat(json.loads((out/'authority-v1.json').read_text())['at'])).total_seconds()
assert upper<1200
report=f'''# Arbor 15.2 — N32R2 prospective release candidates

Status: **CPU PREPARATION COMPLETE; PRODUCTION BLOCKED, ROOT REVIEW REQUIRED**.
Source and code reference: `{v['source_commit']}`. Score: null (no scientific evaluation). No source edits, GPU dispatch, coordinator/agent launch, owning state/checkpoint/ledger changes, provider/network access, or prior outcome reuse.

## Frozen artifacts

- `payload/draft-v1/plan.draft.json`: official `qd_ed_n32_prepare.prepare` output, disabled draft with all 30 fresh manifests.
- `protocol.candidate-v1.json`: exact prospective N32R2 protocol, all-valid 30-cell promotion gate, at least five N32 successes, matched controls, complete-valid-triple futility.
- `payload/runtime.n32r2.candidate-v1.json` and `runtime-provenance-v1.json`: fresh reference binding this implementation checkout; existing task/cache/provider fingerprints retained. GPU/EGL/provider readiness fields are inherited historical claims, **not fresh checks**.
- `source-closure-v1.json`: exact 551-file closure, Git object and local-byte verification, including pinned RDT worker dependency and current repaired worker entrypoint.
- `budget-authority.candidate-v1.json`, `plan.frozen.CANDIDATE-v1.json`, `root-production-review.CANDIDATE-v1.json`, `execution-release.CANDIDATE-v1.json`: detached prospective DAG. Authority/review/release approval is false; plan release and all phase authorizations are false. The root-review candidate says PENDING_INDEPENDENT_ROOT_REVIEW. Frozen means hash-bound candidate bytes only.
- `worker-entrypoints.CANDIDATE-v1.json` and 30 payload contexts: exact Python `-m scripts.qd_ed_n32_worker` command, cwd, context path and digest for each primary. None is production-authorized.
- `validation-v1.json`, `runtime-inventory-check-v1.json`, `entrypoint-negative-v1.json`, `validation-commands-v1.json`: API checks, blockers, commands and hashes. `artifact-index-v1.json` lists every sealed executor-produced artifact.

Payload physical storage: `{(out/'payload').resolve()}`. Logical link: `payload`. No weights/checkpoints were copied; prospective attempt output directories remain absent.

## Preserved authority and science

Cohort `{plan['episodes'][0]['iteration']}` uses 30 fresh `n32r2_dev_*_20261004` identities: ten C0 baseline and twenty Q0/N32 development cells, at most 18,000 GPU seconds (5 GPUh), zero automatic recoveries. Task identities, seeds, 720-step schedule, 20 Hz control, horizon eight, source/run/task bindings and same-process generic/native audits remain fixed. Episode bound is 1,800 seconds including audits plus 40 seconds cleanup. Unknown HTTP telemetry stays Unknown; missing cost/exclusivity telemetry cannot become zero or a valid result.

The root accounting amendment retains **423 attempts / 56.92968407644514 GPUh**, including all old failures and health costs. Maximum after the fresh cohort is 453 attempts / 61.92968407644514 GPUh; effective weekly ceiling is 221.08404692669836 GPUh. Remaining protected hours are 24.240824002430816 validation and 12 formal; remaining protected attempts are 120 validation and 40 formal. Global caps remain 1,800 attempts / 224 GPUh with unchanged bucket ceilings. No reserve borrowing or protected-phase authorization.

Weekly deadline remains `2026-10-10T17:42:00Z`; coordinator end remains `2026-10-11T11:13:13Z`. STOP remains `{plan['stop_path']}`. Full-attempt time, settled accounting, exact GPU7 UUID, exclusive/private allocation and live admission must still pass immediately before production dispatch.

## Checks and evidence

- Clean HEAD at required commit; exact 551-file source closure and current worker origin/spec/hash attestation passed.
- Official draft contract passed. Released-plan structural validation passed on an in-memory enabled shape only; no approved review was generated or passed to execution.
- All 30 external manifests recompose byte-equivalently; fresh task/source/run binding and output paths verified. No old result payloads were read or reused.
- All 3,291 runtime inventory entries were preserved. **2,595 verified; 696 failed because files are missing**: 155 RDT and 541 LeRobot. Full failure paths and expected hashes are in `runtime-inventory-check-v1.json`.
- Task/input/seed/cache validators passed with `require_frozen=False`. Full checkpoint/encoder/DINO weight hashing was deliberately not rerun; root must run the unmodified production validator with its default frozen checks before release.
- Hash-only historical ledger-prefix verification passed against the accounting amendment; no historical or protected outcome analysis was performed.
- `validate_release` rejects the disabled plan. Actual `python -m scripts.qd_ed_n32_worker` with the frozen candidate context and parent gate byte `G` rejected with `released plan contract`, exit 1, before Main/model/provider/GPU execution. This is negative CPU admission evidence, not a successful episode or native outcome audit.
- No broad test suite rerun. Preparation API work took {v['elapsed_seconds']:.3f} seconds. Delivery preparation elapsed upper bound at report creation: {upper:.1f} seconds, within 1,200 seconds.

Exact validation commands, scripts, logs and SHA-256 values are in `validation-commands-v1.json`; per-artifact SHA-256 values are in `artifact-index-v1.json` and `delivery-v1.json`. Prior provenance is referenced directly, not recursively rebuilt.

## Remaining root operation and blockers

1. Independently review the actual source, scientific protocol, accounting amendment, runtime provenance and all candidate digests. No current document grants production approval.
2. Settle the execution checkout. This implementation checkout lacks 696 frozen runtime dependencies; its detached artifacts are reviewable but not runnable. Do not silently omit entries or substitute an adjacent checkout. Root may separately authorize dependency provisioning, or regenerate checkout-specific runtime/manifests/plan for the owning checkout at the same exact source. Any source repair requires a separate implementation report and authorization; none was made here.
3. For the settled checkout, root must independently verify all frozen runtime/model bytes, source closure and worker entrypoint, current accounting prefixes and settled reservations. Root alone can finalize the budget authority, enabled Dev-only plan, new digest-bound root review (`decision: APPROVED`) and detached release (`approved: true`) in dependency order. Recompute affected references and manifests whenever runtime/worktree/source changes; do not approve stale candidate hashes.
4. Root must call unmodified `qd_ed_n32_release.validate_release` on the final refs and independently adopt the exact authority/plan/release into owning state under the normal locks, preserving all historical charges. Owning ledgers/state are not staged or edited by this delivery.
5. Only after those operations may root perform current STOP/deadline/private GPU7/probe/exclusivity/accounting admission through the existing production adapter. Validation/formal remain unauthorized. Existing production scientific/native/telemetry gates must not be weakened.

## Executor result

Idea: prepare fresh N32R2 release artifacts after accepted identity and worker repairs.
Result: 30 prospective manifests, runtime and source references, protocol/accounting candidates, detached disabled release DAG and exact worker contexts prepared; checks passed within their stated scopes, with runtime completeness and root approval still blocking production.
Insight: source closure can verify while the execution dependency inventory remains incomplete; both gates are necessary. Earlier outcomes remain retained and unreused.
'''
(out/'report-v1.md').write_text(report)
# Seal only files generated by this executor; never include changing launcher logs.
items=['prepare-candidates-v1.py','verify-entrypoint-v1.py','finalize-delivery-v1.py','preparation-v1.log','entrypoint-verification-v1.log','entrypoint-negative-v1.log','entrypoint-negative-v1.json','runtime-provenance-v1.json','source-closure-v1.json','protocol.candidate-v1.json','budget-authority.candidate-v1.json','plan.frozen.CANDIDATE-v1.json','root-production-review.CANDIDATE-v1.json','execution-release.CANDIDATE-v1.json','worker-entrypoints.CANDIDATE-v1.json','runtime-inventory-check-v1.json','validation-v1.json','validation-commands-v1.json','report-v1.md']
items += [str(p.relative_to(out)) for p in (out/'payload').rglob('*') if p.is_file()]
records=[{'logical_path':name,**ref(out/name),'size_bytes':(out/name).stat().st_size} for name in sorted(items)]
index=put('artifact-index-v1.json',{'schema':'n32r2-frozen-artifact-index-v1','files':records,'payload_logical_link':str(out/'payload'),'payload_physical':str((out/'payload').resolve())})
delivery={'schema':'n32r2-release-candidate-delivery-v1','node_id':'15.2','status':'CANDIDATES_PREPARED_PRODUCTION_BLOCKED','at':now.isoformat(),
 'code_ref':v['source_commit'],'score':None,'report':ref(out/'report-v1.md'),'artifact_index':index,'validation':ref(out/'validation-v1.json'),
 'entrypoint_validation':ref(out/'entrypoint-negative-v1.json'),'commands':command_ref,
 'draft':v['draft'],'plan_candidate':v['plan'],'release_candidate':v['release'],'runtime_candidate':plan['runtime'],
 'protocol_candidate':v['protocol'],'authority_candidate':v['authority'],'root_review_candidate':ref(out/'root-production-review.CANDIDATE-v1.json'),
 'accounting_amendment':json.loads((out/'authority-v1.json').read_text())['accounting_amendment'],
 'retained_history':{'attempts':423,'gpu_hours':56.92968407644514},'fresh_cohort':{'primaries':30,'gpu_hours':5,'automatic_recoveries':0},
 'blockers':v['blockers'],'missing_dependencies':{'rdt':155,'lerobot':541},'source_changes_required_by_this_delivery':False,
 'source_change_policy':'Any repair/provisioning needs separate root disposition; no source edits made.',
 'root_production_approval':False,'gpu_dispatched':False,'owning_state_checkpoint_ledger_changed':False,'protected_result_payloads_accessed':False,
 'prohibited_document_accessed':False,'credentials_accessed':False,'network_provider_calls':False,'other_agents_launched':False,
 'broad_tests_run':False,'http_counters':'Unknown','elapsed_wall_upper_bound_seconds':upper,
 'result':'Fresh N32R2 candidate artifacts prepared and bounded CPU checks recorded; runtime completeness and independent root production review remain blockers.',
 'insight':'Exact source verification and dependency runtime completeness are separate required release gates.'}
put('delivery-v1.json',delivery)
for record in records:assert sha(record['path'])==record['sha256']
assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
put('final-check-v1.json',{'status':'PASS','sealed_artifacts':len(records),'all_hashes_verified':True,'source_clean':True,
 'delivery':ref(out/'delivery-v1.json'),'artifact_index':index,'gpu_dispatched':False,'release_enabled':False})
print(json.dumps({'status':delivery['status'],'sealed_artifacts':len(records),'report':ref(out/'report-v1.md'),'delivery':ref(out/'delivery-v1.json'),'elapsed_wall_upper_bound_seconds':upper},indent=2))
