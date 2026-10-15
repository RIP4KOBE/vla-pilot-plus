import pathlib,json,hashlib,datetime,os,subprocess,sys,yaml
root=pathlib.Path.cwd();out=root.parent/'autonomy_20261004/turns/000512';sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as runner
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,v):
 t=p.with_name(p.name+'.tmp512');t.write_text(json.dumps(v,indent=2)+'\n');os.replace(t,p)
cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json'
ledger=ref(root/'data/attempt-ledger.jsonl');assert ledger['sha256']=='229878bc3a9d99fd596f363835f4ef1ae3c2757b7f34aa43e0aef985de1aa0f2'
assert not (root.parent/'autonomy_20261004/STOP').exists();assert now<'2026-10-11T11:13:13';assert not pathlib.Path('/proc/1070042').exists()
assert json.loads((out.parent/'000511/receipt.json').read_text())['exit']==0
handles={}
for pid,start in [(268073,97715947),(2342902,133237067)]:
 f=pathlib.Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1].split();assert int(f[19])==start;handles[str(pid)]={'pid':pid,'start_ticks':start,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'state':f[0]}
hyp='Mechanism: N33 current-observation-triggered immediate close-and-dwell competitor in ordinary QD offspring.\nHypothesis: Conditioning closure on present hand-prism entry removes unreliable projected future-arrival timing while preserving ordinary quality and ED selection.\nObservable: First exact dev-only trigger reachability and native-byte change audit; subsequently fresh matched dev success gains with native execution evidence, never promotion from trigger counts.\nConflicts: N31/N32 selected proposals failed; this removes future-arrival extrapolation. N3 residual feedback and N23/N25 clipping failures are not reused; zero observed trigger opportunities reject this design without threshold tuning.'
next_action='N33 CPU feasibility only: inspect availability then hash-bound exact current-observation hand-prism reachability across exposed N32 logical-cohort dev contexts, with complete denominators and Unknown handling, per turn512 ideation-v1.md. Zero changed admissible opportunities closes N33; positive opportunities permit isolated executor source/protocol/native-audit preparation, not GPU release. No replay, protected access or threshold tuning.'
with runner.locked(root/'data/qd-ed-state.lock'):
 s=yaml.safe_load((root/'research-state.yaml').read_text());c=json.loads(cp.read_text());assert s['active_controller'] is None and c['active_controller'] is None;assert not s['current_owned_workers'];assert s['source_commit']=='04d1255016fa13a2d467995b9e37a6a829356a1c'
 tree=json.loads(tp.read_text());assert not any('N33 current-observation' in n.get('hypothesis','') for n in tree['nodes'].values())
 r=subprocess.run([sys.executable,'/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py','add','--cwd',str(root),'--run-name','rdt-qd-ed-final-20260921T093925Z','--parent-id','15','--hypothesis',hyp],check=True,capture_output=True,text=True);print(r.stdout)
 tree=json.loads(tp.read_text());node=next(k for k,n in tree['nodes'].items() if n.get('hypothesis')==hyp)
 record={'schema':'n33-cpu-ideation-registration-v1','at':now,'node_id':node,'source_commit':s['source_commit'],'scientific_source_commit':s['scientific_source_commit'],'ideation':ref(out/'ideation-v1.md'),'evidence':[s['n32r3_projection_review'],s['n32r3_mechanism_review'],s['n32r3_terminal_reconciliation']],'live_handles':handles,'closed_controller_status':'NUMERIC_FUTILITY; exit0; PID1070042 absent','ledger':ledger,'ledger_bytes':6659252,'ledger_rows':1326,'retained_budget':s['budget_snapshot'],'status':'CPU_REACHABILITY_PENDING','next_action':next_action,'gpu_released':False,'goal_met':False}
 write(out/'n33-registration-v1.json',record);rr=ref(out/'n33-registration-v1.json')
 for d in [s,c]:d['n33_cpu_ideation']=rr;d['next_action']=next_action;d['updated_at']=now
 tmp=root/'research-state.yaml.tmp512';tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));os.replace(tmp,root/'research-state.yaml');write(cp,c)
 tree['nodes'][node]['registration']=rr;tree['nodes'][node]['execution_authorized']=False;write(tp,tree)
(out/'operational-summary.md').write_text(f'''Turn512: constraints-first N33 CPU ideation registered as node{node}.

Source04d1255016fa13a2d467995b9e37a6a829356a1c; scientific source1065f38122379a515b60a9a424f574330405b66f unchanged. Driver268073/start97715947 and coordinator2342902/start133237067 verified on boot2a1fa95f-ab0d-488c-a298-fc488ddd2af7. Closed N32R3 controller1070042 absent, NUMERIC_FUTILITY/exit0. State/checkpoint have no active controller or worker. Prior511 exit0 and ledger/review hashes match: no abnormal recovery. STOP absent; window ends2026-10-11T11:13:13Z.

Completed constraints-first four-move ideation and registered only N33 current-observed-proximity capture proposal CPU feasibility, hash-bound {rr['sha256']}. No source edits, new GPU/provider calls, audit replay, threshold changes, or protected result reads. Ledger remains1326 rows/6659252 bytes/{ledger['sha256']};442 dispatches and62.81145837588456GPUh retained.

Next bounded step: {next_action}

Unresolved: trigger reachability, tracked-keypoint grasp relevance, selection and physical efficacy. Original validation/formal/required-ablation goal remains unmet; no completion record. Driver continues.
''')
print(json.dumps(rr))
