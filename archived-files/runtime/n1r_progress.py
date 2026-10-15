from pathlib import Path
import csv, datetime, json, subprocess, time
A = Path(__file__).resolve().parents[1]
W = Path('/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z')

def read(path):
    try: return json.loads(path.read_text())
    except (OSError, ValueError): return {}
def lines(path):
    try: text = path.read_text()
    except OSError: return []
    result=[]
    for line in text.splitlines():
        try: result.append(json.loads(line))
        except ValueError: pass
    return result
s=read(A/'runtime/n1r-gpu2-queue-status.json')
KEY = s.get('current_episode_key','n1r_dev_t00_q0')
r={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'queue_status':s.get('status'),
   'queue_pid':s.get('pid'), 'queue_alive':Path('/proc/'+str(s.get('pid'))).exists(),
   'reason':s.get('reason'), 'physical_gpu':2}
g=next((v for v in s.get('gpu_inventory',[]) if v['physical_gpu']==2),{})
r['idle_seconds_at_queue_poll']=round(g.get('idle_observed_seconds',0))
try:
    q=subprocess.run(['nvidia-smi','-i','2','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=10)
    if q.returncode==0:
        mem,util=next(csv.reader(q.stdout.splitlines()))
        r.update(memory_mib=int(mem.strip()),utilization_pct=int(util.strip()))
except (OSError,ValueError,StopIteration,subprocess.TimeoutExpired): pass
events=[e for e in lines(W/'data/attempt-ledger.jsonl') if e.get('episode_key')==KEY]
if events:
    e=events[-1];out=Path(e['output_dir']);r.update(attempt_id=e['attempt_id'],event=e['event'],outcome_valid=e.get('outcome_valid'))
    dispatch=next((v for v in events if v['event']=='dispatched'),{})
    r['elapsed_seconds']=round(e.get('gpu_process_wall_seconds',time.time()-dispatch.get('time_unix',time.time())),1)
    phases=lines(out/'eds_eval/phase_timing.jsonl')
    r['completed_environment_steps']=max([v.get('global_step',-1)+1 for v in phases if v.get('name')=='adapter_step' and v.get('event')=='exit'],default=0)
    if phases:r['last_phase']={k:phases[-1].get(k) for k in ['name','event','global_step','elapsed_s']}
    errors=out/'cuda-memcheck.log'
    if errors.exists(): r['sanitizer_report']=[v for v in errors.read_text(errors='replace').splitlines() if any(k in v for k in ['Program hit','Invalid __','ERROR SUMMARY','Internal Sanitizer'])][-8:]
    r['xids']=[v.get('xid') for v in read(out/'gpu-kernel-xid.json').get('records',[])]
    r['attempt_stop_reason']=e.get('reason')
    stages=lines(out/'eds_eval/stage_events.jsonl')
    r['stage_calls_completed']=len(stages)
    r['stage_calls_failed']=sum(v.get('query_status')!='ok' for v in stages)
    r['stage_wait_seconds']=round(sum(v.get('codex_call_latency_s',0) for v in stages),1)
    metrics=lines(out/'eds_eval/eds_metrics.jsonl')
    r['guided_chunks_recorded']=len(metrics)
    if metrics:
        r['last_search']={k:metrics[-1].get(k) for k in ['global_step','qd_descriptor',
            'qd_archive_active_for_chunk','search_evaluation_count','score_call_count',
            'nonfinite_count','qd_accounting_violation_count']}
cohort=[v for v in lines(W/'data/attempt-ledger.jsonl') if v.get('identity',{}).get('iteration')=='N1R']
r['cohort_valid_completed']=sum(v.get('event')=='valid' and v.get('outcome_valid') is True for v in cohort)
r['cohort_planned']=30
r['cohort_dispatched']=sum(v.get('event')=='dispatched' for v in cohort)
r['current_episode_key']=KEY
r['profiles']={profile:{'completed':sum(v.get('event')=='valid' and v.get('outcome_valid') is True
    and v.get('identity',{}).get('profile')==profile for v in cohort),
    'successes':sum(v.get('event')=='valid' and v.get('outcome_valid') is True and v.get('success') is True
    and v.get('identity',{}).get('profile')==profile for v in cohort)} for profile in ['C0','Q0','N1']}
record=A/'resource/n1r-gpu2-progress.jsonl'
with record.open('a') as stream:stream.write(json.dumps(r,ensure_ascii=False)+'\n')
print(json.dumps(r,ensure_ascii=False,indent=2))
