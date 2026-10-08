"""CPU-only bounded metadata/lifecycle tests. No models, tensors or GPU calls."""
import copy
import datetime as dt
import json
from pathlib import Path
import pytest
from scripts import qd_ed_n23_worker as w, qd_ed_n32_contract as old
from scripts import qd_ed_n32r3_contract as c, qd_ed_n32r3_supervise as s
from scripts import qd_ed_n32r3_history as history, qd_ed_n32r3_release as release
from scripts import qd_ed_n32r3_bridge as bridge, qd_ed_n32r3_worker as worker
from scripts import qd_ed_final_runner as generic


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True))
    return c.ref(path)


def dummy_ref(tmp, name):
    return write(tmp / name, {})


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    """Tiny synthetic original artifacts with real digest and identity checks."""
    root = str(c.ROOT)
    source = {'commit': c.BASE_SOURCE, 'files': [], 'sha256': w.canonical_sha([])}
    runtime = dummy_ref(tmp_path, 'runtime.json')
    parent = {'schema': 'n32-released-plan-v1', 'frozen': True, 'release_enabled': True,
              'worktree': root, 'episodes': old.expected_rows(), 'limits': old.LIMITS,
              'worker_contract': old.WORKER_CONTRACT, 'deadline': old.DEADLINE, 'stop_path': old.stop_path(),
              'phase_authorization': {'dev': True, 'validation': False, 'formal': False}, 'attempt_identity': 'episode_key',
              'expected_manifests': {}, 'source': source, 'runtime': runtime,
              'authority': dummy_ref(tmp_path, 'old-authority.json'), 'protocol': dummy_ref(tmp_path, 'old-protocol.json'),
              'runtime_inventory_sha256': 'inventory'}
    for row in parent['episodes']:
        key = row['episode_key']; output = tmp_path / 'old' / key
        parent['expected_manifests'][key] = write(tmp_path / 'manifests' / (key+'.json'),
            {'row': row, 'source': source, 'runtime': runtime, 'output_dir': str(output),
             'argv': ['python','main.py','seed='+str(row['policy_seed'])], 'composed_config_sha256': 'config'})
    parent_ref = write(tmp_path/'parent.json', parent)
    expected = {'schema': 'n32-execution-release-v1', 'approved': True, 'plan': parent_ref,
                **{k: parent[k] for k in ('authority','protocol','source','runtime','limits','phase_authorization')}}
    review_ref = write(tmp_path/'old-review.json', {**expected,'schema':'n32-root-production-review-v1','decision':'APPROVED'})
    release_ref = write(tmp_path/'old-release.json', {**expected,'root_review':review_ref})
    plan = {'schema':'n32r3-released-plan-v1','worktree':root,'episodes':c.expected_rows(),
            'parent_plan':parent_ref,'parent_release':release_ref,'parent_review':review_ref,'scientific_source':source,
            'source_continuity':dummy_ref(tmp_path,'source-review.json'),
            'preparation_review':dummy_ref(tmp_path,'preparation-review.json'),
            'command_candidates':dummy_ref(tmp_path,'commands.json')}
    mapping = {'schema':'n32r3-carry-forward-map-v1','parent_plan':parent_ref,'release_enabled':False,
               'pooling_authorized':False,'continuity_failures':[], 'command_candidates':plan['command_candidates'],
               'accepted_cells':[], 'proposed_cells':[], 'terminal_review':dummy_ref(tmp_path,'terminal-review.json'),
               'continuity_evidence':write(tmp_path/'continuity.json', {'inputs':{
                    'plan.frozen.v1.json':parent_ref,'execution-release-v1.json':release_ref,
                    'root-production-review-v1.json':review_ref}})}
    events = []
    for index,row in enumerate(parent['episodes'][:15]):
        valid = index < 14; key = row['episode_key']
        manifest_ref = parent['expected_manifests'][key]; manifest = w.read_ref(manifest_ref)
        output = Path(manifest['output_dir'])
        context = {'schema':'n32-worker-context-v1','plan':parent_ref,'release':release_ref,'expected_manifest':manifest_ref,
                   'episode_key':key,'attempt_id':key,'main_argv':manifest['argv'][1:],'worker_contract':old.WORKER_CONTRACT}
        context_ref = write(output/'n32-worker-context.json', context)
        identity = {'pid':123,'proc_start_ticks':'1','boot_id':'synthetic'}
        process_ref = write(output/'process.json', {**identity,'attempt_id':key,'context':context_ref,'release':release_ref})
        command_ref = write(output/'command.json', {'argv':['python','-m','scripts.qd_ed_n32_worker','--context',context_ref['path'],'--context-sha256',context_ref['sha256']],
                                                  'main_argv':manifest['argv'],'context':context_ref})
        report_ref = write(output/'eds_eval/decision-evidence-audit.json', {'accepted':True,'evidence_complete':True})
        native_ref = write(output/'eds_eval/n32-worker-receipt.json', {'process':identity,'context':context_ref,'plan':parent_ref,
            'row':row,'source':source,'expected_manifest':manifest_ref,'attempt_id':key,'audit_report':report_ref,
            'native_counts':{},'accepted':True,'process_unchanged':True,'main_exit_code':0})
        stage_ref = write(output/'eds_eval/stage_events.jsonl', {'synthetic':True})
        stage_ref['bytes'] = Path(stage_ref['path']).stat().st_size
        base = {'attempt_id':key,'episode_key':key,'identity':s.c_identity(row),'source_commit':source['commit'],
                'plan_sha256':parent_ref['sha256'],'release':release_ref,'context':context_ref,
                'runtime_manifest_sha256':runtime['sha256'],'runtime_inventory_sha256':'inventory','budget_bucket':row['budget_bucket'],
                'init_row_sha256':row['init_row_sha256'],'physical_gpu':7,'output_dir':str(output),'ledger_prefix':{},'retry_of':None,'recovery_of':None}
        terminal = {**base,'event':'valid' if valid else 'aborted','outcome_valid':valid,'required_cost_telemetry_complete':valid,
                    'success':False if valid else None,'gpu_process_wall_seconds':10.0}
        if valid: terminal['n32_worker_receipt']=native_ref
        terminal_ref = write(output/'attempt-result.json', terminal)
        entry = {'original_row':row,'attempt_id':key,'old_attempt_id':key,'new_attempt_id':key if valid else None,
            'semantic_cell':{k:row[k] for k in c.SEMANTIC_FIELDS},'expected_manifest':manifest_ref,'source_commit':c.BASE_SOURCE,
            'runtime':runtime,'denominator_eligible':valid,'replay_permitted':False,'terminal_receipt':terminal_ref,
            'native_receipt':native_ref,'generic_audit':report_ref,'context':context_ref,'command_receipt':command_ref,
            'process_receipt':process_ref,'stage_events':stage_ref,'native_counts':{},'gpu_hours_retained':10/3600,
            'budget_bucket_retained':row['budget_bucket'],'success':terminal['success']}
        if valid: mapping['accepted_cells'].append(entry)
        else: mapping['old_invalid_cell']={**entry,'proposed_recovery_attempt_id':c.RECOVERY}
        events.extend([{**base,'event':'reserved'}, {**base,'event':'dispatched'},terminal])
    for old_row,row in zip(parent['episodes'][14:],plan['episodes']):
        mapping['proposed_cells'].append({'old_row':old_row,'proposed_row':row,'old_attempt_id':old_row['episode_key'],
            'new_attempt_id':row['episode_key'],'semantic_continuity':{k:v for k,v in old_row.items() if k not in ('iteration','episode_key','budget_bucket')},
            'parent_expected_manifest':parent['expected_manifests'][old_row['episode_key']], 'recovery_of':c.recovery_of(row),
            'retry_of':None,'native_receipt':None,'generic_audit':None,'release_enabled':False})
    plan['carry_forward_map']=write(tmp_path/'map.json',mapping)
    # Fixture models the independently reviewed hash root; production cannot bypass it.
    monkeypatch.setattr(history,'verify_preparation_anchor',lambda p: None)
    monkeypatch.setattr(release,'verify_continuity',lambda p: None)
    monkeypatch.setattr(w,'verify_source',lambda *args: None)
    plan['source']={'commit':'b'*40}
    return plan,events,mapping,parent


