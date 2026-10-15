from pathlib import Path
import datetime,importlib.util,json,os,sys,yaml
P=Path(__file__).resolve().parent;R=P.parents[1];W=R/'study_worktree'
os.environ['CUDA_VISIBLE_DEVICES']='';sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n31_contract as c
spec=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
run='rdt-qd-ed-final-20260921T093925Z';session=W/'.arbor/sessions'/run;cpfile=session/'.coordinator/checkpoint.json'
launch=r.read_json(P/'execution/root-launch-v1.json')
def alive(rec):
 raw=Path(f'/proc/{rec["pid"]}/stat').read_text();parts=raw[raw.rfind(')')+2:].split()
 return parts[0] not in ('Z','X') and parts[19]==rec['proc_start_ticks'] and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==rec['boot_id']
assert alive(launch['controller']) and alive(launch['monitor'])
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
with r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml');cp=r.read_json(cpfile);tree=a.load_tree(W,run)
 events=r.read_events(W/'data/attempt-ledger.jsonl');groups=r.event_groups(events)
 live=[]
 for group in groups.values():
  first,last=group[0],group[-1]
  if first.get('identity',{}).get('iteration')==c.COHORT and last['event'] not in r.TERMINAL:
   proc=Path(first['output_dir'])/'process.json'
   if proc.exists():
    handle=r.read_json(proc);assert alive(handle)
    live.append({**handle,'physical_gpu':7,'output_dir':first['output_dir'],'process_record':str(proc)})
 assert len(live)<=1
 controller={**launch['controller'],'monitor':launch['monitor'],'launch':c.ref(P/'execution/root-launch-v1.json'),'status_path':str(P/'execution/supervisor-status-v1.json'),'log':str(P/'execution/supervisor.log'),'cohort_id':c.COHORT}
 before={'state_status':state['study']['status'],'source_commit':state['source_commit'],'active_iteration':state['active_iteration'],'checkpoint_phase':cp.get('phase')}
 state['source_commit']=launch['source_commit']
 state['study'].update(status='N31_DEV_RUNNING_GPU7_TARGET_NOT_MET',automatic_continuation=True)
 state['active_iteration'].update(status='DEV_RUNNING',source_commit=launch['source_commit'],execution_authorized=True,validation_authorized=False,formal_authorized=False,frozen_plan=launch['plan'],execution_release=launch['release'])
 state.update(active_controller=controller,active_plan=launch['plan'],current_owned_workers=live,updated_at=now,next_action='Monitor existing N31 GPU7 controller; consume native receipts and exact Dev gate on completion, then continue authorized research toward original goal. Never duplicate controller or retry this cohort automatically.')
 cp.update(status=state['study']['status'],phase='EXECUTE_DEV',active_node='15.1',active_controller=controller,active_plan=launch['plan'],current_owned_workers=live,automatic_gpu_dispatch_authorized=True,automatic_dispatch_scope={'cohort_id':c.COHORT,'plan':launch['plan'],'single_gpu':7,'no_auto_retry':True},next_action=state['next_action'],updated_at=now,goal_achieved=False,target_achieved=False,target_met=False)
 tree['meta'].update(study_status=state['study']['status'],target_achieved=False)
 leaf=a.node(tree,'15.1');leaf.update(status='running',phase='DEV_RUNNING',active_controller=controller,execution_release=launch['release'],target_achieved=False)
 leaf['result']='N31 source7428ce8 exact frozen cohort released under approved weekly budget; controller launched on GPU7. Target not yet met; validation/formal remain closed.'
 path=W/'research-state.yaml';temp=path.with_name(path.name+'.n31-live-v1')
 with temp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(temp,path);r.durable_json(cpfile,cp);a.save_tree(W,run,tree)
 receipt={'schema':'n31-root-live-registration-v1','recorded_at':now,'before':before,'launch':c.ref(P/'execution/root-launch-v1.json'),'controller':controller,'current_owned_workers':live,'source_commit':launch['source_commit'],'frozen_plan':launch['plan'],'history_retained':True,'target_met':False}
 r.durable_json(P/'execution/root-live-registration-v1.json',receipt)
 note=f'\n### {now} — N31 GPU7 execution live\n\nController {controller["pid"]}, monitor {launch["monitor"]["pid"]}; frozen source {launch["source_commit"]}. Plan: {launch["plan"]["path"]}. One worker at a time, no automatic recovery, Dev gate only. All future budget amendments have standing user authorization. Target not yet met.\n'
 for p in (session/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md'):
  with p.open('a') as f:f.write(note)
print(json.dumps({'registered':True,'controller':controller['pid'],'workers':live,'status':state['study']['status']}))
