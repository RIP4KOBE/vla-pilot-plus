"""Assemble truthful preparation report and non-authorizing root handoff."""
import ast, datetime as dt, hashlib, json, os, shlex, subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=Path.cwd().resolve()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def read(p):return json.loads(Path(p).read_text())
def write(name,value):
    path=OUT/name;assert not path.exists();path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');return ref(path)
now=dt.datetime.now(dt.timezone.utc)
assert not os.path.lexists(ROOT.parent/'autonomy_20261004/STOP')
assert now<dt.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
result=read(OUT/'composition-result-v1.json');plan=read(result['plan']['path'])
authority=read(OUT/'authority-v1.json');adoption=read(authority['adoption']['path'])
checks=read(OUT/'checks-v1.json');preservation=read(OUT/'preservation-after-v1.json')
assert all(x['status']=='PASS' for x in checks.values())
assert len([k for k in checks if k.startswith('manifest_')])==40
assert preservation['equals_before']
for r in preservation['snapshot']['files'].values():assert sha(r['path'])==r['sha256']
assert subprocess.check_output(['git','--no-optional-locks','rev-parse','HEAD']).decode().strip()==result['source']
assert subprocess.check_output(['git','--no-optional-locks','status','--porcelain']).decode()==preservation['snapshot']['status']
for f in ('review-draft-v1.py','verify-public-release-v1.py'):ast.parse((OUT/f).read_text())
python='/home/hynx/miniconda3/envs/vla-pilot/bin/python3.12'
env=['env','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=2','MKL_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2','NUMEXPR_NUM_THREADS=2','PYTHONDONTWRITEBYTECODE=1','GIT_OPTIONAL_LOCKS=0','GIT_NO_LAZY_FETCH=1','TMPDIR='+str(OUT),'HF_HUB_OFFLINE=1','TRANSFORMERS_OFFLINE=1']
review_cmd=env+['timeout','1200',python,'-B',str(OUT/'review-draft-v1.py'),'--plan',result['plan']['path'],'--plan-sha256',result['plan']['sha256'],'--authority',adoption['adopted_authority']['path'],'--authority-sha256',adoption['adopted_authority']['sha256']]
public_cmd=env+['timeout','1200',python,'-B',str(OUT/'verify-public-release-v1.py'),'--plan','<ROOT_FINAL_PLAN_ABSOLUTE_PATH>','--plan-sha256','<INDEPENDENTLY_PINNED_FINAL_PLAN_SHA256>','--release','<ROOT_DETACHED_RELEASE_ABSOLUTE_PATH>','--release-sha256','<INDEPENDENTLY_PINNED_DETACHED_RELEASE_SHA256>']
fields=['native_build','authority','protocol','protocol_review','source','scientific_source','runtime_closure','controller_semantics','runtime','limits','phase_authorization','cohort','accounting']
steps=[
 {'order':1,'action':'Independent final production review of this exact owning-source bundle and inherited readiness scope. Turn1228 adopted the exact PR-01/04 fixes and six focused tests; do not repeat those repair tests. Check all remaining production/lifecycle/native obligations and this prospective binding.','read_only_validation_argv':review_cmd,'cwd':str(ROOT),'command_executed_here':False,'review_targets':[result['plan'],ref(OUT/'source-delta-v1.json'),ref(OUT/'unchanged-inputs-v1.json'),ref(OUT/'all40-composition-v1.json'),ref(OUT/'adopted-accounting-bindings-v1.json'),ref(OUT/'comparison-resolution-v1.json')]},
 {'order':2,'action':'Root alone may construct a NEW immutable final plan after accepting the exact candidate. Preserve all metadata, source/runtime/closure/controller/native/protocol/accounting/episodes/manifests. This executor does not create that plan or grant authority.','changes_required_by_production_validator':{'schema':'n36-released-plan-v1','frozen':True,'release_enabled':True,'authority':adoption['adopted_authority'],'phase_authorization':{'dev':True,'validation':False,'formal':False},'remove_keys':['root_review','execution_release']},'constraints':['Do not mutate the candidate or its artifacts.','Do not change artifact_root: manifests bind it.','Do not change protocol/accounting/authority refs or scientific parameters.','A changed runtime/source/input requires new exact bindings and review.','Keep attempt_identity=episode_key and all40 expected manifests.','Root hashes the final immutable file and independently pins its {path,sha256}.']},
 {'order':3,'action':'Independent reviewer/root must produce a real exact final-plan review, followed by a detached release, only after the review warrants approval. No such artifacts were emitted here.','review_schema':'n36-root-production-review-v1','review_values':{'approved':True,'decision':'APPROVED','plan':'caller-pinned final plan {path,sha256}','copy_exact_final_plan_fields':fields},'release_schema':'n36-execution-release-v1','release_values':{'approved':True,'plan':'same final plan ref','root_review':'independently adopted exact review {path,sha256}','copy_exact_final_plan_fields':fields},'reference_shape':'Exactly path and sha256; absolute regular non-symlink JSON files. Do not include bytes. No review/release back-reference in final plan.','warning':'These are validator schema requirements, not approval or a suggested fabricated review.'},
 {'order':4,'action':'Run full public verify_prospective_release against caller-supplied final plan/release hashes from the owning checkout. This read-only validator verifies every release dependency and all40 composition; no public release PASS can be claimed until it succeeds.','argv':public_cmd,'cwd':str(ROOT),'command_executed_here':False,'placeholders':'Root supplies the four final path/hash values after independently approved immutable final plan -> review -> detached release exist.'},
 {'order':5,'action':'Before any root-authorized Dev dispatch, the existing production runner must recheck STOP/deadline/full1840s, unchanged adopted ledger prefixes and state, settled handles/reservations, protected reserves, global/cohort/weekly budget, current official-login provider status, reusable accounted probe and current GPU7 UUID/idle admission under the normal owner locks. Do not infer current idleness/login from this CPU report.','production_entrypoint':'source_execution.command(bound_python, owner, scripts.qd_ed_n36_runner, --plan, FINAL_PATH, --plan-sha256, FINAL_HASH, --release, RELEASE_PATH, --release-sha256, RELEASE_HASH)','required_source_envelope':['-I','-S','-B','-X','pycache_prefix=/dev/null','scripts/qd_ed_n36_bootstrap.py'],'worker_limit':1,'automatic_recoveries':0,'execution_command_issued':False},
 {'order':6,'action':'Same-worker source/native/arithmetic/controller/live-response and all-arm absence audits remain mandatory. No physical gain, collision/contact/grasp, or success inferred from preparation. Full episode feasibility within 1800s plus bounded40 cleanup remains unproved. Original validation/formal/ablation objective remains unmet; no protected-phase promotion.'}
]
handoff=write('root-handoff-v1.json',{'schema':'n36r1-owner-runtime-rebind-handoff-v1','plan':result['plan'],'root_authority':adoption['adopted_authority'],'ordered_steps':steps,'no_approval_or_release_created':True})
executed=[]
for script,timeout,code in [('compose-owner-v1.py','1200',1),('finish-composition-v2.py','300',0)]:
 executed.append({'cwd':str(ROOT),'argv':env+['timeout',timeout,python,'-B',str(OUT/script)],'exit_code':code,'script':ref(OUT/script)})
