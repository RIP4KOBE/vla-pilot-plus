"""Refresh observation metadata of the existing running N30 controller only."""
from pathlib import Path
import datetime,json,os,sys,yaml
V=Path(__file__).resolve().parent;W=V.parents[1]/'study_worktree';sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n30_contract as c,qd_ed_n23_worker as w
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def live(p):
 try:
  stat=Path(f"/proc/{p['pid']}/stat").read_text().rsplit(')',1)[1].split()
  return stat[0]!='Z' and stat[19]==str(p['proc_start_ticks']) and p['boot_id']==boot
 except FileNotFoundError:return False
controller=w.read_ref(c.ref(V/'execution/controller-process-v1.json'))
assert live(controller),'Controller no longer live; use independent terminal review, not this helper'
with r.locked(W/'data/qd-ed-state.lock'):
 events=r.read_events(W/'data/attempt-ledger.jsonl')
 local=[e for e in events if e.get('identity',{}).get('iteration')==c.COHORT]
 owned=[];unresolved=[]
 for aid,group in r.event_groups(local).items():
  if group[-1]['event']!='dispatched':continue
  e=group[-1];out=Path(e['output_dir']);p=w.read_ref(c.ref(out/'process.json'))
  if not live(p):unresolved.append(aid);continue
  owned.append({'attempt_id':aid,'episode_key':e['episode_key'],'profile':e['identity']['profile'],
    'pid':p['pid'],'proc_start_ticks':p['proc_start_ticks'],'boot_id':p['boot_id'],'physical_gpu':7,
    'process':c.ref(out/'process.json'),'output_dir':str(out),'observed_at':now})
 assert len(owned)<=1
 state=r.read_state(W/'research-state.yaml')
 assert state['active_iteration']==c.COHORT and state['current_iteration']['id']=='N30'
 status=r.read_json(V/'execution/supervisor-status-v1.json')
 state['current_owned_workers']=owned
 state['current_iteration'].update(accepted_cells_observed=len(status.get('completed_keys',[])),
    observed_successes=status.get('successes'),last_observed_at=now,unsettled_exited_handles=unresolved)
 temp=W/'research-state.yaml.n30-live-tmp'
 with temp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(temp,W/'research-state.yaml')
 cp_path=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';cp=r.read_json(cp_path)
 cp.update(active_workers=owned,worker_observation_at=now,unsettled_exited_handles=unresolved,
   budget_snapshot=r.budget_snapshot(events,r.read_events(W/'data/gpu-healthcheck-ledger.jsonl')))
 r.durable_json(cp_path,cp)
print(json.dumps({'at':now,'owned_workers':owned,'accepted_cells':len(status.get('completed_keys',[])),
 'successes':status.get('successes'),'unsettled_exited_handles':unresolved}))

