from pathlib import Path
import os,json,hashlib,time
J=Path(__file__).resolve().parent;os.sched_setaffinity(0,{0,1});start=time.process_time()
for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='2'
def digest(data):return hashlib.sha256(data).hexdigest()
def ref(p,cap=16*1024*1024):
 p=Path(p);assert p.is_file() and not p.is_symlink() and p.stat().st_size<=cap
 data=p.read_bytes();return {'path':str(p.resolve()),'sha256':digest(data),'bytes':len(data)},data
def bound(r):
 got,data=ref(r['path']);assert got['sha256']==r['sha256'];return got,json.loads(data)
release_ref,release=bound({'path':str(J/'root-cpu-repair-release-v2.json'),'sha256':'59af0355a8733626ff78006db6b99523f29f625973fb2c9bda9bde606e61b6ab'})
scope_ref,_=ref(J/'cpu-repair-scope-v2.md');assert scope_ref['sha256']=='5497de51af1f881431a844cc351287b88181cf21d4d9cc97a3336eeee4704fd7'
review_ref,review=bound(release['closed_execution_review']);assert review['source_commit']==release['base_source_commit']
bad=review['invalid_attempt'];aid=bad['attempt_id'];assert aid.endswith('__n30_r1_dev_t00_n30_20261003__2138c682c5a7')
out=Path(bad['attempt_result']['path']).parent;ep=out/'eds_eval/decision_evidence/episode_000'
metadata={'scope':scope_ref,'release':release_ref,'review':review_ref}
for k in ('attempt_result','receipt','context','runner_log'):
 metadata[k],data=ref(bad[k]['path']);assert metadata[k]['sha256']==bad[k]['sha256']
 if k=='context':context=json.loads(data)
metadata['plan'],plan=bound(context['plan']);assert metadata['plan']['sha256']==review['plan']['sha256']
metadata['runtime'],runtime=bound(context['runtime']);metadata['source_manifest'],source=bound(review['source'])
assert context['source']==source and source['commit']==release['base_source_commit'] and context['attempt_id']==aid
for k,p in [('index',ep/'events.jsonl'),('status',ep/'status.json'),('metrics',out/'eds_eval/eds_metrics.jsonl'),('compute',out/'eds_eval/episode_compute.jsonl')]:
 metadata[k],data=ref(p)
 if k=='index':index=[json.loads(s) for s in data.splitlines() if s]
 if k=='status':status=json.loads(data)
assert status['complete'] is True and status['failed'] is False and status['pending_action'] is False and status['bundles']==len(index)<=2500
bundles=[];sequence=0
for i,row in enumerate(index,1):
 name=f'bundle_{i:06d}.pt';p=ep/name;assert row['bundle']==name and p.is_file() and not p.is_symlink() and p.resolve().parent==ep.resolve()
 assert row['first_sequence']==sequence+1 and row['last_sequence']==row['events'][-1]['sequence']
 for e in row['events']:sequence+=1;assert e['sequence']==sequence
 bundles.append({'path':str(p.resolve()),'sha256':row['sha256'],'bytes':p.stat().st_size,'first_sequence':row['first_sequence'],'last_sequence':row['last_sequence'],'events':len(row['events'])})
assert len(bundles)==2250 and sum(x['bytes'] for x in bundles)==297071656<512*1024*1024
cache=Path(runtime['tasks']['0']['cache_dir']).resolve()
providers=[{'path':str(Path(f['path']).resolve()),'sha256':f['sha256'],'bytes':Path(f['path']).stat().st_size} for f in runtime['files']
 if Path(f['path']).resolve().is_relative_to(cache) and Path(f['path']).suffix in {'.txt','.py'}]
assert providers and all(p['bytes']<=1024*1024 for p in providers)
result={'schema':'n30-terminal-feedback-diagnostic-input-v1','attempt_id':aid,'base_commit':source['commit'],'episode_root':str(ep.resolve()),
 'metadata':metadata,'bundles':bundles,'provider_sources':providers,'bundle_count':len(bundles),'bundle_bytes':sum(x['bytes'] for x in bundles),
 'events':sequence,'native_load_count':0,'inventory_index_reads':1,'inventory_cpu_seconds':time.process_time()-start,
 'max_cpu_seconds':900,'threads':2,'max_bundle_bytes':512*1024*1024,'max_bundles':2500,'max_index_bytes':16*1024*1024,
 'real_old_replays':1,'real_repaired_replays':1,'gpu_release':False,'original_receipt_stays_invalid':True}
p=J/'input-manifest.frozen.v1.json'
with p.open('x') as f:f.write(json.dumps(result,indent=2)+'\n')
print(json.dumps({'manifest_sha256':digest(p.read_bytes()),'bundle_count':len(bundles),'bundle_bytes':result['bundle_bytes'],'events':sequence,
 'provider_sources':[(p['path'],p['bytes']) for p in providers],'metadata_bytes':sum(x['bytes'] for x in metadata.values()),'cpu_seconds':result['inventory_cpu_seconds']}))
