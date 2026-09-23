"""Synthetic-only conditional phases; no actual evaluation outcomes/models/GPU."""
import copy
import json
from pathlib import Path
import sys
from contextlib import nullcontext

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import qd_ed_n2_evaluation as e
import qd_ed_n2_evaluation_report as er
from test_qd_ed_n2_plan import r,n,fixture,ROOT


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);r.durable_json(path,value)
    return {'path':str(path),'sha256':r.digest(path)}


@pytest.fixture
def evaluation(fixture):
    root,base,_,runtime,seeds,_,_=fixture;artifact=Path(base['artifact_root'])
    for i in (1,2):
        seeds['blocks']['validation_c1_b'+str(i)]=[{**x,'env_seed':x['env_seed']+i*1000,'policy_seed':x['policy_seed']+i*1000} for x in seeds['blocks']['dev']]
    seeds['blocks']['formal']=[{**x,'env_seed':x['env_seed']+4000,'policy_seed':x['policy_seed']+4000} for x in seeds['blocks']['dev']]
    base.update(seed_plan_path=str(root/'seeds.json'),seed_plan_sha256=e.SEED_SHA)
    save(root/'seeds.json',seeds)
    (root/'data').mkdir()
    for name in ('attempt-ledger.jsonl','exposure-registry.jsonl','historical-exposure-inventory.jsonl'):(root/'data'/name).write_text('')
    (root/'data/qd-ed-state.lock').touch()
    for path in e.TOOLING:
        target=root/path;target.parent.mkdir(parents=True,exist_ok=True)
        if path!=e.PROFILE:target.write_bytes((ROOT/path).read_bytes())
    base['code_files'].append({'path':'scripts/qd_ed_final_runner.py','sha256':'old-tooling-hash'})
    base.update(runtime_manifest_path=str(artifact/'runtime.json'),worktree=str(root),run_name='synthetic')
    save(artifact/'runtime.json',runtime)
    base['episodes']=n.rows_from_dev(seeds)
    bref=save(artifact/'base-dev.json',base)
    observed=r.read_json(root/n.OBSERVED);candidate=r.read_json(root/n.PROFILE)
    profile=e.evaluation_profiles(observed,candidate,r);save(root/e.PROFILE,profile)
    manifest=copy.deepcopy(profile);manifest['profiles']['N2']=r.expand_candidate('N2',candidate,manifest['profiles']['Q0'])
    def plan_for(phase):
        p=copy.deepcopy(base);prior=p.pop('n2_cohort');p.update(frozen=False,source_commit='new-phase-tools',
            profiles_path=str(root/e.PROFILE),profiles_sha256=r.digest(root/e.PROFILE),episodes=e.rows(seeds,phase),
            phase_authorization={'dev':False,'validation':False,'formal':False})
        files={x['path']:x['sha256'] for x in base['code_files']}
        p['code_files']=[{'path':k,'sha256':r.digest(root/k)} for k in sorted(set(files)|e.TOOLING)]
        production=[{'path':k,'sha256':files[k]} for k in sorted(set(files)-e.TOOLING)]
        fp=e.sha_json({'production_files':production,'candidate_profiles':base['candidate_profiles'],
            'runtime_manifest_sha256':base['runtime_manifest_sha256'],'runtime_inventory_sha256':base['runtime_inventory_sha256'],
            'seed_plan_sha256':base['seed_plan_sha256']})
        p['n2_evaluation']={'schema':e.SCHEMA,'phase':phase,'cohort_id':e.PHASES[phase]['cohort_id'],
            'limits':copy.deepcopy(e.PHASES[phase]),'protocol':{'path':e.PROTOCOL,'sha256':e.PROTOCOL_SHA},
            'budget_clarification':{'path':e.CLARIFICATION,'sha256':e.CLARIFICATION_SHA},
            'dev_reporter':{'path':str(e.DEV_REPORT),'sha256':e.DEV_REPORT_SHA},'dev_plan':bref,
            'candidate_fingerprint':fp,'promotion_certificate':None,
            'source_mapping':{'dev_source_commit':base['source_commit'],'evaluation_source_commit':p['source_commit'],
                'allowed_tooling':sorted(e.TOOLING),'production_files':production},
            'runtime_prerequisites':prior['runtime_prerequisites'],'health_resources':prior['health_resources']}
        return p
    return root,base,manifest,runtime,seeds,plan_for


@pytest.mark.parametrize('phase,count,per_arm',[('validation',60,20),('formal',40,10)])
def test_exact_matrix_default_closed_and_seed_blocks_do_not_collapse(evaluation,phase,count,per_arm):
    root,_,manifest,runtime,seeds,make=evaluation;p=make(phase)
    e.validate_contract(p,manifest,runtime,seeds,root,r)
    assert len(p['episodes'])==len({e.cell(x) for x in p['episodes']})==count
    assert sum(x['profile']=='N2' for x in p['episodes'])==per_arm
    assert not any(p['phase_authorization'].values())
    changed=copy.deepcopy(p);changed['episodes'][0]['env_seed']+=1
    with pytest.raises(r.GateError,match='matrix/order'):e.validate_contract(changed,manifest,runtime,seeds,root,r)
    changed=copy.deepcopy(p);changed['phase_authorization'][phase]=True
    with pytest.raises(r.GateError,match='certificate missing'):e.validate_contract(changed,manifest,runtime,seeds,root,r)


