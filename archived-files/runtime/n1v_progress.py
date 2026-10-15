"""Read-only live N1V progress; no provider calls, CUDA initialization or adjudication."""
from pathlib import Path
import collections,datetime,json,re,time
W=Path('/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z')
A=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z')
def read(path):
 try:return json.loads(path.read_text())
 except (OSError,ValueError):return {}
def lines(path):
 try:raw=path.read_text().splitlines()
 except OSError:return []
 values=[]
 for line in raw:
  try:values.append(json.loads(line))
  except ValueError:pass
 return values
all_events=lines(W/'data/attempt-ledger.jsonl');groups={}
for e in all_events:
 if e.get('identity',{}).get('iteration')=='N1V':groups.setdefault(e['attempt_id'],[]).append(e)
last=[g[-1] for g in groups.values()];valid=[e for e in last if e.get('outcome_valid') is True]
s=read(A/'runtime/n1v-gpu2/status.json');qs=read(Path(s.get('queue_status_path','/nonexistent')))
result={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),'status':s.get('status','not_launched'),'queue_status':qs.get('status'),'current':s.get('current_episode_key'),'valid_cells':len(valid),'planned_cells':30,'primary_dispatched':sum(not g[0].get('retry_of') and any(e['event']=='dispatched' for e in g) for g in groups.values()),'recovery_dispatched':sum(bool(g[0].get('retry_of')) and any(e['event']=='dispatched' for e in g) for g in groups.values()),'stage_timeout_aborts':sum(e.get('failure_detail')=='n1v_stage_timeout' for e in last),'profiles':{p:{'success':sum(e['success'] for e in valid if e['identity']['profile']==p),'valid':sum(e['identity']['profile']==p for e in valid)} for p in ('C0','Q0','N1')},'reason':s.get('reason')}
active=[g for g in groups.values() if g[-1]['event']=='dispatched']
if active:
 e=active[-1][-1];o=Path(e['output_dir']);stages=lines(o/'eds_eval/stage_events.jsonl');metrics=lines(o/'eds_eval/eds_metrics.jsonl');phase=lines(o/'eds_eval/phase_timing.jsonl')
 try:log=(o/'runner.log').read_text()[-18000:]
 except OSError:log=''
 steps=[int(x) for x in re.findall(r'Env step:\s*(\d+)',log)]
 result['active']={'attempt_id':e['attempt_id'],'elapsed_seconds':round(time.time()-e['time_unix'],1),'steps':max([v.get('global_step',-1)+1 for v in phase if v.get('name')=='adapter_step' and v.get('event')=='exit'],default=0),'guided_chunks':len(metrics),'stage_calls':len([s for s in stages if s.get('query_status')!='skipped']),'stage_ok':sum(s.get('query_status')=='ok' for s in stages),'stage_errors':sum(s.get('query_status')=='error' for s in stages),'latest_metric_step':metrics[-1].get('global_step') if metrics else None,'latest_stage_step':stages[-1].get('global_step') if stages else None,'phase':{k:v for k,v in (phase[-1] if phase else {}).items() if k in ('event','name','global_step','chunk_id','elapsed_s')}}
result['latest_terminal']={k:v for k,v in (next((e for e in reversed(last) if e['event'] in ('valid','aborted')),{})).items() if k in ('episode_key','event','success','outcome_valid','failure_detail','reason','gpu_process_wall_seconds')}
print(json.dumps(result,ensure_ascii=False))
