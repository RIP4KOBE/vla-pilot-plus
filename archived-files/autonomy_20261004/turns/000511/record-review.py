import pathlib,json,hashlib,datetime,os,sys,math,yaml
root=pathlib.Path.cwd();out=root.parent/'autonomy_20261004/turns/000511';sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as runner
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,v):
 t=p.with_name(p.name+'.tmp511');t.write_text(json.dumps(v,indent=2)+'\n');os.replace(t,p)
obs=json.loads((out/'projection-observation-v1.json').read_text());old=json.loads((out.parent/'000510/mechanism-review-v1.json').read_text());assert ref(out.parent/'000510/mechanism-review-v1.json')==obs['previous_review'];assert obs['ledger']['sha256']=='229878bc3a9d99fd596f363835f4ef1ae3c2757b7f34aa43e0aef985de1aa0f2'
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip();handles={}
for pid,start in [(268073,97715947),(2325717,133207020)]:
 fields=(pathlib.Path('/proc')/str(pid)/'stat').read_text().split(') ',1)[1].split();assert int(fields[19])==start;handles[str(pid)]={'pid':pid,'boot_id':boot,'start_ticks':start,'state':fields[0]}
assert not pathlib.Path('/proc/1070042').exists()
driver=json.loads((root.parent/'autonomy_20261004/driver-status.json').read_text());assert driver['turn']==511
assert not list((root.parent/'autonomy_20261004').glob('*STOP*'))
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
next_action='Constraints-first Arbor ideation using turn511 projection review and existing N23/N25 feedback lessons: choose a falsifiable successor to N32 that addresses unreliable open-loop arrival timing without claiming clipping alone or a scale substitution solves it. Read current tree constraints before ideate skill; prepare prospective dev-only method/protocol in isolated executor worktree. No replay or protected-result access; new GPU dispatch only after frozen source/protocol/audit release.'
review={'schema':'n32-selected-projection-root-review-v1','at':now,'source':'04d1255016fa13a2d467995b9e37a6a829356a1c','scientific_source':'1065f38122379a515b60a9a424f574330405b66f','observation':ref(out/'projection-observation-v1.json'),'source_references':[ref(root/'core/qd_capture_dwell_proposal.py'),ref(root/'core/env_adapters/libero_adapter.py'),ref(root/'scripts/qd_ed_n32_reference.py')],'prior_scale_review':ref(root.parent/'variants/n23_actuator_clipped_quality/root-actuator-goal-scale-review-v1.json'),'live_handles':handles,'controller_status':'NUMERIC_FUTILITY; exited0; PID absent','prior_turn_exit':0,'ledger':obs['ledger'],'conclusions':['All six selected proposal prefixes match parent translation commands through predicted arrival. Projection/actual mismatch therefore does not establish action substitution or decode corruption.','Original canonical projector uses unclipped action translations times0.01 accumulated from observed EEF. N32 uses that parent projection for capture arrival; proposal zeroes pose actions only after arrival.','Projection-to-actual EEF arrival residuals range0.017431 to0.082284m. Four of six prefixes contain translations outside[-1,1]; two have none, so saturation alone is not a complete explanation.','Descriptive float64 clipped0.01 arithmetic yields arrival residuals0.011456 to0.025681m; it is neither a native recomputation nor a causal counterfactual. It cannot establish improved proposal timing or task success.','Context/canonical source-origin differences are below0.000451m and do not account for the centimeter-scale residuals.','Ground-truth target pose, grasp, contact effects, and counterfactual success remain Unknown. Existing scale review does not justify replacing0.01 by0.05.'],'rows':[dict(decision=r['decision'],arrival_index=r['arrival_index'],projection_actual_residual_m=r['projection_actual_distance_at_arrival_m'],clipped_float64_descriptive_residual_m=math.dist(r['clipped_point01_arithmetic_at_arrival'],r['actual_at_arrival']),out_of_interval_components=r['translation_components_outside_unit_interval_through_arrival']) for r in obs['rows']],'next_action':next_action,'new_gpu_dispatches':0,'audit_replay':False,'scientific_promotion':False,'goal_met':False}
write(out/'projection-root-review-v1.json',review);rr=ref(out/'projection-root-review-v1.json');cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json'
with runner.locked(root/'data/qd-ed-state.lock'):
 s=yaml.safe_load((root/'research-state.yaml').read_text());c=json.loads(cp.read_text());assert s['active_controller'] is None and c['active_controller'] is None;assert ref(root/'data/attempt-ledger.jsonl')==obs['ledger']
 for d in [s,c]:d['n32r3_projection_review']=rr;d['next_action']=next_action;d['updated_at']=now
 tmp=root/'research-state.yaml.tmp511';tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));os.replace(tmp,root/'research-state.yaml');write(cp,c)
 tree=json.loads(tp.read_text());tree['nodes']['15.2']['n32r3_projection_review']=rr;write(tp,tree)
(out/'operational-summary.md').write_text(f'''Turn 511: N32 selected-proposal projection review

Current source {review['source']}; scientific source {review['scientific_source']} unchanged. Driver PID268073/start97715947 and coordinator PID2325717/start133207020 verified on boot{boot}. Closed controller1070042 absent, status NUMERIC_FUTILITY, exit0. No active controller in state/checkpoint. Prior turn510 exited0 with matching review/ledger; no recovery needed. STOP absent; deadline2026-10-11T11:13:13Z remains active.

Completed bounded hash-verified CPU extraction for six selected development task4 decisions. All six executed parent translations through projected arrival; actual/projected EEF residuals1.743–8.228cm. Four prefixes contain out-of-unit-interval translation commands; two do not. Float64 clipped0.01 arithmetic reduces some descriptive residuals but leaves1.146–2.568cm and is not a native audit or counterfactual efficacy result. No ground-truth target poses or grasp evidence. Root review SHA256 {rr['sha256']}.

Ledger unchanged1326 rows/6659252 bytes/SHA256 {obs['ledger']['sha256']};442 dispatches/62.81145837588456 GPUh retained. No source, frozen plan, gate, budget or protected-result changes. State/checkpoint/tree link this review.

Next bounded step: {next_action}

Original validation/formal/required-ablation goal remains unmet; no completion record created. Local driver continues coordination.
''')
print(json.dumps(rr))