def test_unchanged_production_and_exact_archive_only_ablation(evaluation):
    root,_,manifest,runtime,seeds,make=evaluation;p=make('formal')
    active=manifest['profiles']['N2'];off=manifest['profiles']['N2_QD_OFF']
    for section in ('restored_profile','resolved_eds_config'):
        assert {k:(active[section].get(k),off[section].get(k)) for k in active[section] if active[section].get(k)!=off[section].get(k)}=={'qd_archive_mode':('grid_archive','none')}
        assert off[section]['qd_quality_mode']=='executed_prefix_v1' and off[section]['qd_parent_sampling']=='sparse_priority'
    changed=copy.deepcopy(p)
    next(x for x in changed['code_files'] if x['path']=='core/qd_ed.py')['sha256']='drift'
    with pytest.raises(r.GateError,match='production source changed'):e.scientific_mapping(changed,root,r)
    changed=copy.deepcopy(p);changed['code_files'].append({'path':'core/new_algorithm.py','sha256':'other'})
    with pytest.raises(r.GateError,match='unapproved'):e.scientific_mapping(changed,root,r)


def test_seed_allocation_exposure_recheck_and_formal_latch(evaluation):
    root,_,_,_,_,make=evaluation;validation=make('validation');row=validation['episodes'][0]
    (root/'data/exposure-registry.jsonl').write_text(json.dumps({'task_id':row['task_id'],'episode_seed':row['env_seed']})+'\n')
    with pytest.raises(r.GateError,match='already exposed'):e.allocate(validation,[],root,r)
    (root/'data/exposure-registry.jsonl').write_text('')
    e.allocate(validation,[],root,r);e.allocate(validation,[],root,r)
    formal=make('formal');e.allocate(formal,[],root,r);e.allocate(formal,[],root,r)
    other=copy.deepcopy(formal);other['n2_evaluation']['candidate_fingerprint']='another-candidate'
    with pytest.raises(r.GateError,match='binding changed|candidate already'):e.allocate(other,[],root,r)


def raw_attempt(plan,row,attempt='a',*,valid=False,event='aborted',reason='external GPU3 process appeared during owned attempt',retry_of=None):
    return {'attempt_id':attempt,'episode_key':row['episode_key'],'identity':r.episode_identity(row),
        'event':event,'outcome_valid':valid,'success':False,'retryable_infrastructure':True,
        'failure_class':'infrastructure','reason':reason,'retry_of':retry_of,'n2_frozen_identity':e.binding(plan),
        'gpu_process_wall_seconds':12.,'time_unix':1 if retry_of is None else 2}


@pytest.mark.parametrize('reason',['GPU3 boot identity changed','GPU3 UUID changed','GPU3 owned process Xid detected; see sanitized kernel monitor evidence','TimeoutExpired','nonfinite action'])
def test_ambiguous_native_algorithm_identity_and_episode_timeout_never_recover(evaluation,reason):
    *_,make=evaluation;p=make('validation');t=raw_attempt(p,p['episodes'][0],reason=reason)
    assert not e.recoverable(t,e.binding(p))


def test_precise_resource_and_transport_recovery_preserve_raw_event(evaluation):
    *_,make=evaluation;p=make('validation');row=p['episodes'][0]
    t=raw_attempt(p,row);assert e.recoverable(t,e.binding(p))
    t=raw_attempt(p,row,reason='GPU3 nvidia-smi monitor query timed out after 15 seconds')
    assert not e.recoverable(t,e.binding(p))
    t.update(failure_detail='gpu_monitor_timeout',gpu_monitor_timeout={'physical_gpu':3,'timeout_seconds':15})
    assert e.recoverable(t,e.binding(p))
    t.update(event='valid',retryable_infrastructure=False,failure_class='task_failure',reason=n.TRANSPORT_GATE,
        compute_outcome='completed',required_cost_telemetry_complete=True,stage_backend='codex_cli',provider_failed_calls=1,stage_failed_queries=1)
    before=copy.deepcopy(t);eligibility=e.transport_eligibility(r.GateError(n.TRANSPORT_GATE),t,p,r)
    assert t==before;t['n2_recovery_eligibility']=eligibility
    assert e.recoverable(t,e.binding(p)) and t['event']=='valid' and t['failure_class']=='task_failure'
    t['outcome_valid']=True;assert not e.recoverable(t,e.binding(p))


def test_partial_report_keeps_full_denominators_unknown_and_ablation_no_superiority_gate(evaluation):
    root,_,_,_,_,make=evaluation;d=e.frozen_report(r)
    p=make('validation');report=er.summarize(p,[],r,d)
    assert not report['complete'] and report['numeric_pass'] is None and len(report['cells'])==60
    assert all(x['expected']==20 and x['success_rate'] is None for x in report['profiles'].values())
    p=make('formal');attempts=[]
    for i,row in enumerate(p['episodes']):
        t=raw_attempt(p,row,str(i),valid=True,event='valid');t['success']=(row['task_id']<5 or row['profile']=='N2_QD_OFF')
        attempts.append({'terminal':t,'status':'complete_valid','metrics':{}})
    report=er.summarize(p,attempts,r,d)
    assert report['complete'] and report['numeric_pass'] is True
    assert report['paired_comparisons']['N2_vs_N2_QD_OFF']['success_delta']==-5


