from pathlib import Path
import json,hashlib,datetime,os,sys,importlib.util,yaml,subprocess
W=Path.cwd();P=W.parent/'variants/n31_capture_dwell_proposal';T=W.parent/'autonomy_20261004/turns/000059';run='rdt-qd-ed-final-20260921T093925Z'
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r
spec=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
def ref(p):
 p=Path(p);return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def verify(x):
 assert ref(x['path'])['sha256']==x['sha256'],x['path']
 return json.loads(Path(x['path']).read_text())
now=datetime.datetime.now(datetime.timezone.utc).isoformat();h=json.loads((W.parent/'autonomy_20261004/handoff-v2.json').read_text())
for k in ['authorization','completion_contract','current_launch','current_plan','current_release']:verify(h[k])
prior=json.loads((T.parent/'000058/operational-summary.json').read_text());prefix={}
for k in ['attempt_ledger_prefix','health_ledger_prefix']:
 old=prior[k];data=Path(old['path']).read_bytes();assert hashlib.sha256(data[:old['bytes']]).hexdigest()==old['sha256'];prefix[k]={**ref(old['path']),'bytes':len(data),'lines':len(data.splitlines())}
result=json.loads((P/'result-v1.json').read_text());end=json.loads((P/'execution/root-launch-result-v1.json').read_text());assert end['exit_code']==0 and end['controller_reaped']
assert all(not Path('/proc/'+str(pid)).exists() for pid in [203563,203562,840181])
assert result['decision']=='REJECT_NUMERIC_DEV_FUTILITY' and result['dispatched']==18
for k in ['plan','terminal_status','ledger_snapshot','reader','source_bridge']:
 assert ref(result[k]['path'])['sha256']==result[k]['sha256']
rows=[json.loads(x) for x in (W/'data/attempt-ledger.jsonl').read_text().splitlines()];cohort=[x for x in rows if x.get('identity',{}).get('iteration')==result['cohort_id']];dispatch=[x for x in cohort if x['event']=='dispatched'];valid=[x for x in cohort if x['event']=='valid'];assert len(dispatch)==len(valid)==18
assert len({x['attempt_id'] for x in valid})==18
native=[]
for cell in result['accepted_cells']:
 audit=verify(cell['audit']);receipt=verify(cell['worker_receipt']);verify(cell['worker_context']);verify(cell['attempt_result'])
 assert audit['accepted'] and audit['evidence_complete'] and not audit['errors'];assert receipt['accepted'] and receipt['process_unchanged'] and receipt['main_exit_code']==0
 terminal=next(x for x in valid if x['attempt_id']==cell['attempt_id']);assert terminal['success'] is False and terminal['outcome_valid']
 native.append({'task_id':cell['task_id'],'profile':cell['profile'],'counts':receipt.get('n31_native_counts',{})})
