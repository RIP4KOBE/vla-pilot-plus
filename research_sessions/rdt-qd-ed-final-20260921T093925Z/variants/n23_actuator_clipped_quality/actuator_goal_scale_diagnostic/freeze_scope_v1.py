from pathlib import Path
import datetime,hashlib,json
H=Path(__file__).resolve().parent;V=H.parent;R=V.parents[1];W=R/'study_worktree';C=Path('/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/robosuite/controllers')
def digest(b):return hashlib.sha256(b).hexdigest()
def ref(p):return {'path':str(p.resolve()),'sha256':digest(p.read_bytes())}
s=V/'actuator-goal-scale-diagnostic-scope-v1.md';m=V/'planned-gripper-continuity-attempts-v1.json';d=V/'executed_proprioceptive_continuity_diagnostic/result-v1.json'
assert ref(s)['sha256']=='b2802ce980098453df6a75bc9e426ac1443bae9c8749cb5067ecaee128f94134'
assert ref(m)['sha256']=='cca36ad827d720aa7973e808d86db7fb00da961f44ba4203f57123626adc39f4'
assert ref(d)['sha256']=='d658ea7ab4a053a69b019dfa39d20035948e8c5d3af75ce1896f0d325e96f02a'
a=json.loads(m.read_text());sourcefiles={name:ref(W/name) for name in ['core/qd_actuator_clipped_quality.py','core/rdt_policy_steer.py','core/rdt_libero_action_converter.py','core/env_adapters/libero_adapter.py','third_party/libero_pro/libero/libero/envs/env_wrapper.py']}
for name in ['config/osc_pose.json','osc.py','base_controller.py']:sourcefiles['installed_robosuite/'+name]=ref(C/name)
rs={'schema':'n23-actuator-goal-scale-read-scope-v1','created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':ref(s),'attempt_manifest':ref(m),'closed_proprioception_result':ref(d),'source_commit':a['source_commit'],'source_files':sourcefiles,
 'attempts':[{'task':x['task'],'attempt_id':x['attempt_id'],'metrics':ref(Path(x['output_dir'])/'eds_eval/eds_metrics.jsonl')} for x in a['attempts']],
 'allowed_metric_fields':['qd_actuator_metadata','global_step','episode'],
 'comparisons':['A=0.01*clip(action_xyz,-1,1)','B=(clip(action_xyz,input_min,input_max)-midpoint_input)*abs(output_range)/abs(input_range)+midpoint_output'],
 'residual_sign':'formula increment minus observed EEF displacement','limits':{'actual_extraction_seconds':120,'engineering_reruns':2,'known_one_step_max':2876,'known_eight_step_max':356,'cpu_threads':2,'cuda_visible_devices':''},
 'excluded':['new native tensor bundles','runtime imports','reward/success/contact/object-pose features','fit/threshold/ranking','source/state/controller/budget writes']}
f=H/'read-scope-v1.json';assert not f.exists();f.write_text(json.dumps(rs,indent=2)+'\n');print(json.dumps({'manifest':ref(f),'source_files':len(sourcefiles),'metrics':4},indent=2))