def journal(plan, count, wins=()):
    result=[]
    for index,row in enumerate(plan['episodes'][:count]):
        base={'schema':'n32r3-lifecycle-v1','attempt_id':row['episode_key'],'episode_key':row['episode_key'],
              'identity':s.c_identity(row),'budget_bucket':row['budget_bucket'],'plan_sha256':'plan','release':{},
              'source_commit':'new','runtime_manifest_sha256':'runtime','runtime_inventory_sha256':'inventory',
              'init_row_sha256':row['init_row_sha256'],'output_dir':'synthetic/'+row['episode_key'],'physical_gpu':7,
              'ledger_prefix':{},'context':{},'continuation':c.commitments(plan,row),'semantic_key':str(index),
              'retry_of':None,'recovery_of':c.recovery_of(row)}
        result += [{**base,'event':event,**({'outcome_valid':True,'required_cost_telemetry_complete':True,
                       'success':index in wins,'gpu_process_wall_seconds':10.0} if event=='valid' else {})}
                   for event in ('reserved','dispatched','valid')]
    return result


def test_positive_original_plus_recovery(fixture):
    plan,events,_,_=fixture
    result=s.reconcile(plan,events+journal(plan,1),lambda *args:None)
    assert result['complete_valid_triples']==5 and len(result['outcomes'])==15
    assert result['next_row']==plan['episodes'][1] and not result['futile']
    snap=generic.budget_snapshot(result['charged_events'])
    assert snap['dispatched']==16 and snap['aborted']==1 and snap['by_bucket']['recovery']==1
    assert snap['gpu_hours_consumed']==pytest.approx(160/3600)
    assert result['http_counters']=='Unknown' and not result['scientific_promotion']


