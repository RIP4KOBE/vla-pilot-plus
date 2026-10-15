import json,pathlib,hashlib,collections,torch,datetime
root=pathlib.Path.cwd();out=root.parent/'autonomy_20261004/turns/000510'
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
ledger=root/'data/attempt-ledger.jsonl';lb=ledger.read_bytes();status=json.load(open(root.parent/'autonomy_20261004/turns/000469/launch-v2/controller-status.json'))
ids={x['attempt_id'] for x in status['outcomes'] if x['task_id'] in [4,5]};cells=[json.loads(x) for x in lb.splitlines() if json.loads(x).get('event')=='valid' and json.loads(x).get('attempt_id') in ids];results=[];manifest=[]
keep={'decision_context','n32_observation_context','n32_archive_eligible_opportunity','final_selection','executed_action','pre_reset_outcome'}
for cell in cells:
 p=pathlib.Path(cell['output_dir'])/'eds_eval/decision_evidence/episode_000'; idx=p/'events.jsonl';manifest.append(ref(idx));groups=collections.defaultdict(list)
 for line in idx.read_text().splitlines():
  b=json.loads(line)
  if not any(e['event'] in keep for e in b['events']):continue
  bp=p/b['bundle'];assert hashlib.sha256(bp.read_bytes()).hexdigest()==b['sha256'];manifest.append({'path':str(bp),'sha256':b['sha256']})
  for e in torch.load(bp,map_location='cpu',weights_only=False)['events']:
   if e['event'] in keep:groups[e['decision_id']].append(e)
 decisions=[];allgrips=[];targetpose=0
 for did,es in groups.items():
  kinds=collections.defaultdict(list)
  for e in es:kinds[e['event']].append(e['values'])
  acts=kinds['executed_action'];obs=kinds['pre_reset_outcome'];allgrips.extend(float(a['action_numpy'][-1]) for a in acts);targetpose+=sum(o.get('contemporaneous_target_pose') is not None for o in obs)
  if not kinds['final_selection']:continue
  f=kinds['final_selection'][0];ops=kinds['n32_archive_eligible_opportunity'];changed=[o for o in ops if o.get('candidate') is not None];sel=[o for o in changed if torch.equal(f['selected_latent'].squeeze(0),o['candidate'])]
  packet=kinds['n32_observation_context'][0]['packet'] if kinds['n32_observation_context'] else None
  row={'decision':did,'changed':len(changed),'selected_proposal':bool(sel),'reasons':dict(collections.Counter(o['reason'] for o in ops)),'executed_gripper':[float(a['action_numpy'][-1]) for a in acts],'selected_quality':f.get('selected_quality'),'target_pose_observations':sum(o.get('contemporaneous_target_pose') is not None for o in obs)}
  if sel:
   o=sel[0]; row['arrival_index']=o['arrival_index'];row['target_index']=o['identity']['target_index']; row['target_keypoint']=packet['keypoints'][row['target_index']].tolist();row['eef_before']=packet['observed_eef'].tolist();row['eef_after']=[v['observation']['robot0_eef_pos'].tolist() for v in obs];row['gripper_qpos_after']=[v['observation']['robot0_gripper_qpos'].tolist() for v in obs]
  if changed:row['proposal_diagnostics']=[{'arrival':o['arrival_index'],'reason':o['reason'],'selected_cell':o['selected_cell'],'selected_in_final':o in [] if False else torch.equal(f['selected_latent'].squeeze(0),o['candidate'])} for o in changed]
  decisions.append(row)
 results.append({'attempt_id':cell['attempt_id'],'task':cell['identity']['task_id'],'profile':cell['identity']['profile'],'success':cell['success'],'guided_decisions':decisions,'all_executed_steps':len(allgrips),'gripper_command_counts':dict(collections.Counter(allgrips)),'native_target_pose_observations':targetpose})
 print(cell['attempt_id'],len(decisions),'selected',sum(d['selected_proposal'] for d in decisions),flush=True)
assert ledger.read_bytes()==lb
report={'schema':'n32-dev-mechanism-observation-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Dev tasks4/5 only; selective native bundle extraction, not audit replay','ledger':ref(ledger),'cells':results,'limitations':['No causal attribution from unmatched trajectory states.','Tracked keypoint is not ground-truth object pose.','No inferred grasp from command sign or success proxy.'],'input_manifest':ref(out/'input-manifest.json') if False else None}
(out/'input-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');report['input_manifest']=ref(out/'input-manifest.json');(out/'mechanism-observation-v1.json').write_text(json.dumps(report,indent=2)+'\n')