def test_recovered_report_charges_both_attempts_and_does_not_drop_invalid(evaluation):
    *_,make=evaluation;p=make('validation');row=p['episodes'][0]
    retry={**row,'episode_key':'retry','retry_of':'a','budget_bucket':'recovery','n2_evaluation_recovery_contract':e.binding(p)}
    p['episodes'].append(retry)
    first=raw_attempt(p,row);second=raw_attempt(p,retry,'b',valid=True,event='valid',retry_of='a')
    report=er.summarize(p,[{'terminal':first,'status':'terminal_invalid'},{'terminal':second,'status':'complete_valid','metrics':{}}],r,e.frozen_report(r))
    assert report['profiles']['C0']['all_attempt_gpu_seconds']['complete_total']==24
    assert len(report['cells'][0]['attempts'])==2 and report['profiles']['C0']['complete_valid']==1
    first['reason']='GPU3 UUID changed'
    with pytest.raises(r.GateError,match='ineligible'):er.summarize(p,[{'terminal':first,'status':'terminal_invalid'},{'terminal':second,'status':'complete_valid','metrics':{}}],r,e.frozen_report(r))


def test_direct_runner_requires_supervisor_before_gpu(evaluation,monkeypatch):
    from test_qd_ed_final_runner import events_for,synced_state
    root,_,manifest,runtime,_,make=evaluation;p=make('validation');p['frozen']=True;p['phase_authorization']['validation']=True
    events=events_for();events[-1]['gpu_process_wall_seconds']=37.6*3600
    state=synced_state(events);state['gpu_pool']=[3]
    monkeypatch.setattr(r,'locked',lambda *a,**k:nullcontext())
    monkeypatch.setattr(r,'validate_plan',lambda *a,**k:(p,manifest,runtime))
    monkeypatch.setattr(r,'read_state',lambda *a:state)
    monkeypatch.setattr(r,'read_events',lambda path:events if Path(path).name=='attempt-ledger.jsonl' else [])
    monkeypatch.setattr(r,'gpu_admission',lambda **kw:pytest.fail('must not reach GPU'))
    with pytest.raises(r.GateError,match='dedicated owned supervisor'):
        r.run_plan('plan',split='validation',iteration=e.PHASES['validation']['cohort_id'],episode_keys=[p['episodes'][0]['episode_key']],root=root)


def dev_promotion(evaluation,monkeypatch):
    root,base,_,_,_,make=evaluation;p=make('validation');artifact=Path(p['artifact_root']);d=e.frozen_report(r)
    base_ref=p['n2_evaluation']['dev_plan'];d.BASE_PLAN_SHA=base_ref['sha256']
    original_loader=e.frozen_report
    def loader(runner):
        value=original_loader(runner);value.BASE_PLAN_SHA=base_ref['sha256'];return value
    monkeypatch.setattr(e,'frozen_report',loader)
    specs=[];events=[]
    for i,row in enumerate(base['episodes']):
        out=artifact/f'dev-{i}';compute_path=out/'eds_eval/episode_compute.jsonl'
        guided=row['profile']=='N2' and row['task_id']==0
        values={k:(None if k in d.HTTP or k=='provider_reasoning_output_tokens' else 0) for k in d.COSTS}
        values.update(guided_chunks=int(guided),candidate_evaluations=176 if guided else 0,score_batches=11 if guided else 0)
        terminal={**values,'attempt_id':f'dev-{i}','episode_key':row['episode_key'],'identity':r.episode_identity(row),
            'event':'valid','outcome_valid':True,'success':row['task_id']<(5 if row['profile']=='N2' else 4),
            'gpu_process_wall_seconds':10.,'time_unix':i,'output_dir':str(out),'physical_gpu':3,
            'source_commit':base['source_commit'],'profile_manifest_sha256':base['profiles_sha256'],
            'runtime_manifest_sha256':base['runtime_manifest_sha256'],'runtime_inventory_sha256':base['runtime_inventory_sha256'],
            'init_row_sha256':row['init_row_sha256'],'retry_of':None,'n2_cohort_id':n.COHORT,
            'n2_frozen_identity':n.binding(base,{'frozen_stage_provider':{'public_config_sha256':'transport'}}),
            'plan_sha256':base_ref['sha256'],'metric_chunks':int(guided),'compute_outcome':'completed',
            'required_cost_telemetry_complete':True,'stage_backend':'codex_cli','stage_condition':'codex_login_astra_low_v1',
            'provider_token_usage_complete':True,'provider_failed_calls':0,'stage_failed_queries':0,'budget_bucket':'development'}
        tref=save(out/'attempt-result.json',terminal)
        audit={'accepted':True,'evidence_complete':True,'errors':[],'original_execution_outcome':'completed',
            'episode_dir':str(out/'eds_eval/decision_evidence/episode_000'),'episode_compute_file':str(compute_path)}
        aref=save(out/'eds_eval/decision-evidence-audit.json',audit)
        compute={**values,'episode_id':0,'task_id':row['task_id'],'episode_seed':row['env_seed'],'outcome':'completed'}
        compute_path.write_text(json.dumps(compute)+'\n');cref={'path':str(compute_path),'sha256':r.digest(compute_path)}
        metrics=[]
        if guided:
            metrics=[{'episode':0,'task_id':0,'global_step':0,'score_call_count':11,'search_evaluation_count':176,
                **dict.fromkeys(d.VIOLATIONS,0),'action_mask_violation_max':0.,'qd_archive_active_for_chunk':True,
                'qd_quality_mode':'executed_prefix_v1','qd_quality_applicable':True,'qd_quality_reason':'recognized',
                'qd_quality_target_index':0,'qd_quality_identity':{'binding':'synthetic'},'qd_quality_changed_candidates':176,
                'qd_selected_raw_reward':-1.,'qd_final_best_raw_reward':-1.,'qd_selected_raw_gap':0.,'selected_reward':-2.,
                'qd_best_observed_raw_reward':-1.,'qd_quality_batches':[{'iter_idx':it,'raw_provider_quality':[-1.]*16,'quality':[-2.]*16,'fingerprints':[str(j) for j in range(16)]} for it in range(-1,10)]}]
        mp=out/'eds_eval/eds_metrics.jsonl';mp.write_text(''.join(json.dumps(x)+'\n' for x in metrics))
        specs.append({'terminal':tref,'audit':aref,'compute':cref,'metrics':{'path':str(mp),'sha256':r.digest(mp)}})
        first={**terminal,'event':'reserved'};events.extend([first,{**first,'event':'dispatched'},terminal])
    protocol_sha=r.digest(e.DEV_REPORT.with_name('protocol.md'))
    auth=save(artifact/'dev-auth.json',{'script':{'path':str(e.DEV_REPORT),'sha256':e.DEV_REPORT_SHA},'protocol_sha256':protocol_sha,'base_plan_sha256':base_ref['sha256']})
    m={'script_sha256':e.DEV_REPORT_SHA,'protocol_sha256':protocol_sha,'base_plan':base_ref,'attempts':specs,'input_scope_complete':True,'authorization':auth}
    attempts=[d.load_attempt(spec,{base_ref['sha256']:base}) for spec in specs]
    report=d.summarize(base,attempts);report['input_manifest']=m
    reportref=save(artifact/'dev-report.json',report)
    evidence=save(artifact/'synthetic-reviewed-evidence.json',{'fixture_only':True})
    review=save(artifact/'review.json',{'schema':'qd-ed-n2-scientific-review-v1','report':reportref,
        'candidate_fingerprint':p['n2_evaluation']['candidate_fingerprint'],'checks':dict.fromkeys(e.CHECKS,True),
        'evidence_by_check':{k:[evidence] for k in e.CHECKS}})
    certificate={'schema':'qd-ed-n2-evaluation-promotion-v1','target_phase':'validation',
        'candidate_fingerprint':p['n2_evaluation']['candidate_fingerprint'],'protocol_sha256':e.PROTOCOL_SHA,'budget_clarification_sha256':e.CLARIFICATION_SHA,'target_binding':e.binding(p),'report':reportref,'review':review}
    p['n2_evaluation']['promotion_certificate']=save(artifact/'certificate.json',certificate)
    return root,p,events,report,certificate


