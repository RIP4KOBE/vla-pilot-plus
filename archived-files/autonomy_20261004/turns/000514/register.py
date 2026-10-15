import pathlib,json,hashlib,datetime,os,subprocess,sys,yaml
root=pathlib.Path.cwd();out=root.parent/'autonomy_20261004/turns/000514';sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as runner
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,v):
 t=p.with_name(p.name+'.tmp514');t.write_text(json.dumps(v,indent=2)+'\n');os.replace(t,p)
cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json'
ledger=ref(root/'data/attempt-ledger.jsonl');assert ledger['sha256']=='229878bc3a9d99fd596f363835f4ef1ae3c2757b7f34aa43e0aef985de1aa0f2'
assert not (root.parent/'autonomy_20261004/STOP').exists();assert now<'2026-10-11T11:13:13';assert not pathlib.Path('/proc/1070042').exists()
assert json.loads((out.parent/'000513/receipt.json').read_text())['exit']==0
handles={}
for pid,start in [(268073,97715947),(2364256,133302164)]:
 f=pathlib.Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1].split();assert int(f[19])==start;handles[str(pid)]={'pid':pid,'start_ticks':start,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'state':f[0]}
hyp='Mechanism: N34 observed jaw-centered approach competitor with observation-triggered close-and-dwell in ordinary QD offspring.\nHypothesis: Supplying approach translations from current geometry counters the missing observed entry that defeated N33 without relying on parent-predicted closure timing.\nObservable: Prespecified dev-only geometric reachability then native-byte feasibility; later fresh matched Dev task gains and actual entry, never promotion from nominal endpoints.\nConflicts: N31/N32 extrapolated arrival and N33 had zero present entry; this supplies approach. N3 feedback-quality and N23/N25 clipping failures do not establish this control proposal, and tracked-keypoint grasp relevance remains Unknown.'
next_action='N34 CPU feasibility only per turn514 ideation-v1.md: reuse hash-bound exposed N32 observation packets and complete denominators to screen fixed jaw-center approach nominal endpoints under8 steps/.01 and clipped translation. Zero eligible reachable outside-prism contexts rejects this instance without tuning. Positive geometry licenses isolated executor native implementation/audits only, not GPU release. Preserve all442 charges, protected gates and Unknown control packets.'
with runner.locked(root/'data/qd-ed-state.lock'):
 s=yaml.safe_load((root/'research-state.yaml').read_text());c=json.loads(cp.read_text());assert s['active_controller'] is None and c['active_controller'] is None;assert not s['current_owned_workers'];assert s['source_commit']=='04d1255016fa13a2d467995b9e37a6a829356a1c'
 tree=json.loads(tp.read_text());assert not any('N34 observed jaw-centered' in n.get('hypothesis','') for n in tree['nodes'].values())
 r=subprocess.run([sys.executable,'/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py','add','--cwd',str(root),'--run-name','rdt-qd-ed-final-20260921T093925Z','--parent-id','15','--hypothesis',hyp],check=True,capture_output=True,text=True);print(r.stdout)
 tree=json.loads(tp.read_text());node=next(k for k,n in tree['nodes'].items() if n.get('hypothesis')==hyp)
 record={'schema':'n34-cpu-ideation-registration-v1','at':now,'node_id':node,'source_commit':s['source_commit'],'scientific_source_commit':s['scientific_source_commit'],'ideation':ref(out/'ideation-v1.md'),'evidence':[s['n33_cpu_reachability_review'],s['n32r3_projection_review'],s['n32r3_terminal_reconciliation']],'live_handles':handles,'closed_controller_status':'NUMERIC_FUTILITY; exit0; PID1070042 absent','ledger':ledger,'ledger_bytes':6659252,'ledger_rows':1326,'retained_budget':s['budget_snapshot'],'status':'CPU_REACHABILITY_PENDING','next_action':next_action,'gpu_released':False,'goal_met':False}
 write(out/'n34-registration-v1.json',record);rr=ref(out/'n34-registration-v1.json')
 for d in [s,c]:d['n34_cpu_ideation']=rr;d['next_action']=next_action;d['updated_at']=now
 tmp=root/'research-state.yaml.tmp514';tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));os.replace(tmp,root/'research-state.yaml');write(cp,c)
 tree['nodes'][node]['registration']=rr;tree['nodes'][node]['execution_authorized']=False;write(tp,tree)
(out/'operational-summary.md').write_text(f'''Turn514: constraints-first N34 CPU ideation registered as node{node}.

Source04d1255016fa13a2d467995b9e37a6a829356a1c; scientific source1065f38122379a515b60a9a424f574330405b66f unchanged. Driver268073/start97715947 and coordinator2364256/start133302164 verified on boot2a1fa95f-ab0d-488c-a298-fc488ddd2af7. Closed N32R3 controller1070042 absent, NUMERIC_FUTILITY/exit0. State/checkpoint have no active controller or worker. Prior513 exit0 and ledger/review hashes match: no abnormal recovery. STOP absent; window ends2026-10-11T11:13:13Z.

Completed constraints-first four-move ideation and registered only N34 observed jaw-centered approach CPU feasibility, hash-bound {rr['sha256']}. No source edits, new GPU/provider calls, audit replay, threshold changes, or protected result reads. Ledger remains1326 rows/6659252 bytes/{ledger['sha256']};442 dispatches and62.81145837588456GPUh retained.

Next bounded step: {next_action}

Unresolved: trigger reachability, tracked-keypoint grasp relevance, selection and physical efficacy. Original validation/formal/required-ablation goal remains unmet; no completion record. Driver continues.
''')
print(json.dumps(rr))
