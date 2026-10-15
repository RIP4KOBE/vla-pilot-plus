import ast,copy,datetime,fcntl,hashlib,json,math,os,subprocess,types
from pathlib import Path
import yaml
owner=Path.cwd(); turns=(owner/'../autonomy_20261004/turns').resolve(); out=turns/'001554'; prior=turns/'001552/graph-rebinding'; candidate=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
def ref(p):
 p=Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2);f.write('\n')
 return ref(p)
now=datetime.datetime.now(datetime.timezone.utc).isoformat();assert not (turns.parent/'STOP').exists();assert now<'2026-10-11T11:13:13'
assert json.loads((prior/'exit-v1.json').read_text())['exit']==0
for pid in [2226929,2226930]:assert not Path(f'/proc/{pid}').exists()
old=turns/'001551/controller-semantics.root-reviewed-v1.json'; proof=json.loads(old.read_text());new=copy.deepcopy(proof)
for k,r in proof['review_evidence'].items():
 assert ref(r['path'])=={a:r[a] for a in ['path','sha256']};assert Path(r['path']).stat().st_size==r['bytes'];new['review_evidence'][k]={a:r[a] for a in ['path','sha256']}
proofref=write(out/'controller-semantics.root-reviewed-v2.json',new)
# Execute only exact passive functions, without importing production dependencies.
w=types.SimpleNamespace(); ns={'Path':Path,'hashlib':hashlib,'json':json}
p=candidate/'scripts/qd_ed_n23_worker.py';tree=ast.parse(p.read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['require','sha','read_ref']];exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),ns)
for name in ['require','sha','read_ref']:setattr(w,name,ns[name])
p=candidate/'scripts/qd_ed_n34_controller.py';tree=ast.parse(p.read_text());nodes=[n for n in tree.body if (isinstance(n,ast.FunctionDef) and n.name=='verify_semantics') or (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FIELDS' for t in n.targets))];ns={'w':w,'math':math};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),ns)
closure=w.read_ref(new['runtime_closure']);assert ns['verify_semantics'](proofref,new['runtime'],closure)==new
try:ns['verify_semantics'](ref(old),proof['runtime'],closure)
except ValueError as e:assert str(e)=='invalid file reference'
else:raise AssertionError('old proof unexpectedly accepted')
summary=json.loads((turns/'001553/operational-summary-v1.json').read_text())
for r in summary['ledgers'].values():assert ref(r['path'])['sha256']==r['sha256'] and Path(r['path']).stat().st_size==r['bytes']
assert subprocess.check_output(['git','-C',str(candidate),'rev-parse','HEAD'],text=True).strip()==summary['candidate_source'];assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==summary['owner_source']
review=write(out/'terminal-and-proof-schema-review-v1.json',{'at':now,'status':'PASS_REFERENCE_SCHEMA_REPAIR_ONLY_GRAPH_REBINDING_PENDING','executor_exit':ref(prior/'exit-v1.json'),'executor_report':ref(prior/'report-v1.json'),'original_proof':ref(old),'corrected_proof':proofref,'changes':'Removed only bytes metadata from three review_evidence references; paths, hashes and reviewed semantics unchanged. Original artifact retained.','exact_verifier':ref(p),'worker_ref_verifier':ref(candidate/'scripts/qd_ed_n23_worker.py'),'original_negative_control':'invalid file reference','corrected_passive_verifier':'PASS','source_edited':False,'release_enabled':False,'b5_review':None,'scientific_success':False})
next_step='Rebind disabled graph to turn001554/controller-semantics.root-reviewed-v2.json (exact unchanged passive verifier PASS); retain turn001552 artifacts. Then independent B5 on exact corrected graph. No GPU release; G7 dispatch veto and runtime readiness unresolved.'
lock=owner/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/state.lock'
with lock.open('a') as f:
 fcntl.flock(f,fcntl.LOCK_EX)
 for p,is_yaml in [(owner/'research-state.yaml',True),(owner/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if is_yaml else json.loads(p.read_text());d['n36_engineering_graph_rebinding']['status']='TERMINAL_GRAPH_REBOUND_REFERENCE_SCHEMA_BLOCKED_RECONCILED';d['n36_engineering_graph_rebinding']['terminal_review']=review;d['n36_controller_reference_schema_repair']=review;d['next_action']=next_step
  tmp=p.with_suffix(p.suffix+'.tmp-001554');tmp.write_text(yaml.safe_dump(d,sort_keys=False) if is_yaml else json.dumps(d,indent=2)+'\n');os.replace(tmp,p)
summary.update(at=now,turn=1554,next_bounded_step=next_step,completed_work='Reconciled normal executor termination and unchanged ledgers/source. Preserved all graph attempts. Corrected proof reference metadata in a new artifact; exact passive verifier passed and original failed as expected.',live_handles=[],STOP_present=False,terminal_review=review,target_met=False)
for role,pid in [('driver',268073),('coordinator',2234664)]:
 a=Path(f'/proc/{pid}/stat').read_text().split(') ')[-1].split();summary['live_handles'].append({'role':role,'pid':pid,'start_ticks':int(a[19]),'state':a[0],'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()})
summary['executor_observation']={'exit':0,'processes_absent':True,'release_enabled':False};summary['unresolved_evidence'][0]={'gate':'G6_exact_graph_rebinding','status':'CORRECTED_PROOF_REBIND_PENDING','reason':'New canonical reference proof passes unchanged verifier; prior graph binds preserved incompatible proof.'}
r=write(out/'operational-summary-v1.json',summary);(out/'operational-summary-v1.sha256').write_text(r['sha256']+'  operational-summary-v1.json\n');print(json.dumps({'review':review,'summary':r,'next':next_step},indent=2))
