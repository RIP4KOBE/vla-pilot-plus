import os
assert os.environ['CUDA_VISIBLE_DEVICES']==''
import json,pathlib,torch,hashlib
O=pathlib.Path(__file__).resolve().parent;torch.set_num_threads(1);torch.set_num_interop_threads(1)
a=json.loads((O.parent.parent/'001137/action-link-v1.json').read_text());rows=[]
for c in a['cells']:
 steps=[696,704,712] if 't00' in c['attempt_id'] else [568,576,584];events=[]
 for b in c['bindings']:
  assert hashlib.sha256(pathlib.Path(b['path']).read_bytes()).hexdigest()==b['sha256']
  events += [e for e in torch.load(b['path'],map_location='cpu',weights_only=True)['events'] if e['global_step'] in steps]
 for step in steps:
  es=[e for e in events if e['global_step']==step];byseq={e['sequence']:e for e in es}
  score=next(e for e in es if e['event']=='scoring_inputs' and e['values']['scoring_scope']['role']=='canonical_offspring' and e['values']['scoring_scope']['iter_idx']==0)
  v=score['values'];plans=v['samples'];xyz=v['projected_xyz'];origin=torch.as_tensor(byseq[v['projection_origin_sequences'][15]]['values']['source_eef_position']);actions=plans[15,:8,[39,40,41]];start=origin.to(actions)
  def proj(delta,typ):
   if typ=='normal':s=delta.cumsum(0)
   elif typ=='sequential':
    acc=torch.zeros(3,dtype=delta.dtype);vals=[]
    for r in delta:acc=acc+r;vals.append(acc)
    s=torch.stack(vals)
   return torch.cat([start[None],start+s])
  candidates={
   'source_cpu':proj(actions*.01,'normal'),
   'fp32_multiply_then_native_cumsum':proj((actions.float()*.01).to(actions),'normal'),
   'native_multiply_sequential_sum':proj(actions*.01,'sequential'),
   'fp32_multiply_native_sequential_sum':proj((actions.float()*.01).to(actions),'sequential'),
   'fp32_all_then_cast':torch.cat([origin[None],origin+(actions.float()*.01).cumsum(0)]).to(actions),
  }
  rows.append({'attempt':c['attempt_id'],'step':step,'origin':origin.tolist(),'actions':actions.float().tolist(),'stored':xyz[15].float().tolist(),'comparisons':{k:{'exact':torch.equal(p,xyz[15]),'max_diff':float((p.float()-xyz[15].float()).abs().max()),'projection':p.float().tolist()} for k,p in candidates.items()}})
(O/'arithmetic-diagnostic-results-v1.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps([{k:r[k] for k in ['attempt','step']}|{'exact':{k:v['exact'] for k,v in r['comparisons'].items()}} for r in rows],indent=2))