def test_recomputes_full_frozen_report_not_passed_boolean(evaluation,monkeypatch):
    root,p,events,report,certificate=dev_promotion(evaluation,monkeypatch)
    e.reviewed_promotion(p,events,root,r)
    with pytest.raises(r.GateError,match='inventory differs'):e.reviewed_promotion(p,events[:-3],root,r)
    drift=copy.deepcopy(events);drift[-1]['success']=not drift[-1]['success']
    with pytest.raises(r.GateError,match='raw authoritative'):e.reviewed_promotion(p,drift,root,r)
    report['profiles']['N2']['successes_observed']=10
    certificate['report']=save(Path(p['artifact_root'])/'forged-report.json',report)
    p['n2_evaluation']['promotion_certificate']=save(Path(p['artifact_root'])/'forged-cert.json',certificate)
    with pytest.raises(r.GateError,match='recomputed Dev evidence'):e.reviewed_promotion(p,events,root,r)


def test_missing_or_partial_promotion_rejected_before_dispatch(evaluation,monkeypatch):
    root,p,events,report,certificate=dev_promotion(evaluation,monkeypatch)
    p['n2_evaluation']['promotion_certificate']=None
    with pytest.raises(r.GateError,match='reference missing'):e.reviewed_promotion(p,events,root,r)
    report['input_manifest']['attempts']=report['input_manifest']['attempts'][:-1]
    certificate['report']=save(Path(p['artifact_root'])/'partial-report.json',report)
    p['n2_evaluation']['promotion_certificate']=save(Path(p['artifact_root'])/'partial-cert.json',certificate)
    with pytest.raises(r.GateError,match='recomputed Dev evidence'):e.reviewed_promotion(p,events,root,r)


def validation_report_fixture(evaluation,monkeypatch):
    root,vplan,dev_events,dev_report,dev_cert=dev_promotion(evaluation,monkeypatch)
    vplan.update(frozen=True,phase_authorization={'dev':False,'validation':True,'formal':False})
    artifact=Path(vplan['artifact_root']);vref=save(artifact/'validation-plan.json',vplan)
    specs=[];journal=[]
    for i,row in enumerate(vplan['episodes']):
        template=dev_report['input_manifest']['attempts'][row['task_id']*3+('C0','Q0','N2').index(row['profile'])]
        out=artifact/f'validation-{i}';t=r.read_json(template['terminal']['path'])
        t.update(attempt_id=f'validation-{i}',episode_key=row['episode_key'],identity=r.episode_identity(row),
            output_dir=str(out),source_commit=vplan['source_commit'],profile_manifest_sha256=vplan['profiles_sha256'],
            n2_cohort_id=vplan['n2_evaluation']['cohort_id'],n2_frozen_identity=e.binding(vplan),plan_sha256=vref['sha256'],
            budget_bucket='validation',time_unix=100+i)
        tref=save(out/'attempt-result.json',t)
        compute=r.read_events(template['compute']['path'])[0];compute['episode_seed']=row['env_seed']
        cp=out/'eds_eval/episode_compute.jsonl';cp.parent.mkdir(parents=True,exist_ok=True);cp.write_text(json.dumps(compute)+'\n')
        audit=r.read_json(template['audit']['path']);audit.update(episode_dir=str(out/'eds_eval/decision_evidence/episode_000'),episode_compute_file=str(cp))
        aref=save(out/'eds_eval/decision-evidence-audit.json',audit)
        mp=out/'eds_eval/eds_metrics.jsonl';mp.write_bytes(Path(template['metrics']['path']).read_bytes())
        specs.append({'terminal':tref,'audit':aref,'compute':{'path':str(cp),'sha256':r.digest(cp)},'metrics':{'path':str(mp),'sha256':r.digest(mp)}})
        journal.extend([{**t,'event':'reserved'},{**t,'event':'dispatched'},t])
    m={'schema':'qd-ed-n2-evaluation-report-input-v1','script_sha256':r.digest(root/e.REPORT),
        'protocol_sha256':e.PROTOCOL_SHA,'base_plan':vref,'attempts':specs}
    report,_,_=er.recompute(m,root,r);report['input_manifest']=m
    return root,vplan,dev_events+journal,report


