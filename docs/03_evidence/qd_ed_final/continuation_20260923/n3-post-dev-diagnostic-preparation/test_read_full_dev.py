"""New wrapper tests only; invented files/arrays, no scientific input reads."""
import copy
import importlib.util
import io
import json
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('n3_complete_wrapper_test', HERE/'read_full_dev.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
DEFINITION = m.parse((HERE/'dependencies-v1.json').read_bytes())


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', '')
    return m.dependencies(DEFINITION)


def put(path, value, lines=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = ('\n'.join(json.dumps(r) for r in value)+'\n').encode() if lines else json.dumps(value).encode()
    path.write_bytes(data)
    return {'path': str(path), 'sha256': m.sha(data)}


def identity_fixture(root, *, defect=None, recovery=False):
    """Thirty fake accepted rows and deliberately undecodable bundle bytes."""
    rows = [dict(split='dev', iteration=m.COHORT, profile=arm, task_id=task, env_seed=100+task,
                 policy_seed=200+task, init_index=0, init_row_sha256='e'*64,
                 episode_key=f't{task}-{arm}', budget_bucket='baseline' if arm == 'C0' else 'development')
            for task in range(10) for arm in m.ARMS]
    base = dict(source_commit=m.SOURCE, artifact_root=str(root), profiles_sha256='a'*64,
                runtime_manifest_sha256='b'*64, runtime_inventory_sha256='c'*64, seed_plan_sha256='d'*64,
                code_files=[{'path': p, 'sha256': s} for p, s in DEFINITION['reviewed_source_sha256'].items()],
                candidate_profiles={'N3': {'sha256': '9'*64}}, episodes=rows,
                n3_cohort={'cohort_id': m.COHORT, 'protocol': {'sha256': '8'*64}, 'accounting_clarification': {'sha256': '7'*64},
                           'limits': {}, 'health_resources': [], 'runtime_prerequisites': {}, 'budget_allocation': {}, 'budget_allocation_amendment': {}})
    if defect == 'source': base['source_commit'] = '0'*40
    if defect == 'inventory': base['code_files'][0]['sha256'] = '0'*64
    if defect == 'converter_missing': base['code_files'] = [r for r in base['code_files'] if r['path'] != 'core/rdt_libero_action_converter.py']
    base_ref = put(root/'base.json', base); plan, plan_ref = base, base_ref
    revisions = []
    if recovery:
        plan = copy.deepcopy(base)
        retry = dict(rows[1], episode_key='t0-Q0-retry', retry_of='t0-Q0', budget_bucket='recovery')
        plan['episodes'].append(retry); plan_ref = put(root/'revision.json', plan); revisions.append(plan_ref)
    if defect == 'revision':
        plan = copy.deepcopy(base); plan['profiles_sha256'] = '1'*64
        revisions = [put(root/'bad-revision.json', plan)]; plan, plan_ref = base, base_ref
    cells, extras, snapshots = [], [], []
    canonical_sha = lambda v:m.sha(json.dumps(v,sort_keys=True,separators=(',',':')).encode())
    frozen = {'cohort_id': m.COHORT, **{k: base[k] for k in m.BINDING},
              'protocol_sha256': '8'*64, 'accounting_clarification_sha256': '7'*64,
              'candidate_sha256':'9'*64,'source_files_sha256':canonical_sha(base['code_files']),
              'resource_contract_sha256':canonical_sha({k:base['n3_cohort'][k] for k in ('limits','health_resources','runtime_prerequisites','budget_allocation','budget_allocation_amendment')})}
    for original in rows:
        row = plan['episodes'][-1] if recovery and original['episode_key'] == 't0-Q0' else original
        used_ref = plan_ref if row.get('retry_of') else base_ref
        attempt_id = row['episode_key']; out = root/'attempts'/attempt_id; ed = out/'eds_eval'; ep = ed/'decision_evidence/episode_000'
        identity = {k: row[k] for k in m.IDENTITY}
        terminal = dict(attempt_id=attempt_id, episode_key=row['episode_key'], identity=identity, event='valid', outcome_valid=True,
                        success=False, output_dir=str(out), plan_sha256=used_ref['sha256'], physical_gpu=3,
                        source_commit=base['source_commit'], profile_manifest_sha256=base['profiles_sha256'],
                        runtime_manifest_sha256=base['runtime_manifest_sha256'], runtime_inventory_sha256=base['runtime_inventory_sha256'],
                        init_row_sha256=row['init_row_sha256'], budget_bucket=row['budget_bucket'], retry_of=row.get('retry_of'),
                        n3_cohort_id=m.COHORT, n3_frozen_identity=frozen, compute_outcome='completed')
        ident = {'episode_id': 0, 'task_id': row['task_id'], 'episode_seed': row['env_seed']}
        compute = dict(ident,outcome='completed',guided_chunks=0,decision_evidence={'bundles':1})
        audit = dict(accepted=True,evidence_complete=True,errors=[],original_execution_outcome='completed',
                     episode_dir=str(ep),episode_compute_file=str(ed/'episode_compute.jsonl'))
        if defect == 'last_audit' and row['task_id'] == 9 and row['profile'] == 'N3': audit['errors'] = ['synthetic failure']
        refs = {'terminal':put(out/'attempt-result.json',terminal),'audit':put(ed/'decision-evidence-audit.json',audit),
                'compute':put(ed/'episode_compute.jsonl',[compute],True),'metrics':put(ed/'eds_metrics.jsonl',[],True)}
        status = put(ep/'status.json',dict(schema='qd-ed-decision-evidence-v1',episode=0,complete=True,failed=False,pending_action=False,bundles=1,decisions=1))
        bundle=ep/'bundle_000001.pt';bundle.write_bytes(b'synthetic non-tensor; decoding is forbidden in admission test')
        index=put(ep/'events.jsonl',[{'bundle':bundle.name,'sha256':m.sha(bundle.read_bytes())}],True)
        extra=dict(attempt_id=attempt_id,metadata=put(ed/'episode_metadata.jsonl',[ident],True),status=status,index=index,
                   stage_events={'status':'not_recorded','path':str(ed/'stage_events.jsonl')})
        extras.append(extra)
        snapshots.append(dict(attempt_id=attempt_id,audit=refs['audit'],status=status,index=index,
                              auditor_sha256=DEFINITION['reviewed_source_sha256']['scripts/audit_decision_evidence.py'],binding=m.SNAPSHOT))
        attempts=[]
        if row.get('retry_of'):
            attempts.append({'status':'terminal_invalid','terminal':dict(attempt_id=row['retry_of'],identity=identity,outcome_valid=defect=='recovery'),
                             'references':{'terminal':{'path':str(root/'NEVER_OPEN_INVALID'),'sha256':'0'*64}}})
        attempts.append({'status':'complete_valid','terminal':terminal,'references':refs})
        cells.append(dict(identity=identity,status='complete_valid',inflight=[],valid_attempt_id=attempt_id,attempts=attempts,metrics={'n3':{'records':[]}}))
    authority=dict(base_plan=base_ref,plan_revisions=revisions,input_scope_complete=True,script_sha256=DEFINITION['modules']['report']['sha256'])
    authority_ref=put(root/'report-input.json',authority)
    report=dict(schema='qd-ed-n3-matrix-report-v1',cohort_id=m.COHORT,matrix='complete_valid_30',input_scope_complete=True,
                inflight_records=[],input_manifest=authority,input_manifest_sha256=authority_ref['sha256'],cells=cells)
    if defect=='cohort':report['cohort_id']='external'
    if defect=='incomplete':report['matrix']='incomplete'
    report_ref=put(root/'report.json',report)
    manifest=dict(schema='n3-post-dev-input-v1',matrix_report=report_ref,matrix_report_input=authority_ref,cells=extras)
    auth=dict(reviewed_matrix_report=report_ref,completed_cohort_reviewed=True,trigger='root_confirmed_existing_dev_gate_failed',
              completed_audit_snapshots=snapshots,
              reviewed_metadata_sources={p:DEFINITION['reviewed_source_sha256'][p] for p in ('scripts/qd_ed_n3_report.py','scripts/qd_ed_n3_plan.py')})
    if defect=='membership':manifest['cells'][-1]=manifest['cells'][0]
    if defect=='snapshot':auth['completed_audit_snapshots'][-1]['binding']='not root verified'
    if defect=='metadata':auth['reviewed_metadata_sources']['scripts/qd_ed_n3_report.py']='0'*64
    return manifest,auth


@pytest.mark.parametrize('defect,reason',[
    ('source','source_or_original'),('inventory','source_inventory'),('converter_missing','source_inventory'),('revision','revision_changes'),
    ('cohort','matrix_authority'),('incomplete','matrix_authority'),('membership','representative_universe'),
    ('snapshot','audit_snapshot'),('metadata','metadata_identity'),('last_audit','audit_link'),('recovery','recovery_link')])
def test_all30_admission_rejects_before_any_decode(tmp_path,modules,monkeypatch,defect,reason):
    manifest,auth=identity_fixture(tmp_path,defect=defect,recovery=defect=='recovery')
    calls=[];monkeypatch.setattr(modules['task0'].torch,'load',lambda *a,**k:calls.append(True))
    with pytest.raises(ValueError,match=reason):m.admit(manifest,auth,DEFINITION,modules,m.Inputs(tmp_path))
    assert calls==[]


def test_complete_admission_keeps_recovery_without_opening_invalid(tmp_path,modules,monkeypatch):
    manifest,auth=identity_fixture(tmp_path,recovery=True)
    calls=[];monkeypatch.setattr(modules['task0'].torch,'load',lambda *a,**k:calls.append(True))
    inputs=m.Inputs(tmp_path);_,admitted=m.admit(manifest,auth,DEFINITION,modules,inputs)
    assert len(admitted)==30 and admitted[1]['terminal']['retry_of']=='t0-Q0'
    assert len([p for p in inputs.hashes if p.endswith('.pt')])==30
    assert calls==[] and not any('NEVER_OPEN_INVALID' in p for p in inputs.hashes)


def synthetic_rows(modules, start=0, count=8, terminal=False):
    """Adapt only declared handmade arrays from the previously tested fixture."""
    ref=DEFINITION['test_sources']['selected_tracking_fixture']
    require=m.require;require(m.sha(Path(ref['path']).read_bytes())==ref['sha256'],'test_fixture_sha')
    fixture=m.dependency_module('old_synthetic_fixture',ref)
    rows=fixture.fixture_rows(start=start,m=count,terminal=terminal)
    rows[0]['values'].update(previous_stage=1,stage_changed=False)
    for row in rows:
        if row['event']=='pre_reset_outcome':row['values'].update(reward=0.0,success=terminal,origin='synthetic_pre_reset')
    return rows


def synthetic_item(tmp_path,modules,rows,stage=None,profile='C0',metrics=None):
    torch=modules['task0'].torch;ep=tmp_path/'episode_000';ep.mkdir()
    # Relink origin refs while merging handmade consecutive decisions.
    for sequence,row in enumerate(rows,1):row['sequence']=sequence
    for i,row in enumerate(rows):
        if row['event']=='scoring_inputs':
            row['values']['projection_origin_sequences']=[next(x['sequence'] for x in rows[:i] if x['decision_id']==row['decision_id'] and x['event']=='projection_origin')]
    buffer=io.BytesIO();torch.save({'schema':'qd-ed-decision-evidence-v1','events':rows},buffer)
    path=ep/'bundle_000001.pt';path.write_bytes(buffer.getvalue())
    index=[dict(bundle=path.name,sha256=m.sha(path.read_bytes()),first_sequence=1,last_sequence=len(rows),
                events=[{k:r[k] for k in ('sequence','event','decision_id','global_step','reset_sequence')} for r in rows])]
    n=sum(r['event']=='decision_context' for r in rows)
    return dict(ep=ep,index=index,status={'episode':0,'decisions':n},stage_rows=stage,metrics=metrics or [],
                compute={'guided_chunks':n},terminal={'attempt_id':'synthetic','identity':{'task_id':0,'profile':profile}},
                refs={'terminal':{'path':'synthetic','sha256':'0'*64},'audit':{'path':'synthetic-audit','sha256':'0'*64}})


def test_real_wrapper_terminal_prefix_and_optional_Stage_unknown(tmp_path,modules):
    rows=synthetic_rows(modules,count=3,terminal=True)
    item=synthetic_item(tmp_path,modules,rows)
    result=m.episode(item,m.Inputs(tmp_path),modules)
    assert result['summary']['observed_actions']==result['summary']['guided_actions']==3
    assert result['chronology']['stage']['status']=='not_recorded'
    assert result['actual_steps'][-1]['reset_sequence']==0 and result['actual_steps'][-1]['returned_reset_sequence']==1
    assert result['selected_tracking'][0]['m']==3
    assert result['summary']['zero_mse_episode_mean'] is None
    assert result['automatic_reset_boundaries'][0]['reset_will_follow'] is True
    item['stage_rows']=[]
    assert m.episode(item,m.Inputs(tmp_path),modules)['chronology']['stage']['status']=='recorded'


def test_runtime_inactive_does_not_erase_structural_pair(tmp_path,modules):
    rows=synthetic_rows(modules)+synthetic_rows(modules,start=8,count=2,terminal=True)
    metrics=[]
    for step in (0,8):
        data=dict(active=False,context={'target_valid':False},previous={},selected={'synthetic':'native provenance'})
        rows.insert(next(i for i,r in enumerate(rows) if r['decision_id']==f'd{step}')+1,
                    dict(sequence=0,event='execution_feedback_selection',episode=0,decision_id=f'd{step}',global_step=step,reset_sequence=0,values=data))
        metrics.append(dict(global_step=step,qd_quality_applicable=True,qd_feedback_active=False,
                            qd_feedback_context=data['context'],qd_feedback_previous={},qd_feedback_selected=data['selected'],
                            qd_quality_reason='recognized',qd_feedback_reason='target_tracking_or_context_unknown'))
    item=synthetic_item(tmp_path,modules,rows,profile='N3',metrics=metrics)
    result=m.episode(item,m.Inputs(tmp_path),modules)
    assert result['summary']['eligible_structural_pairs']==1
    assert result['runtime_feedback'][1]['status']=='recognized_inactive'
    assert result['runtime_feedback'][1]['selected_recorded_provenance']=={'synthetic':'native provenance'}
    assert result['summary']['active_executed_actions']==0
    assert result['summary']['zero_mse_episode_mean'] is not None


def test_optional_Stage_missing_and_empty_declarations_are_distinct(tmp_path):
    inputs=m.Inputs(tmp_path);path=tmp_path/'stage_events.jsonl'
    assert m.optional_stage({'status':'not_recorded','path':str(path)},path,{},inputs) is None
    ref=put(path,[],True)
    assert m.optional_stage({'status':'present','reference':ref},path,{},m.Inputs(tmp_path))==[]
    with pytest.raises(ValueError,match='absent_source_appeared'):inputs.finish()


def test_episode_aggregation_preserves_unknown_without_zero_fill():
    cells=[{'identity':{'task_id':t,'profile':a},'attempt_id':f'{t}{a}',
            'summary':{'transport_minus_zero_episode_mean':None if t else -2.0}} for t in range(10) for a in m.ARMS]
    value=m.aggregate(cells)
    assert value['N3']['eligible_episode_count']==1 and value['N3']['no_eligible_episode_count']==9
    assert value['N3']['episode_mean_transport_minus_zero']==-2.0
    for c in cells:c['summary']['transport_minus_zero_episode_mean']=None
    assert m.aggregate(cells)['N3']['episode_mean_transport_minus_zero'] is None


def test_active_wrapper_keeps_duplicate_native_final_ties_without_activity(modules):
    ref=DEFINITION['test_sources']['first3_fixture']
    fixture=m.dependency_module('first3_synthetic_fixture',ref)
    rows,metric=fixture.active_fixture();torch=modules['task0'].torch
    final=rows[-1]['values'];candidate=final['population'][:1].clone()
    final.update(population=torch.cat([candidate,candidate]),raw_provider_quality=torch.zeros(2),
                 selected_index=1,selected_latent=candidate)
    metric.update(qd_selected_raw_gap=0.,qd_final_best_raw_reward=0.,qd_quality_applicable=True,
                  qd_feedback_active=True,qd_quality_reason='synthetic recognized',qd_feedback_reason='synthetic active',
                  qd_feedback_context={'target_valid':True},qd_feedback_previous={'synthetic':'previous certified prefix'},
                  qd_feedback_selected={'synthetic':'selected provenance'})
    rows.append(dict(event='execution_feedback_selection',sequence=len(rows)+1,values={
        k:metric['qd_feedback_'+k] for k in ('active','context','previous','selected')}))
    result=m.runtime_record('N3',{'use_guidance':True},rows,metric,3,modules['first3'])
    assert result['active'] is True and result['executed_actions']==3
    proof=result['consumer']
    assert proof['canonical_comparator_changes_descriptive_only']
    assert proof['final_pool']['raw_max_indices']==proof['final_pool']['internal_max_indices']==[0,1]
    assert not proof['selected_final_ordering_witness'] and not proof['strict_final_pool_witness']
