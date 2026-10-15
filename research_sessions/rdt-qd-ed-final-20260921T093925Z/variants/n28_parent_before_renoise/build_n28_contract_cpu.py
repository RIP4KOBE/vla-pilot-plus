from pathlib import Path
import ast
p=Path('scripts/qd_ed_n28_contract.py')
s=Path('scripts/qd_ed_n27_contract.py').read_text().replace('n27','n28').replace('N27','N28').replace('n26','n27').replace('N26','N27')
s=s.replace("OLD_DIR=SESSION/'variants/n27_clean_output_rbf'","OLD_DIR=SESSION/'variants/n27_feasible_ray_update'")
s=s.replace("RUN_DIR=SESSION/'variants/n28_feasible_ray_update'","RUN_DIR=SESSION/'variants/n28_parent_before_renoise'")
s=s.replace("SOURCE_PLAN_SHA='cb5fbacbf1a5fe3a77bda0de98bca3b8838474fd6ede7d82319eb35326e32d24'","SOURCE_PLAN_SHA='8632a2f39f0cde0c198f358c1b1700907707d3e0474a75df6b9296cf18f7441f'")
s=s.replace("PROTOCOL=RUN_DIR/'phase-b-integration-protocol-v1.md'","PROTOCOL=RUN_DIR/'execution-integration-cpu-scope-v1.md'")
s=s.replace("PROTOCOL_SHA='165d4efd83a7bf86a5bc1c42c0bea31272b69a86501ee22598bd2a1c6c9fa280'","PROTOCOL_SHA='ab228f33e752a5634103c6294cabcf126640e7ff88e90694c625f741fe96e5db'")
s=s.replace("PHASE_A='bcec3e5e37ee90374c44ca794c81b86eafcb40d6'","PHASE_A='85154b4dcb43046a2fcf2df4e8179b45b58dd2b4'")
s=s.replace("BASE='6026794cd5d52f3a5054bf2704ebb3c516f9f47e'","BASE='e21d48ab33dbd3aca017349b6004c2ba7d981493'")
s=s.replace("COHORT='N28_FEASIBLE_RAY_SCREEN_20261001'","COHORT='N28_PARENT_BEFORE_RENOISE_SCREEN_20261001'")
s=s.replace("'episode_dispatches':18,'recoveries':2,'recoveries_per_cell':1","'episode_dispatches':16,'recoveries':0,'recoveries_per_cell':0")
s=s.replace('9.25','8.25').replace("'attempts':522","'attempts':538").replace("'baseline':62,'development':220","'baseline':66,'development':232")
s=s.replace("PREDECESSOR=OLD_DIR/'root-terminal-review-v1.json'","PREDECESSOR=OLD_DIR/'hydra-continuation-v1/root-terminal-review-v1.json'")
s=s.replace("BUDGET_AUTHORITY=OLD_DIR/'budget-logical-adoption-v1/authority.json'","BUDGET_AUTHORITY=RUN_DIR/'budget-adoption-v1/authority.json'")
s=s.replace("BUDGET_REUSE=RUN_DIR/'budget-reuse-adoption-v1/authority.json'","BUDGET_REUSE=BUDGET_AUTHORITY")
s=s.replace('n28-feasible-ray-screen-v1','n28-parent-before-renoise-screen-v1')
def fn(name,text):
 global s
 tree=ast.parse(s);n=next(n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
 start=min([n.lineno]+[d.lineno for d in n.decorator_list]);lines=s.splitlines(keepends=True)
 lines[start-1:n.end_lineno]=[text.strip()+'\n'];s=''.join(lines)
fn('expected_rows','''def expected_rows():
    rows=original_plan()['episodes']
    w.require(len(rows)==16 and [(x['task_id'],x['profile']) for x in rows]==[(t,a) for t in range(4) for a in ('C0','Q0','N26','N27')],
        'N28 original task-major Dev mapping differs')
    result=[]
    for t in range(4):
        for arm,old in zip(ARMS,rows[t*4:t*4+4]):
            row=copy.deepcopy(old);row.update(iteration=COHORT,profile=arm,episode_key=f'n28_screen_t{t:02d}_{arm.lower()}_20261001')
            w.require(row['split']==row['seed_block']=='dev' and row['timeout_seconds']==1800
                and row['budget_bucket']==('baseline' if arm=='C0' else 'development') and 'retry_of' not in row,'N28 source mapping differs')
            result.append(row)
    return result''')
fn('primary_row','''def primary_row(plan,row):
    w.require(row in plan['episodes'] and not any('retry' in k or 'recovery' in k for k in row),'N28 exact primary only, no retry')
    return row''')
fn('effective_row','''def effective_row(plan,row,events,root,r):
    require_scope(plan,root,r,row);return primary_row(plan,row)''')
fn('supervised_scope','''@contextmanager
def supervised_scope(plan,root,episode_key):
    global _SCOPE
    w.require(_SCOPE is None,'N28 nested scope')
    _SCOPE=(str(Path(root).resolve()),plan['source_commit'],episode_key,os.getpid(),threading.get_ident())
    try:yield
    finally:_SCOPE=None''')
fn('full_capacity','''def full_capacity(state,events,resources,r):
    require_state(state,r);snap=r['budget_snapshot'](events,resources);caps=BASE_CAPS
    from scripts import qd_ed_n28_backend as backend
    backend.settled_proof(w.read_ref(ref(BACKEND_PROOF)),resources,r)
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    charged=[e for e in local if e['event']=='dispatched'];spent=local_seconds(events,resources,r)/3600
    remaining={b:need-sum(e['budget_bucket']==b for e in charged) for b,need in (('baseline',4),('development',12))}
    w.require(len(charged)<=16 and not any(e.get('retry_of') for e in local) and all(v>=0 for v in remaining.values()),'N28 count/retry limit')
    protected_hours=sum(max(0.,h-snap['gpu_hours_by_bucket'][b]) for b,h in caps['protected_gpu_hours'].items())
    protected_attempts=sum(max(0,caps['buckets'][b]-snap['by_bucket'][b]) for b in ('validation','formal'))
    w.require(snap['running']==snap['gpu_healthcheck_inflight']==0
        and all(g[-1]['event'] in r['TERMINAL'] for g in r['event_groups'](events).values()),'N28 unsettled owner/journal')
    w.require(state['budget']['dispatched']==snap['dispatched']
        and abs(state['budget']['gpu_hours_consumed']-snap['gpu_hours_consumed'])<1e-8,'N28 state/ledger mismatch')
    w.require(spent<=8.25 and snap['gpu_hours_consumed']+max(0.,8.25-spent)+protected_hours<=100.+1e-9
        and all(caps['buckets'][b]-snap['by_bucket'][b]>=n for b,n in remaining.items())
        and snap['dispatched']+sum(remaining.values())+protected_attempts<=538,'N28 finite full screen exceeds protected capacity')''')
fn('protected_budget','''def protected_budget(state,events,resources,row,timeout,r,*,plan):
    primary_row(plan,row)
    w.require(row['iteration']==COHORT and row['profile'] in ARMS and timeout==1800,'N28 row/timeout differs')
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    w.require(sum(e['event']=='dispatched' for e in local)<16 and local_seconds(events,resources,r)+1840<=8.25*3600,
        'N28 local cap reached; incomplete is INVALID')
    full_capacity(state,events,resources,r)''')
fn('accepted_cell','''def accepted_cell(plan,row,events,root,r):
    from scripts.qd_ed_n23_v2_recovery import terminal_binding
    groups=list(r['event_groups']([e for e in events if e.get('identity',{}).get('iteration')==COHORT
        and e.get('episode_key')==row['episode_key']]).values())
    w.require(len(groups)==1 and [e['event'] for e in groups[0]]==['reserved','dispatched','valid']
        and not any(e.get('retry_of') for e in groups[0]),'N28 missing/duplicate/retry cell')
    final=groups[0][-1]
    w.require(final.get('outcome_valid') is True and final.get('required_cost_telemetry_complete') is True,'N28 invalid cannot count')
    output=Path(final['output_dir']);context=w.read_ref(ref(output/'n23-worker-context.json'))
    terminal_binding(final,row,plan,context['plan'],r)
    w.require(w.read_ref(context['plan'])==plan and w.read_ref(ref(output/'attempt-result.json'))==final
        and final.get('n23_worker_receipt')==ref(output/'eds_eval/in-worker-audit-receipt.json'),'N28 accepted identity differs')
    report=read_worker_report(output,r);w.require(type(final.get('guided_chunks')) is int,'N28 guided count unknown')
    native.from_output(row['profile'],output,report,final['guided_chunks']);return final''')
fn('admission','''def admission(plan,runtime,row,events,resources,root,r):
    primary=primary_row(plan,row);index=plan['episodes'].index(primary)
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    allowed={v['episode_key'] for v in plan['episodes'][:index]}
    w.require(all(e.get('episode_key') in allowed for e in local),'N28 exact untouched next prefix required')
    for prior in plan['episodes'][:index]:accepted_cell(plan,prior,events,root,r)
    return {'n28_cohort_id':COHORT,'n28_protocol_sha256':PROTOCOL_SHA,'n28_arm_role':'candidate' if row['profile']=='N28' else 'control'}''')
fn('require_protocols','''def require_protocols(root):
    w.require(w.sha(PROTOCOL)==PROTOCOL_SHA,'N28 frozen protocol drift')
    for name,path in (('execution-integration-cpu-scope-v1.md',PROTOCOL),('independent-arithmetic-protocol-v1.md',ARITHMETIC_PROTOCOL)):
        w.require((Path(root)/'experiments/qd_ed_n28'/name).read_bytes()==Path(path).read_bytes(),'N28 tracked protocol drift')
    w.require(w.sha(OBSERVABILITY)==OBSERVABILITY_SHA,'N28 unchanged observability drift')''')
fn('budget_authority','''def budget_authority():
    record=w.read_ref(ref(BUDGET_AUTHORITY))
    w.require(set(record)=={'schema','caps','protocol','predecessor','limits','local_gpu_hours','amendment','recorded_at',
        'authority_interpretation','validation_authorized','formal_authorized'} and record['schema']=='n28-finite-budget-authority-v1'
        and record['caps']==BASE_CAPS and record['protocol']==ref(PROTOCOL) and record['predecessor']==predecessor()
        and record['limits']==LIMITS and record['local_gpu_hours']==8.25 and isinstance(record['amendment'],dict)
        and bool(record['amendment']) and record['validation_authorized'] is False and record['formal_authorized'] is False
        and all(isinstance(record[k],str) and record[k].strip() for k in ('recorded_at','authority_interpretation')),
        'N28 finite budget amendment missing/different')
    return record''')
fn('budget_reuse','''def budget_reuse():
    budget_authority();return ref(BUDGET_AUTHORITY)''')
fn('require_budget_state','''def require_budget_state(state,r):
    authority=budget_authority();caps=authority['caps'];budget=state['budget'];resource=state.get('resource_isolation',{})
    w.require(resource.get('status')=='ACTIVE' and resource.get('validation_status')=='PASS' and resource.get('private_budget') is True
        and state.get('max_concurrent_gpu_workers')==1 and not state.get('external_resource_hold',{}).get('do_not_auto_resume',False)
        and budget.get('gpu_hour_reservations')==caps['protected_gpu_hours'] and state.get('n28_budget_authority')==ref(BUDGET_AUTHORITY)
        and budget['max_episode_attempts']==538 and budget['max_gpu_hours']==100. and budget['reserved']==caps['buckets']
        and budget['amendment']==authority['amendment'] and r['authorized_gpu'](state)==7,'N28 finite budget/resource not adopted')''')
fn('expand_candidate','''def expand_candidate(candidate,baseline,r):
    path=Path(r['ROOT'])/'configs/qd_ed_final/candidate_n28.json'
    w.require(candidate==r['read_json'](path) and candidate['algorithm_contract']=='n28_parent_before_renoise_v1'
        and candidate['baseline_reference']=='N27','N28 closed candidate differs')
    parent=Path(r['ROOT'])/'configs/qd_ed_final/candidate_n27.json'
    w.require(candidate['parent_candidate']=={'path':'configs/qd_ed_final/candidate_n27.json','sha256':w.sha(parent)},'N28 parent differs')
    old=r['read_json'](parent);modes={'rollout_diversity_placement':'parent_before_renoise_v1'}
    w.require(candidate['profile']=={**old['profile'],**modes} and candidate['only_algorithm_change']=={
        'rollout_diversity_placement':{'before':'model_output','after':'parent_before_renoise_v1'}},'N28 sole science delta differs')
    result=r['expand_candidate']('N27',old,baseline)
    result['resolved_eds_config'].update(modes);result['static_override_values'].update({'main.eds_config.'+k:v for k,v in modes.items()})
    result['hydra_overrides']=[f'{k}={r["hydra"](v)}' for k,v in result['static_override_values'].items()]
    return result''')
s=s.replace("n27=manifest['profiles']['N27']['resolved_eds_config'];n28=manifest['profiles']['N28']['resolved_eds_config']\n    w.require(n28=={**n27,'diversity_update_mode':'feasible_ray_v1'}", "n27=manifest['profiles']['N27']['resolved_eds_config'];n28=manifest['profiles']['N28']['resolved_eds_config']\n    w.require(n28=={**n27,'rollout_diversity_placement':'parent_before_renoise_v1'}")
# Existing broad-family exclusions additionally close old N27 administrative markers.
s=s.replace("'n25_','n27_'))", "'n25_','n26_','n27_'))")
s=s.replace("('n25_','n27_','n23_','n24_')","('n25_','n26_','n27_','n23_','n24_')")
s+='''\n\ndef check_retry(events,row,r):
    w.require(row.get('iteration')==COHORT and not any('retry' in k or 'recovery' in k for k in row),'N28 no retry fields')
    w.require(not any(e.get('identity',{}).get('iteration')==COHORT and e.get('episode_key')==row['episode_key'] for e in events),
        'N28 cell already reserved; no restart/retry')
'''
ast.parse(s);p.write_text(s)