def test_formal_requires_recomputed_full60_validation_and_retains_two_blocks(evaluation,monkeypatch):
    root,vplan,journal,report=validation_report_fixture(evaluation,monkeypatch)
    assert report['complete'] and report['numeric_pass'] and report['profiles']['N2']['successes_observed']==10
    assert len(report['cells'])==60 and len(report['profiles']['N2']['blocks'])==2
    formal=evaluation[-1]('formal');artifact=Path(formal['artifact_root'])
    ref=save(artifact/'validation-report.json',report)
    evidence=save(artifact/'validation-review-evidence.json',{'synthetic_only':True})
    review=save(artifact/'validation-review.json',{'schema':'qd-ed-n2-scientific-review-v1','report':ref,
        'candidate_fingerprint':formal['n2_evaluation']['candidate_fingerprint'],'checks':dict.fromkeys(e.CHECKS,True),
        'evidence_by_check':{k:[evidence] for k in e.CHECKS}})
    cert={'schema':'qd-ed-n2-evaluation-promotion-v1','target_phase':'formal','protocol_sha256':e.PROTOCOL_SHA,'budget_clarification_sha256':e.CLARIFICATION_SHA,
        'candidate_fingerprint':formal['n2_evaluation']['candidate_fingerprint'],'target_binding':e.binding(formal),'report':ref,'review':review}
    formal['n2_evaluation']['promotion_certificate']=save(artifact/'formal-cert.json',cert)
    e.reviewed_promotion(formal,journal,root,r)
    with pytest.raises(r.GateError,match='inventory differs'):e.reviewed_promotion(formal,journal[:-3],root,r)
    failed=copy.deepcopy(formal);failed['n2_evaluation']['candidate_fingerprint']='modified'
    with pytest.raises(r.GateError,match='certificate identity'):e.reviewed_promotion(failed,journal,root,r)


def test_rejected_audit_cannot_be_promoted_by_report_boolean(evaluation,monkeypatch):
    root,p,events,report,certificate=dev_promotion(evaluation,monkeypatch)
    spec=report['input_manifest']['attempts'][0]
    audit=r.read_json(spec['audit']['path']);audit['evidence_complete']=False
    spec['audit']=save(Path(spec['audit']['path']),audit)
    # Even a correctly hashed, edited report claiming pass cannot bypass the
    # frozen loader's rule against metric reads after rejected audit.
    certificate['report']=save(Path(p['artifact_root'])/'bad-audit-report.json',report)
    p['n2_evaluation']['promotion_certificate']=save(Path(p['artifact_root'])/'bad-audit-cert.json',certificate)
    with pytest.raises(ValueError,match='rejected audit'):e.reviewed_promotion(p,events,root,r)


@pytest.mark.parametrize('phase,recoveries',[('validation',4),('formal',2)])
def test_recovery_plan_limits_and_required_certificate(evaluation,phase,recoveries):
    root,_,manifest,runtime,seeds,make=evaluation;p=make(phase)
    for i in range(recoveries):
        row=p['episodes'][i]
        p['episodes'].append({**row,'episode_key':f'retry{i}','retry_of':f'old{i}','budget_bucket':'recovery',
            'n2_evaluation_recovery_contract':e.binding(p),'recovery_release':{'path':'unused-unreleased-fixture','sha256':'x'}})
    e.validate_contract(p,manifest,runtime,seeds,root,r)
    missing=copy.deepcopy(p);missing['episodes'][-1].pop('recovery_release')
    with pytest.raises(r.GateError,match='immutable certificate'):e.validate_contract(missing,manifest,runtime,seeds,root,r)
    row=p['episodes'][recoveries]
    p['episodes'].append({**row,'episode_key':'excess','retry_of':'old-last','budget_bucket':'recovery',
        'n2_evaluation_recovery_contract':e.binding(p),'recovery_release':{'path':'unused','sha256':'x'}})
    with pytest.raises(r.GateError,match='retry allowance'):e.validate_contract(p,manifest,runtime,seeds,root,r)


def test_recovery_release_matches_exact_original_terminal(evaluation):
    *_,make=evaluation;p=make('validation');row=p['episodes'][0];original=raw_attempt(p,row)
    ref=save(Path(p['artifact_root'])/'original-terminal.json',original)
    retry={**row,'episode_key':'retry','retry_of':'a','budget_bucket':'recovery','n2_evaluation_recovery_contract':e.binding(p)}
    cert={'schema':'qd-ed-n2-evaluation-recovery-v1','retry_of':'a','frozen_identity':e.binding(p),'original_terminal':ref}
    retry['recovery_release']=save(Path(p['artifact_root'])/'recovery-release.json',cert)
    e.recovery_release(p,retry,original,r)
    changed=copy.deepcopy(original);changed['reason']='GPU3 UUID changed'
    with pytest.raises(r.GateError,match='exact eligible'):e.recovery_release(p,retry,changed,r)


