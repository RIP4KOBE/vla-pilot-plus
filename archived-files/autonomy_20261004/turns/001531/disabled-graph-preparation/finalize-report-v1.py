"""Finalize and verify only the stopped preparation's report and artifact hashes."""
import datetime as dt, hashlib, json, os
from pathlib import Path
OUT=Path(__file__).resolve().parent
p=OUT/'report-v1.json'; r=json.loads(p.read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p): return {'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)}
for record in r['outputs'].values():
 q=Path(record['path']); assert q.resolve().is_relative_to(OUT) and q.stat().st_size==record['bytes'] and sha(q)==record['sha256']
partial=json.loads((OUT/'source-inventory.partial-v1.json').read_text()); blocker=json.loads((OUT/'blocker-v1.json').read_text())
assert partial['required_count']==partial['available_verified_count']+partial['missing_count']+partial['policy_excluded_count']==1110
assert partial['available_verified_count']==572 and partial['missing_count']==537
assert len(blocker['runtime_rebind_missing_paths'])==697
assert all(not (OUT/n).exists() for n in ('source.complete-v1.json','scientific-equivalence-v1.json','runtime.isolated.disabled-v1.json','runtime-closure.isolated.disabled-v1.json'))
r['checks']['report_and_partial_artifact_integrity']={'status':'PASS','required_paths':1110,'verified_available':572,'missing':537,'policy_excluded':1,'all_output_hashes_match':True,'no_full_graph_artifacts_emitted':True}
r['policy_scope_blocker']={'path':'scripts/qd_ed_poe_launch.py','required_by':'scripts/qd_ed_n36_bridge.py:source_paths scripts/*.py inventory','status':'EXCLUDED_FROM_DIAGNOSTIC_SUBSET_ONLY','resolution':'Clarify authorization for hashing this required tracked source helper before attempting a complete source inventory. Do not weaken the production source_paths contract or label the subset complete.','prior_attempt_disclosure':'Direct filesystem read was blocked by audit hook. Before that block, the source helper had batch-read committed Git blobs including the helper; content was not printed. This boundary limitation is recorded in errors.'}
r['next_bounded_step']='Separately authorize local materialization of exact pinned RDT b896f4dcac8ed1c3fae4a056200db267607f131f and LeRobot 715debf6c1723a28f1a57d4274a8c4ec35b6a417 under the fixed candidate SOURCE route, preserving HEAD dcd890474b733743414d2a7711069bb0d2b0337e and existing bytes. Clarify whether the required tracked scripts/qd_ed_poe_launch.py may be hashed for source inventory under the no-Poe-files rule. Then run full G2 without shrinking the inventory before G3/G4. No repair, source adoption, readiness, or dispatch is authorized by this report.'
r['unresolved_gaps'][0]='G2 full source/scientific inventory blocked by 537 missing pinned dependency files and one policy-excluded required tracked helper; BASE ancestry and exact 10-path operational delta pass.'
r['guidance']={'user_AGENTS_policy_applied':True,'filesystem_AGENTS_on_candidate_and_output_ancestor_routes_found':[],'skills_used':['/home/hynx/.codex/skills/arbor-research-agent/SKILL.md','/home/hynx/.codex/skills/arbor-agent-executor/SKILL.md'],'user_executor_constraints_override_default_orchestration':True,'subagents_used':False}
root=Path(r['candidate_worktree'])
inspected=['scripts/qd_ed_n36_build.py','scripts/qd_ed_n36_release.py','scripts/qd_ed_n36_bridge.py','scripts/qd_ed_n34_source.py','scripts/qd_ed_n36_engineering.py','scripts/qd_ed_n23_worker.py','scripts/qd_ed_n36_prepare.py','scripts/qd_ed_n34_bridge.py','scripts/qd_ed_final_runner.py','scripts/qd_ed_audit_backend.py','scripts/audit_decision_evidence.py','scripts/qd_ed_n36_stop.py']
inputs={x['path']:x for x in r['inputs']}
for q in [*(root/name for name in inspected),Path(__file__),*(Path(name) for name in r['guidance']['skills_used']),Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/guidance/task_0/metadata.json')]: inputs[str(q)]=ref(q)
r['inputs']=list(inputs.values())
r['commands'].append('python -B '+str(Path(__file__)))
r['elapsed_seconds_diagnostic_phase']=r.pop('elapsed_seconds')
r['timing']={'first_partial_report_written_before_1100_seconds':True,'finalized_before_1200_seconds':True,'observed_task_elapsed_seconds_before_finalization':283.574,'driver_deadline':'2026-10-11T11:13:13Z','dispatch_prohibited':True,'stop_paths_presence':{s:os.path.lexists(s) for s in ['/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/STOP','/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/STOP']}}
r['at']=dt.datetime.now(dt.timezone.utc).isoformat()
p.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n')
summary={'schema':'n36-disabled-preparation-artifact-check-v1','status':'PASS_REPORT_INTEGRITY_ONLY','report':ref(p),'outputs':r['outputs'],'scripts':[ref(OUT/n) for n in ('prepare-disabled-v1.py','diagnose-blocker-v1.py','finalize-report-v1.py')],'goal_complete':False,'dispatch_enabled':False}
(OUT/'artifact-check-v1.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({'status':r['status'],'report':summary['report'],'artifact_integrity':'PASS'},indent=2))
