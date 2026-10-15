import pathlib,json,hashlib,datetime,fcntl,yaml,sys
root=pathlib.Path.cwd();sys.path.insert(0,str(root))
from scripts import qd_ed_final_runner as r
base=root.parent/'autonomy_20261004';out=(base/'turns/001241').resolve();cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
def ref(p):
 p=pathlib.Path(p);return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
def identity(h):
 p=pathlib.Path('/proc')/str(h['pid'])/'stat'
 if not p.exists():return {**h,'live':False,'identity_matches':False}
 x=p.read_text().rsplit(')',1)[1].split();match=int(x[19])==h['start_ticks'] and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==h['boot_id']
 return {**h,'live':match and x[0]!='Z','identity_matches':match,'observed_state':x[0]}
with open(root/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 s=yaml.safe_load((root/'research-state.yaml').read_text());ck=json.loads(cp.read_text());tree=json.loads((cp.parent/'idea_tree.json').read_text());ds=json.loads((base/'driver-status.json').read_text());assert ds['turn']==1241
 assert identity(ds['driver'])['live'] and identity(ds['process'])['live']
 a=s['active_controller'];prev=json.loads((base/'turns/001240/operational-summary.json').read_text());handles={k:identity(prev['live_handles'][k]) for k in ['controller','runner','worker']};assert not any(h['live'] for h in handles.values())
 prefixes={}
 for name,old in prev['ledger_prefixes'].items():
  p=root/'data'/name;b=p.read_bytes();assert hashlib.sha256(b[:old['bytes']]).hexdigest()==old['sha256'];prefixes[name]={**ref(p),'bytes':len(b)}
 for key in ['launch','plan','release']:
  assert ref(a[key]['path'])['sha256']==a[key]['sha256']
 events=r.read_events(root/'data/attempt-ledger.jsonl');resources=r.read_events(root/'data/gpu-healthcheck-ledger.jsonl');final=events[-1];assert final['attempt_id']=='n36r1_dev_t00_c0_001203' and final['event']=='aborted' and final['classification']=='INVALID'
 p=pathlib.Path(final['output_dir']);assert json.loads((p/'attempt-result.json').read_text())==final
 receipt=json.loads((p/'eds_eval/n36-worker-receipt.json').read_text());assert receipt['error']=='loaded runtime not frozen: _cyutility' and receipt['accepted'] is False
 snap=r.budget_snapshot(events,resources);now=datetime.datetime.now(datetime.timezone.utc).isoformat();plan=json.loads(pathlib.Path(a['plan']['path']).read_text())
 next_action='CPU-only bounded diagnosis of N36R1 post-main runtime closure rejection for _cyutility, starting from frozen qd_ed_n34_source.py attest and exact native receipt/runtime inventory. Preserve invalid attempt, costs and unknown telemetry; do not weaken audits or replay cohort. Any engineering repair requires isolated executor source review and a separately recorded prospective recovery identity/release before GPU dispatch. Scientific gates unchanged.'
 summary={'schema':'arbor-operational-summary-v1','turn':1241,'at':now,'source':s['source_commit'],'status':'N36R1_INVALID_STOP_RECONCILED','live_handles':{'driver':identity(ds['driver']),'coordinator':identity(ds['process'])},'closed_handles':handles,'all_cohort_handles_absent':True,'controller_result':ref(a['result_path']),'receipt':ref(p/'eds_eval/n36-worker-receipt.json'),'terminal':ref(p/'attempt-result.json'),'ledger_prefixes':prefixes,'prior_turn_status':'completed_turn','ledger_prefix_preserved':True,'budget_snapshot':snap,'charge_seconds':final['gpu_process_wall_seconds'],'valid_cohort_outcomes':0,'complete_quadruples':0,'error':receipt['error'],'main_exit_code':receipt['main_exit_code'],'telemetry':'HTTP counters Unknown and required_cost_telemetry_complete=false retained. 23 completed official Codex logical calls.','completed_work':['Verified bound authority, current driver/coordinator identities and prior normal turn exit.','Verified controller/runner/worker termination, frozen plan/release and retained ledger prefixes.','Closed invalid first C0 attempt without replay; recomputed private cumulative accounting.'],'next_step':next_action,'unresolved_evidence':['Exact _cyutility runtime provenance and safe prospective repair','Accepted Dev cohort and scientific promotion','Original validation/formal/required ablation evidence'],'target_met':False,'stop_present':(base/'STOP').exists() or pathlib.Path(plan['stop_path']).exists(),'deadline':'2026-10-11T11:13:13Z'}
 write(out/'operational-summary.json',summary);bound=ref(out/'operational-summary.json')
 for path in [root/'research-state.yaml',cp,cp.parent/'idea_tree.json']:(out/(path.name+'.before-update')).write_bytes(path.read_bytes())
 for d in [s,ck]:
  d['closed_n36r1_controller']=d.pop('active_controller');d.update(status='N36R1_INVALID_STOP_RECONCILED',phase='N36R1_CPU_RUNTIME_DIAGNOSIS',next_action=next_action,updated_at=now,budget_snapshot=snap,automatic_gpu_dispatch_authorized=False,n36r1_terminal_reconciliation=bound)
 tree['nodes']['15.6'].update(result='N36R1_INVALID_STOP_POST_MAIN_RUNTIME_CLOSURE',score=None,insight='First N36R1 C0 episode completed Main but runtime closure rejected _cyutility. No accepted scientific outcome. All 809.4826372319367 GPU seconds retained; bounded CPU diagnosis required.',n36r1_terminal_reconciliation=bound)
 tmp=(root/'research-state.yaml').with_suffix('.tmp');tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(root/'research-state.yaml');write(cp,ck);write(cp.parent/'idea_tree.json',tree)
 (out/'operational-summary.md').write_text(f"Source {s['source_commit']}. N36R1 controller391755, runner391766 and worker396903 exited; no live cohort. Driver {ds['driver']['pid']} and coordinator {ds['process']['pid']} verified.\n\nFirst C0 Main completed but runtime closure rejected _cyutility. Invalid attempt and 809.4826372319367 GPU seconds retained; cumulative {snap['dispatched']} dispatched, {snap['gpu_hours_consumed']:.12f} GPUh. Zero accepted N36R1 outcomes. Unknown/incomplete telemetry preserved.\n\nNext: {next_action}\n\nNo STOP; deadline 2026-10-11T11:13:13Z. Original validation/formal/required ablation goal remains unmet.\n")
 (out/'operational-summary.sha256').write_text(bound['sha256']+'  operational-summary.json\n')
 print(json.dumps({'summary':bound,'budget':snap}))
