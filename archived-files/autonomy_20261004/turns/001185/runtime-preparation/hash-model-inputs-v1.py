import json,hashlib,os,resource,time,datetime
from pathlib import Path
out=Path(__file__).resolve().parent;a=json.loads((out/'authority-v1.json').read_text());root=Path(a['owning_worktree']);os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);resource.setrlimit(resource.RLIMIT_CPU,(300,300));start=time.monotonic();cpu=time.process_time()
def ref(p):
 p=Path(p);h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return {'path':str(p),'sha256':h.hexdigest()}
v=json.loads((root/'data/runtime-inventory.json').read_text());r=json.loads((out/'runtime-disabled-v1.json').read_text());files=v['checkpoint']+[row for e in v['hf_encoders'] for row in e['files']]+[v['dinov2']['weights']];verified=[]
for row in files:
 t=time.monotonic();p=Path(row['path']);actual=ref(p);assert actual['sha256']==row['sha256'],str(p);assert p.stat().st_size==row['size_bytes'];verified.append({**actual,'resolved_path':str(p.resolve()),'bytes':p.stat().st_size,'wall_seconds':time.monotonic()-t})
for e in v['hf_encoders']:
 snapshot=Path(e['snapshot']);assert {p.resolve() for p in snapshot.parent.iterdir() if p.is_dir()}=={snapshot.resolve()}
provider=r['frozen_stage_provider'];binary=ref(provider['cli_path']);assert binary['sha256']==provider['cli_sha256'];assert provider['model']=='gpt-6-astra' and provider['auth_mode']=='chatgpt'
seeds=root/'data/frozen-seed-plan.json';seed_meta=json.loads(seeds.read_text())
record={'schema':'n36-prospective-model-input-bindings-v1','worktree':str(root),'runtime_inventory_path':str(root/'data/runtime-inventory.json'),'runtime_inventory_sha256':ref(root/'data/runtime-inventory.json')['sha256'],'seed_plan_path':str(seeds),'seed_plan_sha256':ref(seeds)['sha256'],'run_name':seed_meta['run_name'],'input_contract_label':'input_repaired','verified_files':verified,'total_bytes_hashed':sum(r['bytes'] for r in verified),'encoder_snapshot_sets_unchanged':True,'provider_binary':binary,'provider_configuration':{'backend':provider['backend'],'model':provider['model'],'auth_mode':provider['auth_mode'],'public_config_sha256':provider['public_config_sha256']},'credential_files_read':False,'model_or_init_tensors_deserialized':False,'wall_seconds':time.monotonic()-start,'cpu_seconds':time.process_time()-cpu,'owning_inventory_not_mutated':True,'runtime_inventory_worktree_resolves':str(Path(v['worktree']).resolve()),'release_enabled':False}
(out/'prospective-input-bindings-v1.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:record[k] for k in ['total_bytes_hashed','wall_seconds','cpu_seconds','release_enabled']}))