commands=write('commands-v1.json',{'executed_composition_commands':executed,'independent_review':{'argv':review_cmd,'executed':False},'public_release_validation':{'argv':public_cmd,'executed':False},'no_gpu_provider_or_worker_commands_executed':True})
artifacts=[]
for name in ['authority-verification-v1.json','preservation-before-v1.json','preservation-after-v1.json','source-record-v1.json','source-delta-v1.json','unchanged-inputs-v1.json','runtime.owner-ready-v1.json','runtime-closure.owner-v1.json','controller-semantics.owner-v1.json','controller-set_goal.owner-v1.json','controller-scale_action.owner-v1.json','controller-wrapper_and_gripper.owner-v1.json','native-binding-provenance-v1.json','all40-composition-v1.json','adopted-accounting-bindings-v1.json','checks-v1.json','composition-result-v1.json','composition-failure-v1.json','comparison-resolution-v1.json','root-handoff-v1.json','commands-v1.json','compose-owner-v1.py','finish-composition-v2.py','review-draft-v1.py','verify-public-release-v1.py','finalize-report-v1.py','draft/plan.draft.json','draft/plan.metadata-complete.draft.json']:
 artifacts.append(ref(OUT/name))
artifacts += list(plan['expected_manifests'].values())
started=read(OUT/'authority-verification-v1.json')['started_at']
report={'schema':'n36r1-owner-runtime-rebind-report-v1','node_id':'15.6','at':now.isoformat(),'status':result['status'],'worktree':str(ROOT),'source':result['source'],'authority':ref(OUT/'authority-v1.json'),'standing_authority':authority['authority'],'adoption':authority['adoption'],'root_source_review':adoption['root_source_review'],'candidate':result['plan'],**{k:result[k] for k in ('runtime','runtime_closure','controller_semantics','native_build')},'release_enabled':False,'frozen':False,'root_approval_granted':False,'native_readiness':False,'scientific_success':False,'target_met':False,'score':None,'runtime_ready':True,'runtime_ready_scope':{'kind':'INHERITED_TURN1223_READINESS_STATICALLY_REBOUND','readiness_review':ref(OUT.parent.parent/'001223/runtime-readiness-review-v1.json'),'provider_ready_preserved':True,'cuda_egl_verified_preserved':True,'metadata_mapping_verified_preserved':True,'provider_contract_and_cli_bytes_unchanged':True,'provider_login_rechecked':False,'probe_reusable_verification':'PASS_UNMODIFIED_PASSIVE_VALIDATOR','current_device_idle_checked':False,'new_live_device_evidence':False,'new_provider_inference_calls':0,'runtime_module_count':len(read(result['runtime_closure']['path'])['modules']),'native_library_count':len(read(result['native_build']['path'])['libraries']),'limitation':'Preserves reviewed historical readiness only; current provider/device admission and same-worker attestations remain mandatory.'},'validation':{'checks':checks,'actual_manifests':40,'expected_manifests':40,'runtime_files_verified':3291,'checkpoint_encoder_dinov2_task_seed_validation':'PASS_STRICT_REQUIRE_FROZEN_TRUE','controller_semantics':'PASS_UNMODIFIED','source_closure':'PASS_OWNING_CA4E6A','loaded_source_owner_binding':'PASS','native_inventory_bytes':'PASS_UNMODIFIED','public_detached_release':'NOT_RUN_NO_INDEPENDENT_FINAL_REVIEW_OR_RELEASE','root_repair_tests_repeated':False},'science_preservation':{'task_seed_arm_order_unchanged':True,'config_differences_only':['exact source commit binding','exact prospective artifact output-root relocation'],'all_other_source_bytes_unchanged':True,'scientific_thresholds_unchanged':True,'validation_formal_ablation_goal_met':False},'accounting':{'authority':adoption['adopted_authority'],'accounting':plan['accounting'],'amendment':adoption['adopted_amendment'],'protocol':plan['protocol'],'protocol_review':plan['protocol_review'],'owning_state_exact_reference_equalities':'PASS','root_totals_recomputed':False,'retained_snapshot':adoption['retained_snapshot'],'retained_margin_gpu_hours':adoption['retained_margin_gpu_hours'],'conservative_charge_gpu_hours':adoption['conservative_charge_gpu_hours'],'original_aborted_charge_seconds':86.40354533703066,'draft_authority_null_reason':'Strict c.validate_draft requires null; exact adopted ref is bound by adopted-accounting-bindings-v1.json and handoff for root finalization.'},'preservation':{'source_unchanged':True,'source_edits':0,'materialized_inputs':0,'owning_state_ledgers_tree_driver_unchanged':True,'before':ref(OUT/'preservation-before-v1.json'),'after':ref(OUT/'preservation-after-v1.json'),'initial_owner_status_was_dirty':True,'status_unchanged':True,'prior_records_overwritten':False,'outputs_only_under':str(OUT)},'auxiliary_failure':{'evidence':ref(OUT/'composition-failure-v1.json'),'resolution':ref(OUT/'comparison-resolution-v1.json'),'source_repair_required':False,'production_validator_weakened':False},'commands':commands,'root_handoff':handoff,'remaining_root_actions':steps,'bounds':{'wall_cap_seconds':1800,'composition_started_at':started,'report_at':now.isoformat(),'elapsed_since_composition_start_seconds':(now-dt.datetime.fromisoformat(started)).total_seconds(),'CPU_threads':2,'CUDA_VISIBLE_DEVICES':'','STOP':str(ROOT.parent/'autonomy_20261004/STOP'),'STOP_present':False,'deadline':'2026-10-11T11:13:13Z'},'scope':{'GPU_probes':0,'worker_controller_launches':0,'agents_launched':0,'provider_inference_calls':0,'credential_reads':0,'protected_outcomes_read':False,'prohibited_design_read':False,'dependency_installs':0,'network_downloads':0,'release_artifacts_created':0,'frozen_authorizations_created':0},'artifacts':artifacts}
report_ref=write('report-v1.json',report)
md=f'''CPU preparation complete: all40 strict composition and verification PASS, bound to the owning study_worktree at `{result['source']}`.

Candidate: `{result['plan']['path']}`  
SHA-256: `{result['plan']['sha256']}`

Source closure, loaded-source ownership, all 3,291 runtime files, frozen checkpoint/encoder/DINO/task/seed inputs, 6,758 runtime modules, controller semantics, native library inventory, exact protocol/accounting authority references, and all40 manifests passed unmodified production validators. Task/seed/arm/order and scientific configuration are preserved; only adopted source bindings and prospective output paths differ. PR-01/04's six adopted tests were not rerun.

Turn1223 provider/CUDA-EGL readiness is preserved narrowly. The existing accounted probe's source/evidence/mapping/frame hashes and frozen provider executable/contract were reverified passively. No current login, current GPU idleness, new live-device evidence, native worker attestation, or scientific success is claimed.

The bundle is disabled and unfrozen. No review approval, detached release, GPU probe, inference, worker/controller, source edit, install, download, or state/ledger/tree mutation was performed. Initial dirty owner state and all recorded ledger bytes remain unchanged. Strict draft validation requires authority=null; `{OUT/'adopted-accounting-bindings-v1.json'}` preserves the exact adopted reference for root finalization. Root accounting remains 503 dispatched, 22 aborted, 463 valid, 18 invalid, 0 running; GPU-hours consumed 75.26779409697457, conservative charge 75.50136578725419. No totals were recomputed or changed.

One auxiliary comparison initially rejected the expected mechanism output-directory relocation. Its failure record is retained; the continuation accepts only exact output-root/source-binding changes and all40 passed. No source repair or audit relaxation was needed.

Remaining root work, in order:

1. Independently review this exact bundle, inherited readiness scope and adopted repair. The following read-only CPU command validates the draft but grants no approval:

```bash
cd {shlex.quote(str(ROOT))}
{shlex.join(review_cmd)}
```

2. Root alone creates a NEW immutable final plan with schema=n36-released-plan-v1, frozen/release_enabled=true, exact adopted authority, and Dev-only phase authorization; remove root_review/execution_release back-reference keys. Preserve metadata, all40 manifests and their bound artifact_root. Exact requirements and refs are in `root-handoff-v1.json`; no such authorization was created here.
3. Obtain a real independent final-plan production review, then a detached release. Both must exactly match the schema/equalities documented in `root-handoff-v1.json`. Reference dictionaries contain exactly path and sha256. Independently pin final plan/release hashes.
4. Substitute those four final path/hash values and run the full public release validator:

```bash
{shlex.join(public_cmd)}
```

This command has NOT run; no public detached-release PASS is claimed. It creates no release and launches no worker.

5. Any subsequent root-authorized Dev execution must use the source-only bootstrap and the existing production runner's locked STOP/deadline/full1840s, accounting/reserves, settled-resource, current provider-login and GPU7 UUID/idle admission checks. One worker, zero automatic recoveries. No runnable dispatch command is issued here.
6. Same-worker native/arithmetic/controller/live-response and all-arm absence audits remain required. 1800-second full-episode feasibility remains unproved. Validation/formal/ablation objectives remain unmet; score is null.

Machine report: `{report_ref['path']}`  
SHA-256: `{report_ref['sha256']}`  
Detailed artifact hashes, actual checks, commands and preservation records are included in report-v1.json.
'''
assert not (OUT/'report-v1.md').exists();(OUT/'report-v1.md').write_text(md)
write('report-checksums-v1.json',{'report_json':report_ref,'report_markdown':ref(OUT/'report-v1.md'),'final_source_and_state_preservation_verified':True})
print(json.dumps({'report':report_ref,'markdown':ref(OUT/'report-v1.md'),'checks':len(checks),'all40':40,'release_enabled':False}))
