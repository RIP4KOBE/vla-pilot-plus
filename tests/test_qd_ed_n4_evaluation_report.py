"""Public metadata fixtures only; no real Dev/protected evidence."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_qd_ed_n4_evaluation import evaluation, fixture, e, r, save
from test_qd_ed_n4_report import d, simple_attempt
import qd_ed_n4_evaluation_report as report


def attempt(plan,row,identifier,*,success=False,valid=True,dispatched=True,time=1.):
    t={'attempt_id':identifier,'episode_key':row['episode_key'],'identity':r.episode_identity(row),
       'n4_evaluation_cohort_id':plan['n4_evaluation']['cohort_id'],'n4_evaluation_frozen_identity':e.binding(plan),
       'event':'valid' if dispatched else 'aborted','success':success,'outcome_valid':valid if dispatched else False,
       'task_failure':not success,'n4_episode_dispatched':dispatched,'retry_of':row.get('retry_of'),
       'gpu_process_wall_seconds':5. if dispatched else 0.,'time_unix':time,'physical_gpu':3,
       'output_dir':str(Path(plan['artifact_root'])/identifier),'budget_bucket':row['budget_bucket'],
       'plan_sha256':'base','source_commit':plan['source_commit'],'profile_manifest_sha256':plan['profiles_sha256'],
       'runtime_manifest_sha256':plan['runtime_manifest_sha256'],'runtime_inventory_sha256':plan['runtime_inventory_sha256'],
       'init_row_sha256':row['init_row_sha256']}
    return {'terminal':t,'status':'complete_valid' if valid and dispatched else 'terminal_invalid' if dispatched else 'predispatch_rejected',
        'metrics':{'n4':{'native_terminal_population_alignment':{'checked_decisions':1},'actual_prefix_different_decisions':0}}}


def run_summary(plan,attempts,rows=None,**kw):
    mapping=rows or {a['terminal']['attempt_id']:next(x for x in plan['episodes'] if x['episode_key']==a['terminal']['episode_key']) for a in attempts}
    return report.summarize(plan,attempts,r,d,validated_rows=mapping,**kw)


@pytest.mark.parametrize('phase,n4_success,expected',[('validation',10,True),('validation',9,False),('formal',5,True)])
def test_exact_full_matrix_no_extra_ablation_or_prefix_superiority_gate(evaluation,phase,n4_success,expected):
    *_,make,_=evaluation;plan=make(phase);counts={};attempts=[]
    for i,row in enumerate(plan['episodes']):
        arm=row['profile'];ordinal=counts.get(arm,0);counts[arm]=ordinal+1
        limit={'N4':n4_success,'C0':4,'Q0':4,'N4_QD_OFF':10}[arm]
        attempts.append(attempt(plan,row,str(i),success=ordinal<limit))
    out=run_summary(plan,attempts,input_scope_complete=True)
    assert out['complete'] and out['numeric_pass'] is expected and out['phase_authorized'] is False
    assert len(out['cells'])==e.PHASES[phase]['originals']
    assert out['candidate_activity']['actual_prefix_different_decisions']==0
    if phase=='formal':
        assert out['profiles']['N4_QD_OFF']['successes_observed']==10
        assert out['paired_comparisons']['N4_vs_N4_QD_OFF']['success_delta']==-5
    else: assert len(out['profiles']['N4']['blocks'])==2
    partial=run_summary(plan,attempts[:-1],input_scope_complete=False)
    assert partial['numeric_pass'] is None and not partial['complete']


def test_immutable_base_61st_recovery_row_and_all_preadmission_costs(evaluation):
    *_,make,_=evaluation;base=make('validation');saved=copy.deepcopy(base);row=base['episodes'][0]
    original=attempt(base,row,'old',valid=False,time=2.)
    original['terminal'].update(event='aborted',reason='external GPU3 process appeared during owned attempt',retryable_infrastructure=True)
    revision=copy.deepcopy(base);retry={**row,'episode_key':'retry','retry_of':'old','budget_bucket':'recovery',
        'n4_evaluation_recovery_contract':e.binding(base)};revision['episodes'].append(retry)
    recovered=attempt(revision,retry,'new',success=True,time=4.)
    recovered['terminal']['plan_sha256']='revision'
    pre=[attempt(base,row,'pre'+str(i),valid=False,dispatched=False,time=1.) for i in range(70)]
    attempts=pre+[original,recovered];rows={a['terminal']['attempt_id']:row for a in pre+[original]};rows['new']=retry
    out=run_summary(base,attempts,rows=rows)
    assert out['raw_terminal_records']==72 and out['actual_dispatches']==2
    assert out['cells'][0]['valid_attempt_id']=='new' and out['profiles']['C0']['all_attempt_gpu_seconds']['complete_total']==10.
    assert base==saved
    original['terminal'].update(event='valid',outcome_valid=True,success=False)
    with pytest.raises(r.GateError,match='ineligible'):run_summary(base,attempts,rows=rows)


def test_same_task_second_seed_block_is_a_different_cell(evaluation):
    *_,make,_=evaluation;plan=make('validation')
    rows=[x for x in plan['episodes'] if x['task_id']==0 and x['profile']=='C0']
    attempts=[attempt(plan,row,str(i)) for i,row in enumerate(rows)]
    out=run_summary(plan,attempts)
    assert out['profiles']['C0']['complete_valid']==2
    assert len({e.cell(x['identity']) for x in out['cells']})==60


def test_inflight_unknown_cost_reserved_only_and_valid_collision(evaluation):
    *_,make,_=evaluation;plan=make('validation');row=plan['episodes'][0]
    active={'attempt_id':'active','cell_identity':{k:row[k] for k in e.FIELDS},'identity':r.episode_identity(row),
        'dispatched':False,'retry_of':None,'gpu_process_wall_seconds':None}
    out=run_summary(plan,[],inflight=[active])
    assert out['actual_dispatches']==0 and out['cells'][0]['status']=='reserved_no_dispatch'
    assert out['profiles']['C0']['all_attempt_gpu_seconds']['complete_total'] is None
    assert out['profiles']['C0']['all_attempt_gpu_seconds']['missing_values']==1
    with pytest.raises(r.GateError,match='valid/excess'):run_summary(plan,[attempt(plan,row,'done')],inflight=[active])


def test_journal_includes_every_invalid_and_predispatch_without_science_reads(evaluation,monkeypatch):
    *_,make,_=evaluation;plan=make('validation');row=plan['episodes'][0]
    attempts=[attempt(plan,row,'pre',valid=False,dispatched=False),attempt(plan,row,'bad',valid=False)]
    events=[];specs=[];values={}
    for a in attempts:
        t=a['terminal'];events.append({**t,'event':'reserved'})
        if t['n4_episode_dispatched']:events.append({**t,'event':'dispatched'})
        events.append(t);spec={'terminal':{'path':str(Path(t['output_dir'])/'attempt-result.json'),'sha256':t['attempt_id']}}
        specs.append(spec);values[t['attempt_id']]=t
    excerpt={'schema':'qd-ed-n4-evaluation-journal-excerpt-v1','cohort_id':plan['n4_evaluation']['cohort_id'],
        'extraction':'all_events_all_phase_attempts_through_snapshot','source_journal':{'path':str(Path(plan['worktree'])/'data/attempt-ledger.jsonl'),'sha256':'f'*64},
        'events':events,'terminal_attempt_ids':['pre','bad'],'inflight_attempt_ids':[]}
    monkeypatch.setattr(d,'read_ref',lambda ref:values[ref['sha256']])
    assert report.journal_excerpt(excerpt,specs,{'base':plan},plan,r,d)==[]
    with pytest.raises(r.GateError,match='omitted'):report.journal_excerpt(excerpt,specs[1:],{'base':plan},plan,r,d)
    changed=copy.deepcopy(excerpt);changed['events'][1]['n4_episode_dispatched']=True
    with pytest.raises(r.GateError,match='dispatch'):report.journal_excerpt(changed,specs,{'base':plan},plan,r,d)


def test_recompute_dev_runs_frozen_whole_journal_and_terminal_only_path(fixture,monkeypatch):
    root,plan,_,runtime,*_=fixture;artifact=Path(plan['artifact_root']);specs=[];events=[]
    for name in ('qd_ed_n4_report.py','qd_ed_n4_plan.py'):
        path='scripts/'+name
        (root/path).write_bytes((Path(d.__file__).parent/name).read_bytes())
        next(x for x in plan['code_files'] if x['path']==path)['sha256']=r.digest(root/path)
    monkeypatch.setattr(e,'frozen_report',lambda runner:d)
    for i,row in enumerate(plan['episodes']):
        t=simple_attempt(plan,runtime,row,'invalid'+str(i),valid=False)['terminal']
        specs.append({'terminal':save(Path(t['output_dir'])/'attempt-result.json',t)})
        events += [{**t,'event':'reserved'},{**t,'event':'dispatched'},t]
    base=save(artifact/'base.json',plan)
    for event in events:event['plan_sha256']=base['sha256']
    for spec,t in zip(specs,events[2::3]):spec['terminal']=save(Path(t['output_dir'])/'attempt-result.json',t)
    journal=save(artifact/'excerpt.json',{'schema':'qd-ed-n4-journal-excerpt-v1','cohort_id':d.COHORT,
        'extraction':'all_events_all_n4_attempts_through_snapshot','source_journal':{'path':str(root/'data/attempt-ledger.jsonl'),'sha256':'c'*64},
        'events':events,'terminal_attempt_ids':[t['attempt_id'] for t in events[2::3]],'inflight_attempt_ids':[]})
    health=[]
    for item in plan['n4_cohort']['health_resources']:
        health.append({**item,'terminal':save(artifact/(item['resource_id']+'.json'),{'resource_id':item['resource_id'],'event':'completed','gpu_process_wall_seconds':1.})})
    auth=save(artifact/'auth.json',{'schema':'qd-ed-n4-report-authorization-v1','status':'authorized',
        'script':{'path':str(Path(d.__file__).resolve()),'sha256':d.sha(d.__file__)},'protocol_sha256':d.sha(d.PROTOCOL),
        'base_plan_sha256':base['sha256'],'journal_excerpt_sha256':journal['sha256']})
    manifest={'schema':'qd-ed-n4-report-input-v1','script_sha256':d.sha(d.__file__),'protocol_sha256':d.sha(d.PROTOCOL),
        'authorization':auth,'base_plan':base,'journal_excerpt':journal,'attempts':specs,'health_resources':health,'input_scope_complete':True}
    out,attempts,base_value=report.recompute_dev(manifest,root,r)
    assert len(attempts)==12 and all(a['status']=='terminal_invalid' for a in attempts)
    assert out['protocol_numeric_dev_criterion'] is None and out['resources']['episode_seconds']==156.
    assert out['input_scope_complete'] is True and base_value==plan
    manifest['attempts']=specs[:-1]
    with pytest.raises(ValueError,match='omitted'):report.recompute_dev(manifest,root,r)


def test_phase_recompute_expands_candidate_in_memory_and_rejects_bad_source(evaluation,monkeypatch):
    root,_,_,runtime,seeds,make,_=evaluation;plan=make('validation');artifact=Path(plan['artifact_root'])
    # Explicit synthetic source constants and a validator spy isolate the report
    # glue from the separately tested private-resource/exposure prerequisites.
    plan['seed_plan_sha256']=r.digest(plan['seed_plan_path'])
    plan['runtime_manifest_sha256']=r.digest(plan['runtime_manifest_path'])
    plan.update(frozen=True,phase_authorization={'dev':False,'validation':True,'formal':False})
    checked=[]
    def validate(p,profiles,rt,seed,owner,runner):
        assert set(profiles['profiles'])=={'C0','Q0','N4','N4_QD_OFF'}
        assert profiles['profiles']['N4']['resolved_eds_config']['qd_final_selection_mode']=='terminal_population_v1'
        checked.append(True)
    monkeypatch.setattr(e,'validate_contract',validate)
    # Use a fresh frozen reader instance, avoiding any persistent patched globals.
    def fresh(_):
        import importlib.util
        spec=importlib.util.spec_from_file_location('phase_frozen_synthetic',d.__file__)
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
    monkeypatch.setattr(e,'frozen_report',fresh)
    base=save(artifact/'phase.json',plan)
    t=attempt(plan,plan['episodes'][0],'bad',valid=False)['terminal'];t['plan_sha256']=base['sha256']
    spec={'terminal':save(Path(t['output_dir'])/'attempt-result.json',t)}
    journal=save(artifact/'phase-excerpt.json',{'schema':'qd-ed-n4-evaluation-journal-excerpt-v1','cohort_id':plan['n4_evaluation']['cohort_id'],
        'extraction':'all_events_all_phase_attempts_through_snapshot','source_journal':{'path':str(root/'data/attempt-ledger.jsonl'),'sha256':'d'*64},
        'events':[{**t,'event':'reserved'},{**t,'event':'dispatched'},t],'terminal_attempt_ids':['bad'],'inflight_attempt_ids':[]})
    auth=save(artifact/'phase-auth.json',{'schema':'qd-ed-n4-evaluation-report-authorization-v1','status':'authorized',
        'script':{'path':str((root/e.REPORT).resolve()),'sha256':r.digest(root/e.REPORT)},'protocol_sha256':e.PROTOCOL_SHA,
        'base_plan_sha256':base['sha256'],'journal_excerpt_sha256':journal['sha256']})
    health=[{**x,'terminal':save(artifact/(x['resource_id']+'.json'),{'resource_id':x['resource_id'],'event':'completed','gpu_process_wall_seconds':1.})}
        for x in plan['n4_evaluation']['health_resources']]
    manifest={'schema':'qd-ed-n4-evaluation-report-input-v1','script_sha256':r.digest(root/e.REPORT),'protocol_sha256':e.PROTOCOL_SHA,
        'authorization':auth,'base_plan':base,'journal_excerpt':journal,'attempts':[spec],'health_resources':health,'input_scope_complete':False}
    out,values,_=report.recompute(manifest,root,r)
    assert checked==[True] and out['numeric_pass'] is None and values[0]['status']=='terminal_invalid'
    assert 'N4' not in r.read_json(plan['profiles_path'])['profiles']  # disk unchanged
    (root/'core/qd_terminal_population.py').write_text('changed')
    with pytest.raises(r.GateError,match='source changed'):report.recompute(manifest,root,r)
