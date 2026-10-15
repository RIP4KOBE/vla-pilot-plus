import pathlib,json,hashlib,datetime,os,sys,yaml
root=pathlib.Path.cwd();base=root.parent/'autonomy_20261004';out=base/'turns/001439'
source=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree')
sys.path.insert(0,str(source))
from scripts import qd_ed_final_runner as r, qd_ed_n36_contract as c

def ref(p):
 b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def write(p,d):
 q=p.with_suffix('.tmp');q.write_text(json.dumps(d,indent=2)+'\n');os.replace(q,p)
def observe(h):
 p=pathlib.Path('/proc')/str(h['pid'])/'stat';v=p.read_text().rsplit(')',1)[1].split() if p.exists() else None
 return {**h,'live':bool(v and int(v[19])==h['start_ticks'] and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==h['boot_id'] and v[0]!='Z'),'observed_state':v[0] if v else None}
old=json.loads((out/'operational-summary-v1.json').read_text()); prior=json.loads((base/'turns/001438/operational-summary-v1.json').read_text())
handles={'wrapper':observe(old['live_handles']['wrapper']),'adapter':observe(json.loads((out/'first-c0-operation-process-v1.json').read_text()))};assert not any(h['live'] for h in handles.values())
assert json.loads((out/'first-c0-operation-exit-v1.json').read_text())['exit']==1
release=json.loads((out/'execution-release-v1.json').read_text());plan=json.loads(pathlib.Path(release['plan']['path']).read_text()); canonical={**release['plan'],'path':str(pathlib.Path(release['plan']['path']).resolve())}
expected={'schema':'n36-execution-release-v1','approved':True,'plan':canonical,**{k:plan[k] for k in ['native_build','authority','protocol','protocol_review','source','scientific_source','runtime_closure','controller_semantics','runtime','phase_authorization']},'limits':c.LIMITS,**c.operational_binding(plan),'readiness':release['readiness']}
diffs={k:{'bound':release.get(k),'cli_expected':v} for k,v in expected.items() if release.get(k)!=v};assert set(diffs)=={'plan'};assert set(release)==set(expected)|{'root_review'}
nextstep='Resolve N36R3 CLI lexical/canonical reference mismatch under scoped engineering review. Frozen plan/source/health evidence must remain intact; do not merely rebind release to canonical plan because health terminal binds original lexical plan. Evaluate an audited operational entrypoint preserving exact frozen references or prospective executor repair with required source/binding review. No automatic retry; first C0 and mandatory G3 remain pending. No health replay or validation/formal access.'
with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(root/'data/qd-ed-state.lock'):
  anchors={}; rows={}
  for n,v in prior['ledger_prefixes'].items():
   p=pathlib.Path(v['path']);actual=ref(p);assert actual['sha256']==v['sha256'] and actual['bytes']==v['bytes'];anchors[n]={**actual,'prior_prefix_preserved':True};rows[n]=[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
  snap=r.budget_snapshot(rows['attempt-ledger.jsonl'],rows['gpu-healthcheck-ledger.jsonl']);assert snap['running']==snap['gpu_healthcheck_inflight']==0 and snap['dispatched']==505 and snap['gpu_hours_consumed']==prior['retained_gpu_hours']
  now=datetime.datetime.now(datetime.timezone.utc).isoformat();status='N36R3_FIRST_C0_PRE_DISPATCH_REFERENCE_FAILURE'
  record={'schema':'n36r3-first-c0-terminal-reconciliation-v1','at':now,'status':status,'source':old['candidate_source'],'handles':handles,'exit':ref(out/'first-c0-operation-exit-v1.json'),'log':ref(out/'first-c0-operation.log'),'consumer':ref(out/'first-c0-release-consumer-v1.json'),'mismatches':diffs,'cause':'CLI main resolves reference paths; direct consumer uses lexical frozen reference; exact release equality fails before admission','ledger_prefixes':anchors,'snapshot':snap,'new_episode_reservations':0,'new_episode_dispatches':0,'new_health_dispatches':0,'new_gpu_charges':0,'scientific_result':None,'next_action':nextstep,'goal_complete':False};write(out/'first-c0-terminal-reconciliation-v1.json',record)
  for p,isyaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
   d=yaml.safe_load(p.read_text()) if isyaml else json.loads(p.read_text());d.update(n36r3_first_c0_terminal_reconciliation=ref(out/'first-c0-terminal-reconciliation-v1.json'),budget_snapshot=snap,next_action=nextstep,status=status,phase=status,updated_at=now)
   d['n36r3_live_first_c0_operation']['status']='TERMINAL_EXIT_1_BEFORE_RESERVATION'
   if isyaml:
    q=p.with_suffix('.tmp');q.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));os.replace(q,p)
   else:write(p,d)
  p=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/idea_tree.json';d=json.loads(p.read_text());d['nodes']['15.6'].update(result=status,insight=nextstep,n36r3_first_c0_terminal_reconciliation=ref(out/'first-c0-terminal-reconciliation-v1.json'));write(p,d)
  old.update(at=now,live_handles=handles,current_controller_status='TERMINAL_EXIT_1_NO_EPISODE_DISPATCH',current_observation='Reference mismatch before reservation; no active controller or GPU worker.',ledger_prefixes=anchors,terminal_reconciliation=ref(out/'first-c0-terminal-reconciliation-v1.json'),driver=json.loads((base/'driver-status.json').read_text()),next_bounded_step=nextstep,completed_work=['Verified handoff, authority, prior normal exit, source and private ledger prefixes.','Prepared first-C0 release and passed direct full production consumer.','Observed idle GPU7 and launched one adapter; adapter failed closed before admission due solely to CLI canonicalizing the lexical plan reference.','Reconciled both dead handles, exit 1 and unchanged ledgers; preserved 505 attempts and 75.53335346582918 GPU-hours.'],driver_stop_exists=(base/'STOP').exists(),goal_complete=False)
  write(out/'operational-summary-v1.json',old);(out/'operational-summary-v1.sha256').write_text(ref(out/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n')
print(json.dumps({'status':status,'mismatched_fields':list(diffs),'ledger_unchanged':True,'summary':ref(out/'operational-summary-v1.json')}))
