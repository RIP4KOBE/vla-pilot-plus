"""Finite root N29 budget adoption; no GPU/process/API experiment dispatch."""
from pathlib import Path
import copy,datetime,json,os,sys,yaml
V=Path(__file__).resolve().parent;ROOT=V.parents[1]/'study_worktree'
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n29_contract as c
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
review=w.read_ref(c.ref(V/'root-phase-b-cpu-review-v1.json'));runtime=w.read_ref(c.ref(V/'root-source-runtime-check-v1.json'))
assert review['decision']=='ACCEPT_CPU_EXECUTION_IMPLEMENTATION' and runtime['accepted']
assert review['source_commit']==runtime['source_commit']=='d855cfd690482e018bb40ce98edec80fad9700e0'
old_authority=V.parent/'n28_parent_before_renoise/budget-adoption-v1/authority.json'
old_caps=w.read_ref(c.ref(old_authority))['caps']
amendment={'id':'n29-finite-dev-budget-20261001-v1','document':c.ref(V/'finite-budget-proposal-v1.md'),
 'previous_authority':c.ref(old_authority),'root_cpu_review':c.ref(V/'root-phase-b-cpu-review-v1.json')}
authority={'schema':'n29-finite-budget-authority-v1','caps':c.BASE_CAPS,'protocol':c.ref(c.PROTOCOL),
 'predecessor':c.predecessor(),'limits':c.LIMITS,'local_gpu_hours':13.5,'amendment':amendment,'recorded_at':now,
 'authority_interpretation':'Root finite adoption under continuing user no-intervention delegation; not a separate numerical user audit. Preserve100 GPUh, all protected reserves and historical charges. One exact40-cell Dev cohort only; stop at complete-quad numerical futility or inability to reserve a full attempt.',
 'validation_authorized':False,'formal_authorized':False}
