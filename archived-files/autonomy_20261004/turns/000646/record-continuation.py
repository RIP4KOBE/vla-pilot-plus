import pathlib,json,hashlib,datetime,sys,yaml,shutil
root=pathlib.Path.cwd();sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as runner
out=(root.parent/'autonomy_20261004/turns/000646').resolve();v=(root.parent/'variants/n34_observed_jaw_approach/recovery4-identity-repair-v1').resolve()
def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
entry=json.loads((out/'entry-reconciliation-v1.json').read_text());process=json.loads((v/'executor-process-v1.json').read_text());boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for k in ['wrapper','executor']:
 h=process[k];stat=pathlib.Path(f"/proc/{h['pid']}/stat").read_text().split(') ',1)[1].split();assert boot==h['boot_id'] and int(stat[19])==h['start_ticks'] and stat[0]!='Z'
for name,prefix in entry['ledger_prefixes'].items():
 b=(root/'data'/name).read_bytes();assert len(b)==prefix['bytes'] and hashlib.sha256(b).hexdigest()==prefix['sha256']
next_action='Monitor existing N34R4 CPU identity executor by boot/PID/start; do not duplicate. After exit independently review scoped commit and focused tests, adopt operational identity repair, regenerate runtime with turn645 corrected inventory, and freeze fresh prospective accounting/protocol/30 manifests/root review/release with full public validation before GPU7 admission. Preserve N34R3 invalid charge and scientific gates.'
record={'status':'CPU_IMPLEMENTATION_RUNNING','node_id':'15.4','authority':ref(v/'authority-v1.json'),'process_record':ref(v/'executor-process-v1.json'),'handles':{k:process[k] for k in ['wrapper','executor']},'worktree':str(v.parent/'production_worktree'),'output_directory':str(v),'gpu_authorized':False,'next_step':next_action}
cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tree=cp.parent/'idea_tree.json';sp=root/'research-state.yaml'
with runner.locked(root/'data/qd-ed-state.lock'):
 s=runner.read_state(sp);c=json.loads(cp.read_text());t=json.loads(tree.read_text());assert s['active_controller'] is None and c['active_controller'] is None
 for p in [sp,cp,tree]:shutil.copyfile(p,out/(p.name+'.before'))
 for o in [s,c]:
  o.update(n34r4_identity_repair=record,in_flight_executor=record,next_action=next_action,automatic_gpu_dispatch_authorized=False)
  # Reconcile obsolete CPU handles already verified absent; retain their original records elsewhere.
  o['in_flight_executors']=[record]
 n=t['nodes']['15.4'];n['n34r4_identity_repair']=record;n['result']='N34R3 retained INVALID; N34R4 CPU-only fresh identity repair running under bounded authority, no GPU dispatch or scientific promotion.'
 for p,obj,is_yaml in [(sp,s,True),(cp,c,False),(tree,t,False)]:
  tmp=p.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(obj,sort_keys=False,allow_unicode=True) if is_yaml else json.dumps(obj,indent=2)+'\n');tmp.replace(p)
end={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':s['source_commit'],'ledger_prefixes':entry['ledger_prefixes'],'executor':record,'active_controller':None,'driver_stop_present':(out.parent.parent/'STOP').exists(),'target_met':False,'next_action':next_action}
(out/'end-reconciliation-v1.json').write_text(json.dumps(end,indent=2)+'\n')
a=json.loads((v/'authority-v1.json').read_text());h=record['handles']
(out/'operational-summary.md').write_text(f"""Turn646 — {end['at']}

Owning source {s['source_commit']}; scientific source71ffff1a0f70d9874b309db9ef1843c02bf17ebf unchanged. Bound handoff, exact authority, continuation and completion contract hashes verified. Driver268073/start97715947 and coordinator715464/start135941335 verified on boot{boot}; closed N34R3 controller666112 and worker669326 absent. Turn645 completed normally; its corrected CPU runtime inventory retained. STOP absent; authorization deadline2026-10-11T11:13:13Z. No active GPU cohort.

Launched one official current-login gpt-6-astra CPU executor in isolated production worktree. Wrapper{h['wrapper']['pid']}/start{h['wrapper']['start_ticks']}; executor{h['executor']['pid']}/start{h['executor']['start_ticks']}. Output: {v}. CPU-only authority bounds work to fresh N34R4 recovery identity and focused tests,1800seconds; no scientific changes or GPU release. State/checkpoint and node15.4 bind authority/process. Driver locks untouched.

Recorded prospective arithmetic before implementation:446 retained dispatches+30=476 of1800;63.6001770799448+5=68.6001770799448 of224GPUh. Additional1 recovery/9 baseline/20 development yields20/98/298. Remaining protected validation24.240824002430816 and formal12GPUh retained. All three owning ledgers unchanged byte-for-byte; no replay, charge erasure or unknown-telemetry normalization.

Next bounded step: {next_action}

Unresolved: native runtime validity, fresh matched Dev efficacy, scientific promotion, validation20/formal10/required ablations and hash-bound original-goal completion. No completion claim; driver continues.
""")
print(json.dumps({'summary':str(out/'operational-summary.md'),'handles':h,'ledgers_unchanged':True}))
