"""Root final finite Dev release. No episode launched by this script."""
from pathlib import Path
import datetime,json,os,sys,yaml,subprocess
V=Path(__file__).resolve().parent;ROOT=V.parents[1]/'study_worktree';sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n29_contract as c,qd_ed_n29_supervise as sup
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
plan_path=V/'plan.frozen.v1.gpu7.json';plan=w.read_ref(c.ref(plan_path));source=json.loads((V/'source-manifest-execution-v1.json').read_text())
assert w.read_ref(c.ref(V/'adoption-v1/root-plan-adoption-record-v1.json'))['plan']==c.ref(plan_path)
assert plan['source_commit']==source['commit'] and plan['code_files']==source['files'] and plan['frozen']
assert plan['episodes']==c.expected_rows() and len(plan['episodes'])==40 and plan['phase_authorization']=={'dev':True,'validation':False,'formal':False}
review=w.read_ref(c.ref(V/'real-command-composition-review-v1.json'));assert review['accepted'] and len(review['commands'])==40
assert [x['episode_key'] for x in review['commands']]==[x['episode_key'] for x in plan['episodes']]
runtime=w.read_ref(c.runtime_ref());r.stage_overrides(runtime)
login=subprocess.run([runtime['frozen_stage_provider']['cli_path'],'login','status'],capture_output=True,text=True)
assert login.returncode==0 and (login.stdout+login.stderr).strip()=='Logged in using ChatGPT'
with r.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(ROOT/'data/qd-ed-state.lock'):
  state=r.read_state(ROOT/'research-state.yaml');events=r.read_events(ROOT/'data/attempt-ledger.jsonl');resources=r.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl')
  c.full_capacity(state,events,resources,vars(r))
  assert not any(e.get('identity',{}).get('iteration')==c.COHORT for e in events)
  admission=r.gpu_admission(physical_gpu=7,expected_uuid=c.GPU7_UUID)
  assert not (V/'execution/supervisor-status-v1.json').exists() and not (V/'result-v1.json').exists()
  release={'schema':'n29-dev-execution-release-v1','plan':c.ref(plan_path),'source_commit':plan['source_commit'],'cohort_id':c.COHORT,
    'episode_keys':[x['episode_key'] for x in plan['episodes']],'authority':plan['n29_cohort']['authority'],'physical_gpu':7,'limits':c.LIMITS,
    'validation_authorized':False,'formal_authorized':False}
  release_path=V/'execution-release-v1.json';w.atomic_json(release_path,release);sup.release_check(release_path,plan_path,plan)
  prelaunch={'schema':'n29-root-final-prelaunch-review-v1','reviewed_at':now,'decision':'RELEASE_ONE_FINITE_DEV_COHORT',
    'plan':c.ref(plan_path),'release':c.ref(release_path),'source_commit':plan['source_commit'],'source_files':411,
    'command_review':c.ref(V/'real-command-composition-review-v1.json'),'cpu_review':c.ref(V/'root-phase-b-cpu-review-v1.json'),
    'native_review':c.ref(V/'root-native-proof-review-v1.json'),'runtime_review':c.ref(V/'root-source-runtime-check-v1.json'),
    'gpu_admission':admission,'gpu_uuid':c.GPU7_UUID,'login_status':'Logged in using ChatGPT','poe_allowed':False,
    'fallback_allowed':False,'budget_snapshot':r.budget_snapshot(events,resources),'dispatches_released':40,'automatic_retries':0,
    'total_gpu_hour_cap':100.,'local_gpu_hour_cap_including_proof':13.5,'validation_authorized':False,'formal_authorized':False,
    'target_status':'TARGET_NOT_MET','gpu_dispatched_by_this_script':False}
  w.atomic_json(V/'root-final-prelaunch-review-v1.json',prelaunch)
  state['current_iteration'].update(status='N29_DEV_RELEASED',execution_authorized=True,execution_release=c.ref(release_path),prelaunch_review=c.ref(V/'root-final-prelaunch-review-v1.json'))
  state['study']['status']='N29_DEV_RELEASED_TARGET_NOT_MET';state['prospective_iteration'].update(status='DEV_RELEASED',gpu_execution_authorized=True)
  state['next_action']='Run exact40-cell task-major N29 Dev cohort on GPU7 using current Codex login only; inspect each accepted cell and close on any invalidity, complete-quad numerical futility, or inability to reserve the full next attempt.'
  path=ROOT/'research-state.yaml';tmp=path.with_suffix('.yaml.n29-release-tmp')
  with tmp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
  os.replace(tmp,path)
  cp_path=ROOT/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';cp=json.loads(cp_path.read_text())
  cp.update(status='N29_DEV_RELEASED',automatic_gpu_dispatch_authorized=True,automatic_gpu_dispatch_scope=c.COHORT,
    n29_execution_release=c.ref(release_path),n29_prelaunch_review=c.ref(V/'root-final-prelaunch-review-v1.json'),next_action=state['next_action'])
  r.durable_json(cp_path,cp)
print(json.dumps({'release':c.ref(V/'execution-release-v1.json'),'gpu':7,'released_cells':40,'login':'ChatGPT/current managed login','poe_allowed':False,'gpu_dispatched':False}))

