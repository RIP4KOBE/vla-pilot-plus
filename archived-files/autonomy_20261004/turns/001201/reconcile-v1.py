import pathlib,json,hashlib,datetime,fcntl,yaml,sys
root=pathlib.Path.cwd();sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as r
out=(root.parent/'autonomy_20261004/turns/001201').resolve();base=root.parent/'autonomy_20261004';cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
def live(pid):
 try:return pathlib.Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[0]!='Z'
 except FileNotFoundError:return False
with open(root/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 s=yaml.safe_load((root/'research-state.yaml').read_text());ck=json.loads(cp.read_text());tree=json.loads((cp.parent/'idea_tree.json').read_text());ds=json.loads((base/'driver-status.json').read_text());assert ds['turn']==1201
 a=s['active_controller'];assert a['kind']=='N36_CONTROLLER'
 assert not any(live(h['pid']) for h in a['handles'].values()) and not live(184652)
 events=r.read_jsonl(root/'data/attempt-ledger.jsonl') if hasattr(r,'read_jsonl') else [json.loads(x) for x in (root/'data/attempt-ledger.jsonl').read_text().splitlines()]
 resources=[json.loads(x) for x in (root/'data/gpu-healthcheck-ledger.jsonl').read_text().splitlines()]
 final=events[-1];assert final['attempt_id']=='n36_dev_t00_c0_001147' and final['event']=='aborted'
 ledger=(root/'data/attempt-ledger.jsonl').read_bytes();pref=final['ledger_prefix'];assert hashlib.sha256(ledger[:pref['bytes']]).hexdigest()==pref['sha256']
 for key in ['launch','plan','release','runner_process']:
  rr=a[key];assert ref(pathlib.Path(rr['path']))['sha256']==rr['sha256']
 p=pathlib.Path(final['output_dir']);receipt=json.loads((p/'eds_eval/n36-worker-receipt.json').read_text());assert receipt['error']=='actual native build metadata' and receipt['accepted'] is False
 snap=r.budget_snapshot(events,resources);now=datetime.datetime.now(datetime.timezone.utc).isoformat()
 next_action='CPU-only bounded diagnosis of N36 native metadata mismatch using exact worker imports and frozen runtime environment; ordinary and source-only Torch metadata probes pass. Preserve aborted C0 attempt and all costs. No automatic recovery; require separately reviewed prospective repair/release/new attempt identity before GPU dispatch. Original scientific gates unchanged.'
 summary={'schema':'autonomy-bounded-operation-summary-v1','at':now,'source':s['source_commit'],'status':'N36_INVALID_STOP_RECONCILED','driver':ds['driver'],'coordinator':ds['process'],'closed_handles':a['handles'],'worker_process':json.loads((p/'process.json').read_text()),'all_cohort_handles_absent':True,'controller_result':ref(pathlib.Path(a['result_path'])),'receipt':ref(p/'eds_eval/n36-worker-receipt.json'),'terminal':ref(p/'attempt-result.json'),'prior_turn_exit':0,'ledger_prefix_verified':True,'ledger':{**ref(root/'data/attempt-ledger.jsonl'),'bytes':len(ledger)},'budget_snapshot':snap,'charge_seconds':final['gpu_process_wall_seconds'],'valid_cohort_outcomes':0,'complete_quadruples':0,'error':receipt['error'],'telemetry':'Unknown/incomplete retained; no Stage queries and main_exit_code null','cpu_probes':[ref(out/'cpu-native-metadata-probe-v1.json'),ref(out/'cpu-bootstrap-native-metadata-probe-v1.json')],'diagnosis':'Failure before native_build_before receipt/main; ordinary and bootstrap CPU probes match frozen metadata. Exact cause unresolved. No audit changes.','completed':'Verified handoff/authority, prior turn successful exit, current controller termination, ledger prefix and frozen plan/release; preserved invalid attempt and recomputed cumulative accounting. GPU7 observed idle.','next_action':next_action,'unresolved':['Native metadata mismatch under worker execution','RT-03/04 native/controller/whole-episode evidence','Original validation/formal/required ablations'],'target_met':False,'stop_present':(base/'STOP').exists(),'deadline':'2026-10-11T11:13:13Z','executor_delegation':'Unavailable: spawn returned no thread; no executor started.'}
 write(out/'operational-summary.json',summary)
 for path in [root/'research-state.yaml',cp,cp.parent/'idea_tree.json']:(out/(path.name+'.before-update')).write_bytes(path.read_bytes())
 for d in [s,ck]:
  d['closed_n36_controller']=d.pop('active_controller');d.update(status='N36_INVALID_STOP_RECONCILED',next_action=next_action,updated_at=now,budget_snapshot=snap,automatic_gpu_dispatch_authorized=False,n36_terminal_reconciliation=ref(out/'operational-summary.json'))
 tree['nodes']['15.6'].update(result='N36_INVALID_STOP_BEFORE_MAIN_NATIVE_METADATA',score=None,insight='First C0 attempt aborted before main: native-build metadata mismatch. No scientific outcome; 86.40354533703066 seconds retained. CPU reproduction unresolved.',terminal_reconciliation=ref(out/'operational-summary.json'))
 tmp=(root/'research-state.yaml').with_suffix('.tmp');tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(root/'research-state.yaml');write(cp,ck);write(cp.parent/'idea_tree.json',tree)
 (out/'operational-summary.md').write_text(f"Source {s['source_commit']}. N36 controller175364, runner175399 and worker184652 exited; no live cohort. Driver {ds['driver']['pid']} and coordinator {ds['process']['pid']} remain recorded.\n\nFirst C0 attempt aborted before main: actual native build metadata mismatch. Retained charge86.40354533703066s; cumulative {snap['dispatched']} dispatched, {snap['gpu_hours_consumed']:.12f} GPUh. No valid N36 outcomes. Unknown telemetry preserved.\n\nOrdinary and bootstrap CPU metadata probes passed; exact worker-context cause remains unresolved. Source/plan/audits unchanged.\n\nNext: {next_action}\n\nOriginal validation/formal/ablation goal remains unmet.\n")
 print(json.dumps({'summary':ref(out/'operational-summary.json'),'budget':snap}))