assert {(x['task_id'],x['profile']) for x in result['accepted_cells']}=={(t,p) for t in range(6) for p in ['C0','Q0','N31']}
hours=sum(x['gpu_process_wall_seconds'] for x in valid)/3600
next_step='Bounded CPU-only N31 Dev mechanism diagnosis: distinguish proposal opportunity, changed content, ordinary selection, actual close/dwell execution and target motion for all six candidate cells with matched Q0 context; then draft a falsifiable prospective next iteration through Arbor ideation. No GPU dispatch until source/protocol/audit review and admission.'
review={'schema':'n31-root-terminal-review-v1','at':now,'source_commit':result['source_commit'],'result':ref(P/'result-v1.json'),'launch_result':ref(P/'execution/root-launch-result-v1.json'),'protocol':ref(P/'prospective-dev-science-protocol-v1.md'),'decision':result['decision'],'counts':result['counts'],'complete_matched_triples':6,'unknown_tasks':[6,7,8,9],'futility_arithmetic':'0 successes + 4 unrun tasks = 4 < frozen minimum 5','native_receipts_verified':18,'native_counts':result['native'],'per_cell_native_counts':native,'accounting':{'retained_pre_N31_dispatches':403,'new_dispatches':18,'total_dispatches':421,'retained_pre_N31_gpu_hours':53.80872756284531,'N31_gpu_hours':hours,'total_gpu_hours':53.80872756284531+hours},'ledger_prefixes':prefix,'validation_authorized':False,'formal_authorized':False,'target_met':False,'next_bounded_step':next_step,'interpretation':'Numerical Dev rejection, not infrastructure failure. Proposal changes and selections occurred but no task success; physical grasp/capture mechanism remains unresolved. Do not rerun valid failures or count unrun cells as failures.'}
reviewpath=P/'root-terminal-review-v1.json';assert not reviewpath.exists();r.durable_json(reviewpath,review)
cpfile=W/'.arbor/sessions'/run/'.coordinator/checkpoint.json'
with r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml');cp=r.read_json(cpfile);tree=a.load_tree(W,run)
 assert state['active_iteration']['candidate_id']=='N31' and state['budget']['running']==0
 assert state['budget']['dispatched']==421 and abs(state['budget']['gpu_hours_consumed']-review['accounting']['total_gpu_hours'])<1e-8
 backup=T/'pre-closure';backup.mkdir(exist_ok=False)
 for p in [W/'research-state.yaml',cpfile,W/'.arbor/sessions'/run/'.coordinator/idea_tree.json']:(backup/p.name).write_bytes(p.read_bytes())
 state['study']['status']='N31_DEV_REJECTED_NUMERIC_TARGET_NOT_MET';state['active_iteration'].update(status='REJECT_NUMERIC_DEV_FUTILITY',execution_authorized=False,terminal_review=ref(reviewpath));state['n31_terminal_result']=ref(P/'result-v1.json');state['closed_n31_controller']=state['active_controller'];state.update(active_controller=None,current_owned_workers=[],next_action=next_step,updated_at=now)
 cp.update(status=state['study']['status'],phase='OBSERVE_N31_TERMINAL',active_controller=None,current_owned_workers=[],automatic_gpu_dispatch_authorized=False,automatic_dispatch_scope=None,n31_terminal_review=ref(reviewpath),next_action=next_step,updated_at=now,target_met=False)
 tree['meta'].update(study_status=state['study']['status'],target_achieved=False)
 leaf=a.node(tree,'15.1');leaf.update(status='done',phase='REJECT_NUMERIC_DEV_FUTILITY',active_controller=None,terminal_review=ref(reviewpath),target_achieved=False,result='N31/C0/Q0 each 0/6; complete-triple futility 0+4<5. Remaining tasks Unknown. No validation promotion.')
 tmp=W/'research-state.yaml.n31-close-v1';tmp.write_text(yaml.safe_dump(state,sort_keys=False,allow_unicode=True));os.replace(tmp,W/'research-state.yaml');r.durable_json(cpfile,cp);a.save_tree(W,run,tree)
 note=f'\n### {now} — N31 terminal numeric rejection\n\nSix matched triples: C0 0/6, Q0 0/6, N31 0/6; tasks6–9 Unknown. Frozen futility 0+4<5. All18 native receipts verified; {hours:.12f} GPUh retained. Review: {reviewpath}. {next_step} Original goal remains unmet.\n'
 for p in [W/'.arbor/sessions'/run/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md']:
  with p.open('a') as f:f.write(note)
summary={'schema':'autonomy-operational-observation-v1','at':now,'turn':59,'source':result['source_commit'],'stop_present':(W.parent/'autonomy_20261004/STOP').exists(),'authorization_until':h['until'],**prefix,'prior_turn_reconciliation':'Turn58 exited0; both ledger prefixes preserved. N31 finished naturally during this turn; no recovery or replay.','handles':{'controller':{'pid':203563,'state':'exited_reaped'},'monitor':{'pid':203562,'state':'exited'},'worker':{'pid':840181,'state':'exited'},'driver':json.loads((W.parent/'autonomy_20261004/driver-status.json').read_text())['driver']},'controller_status':result['decision'],'completed_work':'Verified 18 native receipt/audit/context/result hashes, complete triples, frozen futility arithmetic and exact retained charges. Recorded hash-bound root disposition and synchronized owning state/checkpoint/tree under normal state locks.','root_review':ref(reviewpath),'next_bounded_step':next_step,'unresolved_evidence':'Physical capture and cause of zero success unresolved; original validation/formal/required ablation evidence absent.','target_met':False}
r.durable_json(T/'operational-summary.json',summary)
print(json.dumps({'review':ref(reviewpath),'accounting':review['accounting'],'native':result['native']['N31'],'state_status':state['study']['status']}))