def test_genuine_numeric_failure_is_not_promoted_even_with_true_review(evaluation,monkeypatch):
    root,p,events,report,certificate=dev_promotion(evaluation,monkeypatch)
    spec=report['input_manifest']['attempts'][4*3+2]
    terminal=r.read_json(spec['terminal']['path']);terminal['success']=False
    spec['terminal']=save(Path(spec['terminal']['path']),terminal)
    for i,event in enumerate(events):
        if event['attempt_id']==terminal['attempt_id'] and event['event']=='valid':events[i]=terminal
    d=e.frozen_report(r);m=report['input_manifest'];base=d.read_ref(m['base_plan'])
    report=d.summarize(base,[d.load_attempt(x,{m['base_plan']['sha256']:base}) for x in m['attempts']]);report['input_manifest']=m
    assert report['protocol_numeric_dev_criterion'] is False
    certificate['report']=save(Path(p['artifact_root'])/'numeric-failure.json',report)
    p['n2_evaluation']['promotion_certificate']=save(Path(p['artifact_root'])/'numeric-cert.json',certificate)
    with pytest.raises(r.GateError,match='numeric failure'):e.reviewed_promotion(p,events,root,r)


def test_remaining_global_recovery_capacity_is_still_enforced(evaluation):
    from test_qd_ed_final_runner import events_for,synced_state
    *_,make=evaluation;p=make('validation');row={**p['episodes'][0],'budget_bucket':'recovery'}
    events=[]
    for i in range(20):events+=events_for(str(i),bucket='recovery',terminal='aborted',retryable=True)
    state=synced_state(events);state['gpu_pool']=[3]
    with pytest.raises(r.GateError,match='recovery reserve exhausted'):r.check_budget(state,events,row,physical_gpu=3)


from contextlib import contextmanager
from types import SimpleNamespace
import os
import threading
import qd_ed_n2_supervise as supervision
import qd_ed_n2_evaluate as entry


@contextmanager
def owned_scope(root,plan,keys):
    """Real flock, actual supervisor wrappers; only the kernel/GPU probes mocked."""
    import fcntl
    support=supervision.load_support(ROOT,n.SUPPORT)
    lock=root/'data/qd-ed-runner.lock';lock.touch(exist_ok=True)
    monitor=SimpleNamespace(parent_pid=os.getpid(),root=root,episode_keys=frozenset(keys),require_boot=lambda:None)
    queue=SimpleNamespace(pending_gate=lambda *a,**k:None,bind_plan=lambda *a,**k:None)
    original=r.locked
    with lock.open('a+') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX)
        @contextmanager
        def reentrant(path,**kwargs):
            if Path(path)==lock:yield
            else:
                with original(path,**kwargs):yield
        r.locked=reentrant
        st=lock.stat();status=root/'owned-status.json'
        r.durable_json(status,{'status':'shared_runner_acquired','pid':os.getpid(),'owner_thread_id':threading.get_ident(),
            'boot_id':plan['boot_id'],'runner_lock_path':str(lock),'runner_lock_device':st.st_dev,'runner_lock_inode':st.st_ino})
        try:
            with support.supervise_calls(r,queue,monitor,lambda:None),supervision.frozen_hardware(r,queue):
                with e.supervised_dispatch(plan,keys,root,r,queue,monitor,status):yield queue
        finally:
            r.locked=original;fcntl.flock(stream,fcntl.LOCK_UN)


def retry_plan(plan,journal):
    row=plan['episodes'][0]
    original={**raw_attempt(plan,row,'phase-original'),'budget_bucket':row['budget_bucket']}
    journal=journal+[{**original,'event':'reserved'},{**original,'event':'dispatched'},original]
    retry={**row,'episode_key':row['episode_key']+'_r1','retry_of':'phase-original','budget_bucket':'recovery',
        'n2_evaluation_recovery_contract':e.binding(plan)}
    terminal=save(Path(plan['artifact_root'])/'retry-original.json',original)
    retry['recovery_release']=save(Path(plan['artifact_root'])/'retry-certificate.json',{
        'schema':'qd-ed-n2-evaluation-recovery-v1','retry_of':'phase-original',
        'frozen_identity':e.binding(plan),'original_terminal':terminal})
    plan['episodes'].append(retry)
    plan.update(frozen=True,phase_authorization={'dev':False,'validation':plan['n2_evaluation']['phase']=='validation',
        'formal':plan['n2_evaluation']['phase']=='formal'})
    return retry,journal


def certified_formal(evaluation,monkeypatch):
    root,_,events,report=validation_report_fixture(evaluation,monkeypatch)
    plan=evaluation[-1]('formal');artifact=Path(plan['artifact_root'])
    ref=save(artifact/'release-validation-report.json',report)
    proof=save(artifact/'release-review-proof.json',{'synthetic':True})
    review=save(artifact/'release-review.json',{'schema':'qd-ed-n2-scientific-review-v1','report':ref,
        'candidate_fingerprint':plan['n2_evaluation']['candidate_fingerprint'],'checks':dict.fromkeys(e.CHECKS,True),
        'evidence_by_check':{k:[proof] for k in e.CHECKS}})
    plan['n2_evaluation']['promotion_certificate']=save(artifact/'release-promotion.json',{
        'schema':'qd-ed-n2-evaluation-promotion-v1','target_phase':'formal','protocol_sha256':e.PROTOCOL_SHA,
        'budget_clarification_sha256':e.CLARIFICATION_SHA,'target_binding':e.binding(plan),
        'candidate_fingerprint':plan['n2_evaluation']['candidate_fingerprint'],'report':ref,'review':review})
    return root,plan,events


