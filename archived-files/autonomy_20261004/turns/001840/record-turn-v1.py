import pathlib,json,hashlib,datetime,fcntl,os,yaml
P=pathlib.Path; root=P.cwd();base=(root/'../autonomy_20261004').resolve();out=base/'turns/001840';now=datetime.datetime.now(datetime.timezone.utc).isoformat()
def ref(p):return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
prior=json.loads((base/'turns/001839/operational-summary-v1.json').read_text())
result_path=out/'composition-v5/graph-admission-result-v1.json';result=json.loads(result_path.read_text())
for r in prior['ledger_prefixes'].values():assert ref(P(r['path']))['sha256']==r['sha256'] and P(r['path']).stat().st_size==r['bytes']
status=json.loads((base/'driver-status.json').read_text());handles={}
for k in ['driver','process']:
 h=status[k];st=P(f"/proc/{h['pid']}/stat").read_text().rsplit(')',1)[1].split();assert int(st[19])==h['start_ticks'];assert P('/proc/sys/kernel/random/boot_id').read_text().strip()==h['boot_id'];handles[k]=dict(h,identity_verified=True)
next_action='Review current controller evidence and prior turn001832 static review against unchanged deployed controller/wrapper sources, exact source/runtime/closure bindings and production verification contract. Determine whether authentic scoped root acceptance can satisfy ROOT_REVIEWED while retaining false native/physical-gain/readiness/release flags; create new reviewed artifact only if substantiated. Rebind descendants in fresh graph and rerun production verify_graph. Preserve old records and retained parity failure. No GPU/provider until full graph, parity, release and native-readiness gates pass.'
record=dict(status=result['status'],at=now,source=prior['current_source']['commit'],graph=result['graph'],result=ref(result_path),gpu_authorized=False)
with (root/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for path,is_yaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  d=yaml.safe_load(path.read_text()) if is_yaml else json.loads(path.read_text());d['n36_final_inventory_graph_composition']=record;d['next_action']=next_action;d['updated_at']=now
  tmp=path.with_name(path.name+'.turn001840.tmp');tmp.write_text(yaml.safe_dump(d,sort_keys=False) if is_yaml else json.dumps(d,indent=2)+'\n');os.replace(tmp,path)
summary=dict(schema='autonomy-operational-summary-v1',at=now,turn=1840,current_source=prior['current_source'],owning_source=prior['owning_source'],scientific_source=prior['scientific_source'],live_handles=handles,controller_status='NO_OWNING_GPU_COHORT_OR_CPU_EXECUTOR; GRAPH_COMPOSER_EXITED',completed_work=['Verified bound authority, driver boot/start identities, prior normal exit and unchanged four private ledger prefixes.','Composed fresh disabled graph with final reviewed source, exact amended canonical inventory, derived historical snapshot, source scope, runtime closure, all40 audit and separate engineering manifest.','Ran production verify_graph; retained exact outcome and blockers without GPU/provider dispatch or benchmark edits.'],graph_admission=record,ledger_prefixes=prior['ledger_prefixes'],next_bounded_step=next_action,unresolved_evidence=[result.get('error','Authentic root graph review pending'),'Retained parity test failure','Finite release and native readiness','Original validation/formal/required ablation evidence'],gpu_dispatches=0,provider_calls=0,target_met=False,stop_present=(base/'STOP').exists(),deadline=prior['deadline'])
p=out/'operational-summary-v1.json'
with p.open('x') as f:f.write(json.dumps(summary,indent=2)+'\n')
(out/'operational-summary-v1.sha256').write_text(ref(p)['sha256']+'  operational-summary-v1.json\n');print(json.dumps(dict(summary=ref(p),result=record)))
