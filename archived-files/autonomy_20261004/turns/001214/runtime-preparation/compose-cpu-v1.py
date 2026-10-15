"""Bounded CPU preparation. No source writes, runtime launches, or approval."""
import os, sys, json, hashlib, subprocess, datetime, time, traceback, tarfile, io
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=Path.cwd().resolve(); TURNS=OUT.parent.parent
START=time.monotonic(); SOURCE='066f2bf57e05111fea329ff7c393ac3e002d7c0f'
STOP=ROOT.parent.parent.parent/'autonomy_20261004/STOP'
def guard():
 assert not os.path.lexists(STOP), 'STOP present'
 assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
 assert time.monotonic()-START<1500
 assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def ref(p):
 p=Path(p).resolve();return {'path':str(p),'sha256':sha(p)}
def read(r):
 assert sha(r['path'])==r['sha256'];return json.loads(Path(r['path']).read_text())
def write(p,d):
 guard();p=OUT/p;assert p.is_relative_to(OUT) and not p.exists();p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(d,indent=2)+'\n');return ref(p)
def git(*args):return subprocess.check_output(['git','--no-replace-objects','-C',str(ROOT),*args])
def ledger_checks(a):
 return {k:{**r,'actual_sha256':sha(r['path']),'actual_bytes':Path(r['path']).stat().st_size,'unchanged':sha(r['path'])==r['sha256'] and Path(r['path']).stat().st_size==r['bytes']} for k,r in a['ledger_prefixes'].items()}