def test_scope_real_flock_owner_hooks_and_release(evaluation):
    root,_,_,_,_,make=evaluation;plan=make('validation');keys=[plan['episodes'][0]['episode_key']]
    with pytest.raises(r.GateError,match='dedicated owned'):e.require_scope(plan,root,r)
    with owned_scope(root,plan,keys):
        e.require_scope(plan,root,r,plan['episodes'][0])
        with pytest.raises(r.GateError,match='outside evaluation'):e.require_scope(plan,root,r,plan['episodes'][1])
        before=r.wait_exclusively
        try:
            r.wait_exclusively=lambda *a:None
            with pytest.raises(r.GateError,match='hooks changed'):e.require_scope(plan,root,r)
        finally:r.wait_exclusively=before
    assert e._ACTIVE_SCOPE is None
    with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):pass


def test_generic_bind_and_queue_reject_before_gpu(evaluation,monkeypatch):
    import qd_ed_available_gpu_queue as q
    root,_,manifest,runtime,_,make=evaluation;plan=make('validation')
    monkeypatch.setattr(q,'runner',r)
    monkeypatch.setattr(r,'gpu_admission',lambda *a,**k:pytest.fail('no GPU'))
    monkeypatch.setattr(q,'current_metadata',lambda *a,**k:pytest.fail('no metadata/probe'))
    with pytest.raises(r.GateError,match='generic bind/probe forbidden'):
        q.bind_plan('plan',plan,runtime,{},plan['episodes'][0],'log',root=root)
    monkeypatch.setattr(r,'validate_plan',lambda *a,**k:(plan,manifest,runtime))
    monkeypatch.setattr(r,'read_state',lambda *a:{'artifacts':plan['artifact_root']})
    monkeypatch.setattr(r,'verify_provider',lambda *a,**k:pytest.fail('no provider'))
    with pytest.raises(r.GateError,match='dedicated owned supervisor'):
        q.run_queue('plan',[plan['episodes'][0]['episode_key']],status_path=Path(plan['artifact_root'])/'direct.json',root=root)


@pytest.mark.parametrize('phase',['validation','formal'])
def test_certified_phase_recovery_uses_only_own_hours_without_raw_accounting_change(evaluation,monkeypatch,phase):
    from test_qd_ed_final_runner import events_for,synced_state
    if phase=='validation':root,plan,journal,_,_=dev_promotion(evaluation,monkeypatch)
    else:root,plan,journal=certified_formal(evaluation,monkeypatch)
    row,journal=retry_plan(plan,journal)
    prior=events_for('historical-cost');prior[-1]['gpu_process_wall_seconds']=25*3600
    journal=prior+journal;state=synced_state(journal);state['gpu_pool']=[3]
    before=copy.deepcopy((state,journal,plan));snap=r.budget_snapshot(journal)
    with pytest.raises(r.GateError,match='termination grace'):r.check_budget(state,journal,row,physical_gpu=3)
    with owned_scope(root,plan,[row['episode_key']]):
        permission=e.validated_budget_context(plan,evaluation[3],row,journal,[],root,r)
        assert r.check_budget(state,journal,row,physical_gpu=3,evaluation_context=permission)==1800
        assert e.hour_reservation_exclusion(permission,state,journal,row,[],[],r)==phase
        wrong={**row,'split':'formal' if phase=='validation' else 'validation'}
        with pytest.raises(r.GateError,match='row/journal changed'):
            r.check_budget(state,journal,wrong,physical_gpu=3,evaluation_context=permission)
        altered=copy.deepcopy(state);altered['budget']['reserved']['formal']=39
        with pytest.raises(r.GateError,match='reserve was reduced'):
            r.check_budget(altered,journal,row,physical_gpu=3,evaluation_context=permission)
    with pytest.raises(r.GateError,match='unvalidated evaluation'):
        r.check_budget(state,journal,row,physical_gpu=3,evaluation_context=permission)
    assert (state,journal,plan)==before and r.budget_snapshot(journal)==snap
    assert snap['by_bucket']['recovery']==0  # Permission itself dispatches/charges nothing.


def test_phase_hours_do_not_clip_or_consume_remaining_formal_protection(evaluation,monkeypatch):
    from test_qd_ed_final_runner import events_for,synced_state
    root,plan,journal,_,_=dev_promotion(evaluation,monkeypatch);row,journal=retry_plan(plan,journal)
    old=events_for('history');old[-1]['gpu_process_wall_seconds']=37.6*3600;journal=old+journal
    state=synced_state(journal);state['gpu_pool']=[3]
    with owned_scope(root,plan,[row['episode_key']]):
        permission=e.validated_budget_context(plan,evaluation[3],row,journal,[],root,r)
        # Exact default helper behavior remains; dedicated entry rejects clipping.
        assert 0<r.check_budget(state,journal,row,physical_gpu=3,evaluation_context=permission)<1800
        queue=SimpleNamespace(pending_gate=lambda *a:None,candidate_indices=lambda state:[3],no_unfinished=lambda root:(journal,[]))
        monkeypatch.setattr(r,'read_state',lambda *a:state);monkeypatch.setattr(r,'read_events',lambda *a:[])
        with entry.phase_pending(r,queue,plan,evaluation[3]):
            with pytest.raises(r.GateError,match='no clipping'):queue.pending_gate(root,row)
    unbound={**row,'n2_evaluation_recovery_contract':{}}
    with owned_scope(root,plan,[row['episode_key']]):
        with pytest.raises(r.GateError,match='outside exact frozen plan'):
            e.validated_budget_context(plan,evaluation[3],unbound,journal,[],root,r)


