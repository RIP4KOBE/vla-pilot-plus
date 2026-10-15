import os,json,hashlib,time,resource,datetime
from pathlib import Path
OUT=Path(__file__).resolve().parent;TURNS=OUT.parent.parent;os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);t=time.monotonic();cpu=time.process_time()
a=json.loads((OUT/'authority-v1.json').read_text());root=Path(a['owning_worktree'])
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for x in iter(lambda:f.read(8*1024*1024),b''):h.update(x)
 return h.hexdigest()
def ref(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def write(n,v):
 p=OUT/n;p.write_text(json.dumps(v,indent=2)+'\n');return ref(p)
oldpath=TURNS/'000915/runtime.gpu-ready-v1.json';r=json.loads(oldpath.read_text());oldsource=json.loads((OUT/'source-owning-v1.json').read_text());sourceindex={str(root/x['path']):x['sha256'] for x in oldsource['files']}
# Preserve unused inherited asset commitments without touching nonselected init/task data.
needed={task[k] for task in r['tasks'].values() for k in ['bddl_path','init_path']}
checks=[];unread=[];changes=[];hashed_bytes=0
for row in r['files']:
 p=Path(row['path']);old=row['sha256']
 if p.suffix in ('.pruned_init','.bddl') and str(p) not in needed:
  unread.append(str(p));continue
 if str(p).startswith(str(root)) and str(p) not in sourceindex:
  # Non-source inherited tracked assets are retained, not broadened into protected input access.
  unread.append(str(p));continue
 actual=sha(p);hashed_bytes+=p.stat().st_size
 if str(p) in sourceindex:
  assert actual==sourceindex[str(p)];row['sha256']=actual
  if old!=actual:changes.append({'path':str(p),'old_sha256':old,'sha256':actual,'basis':'adopted Git source'})
 else:assert actual==old, str(p)
 checks.append({'path':str(p),'sha256':actual,'bytes':p.stat().st_size})
assert r['worktree']==str(root)
for key in ['cuda_egl_verified','provider_ready']:r[key]=False
r['cuda_egl_probe']=None
r['preparation']={'source':a['source'],'release_enabled':False,'historical_runtime':ref(oldpath),'historical_device_provider_receipts_are_not_current_readiness':True}
rr=write('runtime-disabled-v1.json',r)
write('runtime-files-verification-v1.json',{'checked':checks,'changed_adopted_source':changes,'inherited_unread_paths':unread,'hashed_bytes':hashed_bytes,'no_init_deserialization':True})
c=json.loads((OUT/'runtime-closure-candidate-v2.json').read_text());c['runtime']=rr
# Freeze new diagnostic code before its process starts. Harness is not production worker.
c['modules']['prepare_artifacts_v1']=ref(OUT/'prepare_artifacts_v1.py')
cr=write('runtime-closure-v1.json',c)
proof=json.loads((TURNS/'000916/runtime-v1/controller-semantics-v1.json').read_text());prior_proof=ref(TURNS/'000916/runtime-v1/controller-semantics-v1.json')
for k,reference in proof['review_evidence'].items():
 assert sha(reference['path'])==reference['sha256'];e=json.loads(Path(reference['path']).read_text())
 for row in e['sources']:
  actual=sha(row['path'])
  if actual!=row['sha256']:
   assert row['path']==str(root/'core/env_adapters/libero_adapter.py')
   diff=json.loads((OUT/'controller-adapter-static-diff-v1.json').read_text());assert diff['changed_functions']==['LiberoAdapter.delta_actions_to_ee_trajectory'] and row['sha256']==diff['old_sha256'] and actual==diff['new_sha256']
   row['sha256']=actual
 e.update(runtime=rr,rebound_from=reference,source_commit=a['source'],binding_review='Reused root-reviewed controller semantics. Exact AST identity of all adapter functions except projection; no constructor/action-forwarding change. This rebind needs independent root review before release.')
 proof['review_evidence'][k]=write('controller-'+k+'-v1.json',e)
proof.update(runtime=rr,rebound_from=prior_proof,scope='Inherited ROOT_REVIEWED controller semantics with candidate runtime rebind; root must independently review this rebind. No live instance or physical gain certification.')
pr=write('controller-semantics-v1.json',proof)
# Static prospective inventory, independently chosen filesystem roots; never learned from /proc maps.
site=Path('/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages')
paths=set()
for base in [site/'torch',site/'nvidia',site/'torchvision']:
 for p in base.rglob('*.so*'):
  if p.is_file():paths.add(p.resolve())
for p in Path('/usr/lib/x86_64-linux-gnu').glob('libcuda.so*'):
 if p.is_file():paths.add(p.resolve())
libs=[ref(p) for p in sorted(paths)];nativebytes=sum(p.stat().st_size for p in paths)
write('native-libraries-static-v1.json',{'libraries':libs,'selection_roots':[str(site/'torch'),str(site/'nvidia'),str(site/'torchvision'),'/usr/lib/x86_64-linux-gnu/libcuda.so*'],'selection':'static files only; not a mapped receipt','bytes_hashed':nativebytes})
write('build-inputs-timing-v1.json',{'wall_seconds':time.monotonic()-t,'cpu_seconds':time.process_time()-cpu,'runtime_bytes_hashed':hashed_bytes,'native_bytes_hashed':nativebytes,'static_native_libraries':len(libs),'runtime':rr,'runtime_closure':cr,'controller':pr,'release_enabled':False})
print(json.dumps({'wall_seconds':time.monotonic()-t,'cpu_seconds':time.process_time()-cpu,'native_libraries':len(libs),'runtime_checked':len(checks),'inherited_unread':len(unread),'native_bytes':nativebytes}))
