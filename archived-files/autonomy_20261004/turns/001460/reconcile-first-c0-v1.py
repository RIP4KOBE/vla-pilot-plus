import json,pathlib,hashlib,datetime,os,sys,subprocess,yaml
root=pathlib.Path.cwd();base=root.parent/'autonomy_20261004';out=base/'turns/001460';prior=base/'turns/001459';launch=base/'turns/001456'
source=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree')
sys.path.insert(0,str(source));from scripts import qd_ed_final_runner as r
def ref(p):
 b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def write(p,d):
 tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(d,indent=2)+'\n');os.replace(tmp,p)
def observe(h):
 p=pathlib.Path('/proc')/str(h['pid'])/'stat';v=p.read_text().rsplit(')',1)[1].split() if p.exists() else None
 return {**h,'live':bool(v and int(v[19])==h['start_ticks'] and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==h['boot_id'] and v[0]!='Z'),'observed_state':v[0] if v else None,'observed_start_ticks':int(v[19]) if v else None,'children':[]}
old=json.loads((prior/'operational-summary-v1.json').read_text());driver=json.loads((base/'driver-status.json').read_text());assert driver['turn']==1460
assert observe(driver['driver'])['live'] and observe(driver['process'])['live']
handles={k:observe(v) for k,v in old['live_handles'].items()};assert not any(v['live'] for v in handles.values())
assert json.loads((launch/'first-c0-operation-exit-v1.json').read_text())['exit']==0
assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==old['candidate_source']
for v in old['frozen_bindings'].values():assert ref(pathlib.Path(v['path']))['sha256']==v['sha256']
nextstep='CPU-only executor repair/design of N36 bootstrap admission for the already runtime-manifest-bound DINOv2 torch.hub source. Preserve fail-closed source-byte/origin/path auditing; no broad directory allowlist. Add focused positive local-hub and negative tamper/foreign-path tests, then independent review. Any later GPU execution requires separately frozen recovery identity/protocol/accounting/runtime/source release and fresh first-C0 G3 boundary. N36R3 stopped INVALID; no replay or later cell, validation/formal remain gated.'
with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(root/'data/qd-ed-state.lock'):
  anchors={};rows={}
  for n,v in old['ledger_prefixes'].items():
   p=pathlib.Path(v['path']);b=p.read_bytes();assert hashlib.sha256(b[:v['bytes']]).hexdigest()==v['sha256'];anchors[n]={**ref(p),'lines':len(b.splitlines()),'prior_prefix_preserved':True};rows[n]=[json.loads(x) for x in b.splitlines() if x.strip()]
  attempts=[x for x in rows['attempt-ledger.jsonl'] if x.get('attempt_id')=='n36r3_dev_t00_c0_001314'];assert [x['event'] for x in attempts]==['reserved','dispatched','aborted']
  terminal=attempts[-1];assert terminal['outcome_valid'] is False and terminal['success'] is None and terminal['classification']=='INVALID'
  result=pathlib.Path(terminal['output_dir'])/'attempt-result.json';assert json.loads(result.read_text())==terminal
  log=result.parent/'runner.log';tail=log.read_text().replace('\r','\n').splitlines()[-20:];assert any('ImportError: N36 foreign import search path:' in x and 'facebookresearch_dinov2_main' in x for x in tail)
  snap=r.budget_snapshot(rows['attempt-ledger.jsonl'],rows['gpu-healthcheck-ledger.jsonl']);assert snap['running']==snap['gpu_healthcheck_inflight']==0 and snap['dispatched']==506
  previous=75.53635665625;added=terminal['gpu_process_wall_seconds']/3600;assert abs(snap['gpu_hours_consumed']-(previous+added))<1e-10
  now=datetime.datetime.now(datetime.timezone.utc).isoformat()
  rec={'schema':'n36r3-first-c0-terminal-reconciliation-v2','at':now,'status':'INVALID_STOP_RECONCILED_DINO_HUB_IMPORT_GUARD','source':old['candidate_source'],'handles':handles,'exit':ref(launch/'first-c0-operation-exit-v1.json'),'controller_log':ref(launch/'first-c0-operation.log'),'result':ref(result),'worker_log':ref(log),'worker_log_tail':tail,'terminal_event':terminal,'ledger_prefixes':anchors,'snapshot':snap,'previous_gpu_hours':previous,'added_gpu_hours':added,'arithmetic':f'{previous} + {terminal["gpu_process_wall_seconds"]}/3600 = {snap["gpu_hours_consumed"]}','native_G3_accepted':False,'no_later_cell_authorized':True,'diagnosis':'torch.hub temporarily adds the runtime DINOv2 cache repository to sys.path; bootstrap allows only checkout/interpreter roots plus narrowly admitted Torch-generated code. The DINO repository is already enumerated (203 files) in the frozen runtime manifest, but lacks a bootstrap admission path. Preserve original generic failure_class/reason and incomplete telemetry; this diagnosis supplements, never rewrites, the ledger.','next_action':nextstep,'goal_complete':False};write(out/'terminal-reconciliation-v1.json',rec)
  for p,isyaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
   d=yaml.safe_load(p.read_text()) if isyaml else json.loads(p.read_text());d.update(n36r3_first_c0_terminal_reconciliation_001460=ref(out/'terminal-reconciliation-v1.json'),budget_snapshot=snap,next_action=nextstep,status=rec['status'],phase=rec['status'],updated_at=now)
   op=d.get('n36r3_live_first_c0_operation',{});op.update(status='TERMINAL_INVALID_STOP',live_handles=[],terminal_reconciliation=ref(out/'terminal-reconciliation-v1.json'));d['n36r3_live_first_c0_operation']=op
   if isyaml:
    d['budget']['gpu_hours_consumed']=snap['gpu_hours_consumed'];tmp=p.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));os.replace(tmp,p)
   else:write(p,d)
  p=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/idea_tree.json';tree=json.loads(p.read_text());tree['nodes']['15.6'].update(n36r3_first_c0_terminal_reconciliation_001460=ref(out/'terminal-reconciliation-v1.json'),result=rec['status'],insight=nextstep);write(p,tree)
