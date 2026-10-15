import pathlib,json,hashlib,datetime,sys,yaml,shutil
root=pathlib.Path.cwd();sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as runner
out=(root.parent/'autonomy_20261004/turns/000696').resolve();v=(root.parent/'variants/n34_observed_jaw_approach/recovery9-identity-repair-v1').resolve()
def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
entry=json.loads((out/'entry-reconciliation-v1.json').read_text());process=json.loads((v/'executor-process-v1.json').read_text());boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for k in ['wrapper','executor']:
 h=process[k];stat=pathlib.Path(f"/proc/{h['pid']}/stat").read_text().split(') ',1)[1].split();assert boot==h['boot_id'] and int(stat[19])==h['start_ticks'] and stat[0]!='Z'
for name,prefix in entry['ledger_prefixes'].items():
 b=(root/'data'/name).read_bytes();assert len(b)==prefix['bytes'] and hashlib.sha256(b).hexdigest()==prefix['sha256']
next_action='Monitor existing N34R9 CPU identity executor by boot/PID/start; do not duplicate. After exit independently review scoped commit and focused tests, adopt operational identity repair, regenerate runtime with turn695 corrected inventory, and freeze fresh prospective accounting/protocol/30 manifests/root review/release with full public validation before GPU7 admission. Preserve N34R8 invalid charge and scientific gates.'
record={'status':'CPU_IMPLEMENTATION_RUNNING','node_id':'15.4','authority':ref(v/'authority-v1.json'),'process_record':ref(v/'executor-process-v1.json'),'handles':{k:process[k] for k in ['wrapper','executor']},'worktree':str(v.parent/'production_worktree'),'output_directory':str(v),'gpu_authorized':False,'next_step':next_action}
cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tree=cp.parent/'idea_tree.json';sp=root/'research-state.yaml'
with runner.locked(root/'data/qd-ed-state.lock'):
 s=runner.read_state(sp);c=json.loads(cp.read_text());t=json.loads(tree.read_text());assert s['active_controller'] is None and c['active_controller'] is None
 for p in [sp,cp,tree]:shutil.copyfile(p,out/(p.name+'.before'))
 for o in [s,c]:
  o.update(status='N34R9_CPU_IDENTITY_REPAIR_RUNNING',updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),n34r9_identity_repair=record,in_flight_executor=record,next_action=next_action,automatic_gpu_dispatch_authorized=False)
  # Reconcile obsolete CPU handles already verified absent; retain their original records elsewhere.
  o['in_flight_executors']=[record]
 n=t['nodes']['15.4'];n['n34r9_identity_repair']=record;n['result']='N34R8 retained INVALID; N34R9 CPU-only fresh identity repair running under bounded authority, no GPU dispatch or scientific promotion.'
 for p,obj,is_yaml in [(sp,s,True),(cp,c,False),(tree,t,False)]:
  tmp=p.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(obj,sort_keys=False,allow_unicode=True) if is_yaml else json.dumps(obj,indent=2)+'\n');tmp.replace(p)
end={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':s['source_commit'],'ledger_prefixes':entry['ledger_prefixes'],'executor':record,'active_controller':None,'driver_stop_present':(out.parent.parent/'STOP').exists(),'target_met':False,'next_action':next_action}
(out/'end-reconciliation-v1.json').write_text(json.dumps(end,indent=2)+'\n')

h=record['handles'];b=s['budget_snapshot']
(out/'operational-summary.md').write_text(f"""Turn 696 — {end['at']}

Current owning source: {s['source_commit']}. Frozen scientific implementation remains unchanged. Bound handoff, user authority, continuation and completion contract hashes verified. Driver 268073/start 97715947 and current coordinator 1135100/start 136887425 match boot {boot}. Prior turn 695 completed normally. Closed N34R8 controller 1085789 and worker 1088632 are absent; no active GPU cohort. STOP absent; authorization deadline 2026-10-11T11:13:13Z.

Prepared hash-bound N34R9 CPU-only identity authority and launched one official current-login gpt-6-astra executor in the existing isolated production worktree. Wrapper {h['wrapper']['pid']}/start {h['wrapper']['start_ticks']}; executor {h['executor']['pid']}/start {h['executor']['start_ticks']}. Outputs: {v}. Scope: fresh recovery identities and focused rejection tests, 1800 seconds; no scientific edits, runtime preparation or GPU release. Owning state/checkpoint/node 15.4 bind the authority and live process records under the normal state lock. Driver locks untouched.

All three owning ledger prefixes unchanged. Retained cost: 451 dispatches and 64.35541576467786 GPU hours. Prospective maximum 30 attempts/5 GPU hours gives 481/1800 attempts and 69.35541576467786/224 GPU hours; additional 1 recovery/9 baseline/20 development yields bucket totals 25/98/298. Protected remaining validation 24.240824002430816 and formal 12 GPU hours preserved. Nine invalid N34 executions retain charges and unknown telemetry.

Next bounded step: {next_action}

Unresolved: full native runtime validity, matched Dev efficacy, scientific promotion, validation/formal/required ablation evidence. Original goal remains unevidenced; no completion record. Local driver continues.
""")
print(json.dumps({'summary':str(out/'operational-summary.md'),'handles':h,'ledgers_unchanged':True}))
