import pathlib,json,datetime,collections,os
N=pathlib.Path("/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n28_parent_before_renoise");W=pathlib.Path("/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree");COHORT='N28_PARENT_BEFORE_RENOISE_SCREEN_20261001'
def lines(p):
 if not p.exists():return []
 out=[]
 for s in p.read_text().splitlines():
  try:out.append(json.loads(s))
  except json.JSONDecodeError:pass
 return out
es=[e for e in lines(W/'data/attempt-ledger.jsonl') if e.get('identity',{}).get('iteration')==COHORT]
groups={}
for e in es:groups.setdefault(e['attempt_id'],[]).append(e)
s={'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'episode_attempts':len(groups),'accepted':[],'live':[],'stage':{},'native':{}}
p=N/'execution/supervisor-status-v1.json'
if p.exists():
 x=json.loads(p.read_text());s.update(status=x.get('status'),completed_keys=x.get('completed_keys'),successes=x.get('successes'),failure=x.get('failure'),native=x.get('native'))
for aid,g in groups.items():
 e=g[-1];d=pathlib.Path(e['output_dir']);c={'attempt_id':aid,'episode_key':e['episode_key'],'event':e['event']}
 pp=d/'process.json'
 if pp.exists():
  pr=json.loads(pp.read_text());pid=pr['pid'];stat=pathlib.Path('/proc')/str(pid)/'stat'
  c['pid']=pid;c['original_worker_alive']=stat.exists() and stat.read_text().split(') ',1)[1].split()[19]==str(pr.get('proc_start_ticks'))
 ev=lines(d/'eds_eval/stage_events.jsonl');actual=[v for v in ev if v.get('query_status')!='skipped']
 stages=collections.Counter(v.get('query_status') for v in actual);bindings=collections.Counter((v.get('transport',{}).get('backend'),v.get('transport',{}).get('auth_mode'),v.get('transport',{}).get('model')) for v in actual)
 c.update(observed_stage_calls=len(actual),stage_status=dict(stages),bindings=[{'backend':k[0],'auth_mode':k[1],'model':k[2],'calls':v} for k,v in bindings.items()])
 if ev:c['last_stage_step']=ev[-1].get('global_step')
 if e['event'] in ['valid','aborted']:
  c.update({k:e.get(k) for k in ['success','outcome_valid','guided_chunks','provider_failed_calls','gpu_process_wall_seconds']});s['accepted'].append(c)
 else:s['live'].append(c)
 if actual:
  for k,v in stages.items():s['stage'][k]=s['stage'].get(k,0)+v
p=N/'result-v1.json'
if p.exists():
 x=json.loads(p.read_text());s['terminal']={k:x.get(k) for k in ['decision','counts','dispatched','audited_cells','goal_status','failure']}
print(json.dumps(s,ensure_ascii=False))
