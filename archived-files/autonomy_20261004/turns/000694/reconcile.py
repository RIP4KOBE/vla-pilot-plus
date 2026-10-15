import pathlib,json,sys,hashlib,datetime,shutil,yaml
root=pathlib.Path.cwd();sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as r
out=(root.parent/'autonomy_20261004/turns/000694').resolve();co=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator';cp=co/'checkpoint.json'
def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
assert not (root.parent/'autonomy_20261004/STOP').exists()
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
handoff=json.loads((root.parent/'autonomy_20261004/handoff-v2.json').read_text())
for k in ['authorization','required_continuation_context','completion_contract']:
 item=handoff[k];assert ref(item['path'])['sha256']==item['sha256']
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip();handles=[]
for pid,start in [(268073,97715947),(1123153,136839835),(1085789,136765765),(1088632,136774802)]:
 p=pathlib.Path(f'/proc/{pid}/stat');f=p.read_text().split() if p.exists() else None;handles.append({'pid':pid,'boot_id':boot,'expected_start_ticks':start,'actual_start_ticks':int(f[21]) if f else None,'state':f[2] if f else 'ABSENT','identity_matches':bool(f and int(f[21])==start)})
assert all(h['identity_matches'] for h in handles[:2]) and all(h['state']=='ABSENT' for h in handles[2:])
with r.locked(root/'data/qd-ed-state.lock'):
 s=r.read_state(root/'research-state.yaml');assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS';c=json.loads(cp.read_text());active=s['active_controller'];assert active==c['active_controller'];assert active['handles']['controller']['pid']==1085789
 for k in ['launch','plan','release']:assert ref(active[k]['path'])['sha256']==active[k]['sha256']
 result=json.loads(pathlib.Path(active['result_path']).read_text());terminal=result['result']['terminal'];assert result['result']['status']=='INVALID_STOP'
 attempt=pathlib.Path(terminal['output_dir']);receipt=json.loads((attempt/'eds_eval/n34-worker-receipt.json').read_text());assert receipt['error']=='loaded runtime not frozen: dinov2' and receipt['main_exit_code']==0
 events=r.read_events(root/'data/attempt-ledger.jsonl');resources=r.read_events(root/'data/gpu-healthcheck-ledger.jsonl');snapshot=r.budget_snapshot(events,resources)
 assert snapshot['running']==0 and events[-1]['attempt_id']==terminal['attempt_id'] and events[-1]['event']=='aborted'
 prior=json.loads((out.parent/'000693/end-reconciliation-v1.json').read_text())['ledger_prefixes'];prefixes={}
 for name,v in prior.items():
  b=(root/'data'/name).read_bytes();assert hashlib.sha256(b[:v['bytes']]).hexdigest()==v['sha256'];prefixes[name]={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
 next_action='CPU-only prospective runtime inventory repair for DINOv2 dynamic imports, with bounded representative CPU paths and strict audits preserved. Then fresh recovery identity, exact accounting amendment and independently reviewed frozen release before dispatch. No retroactive acceptance, replay or protected evaluation.'
 closure={'schema':'n34r8-root-terminal-closure-v1','at':now,'source':s['source_commit'],'controller':active,'controller_result':ref(active['result_path']),'worker_receipt':ref(attempt/'eds_eval/n34-worker-receipt.json'),'terminal_status':'INVALID_STOP','attempt_id':terminal['attempt_id'],'budget_snapshot':snapshot,'ledger_prefixes':prefixes,'prior_prefixes_intact':True,'controller_and_worker_absent':True,'handles':handles,'error':receipt['error'],'raw_failure_class_preserved':terminal['failure_class'],'scientific_interpretation':'Main exited 0; post-run runtime attestation rejected unbound DINOv2 module. No valid matched cell or efficacy conclusion. Raw task_failure classification retained; not scientific futility.','old_charges_preserved':True,'additional_attempts':1,'additional_gpu_hours':terminal['gpu_process_wall_seconds']/3600,'protected_access_authorized':False,'target_met':False,'next_action':next_action}
 write(out/'terminal-closure-v1.json',closure);binding=ref(out/'terminal-closure-v1.json')
 for p in [root/'research-state.yaml',cp,co/'idea_tree.json']:shutil.copyfile(p,out/(p.name+'.before'))
 for obj in [s,c]:obj.update(closed_n34r8_controller=active,active_controller=None,n34r8_terminal_closure=binding,budget_snapshot=snapshot,status='N34R8_INVALID_RUNTIME_ATTESTATION_CPU_REPAIR',n34_continuation_status='N34R8_INVALID_RUNTIME_ATTESTATION_CPU_REPAIR',automatic_gpu_dispatch_authorized=False,next_action=next_action,updated_at=now)
 tmp=root/'research-state.yaml.tmp';tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(root/'research-state.yaml');write(cp,c)
 tree=json.loads((co/'idea_tree.json').read_text());tree['nodes']['15.4'].update(n34r8_terminal_closure=binding,result='N34R8 invalid at post-run runtime attestation (dinov2); charge retained, no valid Dev denominator. CPU dynamic-import inventory repair and fresh prospective recovery release required.');write(co/'idea_tree.json',tree)
 record={'at':now,'source':s['source_commit'],'handles':handles,'ledger_prefixes':prefixes,'terminal_closure':binding,'driver_stop_present':(root.parent/'autonomy_20261004/STOP').exists(),'authorization_deadline':'2026-10-11T11:13:13Z','target_met':False,'next_action':next_action};write(out/'end-reconciliation-v1.json',record)
 (out/'operational-summary.md').write_text(f'''Turn694 — {now}

Current source {s['source_commit']}; scientific source 1065f38122379a515b60a9a424f574330405b66f. Bound handoff, exact authority, continuation context and completion contract verified. Driver268073/start97715947 and coordinator1123153/start136839835 alive on boot {boot}; controller1085789/start136765765 and worker1088632/start136774802 absent. Prior turn693 completed normally; three owning ledger prefixes preserved. STOP absent; authorization deadline 2026-10-11T11:13:13Z.

N34R8 task0 C0 terminated INVALID_STOP. Main exit0, then strict post-run runtime audit rejected dinov2. No accepted Dev denominator or scientific promotion. Charge +1 recovery attempt, +{closure['additional_gpu_hours']:.12f} GPUh retained; cumulative {snapshot['dispatched']} dispatches / {snapshot['gpu_hours_consumed']:.12f} GPUh; zero running. Unknown telemetry and raw failure classification preserved. State/checkpoint/tree now bind terminal closure; automatic dispatch disabled pending reviewed fresh release. No GPU dispatch, source change, process signal, or driver/coordinator lock acquisition.

Receipt identifies missing dinov2; bounded CPU reproduction and inventory diagnosis remain pending. Existing native validity gate remains unchanged.

Next bounded step: {next_action}

Unresolved: complete native runtime validity, matched Dev efficacy, scientific promotion, validation20/formal10/required ablations and hash-bound original-goal completion. No completion claim; driver continues.
''')
 print(json.dumps({'closure':binding,'budget':snapshot,'summary':str(out/'operational-summary.md')}))