def test_release_only_prepared_and_verified_from_full_certificate_and_settled_prefix(evaluation,monkeypatch):
    from test_qd_ed_final_runner import synced_state
    root,plan,events=certified_formal(evaluation,monkeypatch)
    artifact=Path(plan['artifact_root']);before=copy.deepcopy(events)
    health=[{'event':kind,'resource_id':'prior','kind':'reviewed-existing-diagnostic','gpu_process_wall_seconds':7.}
        for kind in ('reserved','dispatched','completed')]
    inventory=save(artifact/'health-inventory.json',{'schema':'qd-ed-settled-healthcheck-inventory-v1','resources':[
        {'resource_id':'prior','terminal':save(artifact/'prior-health-terminal.json',health[-1])}]})
    event=e.prepare_reservation_release(plan,events,health,root,r,healthcheck_inventory=inventory,rationale='full60 audited pass',time_unix=123.)
    state=synced_state(events);state['budget']['gpu_hours_consumed']+=7/3600
    state['budget']['gpu_hour_reservations']={'validation':0.,'formal':10.}
    e.verify_reservation_release(plan,state,events,health,[event],root,r)
    state['gpu_pool']=[3]
    plan.update(frozen=True,phase_authorization={'dev':False,'validation':False,'formal':True})
    row=plan['episodes'][0]
    with owned_scope(root,plan,[row['episode_key']]):
        permission=e.validated_budget_context(plan,evaluation[3],row,events,health,root,r)
        assert r.check_budget(state,events,row,health,[event],physical_gpu=3,evaluation_context=permission)==1800
    assert events==before and not (root/'data/gpu-hour-reservation-ledger.jsonl').exists()
    changed=copy.deepcopy(event);changed['n2_evaluation_release']['promotion_certificate']['sha256']='forged'
    with pytest.raises(r.GateError,match='certificate/evidence differs'):
        e.verify_reservation_release(plan,state,events,health,[changed],root,r)
    state['budget']['gpu_hour_reservations']['formal']=9
    with pytest.raises(r.GateError,match='state/event/phase'):
        e.verify_reservation_release(plan,state,events,health,[event],root,r)
    for incomplete in (health[:1],health[:2]):
        with pytest.raises(r.GateError,match='unsettled healthcheck'):
            e.prepare_reservation_release(plan,events,incomplete,root,r,healthcheck_inventory=inventory,rationale='test',time_unix=1.)
    unknown=health+[{'event':'reserved','resource_id':'new'}, {'event':'aborted','resource_id':'new','gpu_process_wall_seconds':0.}]
    with pytest.raises(r.GateError,match='unrecognized/missing'):
        e.prepare_reservation_release(plan,events,unknown,root,r,healthcheck_inventory=inventory,rationale='test',time_unix=1.)
    unfinished=events+[{'attempt_id':'open','identity':{'iteration':'another'},'event':'reserved'}]
    with pytest.raises(r.GateError,match='unsettled episode'):
        e.prepare_reservation_release(plan,unfinished,health,root,r,healthcheck_inventory=inventory,rationale='test',time_unix=1.)
    with pytest.raises(r.GateError,match='only completed validation'):
        e.prepare_reservation_release(evaluation[-1]('validation'),events,health,root,r,healthcheck_inventory=inventory,rationale='test',time_unix=1.)


@pytest.mark.parametrize('failure',['partial','numeric','audit'])
def test_release_rejects_partial_failed_or_unaudited_validation(evaluation,monkeypatch,failure):
    root,plan,events=certified_formal(evaluation,monkeypatch);artifact=Path(plan['artifact_root'])
    cert=e.read_ref(plan['n2_evaluation']['promotion_certificate'],plan,r)
    report=e.read_ref(cert['report'],plan,r)
    if failure=='partial':report['input_manifest']['attempts'].pop()
    elif failure=='numeric':
        for spec in report['input_manifest']['attempts']:
            terminal=r.read_json(spec['terminal']['path'])
            if terminal['identity']['profile']=='N2' and terminal['identity']['task_id']==4:
                terminal['success']=False
                spec['terminal']=save(Path(spec['terminal']['path']),terminal)
                for i,x in enumerate(events):
                    if x['event']=='valid' and x['attempt_id']==terminal['attempt_id']:events[i]=terminal
        manifest=report['input_manifest'];report,_,_=er.recompute(manifest,root,r);report['input_manifest']=manifest
        assert report['numeric_pass'] is False
    else:
        spec=report['input_manifest']['attempts'][0];audit=r.read_json(spec['audit']['path']);audit['accepted']=False
        spec['audit']=save(Path(spec['audit']['path']),audit)
    cert['report']=save(artifact/'bad-validation-release-report.json',report)
    plan['n2_evaluation']['promotion_certificate']=save(artifact/'bad-release-certificate.json',cert)
    inventory=save(artifact/'empty-health-inventory.json',{'schema':'qd-ed-settled-healthcheck-inventory-v1','resources':[]})
    with pytest.raises((r.GateError,ValueError),match='recomputed validation|rejected audit|numeric failure'):
        e.prepare_reservation_release(plan,events,[],root,r,healthcheck_inventory=inventory,rationale='cannot release',time_unix=1.)
