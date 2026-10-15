import json,pathlib,hashlib,datetime,math,os,sys,yaml
root=pathlib.Path.cwd();out=root.parent/'autonomy_20261004/turns/000510';sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as runner
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,v):
 t=p.with_name(p.name+'.tmp510');t.write_text(json.dumps(v,indent=2)+'\n');os.replace(t,p)
obs=json.loads((out/'mechanism-observation-v1.json').read_text());previous=json.loads((out.parent/'000509/terminal-reconciliation-v1.json').read_text()); assert ref(root/'data/attempt-ledger.jsonl')['sha256']==previous['ledger']['sha256']==obs['ledger']['sha256']
summary=[]
for c in obs['cells']:
 ds=c['guided_decisions']; row={k:c[k] for k in ['attempt_id','task','profile','success','all_executed_steps','gripper_command_counts','native_target_pose_observations']};row.update(guided_decisions=len(ds),changed_proposals=sum(d['changed'] for d in ds),selected_proposal_decisions=sum(d['selected_proposal'] for d in ds));row['selected_details']=[]
 for d in ds:
  if d['selected_proposal']:
   distances=[math.dist(x,d['target_keypoint']) for x in d['eef_after']];row['selected_details'].append({'decision':d['decision'],'arrival_index':d['arrival_index'],'executed_gripper':d['executed_gripper'],'distance_to_fixed_context_keypoint_at_arrival_m':distances[d['arrival_index']],'minimum_distance_to_fixed_context_keypoint_m':min(distances),'final_gripper_qpos':d['gripper_qpos_after'][-1]})
 summary.append(row)
assert [x['selected_proposal_decisions'] for x in summary if x['profile']=='N32']==[6,0]
next_action='Dev-only bounded source/trace review of the six task4 selected N32 proposals: compare recorded parent projected arrival with actual pre-reset EEF at arrival and actuator clipping, distinguishing fixed tracked keypoint from unknown ground-truth target pose. Then constraints-first ideation; no rerun, gate relaxation or protected-result access.'
review={'schema':'n32r3-dev-mechanism-root-review-v1','at':now,'source':'04d1255016fa13a2d467995b9e37a6a829356a1c','scientific_source':'1065f38122379a515b60a9a424f574330405b66f','terminal_review':ref(out.parent/'000509/terminal-reconciliation-v1.json'),'observations':ref(out/'mechanism-observation-v1.json'),'extraction_source':ref(out/'diagnose.py'),'cells':summary,'conclusions':['Task4 proposal content survives selection six times and reaches execution; selection loss alone does not explain this failure.','Task5 one changed proposal is not selected; the corresponding executed prefix is all -1 gripper commands.','All six inspected episodes lack contemporaneous ground-truth target pose observations; no claim of grasp or target motion is supported.','At task4 decision e0:d79:s624, projected arrival index2 corresponds to actual EEF distance about0.081m from the fixed context target keypoint. This is a diagnostic discrepancy, not a causal estimate or proof of object location.','Task4 and task5 controls differ in rollout length/trajectory; raw gripper totals cannot estimate a method effect.'],'next_action':next_action,'scientific_promotion':False,'goal_met':False,'ledger_unchanged':True,'gpu_dispatches':0,'audit_replay':False}
write(out/'mechanism-review-v1.json',review);rr=ref(out/'mechanism-review-v1.json');cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json'
with runner.locked(root/'data/qd-ed-state.lock'):
 s=yaml.safe_load((root/'research-state.yaml').read_text());c=json.loads(cp.read_text());assert s['active_controller'] is None and c['active_controller'] is None;assert ref(root/'data/attempt-ledger.jsonl')['sha256']==obs['ledger']['sha256']
 for d in [s,c]:d['n32r3_mechanism_review']=rr;d['next_action']=next_action;d['updated_at']=now
 tmp=root/'research-state.yaml.tmp510';tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));os.replace(tmp,root/'research-state.yaml');write(cp,c)
 tree=json.loads(tp.read_text());tree['nodes']['15.2']['n32r3_mechanism_review']=rr;write(tp,tree)
(out/'operational-summary.md').write_text(f'''Turn 510: bounded N32 development mechanism review

Source {review['source']}; scientific source {review['scientific_source']} unchanged. Driver PID268073/start97715947 and current coordinator PID2304131/start133172972 match boot2a1fa95f-ab0d-488c-a298-fc488ddd2af7. Closed controller1070042 and all four N32R3 workers absent. Prior turn509 exited0; its terminal closure and ledger reconciled. STOP absent and deadline2026-10-11T11:13:13Z not reached. No active GPU cohort or new dispatch.

Completed CPU-only selective hash-verified native trace extraction for matched development tasks4/5 C0/Q0/N32. Task4 N32:20 changed proposals,6 selected/executed decisions; task5 N32:1 changed,0 selected. One task4 projected arrival corresponds to actual EEF about8.1cm from the fixed context keypoint. All six episodes lack contemporaneous ground-truth target poses, so grasp/target motion remain unknown. Distinct control trajectories do not support causal attribution. Full observation and input manifest are bound by mechanism-review-v1.json SHA256 {rr['sha256']}.

Owning state/checkpoint/tree now link review. Ledger unchanged1326 rows/6659252 bytes/SHA256 {obs['ledger']['sha256']};442 dispatches/62.81145837588456 GPUh retained. No code, threshold, frozen plan, budget or protected-result changes.

Next bounded step: {next_action}

Original validation/formal/required-ablation goal remains unmet; no completion record created. The local driver continues autonomous coordination.
''')
print(json.dumps(rr))
