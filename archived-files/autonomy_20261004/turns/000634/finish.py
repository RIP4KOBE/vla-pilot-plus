import pathlib,json,hashlib,datetime,sys,yaml
root=pathlib.Path.cwd();sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as r
out=(root.parent/'autonomy_20261004/turns/000634').resolve();cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
next_action='Prepare CPU-only prospective runtime inventory correction adding dotenv code imports without loading credentials; inspect analogous nested imports. Then separate N34R3 identity/source review and fresh protocol/accounting/release, preserving all 445 charges and strict native audit. No replay or protected evaluation.'
with r.locked(root/'data/qd-ed-state.lock'):
 s=r.read_state(root/'research-state.yaml');c=json.loads(cp.read_text());assert s['active_controller'] is None and c['active_controller'] is None
 for obj in [s,c]:obj.update(n34r2_runtime_diagnosis=ref(out/'cpu-diagnosis-v1.json'),next_action=next_action)
 p=root/'research-state.yaml';t=p.with_suffix('.tmp');t.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));t.replace(p)
 t=cp.with_suffix('.tmp');t.write_text(json.dumps(c,indent=2)+'\n');t.replace(cp)
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip();handles=[]
for pid,start in [(268073,97715947),(624508,135703323),(592818,135643655),(595896,135652737)]:
 p=pathlib.Path(f'/proc/{pid}/stat');fields=p.read_text().split() if p.exists() else None;handles.append({'pid':pid,'boot_id':boot,'expected_start_ticks':start,'actual_start_ticks':int(fields[21]) if fields else None,'state':fields[2] if fields else 'ABSENT','identity_matches':bool(fields and int(fields[21])==start)})
b=(root/'data/attempt-ledger.jsonl').read_bytes();record={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':s['source_commit'],'handles':handles,'driver_stop_present':(out.parent.parent/'STOP').exists(),'deadline':'2026-10-11T11:13:13Z','ledger':{'bytes':len(b),'lines':len(b.splitlines()),'sha256':hashlib.sha256(b).hexdigest()},'terminal_closure':ref(out/'terminal-closure-v1.json'),'diagnosis':ref(out/'cpu-diagnosis-v1.json'),'next_action':next_action,'target_met':False}
(out/'end-reconciliation-v1.json').write_text(json.dumps(record,indent=2)+'\n')
(out/'operational-summary.md').write_text(f'''Turn634 — {record['at']}

Current source {s['source_commit']}; scientific source 71ffff1a0f70d9874b309db9ef1843c02bf17ebf. Bound handoff and exact user authority hashes verified. Driver268073/start97715947 and coordinator624508/start135703323 verified on boot{boot}; controller592818 and worker595896 absent. Prior turn633 completed normally; preserved its complete ledger prefix. STOP absent; authorization deadline2026-10-11T11:13:13Z.

N34R2 task0 C0 ended INVALID_STOP: Main exit0 followed by strict post-run runtime attestation rejection, loaded runtime not frozen: dotenv.parser. No valid matched Dev cell, no promotion. Terminal closure and private budget reconciled under ordinary state lock:445 dispatched,63.45894268680093 GPUh, zero running; latest attempt retained as aborted/INVALID with raw classification and unknown telemetry intact. All prior charges/reserves preserved. Source, frozen plan and scientific thresholds unchanged; no dispatch or driver lock acquisition.

CPU-only import diagnosis reproduced four missing dotenv module bindings. Main's dotenv import is nested in a try block excluded by the direct top-level-import inventory probe. No dotenv loader, credential read, Main/model/environment/provider/GPU execution performed in diagnosis. Checkpoint/state now reference closure and diagnosis; active controller cleared and automatic dispatch disabled pending a new prospective release.

Next bounded step: {next_action}

Unresolved: full native runtime completeness, matched Dev efficacy, scientific promotion, validation20/formal10/required ablations and hash-bound original-goal completion. Driver continues; no completion claim.
''')
print(json.dumps({'summary':str(out/'operational-summary.md'),'handles':handles,'ledger':record['ledger']}))
