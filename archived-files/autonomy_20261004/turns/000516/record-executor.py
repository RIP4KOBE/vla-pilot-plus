import pathlib,json,hashlib,datetime,os,sys,yaml
root=pathlib.Path.cwd();out=root.parent/'autonomy_20261004/turns/000516';dest=root.parent/'variants/n34_observed_jaw_approach/implementation-v1';sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as runner
cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json'
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,v):
 t=p.with_name(p.name+'.tmp516');t.write_text(json.dumps(v,indent=2)+'\n');os.replace(t,p)
process=json.loads((dest/'executor-process-v1.json').read_text());boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip();handles={}
for label,h in [('driver',{'pid':268073,'start_ticks':97715947,'boot_id':boot}),('coordinator',{'pid':2381553,'start_ticks':133360756,'boot_id':boot}),('wrapper',process['wrapper']),('executor',process['executor'])]:
 f=pathlib.Path(f"/proc/{h['pid']}/stat").read_text().split(') ',1)[1].split();assert int(f[19])==h['start_ticks'] and h['boot_id']==boot;handles[label]={**h,'state':f[0]}
assert not pathlib.Path('/proc/1070042').exists();assert not (out.parent.parent/'STOP').exists();assert not (dest/'executor-exit-v1.json').exists()
ledger=ref(root/'data/attempt-ledger.jsonl');assert ledger['sha256']=='229878bc3a9d99fd596f363835f4ef1ae3c2757b7f34aa43e0aef985de1aa0f2'
next_step='Monitor existing N34 CPU executor by boot/PID/start identity; never duplicate it. On termination reconcile isolated diff/commit/tests and native encoding/audit evidence against turn514 frozen method before root integration. No GPU release yet; prospective fresh matched Dev protocol and budget/native/source review remain required.'
r={'status':'CPU_IMPLEMENTATION_RUNNING','node_id':'15.4','authority':ref(dest/'authority-v1.json'),'process_record':ref(dest/'executor-process-v1.json'),'handles':{k:handles[k] for k in ['wrapper','executor']},'base_source':'04d1255016fa13a2d467995b9e37a6a829356a1c','implementation_worktree':str(dest.parent/'implementation_worktree'),'output_directory':str(dest),'gpu_authorized':False,'next_step':next_step}
review={'schema':'n34-cpu-executor-launch-review-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'handles':handles,'prior_turn_exit':0,'closed_controller':'NUMERIC_FUTILITY/exit0/PID1070042 absent','ledger':ledger,'ledger_rows':1326,'ledger_bytes':6659252,'source':r['base_source'],'executor':r,'goal_met':False}
write(out/'executor-launch-review-v1.json',review)
with runner.locked(root/'data/qd-ed-state.lock'):
 s=yaml.safe_load((root/'research-state.yaml').read_text());c=json.loads(cp.read_text());assert s['active_controller'] is None and s['in_flight_executor'] is None;assert ledger==ref(root/'data/attempt-ledger.jsonl')
 for d in [s,c]:
  d['n34_cpu_implementation']=r;d['in_flight_executor']=r;d['next_action']=next_step;d['updated_at']=review['at']
 temp=root/'research-state.yaml.tmp516';temp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));os.replace(temp,root/'research-state.yaml');write(cp,c)
 tree=json.loads(tp.read_text());n=tree['nodes']['15.4'];assert n['status']=='pending';n.update(status='running',result='CPU_IMPLEMENTATION_RUNNING',cpu_implementation=r,execution_authorized=False);write(tp,tree)
(out/'operational-summary.md').write_text(f'''Turn516: N34 isolated CPU implementation dispatched under standing authority and Arbor executor workflow.

Owning source04d1255016fa13a2d467995b9e37a6a829356a1c; scientific source1065f38122379a515b60a9a424f574330405b66f unchanged. Bound handoff and exact authority verified. Prior515 exited0; no abnormal recovery. Driver268073/start97715947 and coordinator2381553/start133360756 verified on boot{boot}. STOP absent; authorization ends2026-10-11T11:13:13Z. N32R3 controller1070042 absent, terminal NUMERIC_FUTILITY/exit0, six matched triples C0 1/6 Q0 0/6 N32 0/6. No GPU cohort running or dispatched.

N34 node15.4 uses registered turn514 method and turn515 reviewed geometry30/102 nominal reachable; CPU-only evidence is not task success. Created isolated branch exp/n34-observed-jaw-approach-20261008 at {r['implementation_worktree']} on study data volume. Hash-bound scope/prompt and official current-login gpt-6-astra executor launched. Wrapper{handles['wrapper']['pid']}/start{handles['wrapper']['start_ticks']}; executor{handles['executor']['pid']}/start{handles['executor']['start_ticks']}; same boot. Durable launch record {dest}/executor-process-v1.json; eventual executor-exit-v1.json/report-v1.md/implementation-result-v1.json. GPU disabled. Owning state/checkpoint/tree now record in-flight CPU executor; no competing coordinator locks acquired.

Ledger unchanged1326 rows/6659252 bytes/{ledger['sha256']};442 dispatches,62.81145837588456GPUh and all historical charges/reserves retained. No protected result or prohibited file reads.

Next: {next_step}

Unresolved: native channel/FP32/BF16 feasibility and audit completeness, selection and physical efficacy; original validation/formal/required ablation evidence absent. Goal unmet; no completion record. Driver continues monitoring.
''')
print(json.dumps({'review':ref(out/'executor-launch-review-v1.json'),'handles':handles,'next':next_step},indent=2))
