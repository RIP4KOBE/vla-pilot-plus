import pathlib,json,yaml,os,hashlib,datetime
from scripts import qd_ed_final_runner as r, qd_ed_n32r3_contract as c
root=pathlib.Path.cwd(); t=pathlib.Path('../autonomy_20261004/turns/000468').resolve(); status=json.loads((t/'release-validation-v2.json').read_text());assert status['status']=='PASS'
next_step='N32R3 release v2 passed full production validation. Perform fresh official-login Stage image transport and GPU7 admission, adopt plan/release into owning state under ordinary locks, and launch one controller with durable boot/PID/start handles. Preserve 14 historical valid cells, invalid task4 charge, all438 charges and frozen scientific source; no replay. Use turn468 release-validation-v2.json and plan/release references.'
record={'status':'RELEASE_VALIDATED_PENDING_FRESH_ADMISSION','source':'04d1255016fa13a2d467995b9e37a6a829356a1c','composition':c.ref(t/'composition-result-v2.json'),'validation':c.ref(t/'release-validation-v2.json'),'plan':status['plan'],'release':status['release'],'gpu_dispatched':False,'production_plan_adopted':False,'next_step':next_step}
paths=[root/'research-state.yaml',root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/idea_tree.json']
with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True), r.locked(root/'data/qd-ed-state.lock'):
 ledger=(root/'data/attempt-ledger.jsonl').read_bytes(); assert hashlib.sha256(ledger).hexdigest()=='8294b4ed47b8f645f2b3ab6511329f548b5788a5f40d0822b54d3c6c8c814da6'
 objs=[]
 for p in paths:
  raw=p.read_bytes(); backup=t/(p.name+'.before');backup.write_bytes(raw)
  obj=yaml.safe_load(raw) if p.suffix=='.yaml' else json.loads(raw);objs.append(obj)
 state,checkpoint,tree=objs;assert state['active_controller'] is None and state['current_owned_workers']==[]
 budget_before=json.dumps(state['budget'],sort_keys=True)
 for obj in [state,checkpoint]:
  obj['n32r3_fresh_release_validation']=record
  obj['next_action']=next_step
  obj['status']='N32R3_RELEASE_VALIDATED_PENDING_ADMISSION'
  obj['phase']='PROSPECTIVE_RELEASE_ADMISSION'
  obj['updated_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
  obj['n32r3_command_path_repair']['status']='RELEASE_VALIDATED_PENDING_FRESH_ADMISSION'
  obj['n32r3_command_path_repair']['next_step']=next_step
 tree['nodes']['15.2']['result']=next_step
 tree['nodes']['15.2']['n32r3_fresh_release_validation']=record
 assert json.dumps(state['budget'],sort_keys=True)==budget_before
 for p,obj in zip(paths,objs):
  tmp=p.with_name(p.name+'.turn468.tmp')
  with tmp.open('x') as f:
   f.write(yaml.safe_dump(obj,sort_keys=False) if p.suffix=='.yaml' else json.dumps(obj,indent=2)+'\n');f.flush();os.fsync(f.fileno())
  os.replace(tmp,p)
(t/'progress-record.json').write_text(json.dumps(record,indent=2)+'\n')
summary=f'''Current owning operational source: 04d1255016fa13a2d467995b9e37a6a829356a1c; frozen scientific source1065f38122379a515b60a9a424f574330405b66f unchanged.
Live handles: driver268073/start97715947; current coordinator1022259/start132306121; boot2a1fa95f-ab0d-488c-a298-fc488ddd2af7. No active GPU controller/worker. CPU manifest composition and release-validation processes completed exit0; no live child remains.
Completed: verified bound authority, continuation context/completion contract, prior467 exit0 and actual source adoption; checked owning isolation ACTIVE/PASS and unchanged ledger. Prepared fresh source inventory and detached continuity review, bound exact reviewed disabled command-path amendment, composed16 fresh manifests-v2 and validated fresh detached production release v2: PASS (109.48s). No scientific source edits or broad test repeats. Prior156 focused passing tests retained. Updated owning state/checkpoint/Idea Tree under normal runner/state locks; driver locks untouched.
Plan: {status['plan']['path']} SHA256 {status['plan']['sha256']}
Release: {status['release']['path']} SHA256 {status['release']['sha256']}
Validation: {record['validation']['path']} SHA256 {record['validation']['sha256']}
Ledger unchanged:5694864 bytes SHA2568294b4ed47b8f645f2b3ab6511329f548b5788a5f40d0822b54d3c6c8c814da6; all438 charges, failures, unknown telemetry and protected reserves preserved. Previous rejected releasev1 retained. No GPU dispatch or production-plan state adoption.
Next bounded step: {next_step}
Unresolved evidence: admission/launch and remaining native outcomes; validation/formal/required ablation goal unmet. No completion record. STOP absent at entry; recheck before admission. Autonomy ends2026-10-11T11:13:13Z; cohort deadline remains2026-10-10T17:42:00Z. Local driver continues.
'''
(t/'operational-summary.md').write_text(summary)
print(json.dumps({'status':'RECORDED','progress':c.ref(t/'progress-record.json'),'summary':str(t/'operational-summary.md')}))