summary={'schema':'arbor-operational-summary-v1','at':now,'turn':1460,'owning_source':old['owning_source'],'candidate_source':old['candidate_source'],'live_handles':handles,'driver':driver,'current_controller_status':rec['status'],'ledger_prefixes':anchors,'retained_attempts':506,'retained_gpu_hours':snap['gpu_hours_consumed'],'completed_work':['Verified handoff/authority hashes, driver/coordinator identities, ACTIVE/PASS isolation, prior normal turn receipt, frozen plan/release and preserved ledger prefixes.','Reconstructed existing first-C0 terminal side effects: wrapper exit 0, controller INVALID_STOP, worker import failure; all three PIDs absent. No duplicate, replay or signals.','Reconciled one charged invalid attempt and 251.3019977810327 GPU-seconds; retained incomplete telemetry, old charges and protected reserves.','Bounded source diagnosis found already manifest-bound DINOv2 hub root rejected by bootstrap search guard. No benchmark edits, new dispatch or protected-result access.'],'terminal_reconciliation':ref(out/'terminal-reconciliation-v1.json'),'next_bounded_step':nextstep,'unresolved_evidence':['Audited DINOv2 runtime import admission engineering repair','First-C0 native G3 acceptance and fresh matched development promotion','Original validation/formal/required ablations'],'driver_stop_exists':(base/'STOP').exists(),'deadline':'2026-10-11T11:13:13Z','goal_complete':False}
write(out/'operational-summary-v1.json',summary);(out/'operational-summary-v1.sha256').write_text(ref(out/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n');print(json.dumps({'status':rec['status'],'snapshot':snap,'summary':ref(out/'operational-summary-v1.json')}))