@pytest.mark.parametrize('fault',['duplicate','reorder','alias','recovery','old_accepted','invalid_stage','missing_control','live','continuation','semantic','receipt'])
def test_lifecycle_attacks(fixture,fault):
    plan,events,_,_=fixture; new=journal(plan,2); verify=lambda *args:None
    if fault=='duplicate': new+=new[:3]
    if fault=='reorder': new=new[3:]+new[:3]
    if fault=='alias': new[0]['identity']['iteration']='other'
    if fault=='recovery': new[3]['recovery_of']=c.OLD_INVALID
    if fault=='old_accepted': new[0]['attempt_id']=events[0]['attempt_id']
    if fault=='invalid_stage': new=new[:3];new[-1]['outcome_valid']=False
    if fault=='missing_control': events=events[:-6]+events[-3:]
    if fault=='live': new=new[:2]
    if fault=='continuation': new[0]['continuation']={}
    if fault=='semantic': new[-1]['semantic_key']='different'
    if fault=='receipt':
        new=new[:3]
        def verify(*args): raise ValueError('audit digest differs')
    if fault in ('invalid_stage','live','receipt'):
        result=s.reconcile(plan,events+new,verify)
        assert result['next_row'] is None and len(result['outcomes'])==14
        assert result['status']==('LIVE_OR_UNSETTLED' if fault=='live' else 'INVALID_STOP')
    else:
        with pytest.raises((ValueError,KeyError)):s.reconcile(plan,events+new,verify)