def save_yaml(path,data):
    tmp=path.with_suffix(path.suffix+'.n29-tmp')
    with tmp.open('x') as f:yaml.safe_dump(data,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
with r.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True):
  with r.locked(ROOT/'data/qd-ed-state.lock'):
    state=r.read_state(ROOT/'research-state.yaml')
    events=r.read_events(ROOT/'data/attempt-ledger.jsonl');resources=r.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl')
    snapshot=r.budget_snapshot(events,resources)
    assert snapshot['dispatched']==371 and abs(snapshot['gpu_hours_consumed']-49.99373352883483)<1e-8
    assert snapshot['running']==snapshot['gpu_healthcheck_inflight']==0
    assert all(g[-1]['event'] in r.TERMINAL for g in r.event_groups(events).values())
    assert state['budget']['max_episode_attempts']==old_caps['attempts']==538
    assert state['budget']['max_gpu_hours']==old_caps['gpu_hours']==100.
    assert state['budget']['reserved']==old_caps['buckets'] and state['budget']['gpu_hour_reservations']==c.BASE_CAPS['protected_gpu_hours']
    assert not state.get('current_owned_workers') and not state.get('external_resource_hold',{}).get('do_not_auto_resume')
    assert not any(e.get('identity',{}).get('iteration')==c.COHORT for e in events)
    protected=sum(max(0,h-snapshot['gpu_hours_by_bucket'][bucket]) for bucket,h in c.BASE_CAPS['protected_gpu_hours'].items())
    assert snapshot['gpu_hours_consumed']+protected+13.5<=100
    protected_attempts=sum(c.BASE_CAPS['buckets'][b]-snapshot['by_bucket'][b] for b in ('validation','formal'))
    assert snapshot['dispatched']+40+protected_attempts<=578
    w.atomic_json(c.BUDGET_AUTHORITY,authority)
    before={'budget':copy.deepcopy(state['budget']),'source_commit':state['source_commit'],'worktree':state['worktree'],'authorized_gpu_selection':copy.deepcopy(state.get('authorized_gpu_selection'))}
    w.atomic_json(V/'budget-adoption-v1/before-operational-fields.json',before)
    state['budget'].update(max_episode_attempts=578,max_gpu_hours=100.,reserved=copy.deepcopy(c.BASE_CAPS['buckets']),amendment=amendment)
    state['n29_budget_authority']=c.ref(c.BUDGET_AUTHORITY)
    state['source_commit']=review['source_commit'];assert Path(state['worktree']).resolve()==ROOT.resolve()
    state['authorized_gpu_selection'].update(policy='N29 one native resource and separately released40-cell Dev only on idle GPU7; no automatic fallback',root_policy_updated_at=now)
    state['study']['status']='N29_NATIVE_PREFLIGHT_PREPARATION_TARGET_NOT_MET'
    state['cpu_iteration_before_n29_adoption']=copy.deepcopy(state.get('current_iteration'))
    state['current_iteration']={'candidate_id':'N29','arbor_node':'13.1','cohort_id':c.COHORT,'status':'N29_NATIVE_PREFLIGHT_PREPARATION',
       'source_commit':review['source_commit'],'cpu_review':c.ref(V/'root-phase-b-cpu-review-v1.json'),
       'runtime_review':c.ref(V/'root-source-runtime-check-v1.json'),'budget_authority':c.ref(c.BUDGET_AUTHORITY),
       'execution_authorized':False,'validation_authorized':False,'formal_authorized':False,'target_achieved':False}
    state['prospective_iteration'].update(status='NATIVE_PREFLIGHT_PREPARATION',gpu_execution_authorized=False,budget_amendment_adopted=True)
    state['current_cpu_task']={'agent':'n22_cpu_executor','status':'CPU_PHASE_B_COMPLETE_ACCEPTED','cpu_review':c.ref(V/'root-phase-b-cpu-review-v1.json')}
    state['next_action']='Prepare separately released one-shot N29 native proof after finite budget/source acceptance; Dev remains closed.'
    c.require_budget_state(state,vars(r))
    save_yaml(ROOT/'research-state.yaml',state)
    config=r.read_state(ROOT/'research_config.yaml');old_config=copy.deepcopy(config)
    config['budget'].update(max_gpu_hours=100,max_episode_attempts=578);config['task']='Continue frozen RDT/QD/ED autoresearch toward original target; N29 one native proof and separately released Dev on GPU7 only.'
    save_yaml(ROOT/'research_config.yaml',config)
    checkpoint=ROOT/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
    cp=json.loads(checkpoint.read_text());cp.update(status='N29_NATIVE_PREFLIGHT_PREPARATION',active_node='13.1',automatic_gpu_dispatch_authorized=False,
      automatic_gpu_dispatch_scope=None,active_controller=None,owned_gpu_workers=[],in_flight_executor=None,
      executor_task='CPU implementation complete and independently accepted; root preparing one-shot native proof.',budget_snapshot=snapshot,
      source_commit=review['source_commit'],budget_caps=c.BASE_CAPS,n29_phase_b_cpu_review=c.ref(V/'root-phase-b-cpu-review-v1.json'),n29_source_runtime_review=c.ref(V/'root-source-runtime-check-v1.json'),
      next_action=state['next_action'])
    r.durable_json(checkpoint,cp)
    w.atomic_json(V/'budget-adoption-v1/root-adoption-record-v1.json',{'schema':'n29-root-budget-adoption-record-v1','recorded_at':now,
      'authority':c.ref(c.BUDGET_AUTHORITY),'before':before,'after_caps':c.BASE_CAPS,'snapshot':snapshot,
      'protected_remaining_gpu_hours':protected,'nonprotected_available_before':100-snapshot['gpu_hours_consumed']-protected,
      'old_research_config_budget':old_config['budget'],'configuration_synchronized':True,'gpu_dispatch':False,'episode_ledger_changed':False})
print(json.dumps({'adopted':True,'caps':c.BASE_CAPS,'dispatched':snapshot['dispatched'],'gpu_hours':snapshot['gpu_hours_consumed'],'gpu_dispatch':False}))

