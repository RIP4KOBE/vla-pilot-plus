import pathlib,json,sys,hashlib,datetime,shutil,yaml
root=pathlib.Path.cwd();sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as r
out=(root.parent/'autonomy_20261004/turns/000634').resolve();co=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator';cp=co/'checkpoint.json'
def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
with r.locked(root/'data/qd-ed-state.lock'):
 s=r.read_state(root/'research-state.yaml');c=json.loads(cp.read_text());active=s['active_controller'];assert active==c['active_controller'];assert active['handles']['controller']['pid']==592818
 result=json.loads(pathlib.Path(active['result_path']).read_text());terminal=result['result']['terminal'];assert result['result']['status']=='INVALID_STOP'
 attempt=pathlib.Path(terminal['output_dir']);receipt=json.loads((attempt/'eds_eval/n34-worker-receipt.json').read_text());assert receipt['error']=='loaded runtime not frozen: dotenv.parser'
 assert not pathlib.Path('/proc/592818').exists() and not pathlib.Path('/proc/595896').exists()
 events=r.read_events(root/'data/attempt-ledger.jsonl');resources=r.read_events(root/'data/gpu-healthcheck-ledger.jsonl');snapshot=r.budget_snapshot(events,resources)
 assert snapshot['running']==0 and events[-1]['attempt_id']==terminal['attempt_id'] and events[-1]['event']=='aborted'
 prefixes={}
 for name in ['attempt-ledger.jsonl','gpu-healthcheck-ledger.jsonl','gpu-hour-reservation-ledger.jsonl']:
  b=(root/'data'/name).read_bytes();prefixes[name]={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
 prior=json.loads((out.parent/'000633/end-reconciliation-v1.json').read_text())['ledger'];b=(root/'data/attempt-ledger.jsonl').read_bytes();assert hashlib.sha256(b[:prior['bytes']]).hexdigest()==prior['sha256']
 closure={'schema':'n34r2-root-terminal-closure-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':s['source_commit'],'controller':active,'controller_result':ref(active['result_path']),'worker_receipt':ref(attempt/'eds_eval/n34-worker-receipt.json'),'terminal_status':'INVALID_STOP','attempt_id':terminal['attempt_id'],'budget_snapshot':snapshot,'ledger_prefixes':prefixes,'prior_prefix_intact':True,'controller_and_worker_absent':True,'error':receipt['error'],'raw_failure_class_preserved':terminal['failure_class'],'scientific_interpretation':'Main exited 0 but post-run runtime attestation rejected dotenv.parser. Invalid outcome, no accepted matched cells or scientific promotion. Raw task_failure classification retained; not scientific futility.','old_charges_preserved':True,'additional_attempts':1,'additional_gpu_hours':terminal['gpu_process_wall_seconds']/3600,'protected_access_authorized':False,'target_met':False,'next_action':'CPU-only prospective runtime import inventory repair, preserving strict checks; fresh recovery identity and release required before dispatch.'}
 write(out/'terminal-closure-v1.json',closure);binding=ref(out/'terminal-closure-v1.json')
 for p in [root/'research-state.yaml',cp,co/'idea_tree.json']:shutil.copyfile(p,out/(p.name+'.before'))
 for obj in [s,c]:obj.update(closed_n34r2_controller=active,active_controller=None,n34r2_terminal_closure=binding,budget_snapshot=snapshot,n34_continuation_status='N34R2_INVALID_POST_RUNTIME_ATTESTATION_CPU_DIAGNOSIS',automatic_gpu_dispatch_authorized=False,next_action=closure['next_action'])
 tmp=root/'research-state.yaml.tmp';tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(root/'research-state.yaml');write(cp,c)
 tree=json.loads((co/'idea_tree.json').read_text());tree['nodes']['15.4'].update(n34r2_terminal_closure=binding,result='N34R2 invalid at post-run runtime attestation (dotenv.parser); charges retained, no valid Dev denominator. CPU inventory repair and prospective recovery release required.');write(co/'idea_tree.json',tree)
 print(json.dumps({'closure':binding,'budget':snapshot}))
