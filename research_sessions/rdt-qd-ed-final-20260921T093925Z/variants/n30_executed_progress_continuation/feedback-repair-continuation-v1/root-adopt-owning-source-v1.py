"""Root adopts only independently accepted frozen source; no GPU dispatch."""
from pathlib import Path
import copy,datetime,hashlib,importlib.util,json,os,subprocess,sys,yaml
K=Path(__file__).resolve().parent;P=K.parent;W=P.parents[1]/'study_worktree';I=K/'implementation'
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r
read=r.read_json
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
ref=lambda p:{'path':str(Path(p).resolve()),'sha256':sha(p)}
def git(root,*args):return subprocess.check_output(['git',*args],cwd=root)
source=read(K/'source-manifest-execution-v1.json')
cpu=read(K/'root-cpu-integration-review-v1.json');review=read(K/'root-source-review-execution-v1.json')
assert cpu['disposition']=='ACCEPT_CPU_INTEGRATION_ONLY' and cpu['source_commit']==source['commit']
assert review['decision']=='ACCEPT_SOURCE_BYTE_SCOPE' and review['commit']==source['commit']
assert review['source']==ref(K/'source-manifest-execution-v1.json')
assert git(I,'rev-parse','HEAD').decode().strip()==source['commit'] and git(I,'status','--porcelain')==b''
old='b2775fa2008a8a88e374c43a5753f8862485af1f';base='debda23a0e8eda86a3bb4f398e9596edf05b37e5'
assert subprocess.run(['git','merge-base','--is-ancestor',base,source['commit']],cwd=I).returncode==0
now=datetime.datetime.now(datetime.timezone.utc).isoformat();run='rdt-qd-ed-final-20260921T093925Z'
spec=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
with r.locked(W/'data/qd-ed-runner.lock',nonblocking=True),r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml')
 assert state['current_cpu_task']['phase']=='N30_R2_CPU_CONTINUATION_INTEGRATION'
 assert not state.get('current_owned_workers') and not state.get('active_iteration') and not state.get('active_controller')
 budget=copy.deepcopy(state['budget']);lexical=state['worktree']
 snap=r.budget_snapshot(r.read_events(W/'data/attempt-ledger.jsonl'),r.read_events(W/'data/gpu-healthcheck-ledger.jsonl'))
 assert snap['dispatched']==399 and snap['running']==snap['gpu_healthcheck_inflight']==0
 assert abs(snap['gpu_hours_consumed']-53.485552730447566)<1e-8 and budget['max_gpu_hours']==100 and budget['max_episode_attempts']==578
 assert git(W,'rev-parse','HEAD').decode().strip()==old
 dirty=git(W,'diff','--name-only','-z').decode().strip('\x00').split('\x00')
 assert set(dirty)=={
 '.arbor/sessions/'+run+'/.coordinator/checkpoint.json','.arbor/sessions/'+run+'/.coordinator/idea_tree.json',
 '.arbor/sessions/'+run+'/.coordinator/idea_tree.md','.arbor/sessions/'+run+'/REPORT.md',
 'data/attempt-ledger.jsonl','data/exposure-registry.jsonl','data/gpu-healthcheck-ledger.jsonl',
 'data/gpu-hour-reservation-ledger.jsonl','docs/03_evidence/qd_ed_final/iteration-ledger.md',
 'research-state.yaml','research_config.yaml'}
 before={name:sha(W/name) for name in dirty}
 changed=set(git(I,'diff','--name-only',old,source['commit']).decode().splitlines())
 assert not changed.intersection(dirty)
 for f in source['files']:
  assert sha(I/f['path'])==f['sha256']
  assert hashlib.sha256(git(I,'show',source['commit']+':'+f['path'])).hexdigest()==f['sha256']
 subprocess.run(['git','merge','--ff-only',source['commit']],cwd=W,check=True,stdout=subprocess.DEVNULL)
 assert git(W,'rev-parse','HEAD').decode().strip()==source['commit']
 assert {name:sha(W/name) for name in dirty}==before
 for f in source['files']:assert sha(W/f['path'])==f['sha256']
 record={'schema':'n30-r2-root-source-adoption-v1','at':now,'old_commit':old,'repair_base':base,'commit':source['commit'],
  'source':ref(K/'source-manifest-execution-v1.json'),'cpu_review':ref(K/'root-cpu-integration-review-v1.json'),
  'source_review':ref(K/'root-source-review-execution-v1.json'),'source_files_verified':len(source['files']),
  'operational_dirty_files_unchanged_through_fast_forward':before,'gpu_dispatched':False,'budget_changed':False}
 r.durable_json(K/'root-owning-source-adoption-v1.json',record)
 state['current_cpu_task'].update(status='COMPLETED_ACCEPTED',delivery=ref(K/'delivery-manifest-v1.json'),review=ref(K/'root-cpu-integration-review-v1.json'))
 state['study']['status']='N30_R2_SOURCE_ADOPTED_PLAN_PREPARATION_TARGET_NOT_MET'
 state['prospective_iteration'].update(status='R2_SOURCE_ADOPTED',gpu_execution_authorized=False,
  continuation_source_commit=source['commit'],continuation_source_adoption=ref(K/'root-owning-source-adoption-v1.json'))
 state['next_action']='Build root source/history bridge and unchanged-budget authority, verify all10real continuation commands and freeze plan; no GPU release yet.'
 state['updated_at']=now
 assert state['budget']==budget and state['worktree']==lexical
 tmp=W/'research-state.yaml.n30-r2-source-tmp'
 with tmp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(tmp,W/'research-state.yaml')
 coord=W/'.arbor/sessions'/run/'.coordinator';cp=read(coord/'checkpoint.json')
 cp.update(status=state['study']['status'],phase='REVIEW',in_flight_executor=None,in_flight_executors=[],
  inflight_executor=None,inflight_executors=[],executor_task=None,
  n30_r2_cpu_review=ref(K/'root-cpu-integration-review-v1.json'),n30_r2_source_adoption=ref(K/'root-owning-source-adoption-v1.json'),
  next_action=state['next_action'],updated_at=now)
 r.durable_json(coord/'checkpoint.json',cp)
 tree=a.load_tree(W,run);a.node(tree,'14.1').update(code_ref=source['commit'],phase='R2_DEV_PREPARATION',
  gpu_execution_authorized=False,continuation_source_review=ref(K/'root-source-review-execution-v1.json'))
 a.save_tree(W,run,tree)
print(json.dumps({'adopted':source['commit'],'source_files':len(source['files']),'operational_files_preserved':len(before),'gpu_dispatched':False}))

