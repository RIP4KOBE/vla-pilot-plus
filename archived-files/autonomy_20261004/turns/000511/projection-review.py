import pathlib,json,hashlib,collections,torch,math,datetime
root=pathlib.Path.cwd();out=root.parent/'autonomy_20261004/turns/000511';prev=out.parent/'000510'
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
ob=json.loads((prev/'mechanism-observation-v1.json').read_text());cell=next(c for c in ob['cells'] if c['task']==4 and c['profile']=='N32');selected={d['decision'] for d in cell['guided_decisions'] if d['selected_proposal']};groups=collections.defaultdict(list);inputs=[]
for r in json.loads((prev/'input-manifest.json').read_text()):
 if 't04_n32' not in r['path'] or not r['path'].endswith('.pt'):continue
 p=pathlib.Path(r['path']);assert ref(p)['sha256']==r['sha256'];es=torch.load(p,map_location='cpu',weights_only=False)['events']
 relevant=[e for e in es if e['decision_id'] in selected]
 if relevant:inputs.append(r)
 for e in relevant:groups[e['decision_id']].append(e)
rows=[]
for did,es in groups.items():
 k=collections.defaultdict(list)
 for e in sorted(es,key=lambda x:x['sequence']):k[e['event']].append(e['values'])
 f=k['final_selection'][0];matches=[o for o in k['n32_archive_eligible_opportunity'] if o.get('candidate') is not None and torch.equal(o['candidate'],f['selected_latent'].squeeze(0))];o=matches[0];parent=next(p for p in o['parents'] if p['cell_id']==o['selected_cell'])['source'];a=o['arrival_index'];packet=k['n32_observation_context'][0]['packet'];target=packet['keypoints'][o['identity']['target_index']].double();actual=torch.tensor([v['observation']['robot0_eef_pos'].tolist() for v in k['pre_reset_outcome']],dtype=torch.float64);proj=parent['projection'].double();acts=torch.tensor([v['action_numpy'].tolist() for v in k['executed_action']],dtype=torch.float64);origin=parent['source_origin'].double();translation=parent['plan'][:8,39:42].double()
 row={'decision':did,'arrival_index':a,'matching_proposal_occurrences':len(matches),'selected_parent_cell':o['selected_cell'],'projected_at_arrival':proj[a].tolist(),'actual_at_arrival':actual[a].tolist(),'fixed_keypoint':target.tolist(),'projection_actual_distance_at_arrival_m':float(torch.linalg.vector_norm(proj[a]-actual[a])),'projected_target_distance_m':float(torch.linalg.vector_norm(proj[a]-target)),'actual_fixed_target_distance_m':float(torch.linalg.vector_norm(actual[a]-target)),'origin_observation_distance_m':float(torch.linalg.vector_norm(origin-packet['observed_eef'].double())),'commands_through_arrival':acts[:a+1].tolist(),'translation_components_outside_unit_interval_through_arrival':int((acts[:a+1,:3].abs()>1).sum()),'max_abs_translation_through_arrival':float(acts[:a+1,:3].abs().max()),'parent_translation_matches_executed_through_arrival':bool(torch.equal(translation[:a+1],acts[:a+1,:3])),'parent_projection_displacements':(proj-origin).tolist(),'actual_displacements':(actual-origin).tolist(),'clipped_point01_arithmetic_at_arrival':(origin+acts[:a+1,:3].clamp(-1,1).sum(0)*.01).tolist(),'ground_truth_target_pose':'Unknown'}
 rows.append(row)
assert len(rows)==6
report={'schema':'n32-selected-projection-observation-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'six selected proposal decisions, development task4 only; no native audit replay','previous_review':ref(prev/'mechanism-review-v1.json'),'input_bundles':inputs,'rows':rows,'extraction':ref(out/'projection-review.py'),'ledger':ref(root/'data/attempt-ledger.jsonl')}
(out/'projection-observation-v1.json').write_text(json.dumps(report,indent=2)+'\n')
for r in rows:print({k:r[k] for k in ['decision','arrival_index','projection_actual_distance_at_arrival_m','actual_fixed_target_distance_m','translation_components_outside_unit_interval_through_arrival','max_abs_translation_through_arrival','parent_translation_matches_executed_through_arrival']})
