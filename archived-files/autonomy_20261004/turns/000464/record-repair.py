import pathlib,json,hashlib,datetime,os,yaml
from scripts import qd_ed_final_runner as r
root=pathlib.Path.cwd();out=root.parent/'autonomy_20261004/turns/000464';dest=root.parent/'variants/n32_archive_eligible_capture/command-path-repair-v1'
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
record=json.loads((dest/'executor-process-v1.json').read_text());boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for h in [record['wrapper'],record['executor']]:
 stat=pathlib.Path(f"/proc/{h['pid']}/stat").read_text().split(') ',1)[1].split();assert int(stat[19])==h['start_ticks'] and h['boot_id']==boot
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
next_action='Monitor existing CPU-only command-path repair executor; never duplicate or restart on coordinator timeout. On exit review isolated operational diff and focused negative tests, then adopt source, exact prospective path amendment, fresh manifests and detached release only after unchanged scientific/native gates pass. Retain rejected release v1 and all438 charges. No GPU dispatch until full release validation and fresh admission.'
task={'status':'CPU_REPAIR_RUNNING','node_id':'15.2','authority':ref(dest/'authority-v1.json'),'process_record':ref(dest/'executor-process-v1.json'),'handles':{k:record[k] for k in ['wrapper','executor']},'gpu_authorized':False,'source_changes_authorized':'Isolated scripts/qd_ed_n32r3_*.py and tests/test_n32r3*.py only; scientific source immutable','output_directory':str(dest),'next_step':next_action}
with r.locked(root/'data/qd-ed-state.lock'):
 sp=root/'research-state.yaml';cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json'
 s=yaml.safe_load(sp.read_text());ck=json.loads(cp.read_text());tree=json.loads(tp.read_text())
 assert s['active_controller'] is None and not s['current_owned_workers']
 ledger=root/'data/attempt-ledger.jsonl';assert hashlib.sha256(ledger.read_bytes()).hexdigest()=='8294b4ed47b8f645f2b3ab6511329f548b5788a5f40d0822b54d3c6c8c814da6'
 for path in [sp,cp,tp]:(out/('pre-repair-'+path.name)).write_bytes(path.read_bytes())
 for obj in [s,ck]:obj.update(status='N32R3_COMMAND_PATH_REPAIR_RUNNING',next_action=next_action,updated_at=now,n32r3_command_path_repair=task,in_flight_executor=task)
 tree['nodes']['15.2'].update(n32r3_command_path_repair=task,result=next_action)
 for path,obj,isy in [(sp,s,True),(cp,ck,False),(tp,tree,False)]:
  tmp=path.with_name(path.name+'.turn464.tmp');tmp.write_text(yaml.safe_dump(obj,sort_keys=False) if isy else json.dumps(obj,indent=2)+'\n');os.replace(tmp,path)
entry={'at':now,'driver':{'pid':268073,'start_ticks':97715947,'boot_id':boot},'coordinator':{'pid':992226,'start_ticks':132210940,'boot_id':boot},'historical_n31_handles_absent':True,'owning_active_controller':None,'ledger':{'bytes':ledger.stat().st_size,'sha256':hashlib.sha256(ledger.read_bytes()).hexdigest()},'prior_turn463':'completed exit0; rejected v1 preserved; storage side effects reconstructed from current resolved paths','STOP':False,'source':'36aac818c8ea0ec3ce18413e678963818bb5bb5d','scientific_source':'1065f38122379a515b60a9a424f574330405b66f','executor':task}
(out/'entry-reconciliation.json').write_text(json.dumps(entry,indent=2)+'\n')
summary=f'''Current owning source:36aac818c8ea0ec3ce18413e678963818bb5bb5d; scientific source1065f38122379a515b60a9a424f574330405b66f unchanged.
Live handles: driver268073/start97715947; coordinator992226/start132210940; boot{boot}. CPU repair wrapper{record['wrapper']['pid']}/start{record['wrapper']['start_ticks']}, executor{record['executor']['pid']}/start{record['executor']['start_ticks']}. No active GPU controller or worker. STOP absent; cohort deadline2026-10-10T17:42:00Z; autonomy ends2026-10-11T11:13:13Z.
Completed: verified handoff/authorization, current state/checkpoint and prior turn463 exit0/side effects. Ledger unchanged5694864 bytes/SHA8294b4ed47b8f645f2b3ab6511329f548b5788a5f40d0822b54d3c6c8c814da6. Diagnosed that prospective command correction additionally requires preserving the hard-bound preparation-review anchor. Launched one official current-login gpt-6-astra CPU executor in existing isolated implementation worktree, with exact bounded scope and no GPU authority. Source unchanged in owning study; rejected releasev1 remains intact.
Next bounded step: {next_action}
Unresolved: repair source review, valid amended production release and fresh GPU admission. Validation/formal/required ablation evidence and hash-bound completion record absent; goal unmet. All438 attempts/61.35722319715016GPUh and protected reserves retained. Driver retains its locks; no competing coordinator launched.
'''
(out/'operational-summary.md').write_text(summary)
print(json.dumps({'status':'recorded','executor':record['executor'],'summary':ref(out/'operational-summary.md')}))
