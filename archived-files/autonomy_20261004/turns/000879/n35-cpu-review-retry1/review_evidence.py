import os
os.environ.update(OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1')
import json,hashlib,torch
from pathlib import Path
torch.set_num_threads(2);torch.set_num_interop_threads(1)
out=Path(__file__).resolve().parent
base=out.parents[1]
ex=base/'000877/native-mechanism-extraction-v1.json'
t=next(t for t in json.loads(ex.read_text())['tasks'] if t['attempt_id']=='n34r11_dev_t06_n34_20261008')
refs={Path(r['path']).name:r for r in t['bundles']}
names={'decision_context','n34_observation_context','n34_capture_dwell_opportunity','final_selection','policy_action_decode','canonical_candidate_identity','executed_action','action_dispatch','decision_committed','step_returned','n34_archive_update','n34_canonical_cache'}
events=[]; used=[]
for line in Path(t['event_index']['path']).open():
 r=json.loads(line)
 if r['bundle'] not in refs:continue
 if not any(536<=e['global_step']<=544 and e['event'] in names for e in r['events']):continue
 p=Path(refs[r['bundle']]['path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==refs[r['bundle']]['sha256'];used.append(refs[r['bundle']])
 for e in torch.load(p,map_location='cpu',weights_only=True)['events']:
  if 536<=e['global_step']<=544 and e['event'] in names:
   e['_bundle']=str(p);events.append(e)
def get(step,name):return next(e for e in events if e['global_step']==step and e['event']==name)
def evref(e):return dict(bundle=e['_bundle'],sequence=e['sequence'],event=e['event'],decision_id=e['decision_id'],global_step=e['global_step'])
def raw(x):return x.detach().contiguous().view(torch.uint8).numpy().tobytes()
def digest(x):return hashlib.sha256(raw(x)).hexdigest()
def same(x,y):return x.dtype==y.dtype and x.shape==y.shape and raw(x)==raw(y)
ctx={s:get(s,'decision_context') for s in (536,544)}
op={s:get(s,'n34_capture_dwell_opportunity') for s in (536,544)}
f=get(536,'final_selection'); dec=get(536,'policy_action_decode'); ci=next(e for e in events if e['global_step']==536 and e['event']=='canonical_candidate_identity' and e['values']['iter_idx']==0)
proposal=op[536]['values']['candidate']; selected=f['values']['selected_latent'].reshape(64,128)
a=dict(status='PASS',guidance=ctx[536]['values']['use_guidance'],reason=op[536]['values']['reason'],proposal_selected_native_bytes_equal=same(proposal,selected),proposal_native_bytes_sha256=digest(proposal),selected_native_bytes_sha256=digest(selected),fingerprint=f['values']['selected_canonical_fingerprint'],slot15_fingerprint=ci['values']['fingerprints'][15],refs=[evref(e) for e in (ctx[536],op[536],ci,f)])
assert a['guidance'] and a['reason']=='observed_close_dwell' and a['proposal_selected_native_bytes_equal'] and a['fingerprint']==a['slot15_fingerprint']
linked=[]
for s in range(536,544):
 e=get(s,'executed_action');v=e['values']; action=torch.as_tensor(v['action_numpy']).reshape(7); expected=dec['values']['action_chunk'].reshape(-1,7)[s-536]
 linked.append(dict(step=s,decision_id=e['decision_id'],gripper=action[-1].item(),decoded_action_equal=torch.equal(action,expected),same_decision=e['decision_id']==f['decision_id']==dec['decision_id'],ref=evref(e),available_value_fields=list(v)))
assert all(r['gripper']>0 and r['decoded_action_equal'] and r['same_decision'] for r in linked)
b=dict(status='PASS',actions=linked,decode_ref=evref(dec),decoded_selected_matches_final=torch.equal(dec['values']['selected_latent'].reshape(64,128),selected.float()),decode_fingerprint=dec['values'].get('selected_canonical_fingerprint'))
ident={s:op[s]['values']['identity'] for s in (536,544)}
c=dict(status='PASS',identities=ident,contexts={s:{k:ctx[s]['values'].get(k) for k in ('stage','previous_stage','stage_changed','use_guidance','previous_decision_id')} for s in (536,544)},refs=[evref(e) for e in (ctx[536],ctx[544],op[536],op[544])])
assert all(ident[536][k]==ident[544][k] for k in ('episode','stage','provider','target_index','tracker_instance','tracker_generation','target_status'))
assert ident[536]['target_status']=='tracked' and ctx[536]['values']['stage']==ctx[544]['values']['stage']==ident[536]['stage'] and ctx[544]['values']['use_guidance'] is True
jaws={s:get(s,'n34_observation_context')['values']['packet']['gripper_qpos'].tolist() for s in (536,544)}
sep={s:jaws[s][0]-jaws[s][1] for s in jaws}
import math
assert all(math.isfinite(x) for row in jaws.values() for x in row) and sep[544]<sep[536]
d=dict(status='PASS',qpos=jaws,separation_m=sep,strict_decrease_m=sep[536]-sep[544],refs=[evref(get(s,'n34_observation_context')) for s in (536,544)])
r=dict(schema='n35-bounded-cpu-facts-v1',attempt_id=t['attempt_id'],gates=dict(a=a,b=b,c=c,d=d),verified_bundles=used)
# CPU copy only; does not call production proposal/search/model code.
p=op[544]['values']['source']['plan'];q=p.clone();q[:8,10]=1
r['native_copy_check']=dict(source_ref=evref(op[544]),source_archive=op[544]['values']['archive'],source_iteration=op[544]['values']['source']['iteration'],source_row=op[544]['values']['source']['row'],shape=list(p.shape),dtype=str(p.dtype),native_gripper_before=p[:8,10].tolist(),native_gripper_after=q[:8,10].tolist(),original_bytes_sha256=digest(p),candidate_bytes_sha256=digest(q),nonidentical=not same(p,q),translation_rotation_unchanged=same(p[:,39:45],q[:,39:45]),later_actions_unchanged=same(p[8:],q[8:]),changed_coordinates=torch.nonzero(p!=q).tolist())
archive_event=next(e for e in events if e['global_step']==544 and e['event']=='n34_archive_update' and e['values']['iter_idx']==-1)
best=min(archive_event['values']['archive'],key=lambda x:(-x['reward'],x['fingerprint'],x['cell_id']))
assert best['cell_id']==14 and best['fingerprint']==op[544]['values']['archive']['fingerprint']
assert best['reward']==op[544]['values']['source']['quality'].item()
r['ordinary_archive_best_proof']=dict(ref=evref(archive_event),best=best,ordering=['descending reward','ascending fingerprint','ascending cell_id'],entry_count=len(archive_event['values']['archive']))
checks=[]
for st in range(536,544):
 dispatch=get(st,'action_dispatch');returned=get(st,'step_returned')
 checks.append(dict(step=st,dispatch_ref=evref(dispatch),returned_ref=evref(returned),dispatch_values=dispatch['values'],return_termination_fields={k:v for k,v in returned['values'].items() if k in ('terminated','truncated')},same_decision=dispatch['decision_id']==returned['decision_id']==f['decision_id']))
assert all(x['same_decision'] for x in checks)
r['execution_return_checks']=checks
r['source_refs']=[]
for name,expected_hash in op[544]['values']['source_hashes'].items():
 if name not in ['core/qd_observed_jaw_approach.py','core/rdt_libero_action_converter.py','core/qd_capture_dwell.py','core/rdt_policy_steer.py','core/qd_ed.py','core/env_adapters/libero_adapter.py','main.py']:continue
 src=Path.cwd()/name; actual=hashlib.sha256(src.read_bytes()).hexdigest()
 r['source_refs'].append(dict(path=str(src),sha256=actual,bound_event_sha256=expected_hash,matches_bound_event=actual==expected_hash))
assert all(x['matches_bound_event'] for x in r['source_refs'])
(out/'bounded-facts-v1.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({'gates':{k:v['status'] for k,v in r['gates'].items()},'native_copy_check':r['native_copy_check']},indent=2))