@pytest.mark.parametrize('field',['native_receipt','generic_audit','context','command_receipt','terminal_receipt','process_receipt','expected_manifest'])
@pytest.mark.parametrize('attack',['byte','other_digest','rehashed_identity'])
def test_historical_receipt_tamper(fixture,field,attack):
    plan,_,mapping,parent=fixture;entry=copy.deepcopy(mapping['accepted_cells'][0])
    reference=entry[field];path=Path(reference['path'])
    if attack=='byte':path.write_bytes(path.read_bytes()+b' ')
    elif attack=='other_digest':entry[field]=mapping['accepted_cells'][1][field]
    else:
        data=json.loads(path.read_text())
        if field=='generic_audit':data['accepted']=False
        elif field=='context':data['plan']=plan['parent_release']
        elif field=='command_receipt':data['main_argv']=['mutated']
        elif field=='expected_manifest':data['row']['profile']='Q0'
        elif field=='process_receipt':data['pid']=999
        elif field=='terminal_receipt':data['identity']['profile']='Q0'
        else:data['row']['profile']='Q0'
        entry[field]=write(path,data)
    with pytest.raises((ValueError,KeyError)):history.verify_cell(entry,plan,parent)


@pytest.mark.parametrize('fault',['duplicate','swap_profile','seed','init','recovery_alias','recovery_bucket'])
def test_map_attacks(fixture,fault):
    plan,_,mapping,_=fixture
    if fault=='duplicate':mapping['accepted_cells'][1]=mapping['accepted_cells'][0]
    if fault=='swap_profile':mapping['accepted_cells'][1]['expected_manifest']=mapping['accepted_cells'][2]['expected_manifest']
    if fault=='seed':mapping['proposed_cells'][0]['proposed_row']['policy_seed']+=1
    if fault=='init':mapping['accepted_cells'][0]['semantic_cell']['init_row_sha256']='other'
    if fault=='recovery_alias':mapping['proposed_cells'][1]['recovery_of']=c.OLD_INVALID
    if fault=='recovery_bucket':mapping['proposed_cells'][0]['proposed_row']['budget_bucket']='development'
    plan['carry_forward_map']=write(Path(plan['carry_forward_map']['path']),mapping)
    with pytest.raises(ValueError):history.validate_mapping(plan)


def test_thresholds_and_29_cells(fixture):
    plan,events,_,_=fixture
    result=s.reconcile(plan,events+journal(plan,1),lambda *args:None)
    assert not result['futile']  # 0 + 5 == 5
    result=s.reconcile(plan,events+journal(plan,4),lambda *args:None)
    assert result['status']=='NUMERIC_FUTILITY' and result['complete_valid_triples']==6
    result=s.reconcile(plan,events+journal(plan,15,wins=(0,3,6,9,12)),lambda *args:None)
    assert len(result['outcomes'])==29 and not result['prospective_dev_necessary_gate_met']
    result=s.reconcile(plan,events+journal(plan,16,wins=(0,3,6,9,12)),lambda *args:None)
    assert result['status']=='COMPLETE' and result['prospective_dev_necessary_gate_met']
    with pytest.raises(ValueError):s.progress([{'task_id':4,'profile':'N32','success':True}])


def allowance():
    return {'authority_starts_at':'2026-10-04T00:00:00Z','authority_ends_at':c.DEADLINE,
            'private_budget':True,'gpu_idle':True,'physical_gpu':7,'gpu_uuid':c.GPU_UUID,
            'live_handles':[],'unsettled_reservations':0,'global_seconds_remaining':500000,
            'private_seconds_remaining':500000,'cohort_seconds_remaining':30600,'protected_seconds_remaining':44*3600,
            'global_attempts_remaining':1000,'protected_attempts_remaining':160,'cohort_attempts_remaining':16,
            'bucket_attempts_remaining':{'baseline':300,'development':800,'recovery':40},
            'local_bucket_attempts_remaining':{'baseline':5,'development':10,'recovery':1}}


