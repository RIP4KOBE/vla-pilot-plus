import collections,datetime,json,pathlib,time
W=pathlib.Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z');B=pathlib.Path(__file__).resolve().parent
result={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
p=B/'first3-status.json'
if p.exists():
 st=json.loads(p.read_text());result['supervisor']={k:st.get(k) for k in ['status','current_episode_key','completed_keys','selected_physical_gpu']}
 result['GPU3_admission']=[{k:d.get(k) for k in ['physical_gpu','memory_used_mib','idle_observed_seconds','idle_stable']} for d in st.get('gpu_inventory',[]) if d.get('physical_gpu')==3]
groups=collections.OrderedDict()
for line in (W/'data/attempt-ledger.jsonl').read_text().splitlines():
 e=json.loads(line)
 if e.get('identity',{}).get('iteration')=='N4_TERMINAL_POPULATION_DEV_20260924':groups.setdefault(e['attempt_id'],[]).append(e)
result['N4_attempts']=[]
for aid,events in groups.items():
 e=events[-1];item={k:e.get(k) for k in ['attempt_id','episode_key','event','physical_gpu','gpu_process_wall_seconds','outcome_valid','success']}
 dispatch=next((v for v in events if v['event']=='dispatched'),None)
 if e['event'] not in ['valid','invalid','aborted'] and dispatch:item['elapsed_since_dispatch_s']=round(time.time()-dispatch['time_unix'],1)
 out=pathlib.Path(e['output_dir']);process=out/'process.json'
 if process.exists():
  proc=json.loads(process.read_text());item['pid']=proc['pid'];item['pid_exists']=pathlib.Path('/proc/'+str(proc['pid'])).exists()
 metrics=out/'eds_eval/eds_metrics.jsonl'
 if metrics.exists():
  complete=metrics.read_bytes().split(b'\n')[:-1];item['guided_metrics_records']=len(complete)
  if complete:item['latest_guided_global_step']=json.loads(complete[-1]).get('global_step')
 audit=out/'eds_eval/decision-evidence-audit.json'
 if audit.exists():
  au=json.loads(audit.read_text());item['audit']={k:au.get(k) for k in ['accepted','evidence_complete','errors']}
 result['N4_attempts'].append(item)
launch=B/'first3-launch-result.json'
if launch.exists():result['supervisor_exit']=json.loads(launch.read_text())['exit_code']
result['supervisor_stderr_bytes']=(B/'first3-supervisor.stderr.log').stat().st_size
print(json.dumps(result,indent=2))