guard();os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
assert git('rev-parse','HEAD').decode().strip()==SOURCE
assert git('status','--porcelain')==b''
a=json.loads((OUT/'authority-v1.json').read_text())
assert a['implementation_worktree']==str(ROOT) and a['output_directory']==str(OUT) and a['source']==SOURCE
for k in ['standing_authority','source_adoption']:read(a[k])
initial=ledger_checks(a);assert all(r['unchanged'] for r in initial.values())
write('authority-verification-v1.json',{'authority':ref(OUT/'authority-v1.json'),'source':SOURCE,'clean':True,'ledger_checks':initial,'STOP_present':False,'CUDA_VISIBLE_DEVICES':'','at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
DEST=OUT/'runtime-candidate-v1';DEST.mkdir()
sys.path.insert(0,str(ROOT))
from scripts import qd_ed_n36_bridge as b, qd_ed_n36_contract as c, qd_ed_n36_recovery as recovery
from scripts import qd_ed_n36_build as native
from scripts.qd_ed_n34_controller import verify_semantics
from scripts.qd_ed_n36_prepare import prepare
oldplan=read(ref(TURNS/'001199/plan.frozen-v2.json')); oldruntime=read(oldplan['runtime']);oldroot=oldruntime['worktree']
protocol_ref={'path':str(TURNS/'001205/identity-repair/protocol.n36r1.unsigned-v1.json'),'sha256':'d76046f9e697831114b04f23e1db3746e614d504a018e2923fdbc4e3f927b3ce'}
protocol=read(protocol_ref); accounting=read(protocol['accounting'])
native_ref={'path':str(TURNS/'001203/recovery-preparation/native-build-n36r1.draft-v1.json'),'sha256':'3e7e4f522f8d463671e7fe83bef4762f45f0ab0e32298959e38b8357998052d7'}
read(native_ref)
checks={};errors=[]
def check(name,fn):
 guard();t=time.monotonic()
 try:
  val=fn();checks[name]={'status':'PASS','seconds':time.monotonic()-t};return val
 except Exception as e:
  checks[name]={'status':'FAIL','error':repr(e),'seconds':time.monotonic()-t}
  errors.append({'operation':name,'error':repr(e),'traceback':traceback.format_exc()});return None
# Materialization remains entirely under OUT. Strict source gate still requires ROOT files.
materialized=[];missing=[]
for sub in b.closure.PINNED_SUBMODULES:
 pin,db=b.closure.submodule_pin(ROOT,sub)
 data=subprocess.check_output(['git','--no-replace-objects','--git-dir',str(db),'archive','--format=tar',pin],cwd=ROOT)
 name=Path(sub).name;dest=DEST/'materialized'/name;dest.mkdir(parents=True)
 with tarfile.open(fileobj=io.BytesIO(data)) as tf:
  for m in tf.getmembers():
   assert not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
  tf.extractall(dest,filter='data')
 paths=b.closure.submodule_paths(ROOT,sub)
 for rel in sorted(paths):
  if not (ROOT/rel).is_file():missing.append(rel)
 materialized.append({'submodule':sub,'pin':pin,'archive_sha256':hashlib.sha256(data).hexdigest(),'archive_bytes':len(data),'staged_path':str(dest),'required_destination':str(ROOT/sub),'required_source_files':len(paths),'not_installed':True})
write('materialization-v1.json',materialized)
# Correct source-dependent lexical paths; no old readiness survives.
def relocate(v):
 if isinstance(v,str):return v.replace(oldroot,str(ROOT))
 if isinstance(v,list):return [relocate(x) for x in v]
 if isinstance(v,dict):return {k:relocate(x) for k,x in v.items()}
 return v
runtime=relocate(oldruntime)
for k in ['cuda_egl_verified','provider_ready','metadata_mapping_verified']:runtime[k]=False
runtime['cuda_egl_probe']=None;runtime['provider_evidence']=None
runtime['gpu_mapping']={k:oldruntime['gpu_mapping'][k] for k in ['physical_gpu','egl_device_index','uuid','pci_bus_id','driver_version']}
runtime['gpu_mapping'].update(cuda_egl_verified=False,metadata_mapping_verified=False,drm_pci_verified=False)
runtime['preparation']={'source':SOURCE,'release_enabled':False,'runtime_ready':False,'historical_runtime':oldplan['runtime'],'historical_device_provider_receipts_are_not_current_readiness':True,'status':'BLOCKED_SOURCE_MATERIALIZATION','no_provider_or_device_probe':True}
source_changes=[];pending=[]
for row in runtime['files']:
 p=Path(row['path'])
 if p.is_relative_to(ROOT):
  rel=str(p.relative_to(ROOT))
  if rel.startswith(('third_party/rdt/','third_party/lerobot/')):
   dest=DEST/'materialized'/Path(rel).parts[1]/Path(*Path(rel).parts[2:])
   assert dest.is_file(),str(dest)
   actual=sha(dest);assert actual==row['sha256'],rel
   pending.append({'path':str(p),'staged_path':str(dest),'sha256':actual})
  elif p.suffix in ('.py','.yaml','.yml','.json') and p.is_file():
   actual=sha(p)
   if actual!=row['sha256']:source_changes.append({'path':str(p),'old_sha256':row['sha256'],'sha256':actual})
   row.update(sha256=actual,size_bytes=p.stat().st_size,resolved_path=str(p.resolve()))
rr=write('runtime-candidate-v1/runtime.disabled-candidate.json',runtime)
closure=read(oldplan['runtime_closure']);closure['runtime']=rr
cr=write('runtime-candidate-v1/runtime-closure.candidate.json',closure)
proof=read(oldplan['controller_semantics'])
for key,evref in list(proof['review_evidence'].items()):
 ev=read(evref)
 for row in ev['sources']:
  assert sha(row['path'])==row['sha256']
  replacement=relocate(row['path']);assert sha(replacement)==row['sha256'];row['path']=replacement
 ev.update(runtime=rr,rebound_from=evref,source_commit=SOURCE,binding_review='Unchanged reviewed controller source bytes; prospective checkout/runtime rebind only. No new root approval; independent root rebind review remains required.')
 proof['review_evidence'][key]=write('runtime-candidate-v1/controller-'+key+'.candidate.json',ev)
proof.update(runtime=rr,rebound_from=oldplan['controller_semantics'],scope='Inherited ROOT_REVIEWED semantics for unchanged controller bytes only. Candidate rebind is not root production review; no device/live controller readiness.',gpu_authorized=False,scientific_promotion=False)
pr=write('runtime-candidate-v1/controller-semantics.candidate.json',proof)
metadata={k:oldplan[k] for k in ['run_name','input_contract_label']};metadata['attempt_identity']='episode_key'
for kind,filename in [('runtime_inventory','runtime-inventory.json'),('seed_plan','frozen-seed-plan.json')]:
 path=ROOT/'data'/filename;assert sha(path)==oldplan[kind+'_sha256'];metadata[kind+'_path']=str(path);metadata[kind+'_sha256']=sha(path)
write('runtime-candidate-v1/input-bindings.json',{**metadata,'source_commit':SOURCE,'runtime':rr,'provenance_plan':ref(TURNS/'001199/plan.frozen-v2.json'),'unchanged_inventory_and_seed_bytes':True,'runtime_ready':False})
plan={'schema':'n36r1-blocked-preparation-draft-v1','frozen':False,'release_enabled':False,'runtime_ready':False,'worktree':str(ROOT),'source':None,'scientific_source':None,'required_source_commit':SOURCE,'artifact_root':str(DEST/'draft'/'prospective-artifacts'),'runtime':rr,'runtime_closure':cr,'controller_semantics':pr,'native_build':native_ref,'cohort':c.RECOVERY_COHORT,'protocol':protocol_ref,'protocol_review':protocol['inherited_protocol_review'],'accounting':protocol['accounting'],'episodes':c.expected_rows(ROOT,cohort=c.RECOVERY_COHORT),'limits':c.LIMITS,'worker_contract':c.WORKER_CONTRACT,'deadline':c.DEADLINE,'stop_path':c.stop_path(ROOT),'root_review':None,'authority':None,'execution_release':None,'phase_authorization':{'dev':False,'validation':False,'formal':False},'expected_manifests':{},**metadata}
check('protocol_accounting_inheritance',lambda:recovery.validate_protocol(plan))
check('stage_provider_contract',lambda:b.runner.stage_overrides(runtime))
check('runtime_closure_static',lambda:b.closure.verify_runtime(closure,rr))
check('controller_semantics_static',lambda:verify_semantics(pr,rr,closure))
check('native_build_static_bytes',lambda:native.manifest(native_ref))
# Actual existing preparation function: fail closed; no hand-made source/manifest substitute.
check('prepare_all40',lambda:prepare(DEST/'draft',rr,runtime_closure_ref=cr,controller_semantics_ref=pr,native_build_ref=native_ref,root=ROOT,recovery_protocol_ref=protocol_ref))
assert checks['prepare_all40']['status']=='FAIL', 'unexpected success needs separately reviewed continuation'
plan['blockers']=['Pinned RDT/LeRobot source absent in isolated worktree; strict prepare failed before all40 generation. All writes restricted to output directory; staged dependencies not installed.','No root accounting authority, detached production review/release or current device/provider/native readiness.']
write('runtime-candidate-v1/plan.blocked-draft.json',plan)
write('source-materialization-blocker-v1.json',{'source':SOURCE,'missing_source_paths':missing,'missing_source_count':len(missing),'materialization':ref(OUT/'materialization-v1.json'),'runtime_source_changes':source_changes,'pending_runtime_files':pending,'no_source_inventory_fabricated':True})
# Check only exposed original aborted identity, without reading protected outcomes.
events=[]
with open(a['ledger_prefixes']['attempt-ledger.jsonl']['path']) as f:
 for line in f:
  if 'n36_dev_t00_c0_001147' in line:events.append(json.loads(line))
check('original_aborted_charge_retained',lambda:recovery.preserve_charge(events))
write('checks-v1.json',checks);write('errors-v1.json',errors)
write('final-preservation-v1.json',{'source':git('rev-parse','HEAD').decode().strip(),'git_status':git('status','--porcelain').decode(),'ledger_checks':ledger_checks(a),'STOP_present':os.path.lexists(STOP),'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-START})
print(json.dumps({'status':'BLOCKED_SOURCE_MATERIALIZATION','checks':checks,'missing_source_files':len(missing),'all40_actual_manifests':0,'runtime_ready':False}))