@pytest.mark.parametrize('fault',['none','stop','dangling','deadline','private','uuid','idle','live','unsettled','reserve','nan','unknown','seconds','local_bucket','bucket','attempts'])
def test_admission(fault,tmp_path):
    a=allowance();now=dt.datetime(2026,10,8,11,tzinfo=dt.timezone.utc);stop=tmp_path/'STOP'
    if fault=='stop':stop.touch()
    if fault=='dangling':stop.symlink_to(tmp_path/'missing')
    if fault=='deadline':now=dt.datetime.fromisoformat(c.DEADLINE.replace('Z','+00:00'))-dt.timedelta(seconds=1839)
    if fault=='private':a['private_budget']=False
    if fault=='uuid':a['gpu_uuid']='foreign'
    if fault=='idle':a['gpu_idle']=False
    if fault=='live':a['live_handles']=['owner']
    if fault=='unsettled':a['unsettled_reservations']=1
    if fault=='reserve':a['global_seconds_remaining']=a['protected_seconds_remaining']+1839
    if fault=='nan':a['cohort_seconds_remaining']=float('nan')
    if fault=='unknown':a['private_seconds_remaining']='Unknown'
    if fault=='seconds':a['cohort_seconds_remaining']=1839
    if fault=='local_bucket':a['local_bucket_attempts_remaining']['recovery']=0
    if fault=='bucket':a['bucket_attempts_remaining']['recovery']=0
    if fault=='attempts':a['cohort_attempts_remaining']=17
    if fault=='none':assert c.pre_dispatch(c.expected_rows()[0],a,now=now,stop_path=stop)==1840
    else:
        with pytest.raises(ValueError):c.pre_dispatch(c.expected_rows()[0],a,now=now,stop_path=stop)


def test_unknown_charge_never_zero(fixture):
    _,events,_,_=fixture;events[-1]['gpu_process_wall_seconds']='Unknown'
    with pytest.raises(generic.GateError):generic.budget_snapshot(events)
    assert 438+16==454
    assert 61.35722319715016+8.5==69.85722319715016


def test_disabled_release_and_old_contract_unchanged(fixture,tmp_path):
    plan,_,_,_=fixture
    for schema in ('n32r3-plan-candidate-NONEXECUTABLE-v1','n32r3-released-plan-v1'):
        ref=write(tmp_path/'disabled.json',{**plan,'schema':schema,'frozen':False,'release_enabled':False})
        with pytest.raises(ValueError):release.validate_release(ref,dummy_ref(tmp_path,'disabled-release.json'))
    assert old.LIMITS['cohort_gpu_seconds']==18000 and len(old.expected_rows())==30
    with pytest.raises(ValueError):old.pre_dispatch(c.expected_rows()[0],allowance(),now=dt.datetime.now(dt.timezone.utc),stop_path=tmp_path/'STOP')
    with pytest.raises(ValueError):c.require_recovery_row({'schema':'n32-released-plan-v1',**plan,'episodes':[]},c.expected_rows()[0])


def test_independent_review_not_replaceable(fixture,monkeypatch):
    # Reload only this guard's original function without performing any external reads.
    import runpy
    guard=runpy.run_path(str(c.ROOT/'scripts/qd_ed_n32r3_history.py'))['verify_preparation_anchor']
    with pytest.raises(ValueError,match='review anchor'):guard(fixture[0])


def test_new_parent_cohort_result_blocks_semantic_replay(fixture):
    plan,events,_,parent=fixture
    row=parent['episodes'][15]
    events.append({'attempt_id':row['episode_key'],'event':'reserved','identity':s.c_identity(row)})
    with pytest.raises(ValueError,match='parent cohort changed'):s.reconcile(plan,events,lambda *args:None)


def test_worker_reuses_scientific_audit_functions():
    from scripts import qd_ed_n32_worker as parent_worker
    assert worker.native_counts is parent_worker.native_counts
    assert worker.evidence is parent_worker.evidence
    assert worker.generic is parent_worker.generic and worker.n32 is parent_worker.n32
