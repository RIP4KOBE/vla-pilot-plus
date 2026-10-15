"""Bounded root review of the first repaired live cell; no native replay."""
from pathlib import Path
import datetime,json,os,sys,time
L=Path(__file__).resolve().parent;W=L.parent.parents[1]/'study_worktree'
os.environ['CUDA_VISIBLE_DEVICES']='';os.sched_setaffinity(0,{0,1})
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='2'
sys.dont_write_bytecode=True;sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n30_r2_contract as c,qd_ed_n30_native as native
start=time.process_time();plan=r.read_json(c.PLAN);row=plan['episodes'][0]
events=r.read_events(W/'data/attempt-ledger.jsonl')
e=c.accepted_cell(plan,row,events,W,vars(r));out=Path(e['output_dir'])
assert e['attempt_id']=='rdt-qd-ed-final-20260921T093925Z__n30_r2_dev_t00_n30_20261003__4300bcf89485'
assert e['outcome_valid'] is True and e['success'] is False and e['guided_chunks']==24 and e['unguided_chunks']==66
rec=r.read_json(out/'eds_eval/in-worker-audit-receipt.json');report=w.read_ref(rec['audit_report'])
assert rec['worker_error_type'] is None if 'worker_error_type' in rec else True
assert rec['accepted'] and rec['process_unchanged'] and rec['main_exit_code']==0
counts,aux=native.from_output('N30',out,report,24);assert counts==rec['n30_native_counts']
assert counts['active_insertions_verified']==14 and counts['parent_rounds_verified']==240
calls=[x for x in r.read_events(out/'eds_eval/stage_events.jsonl') if x.get('query_status')!='skipped']
assert len(calls)==15 and e['provider_failed_calls']==0
for call in calls:
 t=call['transport'];assert (t['backend'],t['auth_mode'],t['model'])==('codex_cli','chatgpt','gpt-6-astra')
 assert call['query_ok'] and call['query_status']=='ok'
usage={key:e['provider_'+key] for key in ('input_tokens','output_tokens','cached_input_tokens')}
for key,v in usage.items():assert sum(call['codex_'+key] for call in calls)==v
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def live(p):
 try:
  f=Path(f"/proc/{p['pid']}/stat").read_text().rsplit(')',1)[1].split()
  return p['boot_id']==boot and str(p['proc_start_ticks'])==f[19] and f[0]!='Z'
 except FileNotFoundError:return False
proc=r.read_json(out/'process.json');assert not live(proc)
controller=r.read_json(L/'execution/controller-process-v1.json')
h=c.history();controls=[v['cell'] for v in h['imports']]
assert len(controls)==2 and all(v['task_id']==0 and v['success'] is False for v in controls)
review={'schema':'n30-r2-root-first-valid-cell-review-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'decision':'FIRST_N30_LIVE_NATIVE_AUDIT_ACCEPTED_TASK_FAILURE','source_commit':plan['source_commit'],
 'attempt':c.ref(out/'attempt-result.json'),'context':c.ref(out/'n23-worker-context.json'),
 'receipt':c.ref(out/'eds_eval/in-worker-audit-receipt.json'),'audit':rec['audit_report'],
 'source':c.ref(L/'source-manifest-execution-v1.json'),'process':c.ref(out/'process.json'),
 'worker_original_exited':True,'controller_live_observed':live(controller),'controller':c.ref(L/'execution/controller-process-v1.json'),
 'native':counts,'matched_task0':{'C0':False,'Q0':False,'N30':False},
 'inherited_controls':controls,'guided_chunks':24,'unguided_chunks':66,
 'new_episode_gpu_seconds':e['gpu_process_wall_seconds'],'stage':{'logical_calls':15,'failed_calls':0,**usage},
 'http_requests':None,'http_retries':None,'scientific_interpretation':'First real post-repair receipt proves existing mechanism executed and terminal feedback audit passes. It supplies one valid N30 task failure, no success benefit. Insertion does not establish selection or causal benefit.',
 'frozen_gate_action':'Continue unchanged prospective matched queue:0+3remaining can still reach3/4. No validation release or algorithm edit during the cohort.',
 'root_tensor_deserializations':0,'root_numerical_replays':0,'evidence_blob_hashes_rechecked':True,
 'cpu_seconds':time.process_time()-start,'goal_status':'TARGET_NOT_MET'}
with (L/'root-first-valid-repair-cell-review-v1.json').open('x') as f:json.dump(review,f,indent=2);f.write('\n')
print(json.dumps({k:review[k] for k in ('decision','native','new_episode_gpu_seconds','stage','cpu_seconds')}))

