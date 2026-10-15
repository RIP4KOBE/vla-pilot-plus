import collections, hashlib, json, pathlib, time
ROOT=pathlib.Path(__file__).resolve().parent
W=pathlib.Path.cwd()
def binding(p):
 b=p.read_bytes();return {'path':str(p.resolve()),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
rows=[json.loads(l) for l in (W/'data/attempt-ledger.jsonl').read_text().splitlines()]
rows=[r for r in rows if r.get('event')=='valid' and r.get('identity',{}).get('iteration')=='N31_CAPTURE_DWELL_PROPOSAL_DEV_20261004' and r['identity']['profile'] in ['Q0','N31']]
assert len(rows)==12 and len({(r['identity']['task_id'],r['identity']['profile']) for r in rows})==12
inputs=[]
for r in rows:
 p=pathlib.Path(r['output_dir'])/'eds_eval/decision_evidence/episode_000/events.jsonl'
 inputs.append(dict(binding(p),identity=r['identity']))
scope={'schema':'n31-native-metadata-scope-v1','inputs':inputs,'read_scope':'JSON manifests only; no tensor/video payload reads','cpu_seconds_limit':120,'gpu_dispatch':False,'protected_data_access':False}
(ROOT/'scope.json').write_text(json.dumps(scope,indent=2)+'\n')
t0=time.process_time();results=[]
for inp in inputs:
 p=pathlib.Path(inp['path']);assert binding(p)['sha256']==inp['sha256']; counts=collections.Counter();decisions={};bundles=[]
 for line in p.open():
  b=json.loads(line);bundle={k:v for k,v in b.items() if k!='events'};bundle['bytes_on_disk']=(p.parent/b['bundle']).stat().st_size;bundles.append(bundle)
  for e in b['events']:
   counts[e['event']]+=1
   if e['event']=='projection_origin' or e['event']=='provider_return':continue
   d=decisions.setdefault(e['decision_id'],{})
   d.setdefault(e['event'],[]).append({'sequence':e['sequence'],'global_step':e.get('global_step'),'bundle':b['bundle']})
 results.append({'identity':inp['identity'],'manifest':inp,'counts':dict(counts),'decisions':decisions,'bundles':bundles})
summary={'schema':'n31-native-metadata-inventory-v1','results':results,'cpu_seconds':time.process_time()-t0,'limitations':'Manifest metadata does not contain proposal changed/selected payload flags; cannot infer selected decision IDs from opportunity or final_selection presence. Payload decoding required. Bundle hashes are recorded commitments, not reverified payloads.'}
(ROOT/'inventory.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps([{'identity':r['identity'],'bundles':len(r['bundles']),'decisions':len(r['decisions']),'bytes':sum(b['bytes_on_disk'] for b in r['bundles'])} for r in results],indent=2))
print('cpu_seconds',summary['cpu_seconds'])
