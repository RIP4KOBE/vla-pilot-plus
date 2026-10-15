"""Bounded synthetic CPU tests; never open real episode inputs."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest
import torch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('full_dev_chronology', HERE/'read_full_dev.py')
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
h, auditor, deps = r.dependencies()


def put(path, value, *, lines=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(x)+'\n' for x in value) if lines else json.dumps(value)+'\n')
    return {'path': str(path), 'sha256': r.sha(path.read_bytes())}


def step(i, x, *, reset=0, command=1, terminal=False, qpos=True):
    return {'global_step': i, 'reset_sequence': reset, 'eef': {'dtype': 'torch.float64', 'shape': [3], 'value': [x, 0., 0.]},
            'command': {'dtype': 'torch.float32', 'shape': [7], 'value': [0.]*6+[command]},
            'gripper_qpos': {'value': [x, -x]} if qpos else None, 'terminated': terminal, 'truncated': False}


def decision(i, start, count, guidance, *, reset=0):
    return {'decision_id': str(i), 'global_step': start, 'last_executed_step': start+count-1 if count else None,
            'executed_prefix_length': count, 'reset_sequence': reset, 'stage': 1, 'use_guidance': guidance, 'providers': []}


def episode(ep, terminal=False):
    latent = torch.tensor([[1., 2.]], dtype=torch.bfloat16)
    chunk = torch.zeros(1, 8, 7); chunk[:, :, 6] = -1
    fp = auditor.fingerprints(latent)[0]
    rows = []
    def add(kind, values, reset=0):
        rows.append({'schema': 'qd-ed-decision-evidence-v1', 'sequence': len(rows)+1, 'episode': 0,
                     'event': kind, 'decision_id': 'd', 'global_step': 0, 'reset_sequence': reset, 'values': values})
    add('decision_context', {'previous_decision_id': None, 'previous_stage': None, 'stage': 1, 'stage_changed': False,
        'use_guidance': False, 'providers': [], 'keypoints': 'SENTINEL_NOT_EXPORTED'})
    add('policy_action_decode', {'action_chunk': chunk, 'selected_latent': latent, 'selected_canonical_fingerprint': fp})
    add('decision_committed', {'action_chunk': chunk, 'execution_horizon': 8})
    add('action_dispatch', {'execution_index': 1})
    add('executed_action', {'action_numpy': chunk[0, 0]})
    add('pre_reset_outcome', {'observation': {'robot0_eef_pos': torch.tensor([.001, 0., 0.], dtype=torch.float64)},
        'reward': 1. if terminal else 0., 'terminated': terminal, 'success': terminal, 'origin': 'actual_env_step_before_automatic_reset'})
    if terminal:
        add('automatic_reset_boundary', {'reset_will_follow': True, 'reset_completed': None})
    add('step_returned', {'terminated': terminal, 'truncated': not terminal, 'success': terminal,
                          'returned_reset_observation_sentinel': [999., 999., 999.]}, reset=int(terminal))
    ep.mkdir(parents=True)
    path = ep/'bundle_000001.pt'; torch.save({'schema': 'qd-ed-decision-evidence-v1', 'events': rows}, path)
    status = {'schema': 'qd-ed-decision-evidence-v1', 'episode': 0, 'complete': True, 'failed': False,
              'pending_action': False, 'decisions': 1, 'committed_decisions': 1, 'bundles': 1}
    sr = put(ep/'status.json', status)
    index = [{'bundle': path.name, 'sha256': r.sha(path.read_bytes()), 'first_sequence': 1, 'last_sequence': len(rows),
              'events': [{k: x[k] for k in ('sequence', 'event', 'decision_id', 'global_step', 'reset_sequence')} for x in rows]}]
    ir = put(ep/'events.jsonl', index, lines=True)
    return status, sr, ir


@pytest.fixture
def universe(tmp_path, monkeypatch):
    root = tmp_path/'artifacts'; root.mkdir(); monkeypatch.setattr(r, 'ARTIFACT_ROOT', root)
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', '')
    rows = [{'split': 'dev', 'iteration': r.COHORT, 'profile': arm, 'task_id': task, 'env_seed': 100+task,
             'policy_seed': 100+task, 'init_index': 0, 'init_row_sha256': 'row'+str(task), 'episode_key': f't{task:02d}-{arm}'}
            for task in range(10) for arm in ('C0', 'Q0', 'N2')]
    plan = {'source_commit': r.SOURCE_COMMIT, 'profiles_sha256': 'profiles', 'runtime_manifest_sha256': 'runtime',
            'runtime_inventory_sha256': 'inventory', 'seed_plan_sha256': 'seeds', 'candidate_profiles': {'N2': {'sha256': 'candidate'}},
            'code_files': [{'path': 'scripts/audit_decision_evidence.py', 'sha256': deps['sources']['auditor']['sha256']}],
            'n2_cohort': {'cohort_id': r.COHORT, 'protocol': {'sha256': 'protocol'}, 'accounting_clarification': {'sha256': 'clarification'}}, 'episodes': rows}
    pref = put(root/'plan.json', plan); monkeypatch.setattr(r, 'BASE_PLAN_SHA', pref['sha256'])
    frozen = {**{k: plan[k] for k in r.BINDING}, 'cohort_id': r.COHORT, 'candidate_sha256': 'candidate',
              'protocol_sha256': 'protocol', 'accounting_clarification_sha256': 'clarification'}
    cells, extras = [], []
    for n, row in enumerate(rows):
        name = f'attempt-{n}'; out = root/'attempts'/name; ed = out/'eds_eval'; ep = ed/'decision_evidence/episode_000'
        status, sr, ir = episode(ep, terminal=n==0)
        ident = {'episode_id': 0, 'task_id': row['task_id'], 'episode_seed': row['env_seed']}
        cp = put(ed/'episode_compute.jsonl', [{**ident, 'outcome': 'completed', 'guided_chunks': 0, 'unguided_chunks': 1, 'decision_evidence': status}], lines=True)
        fresh = auditor.audit_episode(ep, ed/'episode_compute.jsonl'); assert fresh['accepted'], fresh
        ap = put(ed/'decision-evidence-audit.json', fresh)
        t = {'attempt_id': name, 'episode_key': row['episode_key'], 'identity': {k: row[k] for k in r.IDENTITY},
             'event': 'valid', 'outcome_valid': True, 'success': n==0, 'task_failure': n!=0, 'compute_outcome': 'completed',
             'plan_sha256': pref['sha256'], 'retry_of': None, 'output_dir': str(out), 'physical_gpu': 3,
             'source_commit': r.SOURCE_COMMIT, 'profile_manifest_sha256': plan['profiles_sha256'],
             'runtime_manifest_sha256': plan['runtime_manifest_sha256'], 'runtime_inventory_sha256': plan['runtime_inventory_sha256'],
             'init_row_sha256': row['init_row_sha256'], 'n2_cohort_id': r.COHORT, 'n2_frozen_identity': frozen}
        tp = put(out/'attempt-result.json', t)
        refs = {'terminal': tp, 'audit': ap, 'compute': cp}
        cells.append({'identity': t['identity'], 'status': 'complete_valid', 'valid_attempt_id': name,
            'attempts': [{'terminal': t, 'references': refs, 'status': 'complete_valid'}], 'metrics': {'n2': None}})
        sp = {'status': 'not_recorded', 'path': str(ed/'stage_events.jsonl')}
        if n==1: sp = {'status': 'present', 'reference': put(ed/'stage_events.jsonl', [], lines=True)}
        extras.append({'attempt_id': name, 'metadata': put(ed/'episode_metadata.jsonl', [ident], lines=True),
                       'status': sr, 'index': ir, 'stage_events': sp})
    report = {'schema': 'qd-ed-n2-matrix-report-v1', 'cohort_id': r.COHORT, 'matrix': 'complete_valid_30', 'cells': cells,
              'input_manifest': {'script_sha256': r.MATRIX_SHA, 'base_plan': pref, 'input_scope_complete': True}}
    manifest = {'schema': 'n2-dev-chronology-input-v1', 'matrix_report': put(root/'matrix.json', report), 'cells': extras}
    return root, plan, report, manifest


def auth_fixture(root, manifest):
    mr = put(root/'manifest.json', manifest)
    files = ('read_full_dev.py', 'protocol-v1.md', 'input-schema-v1.json', 'dependencies-v1.json', 'test_read_full_dev.py')
    freeze = {'status': 'CPU_TESTED_FROZEN_BEFORE_FULL_DEV_READ', 'actual_read_authorized': False,
              'local_files': {n: r.sha((HERE/n).read_bytes()) for n in files}}
    fr = put(root/'freeze.json', freeze)
    auth = {'schema': 'n2-dev-chronology-read-authorization-v1', 'status': 'AUTHORIZED_CPU_READ', 'scope_reviewed': True,
            'freeze': fr, 'matrix_report': manifest['matrix_report'], 'input_manifest': mr}
    return put(root/'authorization.json', auth)


def test_all30_real_frozen_auditor_and_reader_keep_optional_absence_and_early_success(universe):
    root, plan, report, manifest = universe
    before = {a['terminal']['attempt_id']: a['terminal']['success'] for c in report['cells'] for a in c['attempts']}
    manifest['cells'].reverse()  # Stable output order must come from the fixed matrix.
    auth = auth_fixture(root, manifest); out = root/'continuation_20260923/full-dev-closed-loop-analysis/test'
    r.run(auth['path'], auth['sha256'], out)
    index = r.parse((out/'index.json').read_bytes()); assert len(index['cells']) == 30
    assert [x['cell'] for x in index['cells']] == [f't{t:02d}-{p}' for t in range(10) for p in ('c0', 'q0', 'n2')]
    first = r.parse((out/'t00-c0.json').read_bytes()); second = r.parse((out/'t00-q0.json').read_bytes())
    assert first['original_outcome']['success'] is True and first['summary']['observed_actions'] == 1
    assert first['summary']['stage']['events'] is None and first['summary']['stage']['query_status_counts'] is None
    assert second['summary']['stage']['events'] == [] and second['summary']['stage']['query_status_counts'] == {}
    assert first['actual_steps'][0]['eef']['dtype'] == 'torch.float64' and first['actual_steps'][0]['eef']['value'] == [.001, 0., 0.]
    assert first['actual_steps'][0]['returned_reset_sequence'] == 1 and first['automatic_reset_boundaries'][0]['reset_completed'] is None
    assert 'SENTINEL_NOT_EXPORTED' not in (out/'t00-c0.json').read_text() and '999.0' not in (out/'t00-c0.json').read_text()
    assert before == {a['terminal']['attempt_id']: a['terminal']['success'] for c in report['cells'] for a in c['attempts']}
    assert not torch.cuda.is_initialized()


@pytest.mark.parametrize('bad', ['missing', 'duplicate', 'invalid', 'audit', 'source', 'outside', 'absent_now_present'])
def test_membership_fails_before_any_bundle_load(universe, monkeypatch, bad):
    root, plan, report, manifest = universe
    if bad=='missing': manifest['cells'].pop()
    elif bad=='duplicate': manifest['cells'][-1] = manifest['cells'][0]
    elif bad=='invalid': report['cells'][0]['status'] = 'terminal_invalid'
    elif bad=='audit':
        ref = report['cells'][0]['attempts'][0]['references']['audit']; a = r.parse(Path(ref['path']).read_bytes()); a['accepted'] = False
        report['cells'][0]['attempts'][0]['references']['audit'] = put(Path(ref['path']), a)
    elif bad=='source':
        revision = copy.deepcopy(plan); revision['code_files'][0]['sha256'] = 'changed'
        report['input_manifest']['plan_revisions'] = [put(root/'revision.json', revision)]
    elif bad=='outside': manifest['cells'][0]['metadata']['path'] = str(root.parent/'foreign.json')
    else: Path(manifest['cells'][0]['stage_events']['path']).write_text('')
    manifest['matrix_report'] = put(root/'matrix.json', report)
    monkeypatch.setattr(torch, 'load', lambda *a, **k: pytest.fail('must reject before decoding'))
    with pytest.raises((ValueError, KeyError)):
        r.admit(manifest, r.Inputs(root), deps)


def test_immutable_base_recovery_revision_has_exact_representative(universe):
    root, plan, report, manifest = universe
    base_ref = report['input_manifest']['base_plan']; original_bytes = Path(base_ref['path']).read_bytes()
    cell = report['cells'][0]; valid = cell['attempts'][0]
    predecessor = copy.deepcopy(valid['terminal']); predecessor.update(attempt_id='original-invalid', outcome_valid=False)
    old = plan['episodes'][0]; revision = copy.deepcopy(plan)
    retry = {**old, 'episode_key': 'recovery-key', 'retry_of': predecessor['attempt_id']}; revision['episodes'].append(retry)
    revision_ref = put(root/'recovery-plan.json', revision)
    t = copy.deepcopy(valid['terminal']); t.update(episode_key='recovery-key', retry_of='original-invalid', plan_sha256=revision_ref['sha256'])
    valid['terminal'] = t; valid['references']['terminal'] = put(Path(valid['references']['terminal']['path']), t)
    cell['attempts'].insert(0, {'terminal': predecessor, 'status': 'terminal_invalid', 'references': {'terminal': {'path': '/must/not/read', 'sha256': '0'*64}}})
    report['input_manifest']['plan_revisions'] = [revision_ref]; manifest['matrix_report'] = put(root/'matrix.json', report)
    _, admitted = r.admit(manifest, r.Inputs(root), deps)
    assert len(admitted) == 30 and admitted[0]['terminal']['retry_of'] == 'original-invalid'
    assert Path(base_ref['path']).read_bytes() == original_bytes and len(plan['episodes']) == 30


def test_reactivations_zero_action_and_partial_prefix_count_actual_coverage():
    ds = [decision(0,0,2,True), decision(1,2,1,False), decision(2,3,2,True), decision(3,5,1,False), decision(4,6,0,True)]
    ss = [step(i,float(i)) for i in range(6)]
    out = r.chronology(h, ds, ss, [])
    assert out['guided_actions'] == 4 and out['observed_actions'] == 6 and out['guided_action_fraction'] == 4/6
    assert out['all_on_to_off_steps'] == [2,5] and out['all_off_to_on_steps'] == [3,6]
    assert out['last_guided_action'] == 4 and sum(len(x['decision_ids']) for x in out['state_runs']) == 4
    assert r.motion(h, [])['status'] == 'not_observed'
    assert r.chronology(h, [decision(0,0,1,False)], [step(0,0.)], None)['first_on_to_off'] == {'step': None, 'status': 'not_observed'}


def test_stage_all_events_exact_first_last_and_unknown_predecessors():
    ds=[decision(0,0,2,True),decision(1,2,1,False)]
    ss=[step(0,0.,command=1),step(1,1.,command=-1),step(2,2.,command=-1)]
    events=[{'global_step':0,'query_status':'ok','gripper_value_used':1},
            {'global_step':2,'query_status':'ok','stage_after':1,'guidance_after':False,'gripper_value_used':1,'vlm_query_limit':3},
            {'global_step':2,'query_status':'skipped','skipped_reason':'query_limit','gripper_value_used':-1},
            {'global_step':3,'query_status':'error','gripper_value_used':1}]
    out=r.joined_stage(events,ds,ss)
    assert len(out['events'])==len(out['associations'])==4 and out['query_status_counts']=={'ok':2,'skipped':1,'error':1}
    assert out['associations'][0]['matches_first_sent'] is None
    assert out['associations'][1]['matches_first_sent'] is True and out['associations'][1]['matches_last_sent'] is False
    assert out['associations'][2]['matches_last_sent'] is True and out['associations'][3]['same_step_context_agrees'] is None
    ds[1]['reset_sequence']=1
    assert r.joined_stage(events,ds,ss)['associations'][1]['matches_first_sent'] is None


def test_motion_origins_sign_boundary_optional_fingers_and_resets():
    ss=[step(0,0.,command=1),step(1,2.,command=-1),step(2,1.,command=-1)]
    out=r.motion(h,ss[1:],ss[0])
    assert out['origin_step']==0 and out['gripper_qpos_origin_step']==1 and out['eef_path_length_m']==3
    assert out['command_sign_changes']==0
    assert r.motion(h,[step(2,100.,reset=1,qpos=False)],ss[1])['contiguous_observed_edges']==0
    assert r.motion(h,[step(0,0.,qpos=False)])['gripper_qpos_start'] is None
    incompatible=[step(0,0.),step(1,1.)];incompatible[1]['gripper_qpos']['value']=[1.]
    assert r.motion(h,incompatible)['gripper_qpos_start'] is None
    gap=r.motion(h,[step(0,0.),step(2,99.)])
    assert gap['eef_net_displacement_m'] is None and gap['contiguous_observed_edges']==0
    resetsteps=[step(0,0.,terminal=True),step(1,100.,reset=1),step(2,101.,reset=1)]
    ds=[decision(0,0,1,True),decision(1,1,2,False,reset=1)]
    out=r.chronology(h,ds,resetsteps,[])
    assert out['all_on_to_off_steps']==[] and len(out['motion_components'])==2
    assert [x['eef_path_length_m'] for x in out['motion_components']]==[0.,1.]


def test_native_dtype_no_prose_or_new_quality_and_fallback_passthrough(universe, monkeypatch):
    root, _, _, manifest=universe
    _, admitted=r.admit(manifest,r.Inputs(root),deps); item=admitted[2]
    item['cell']['metrics']['n2']={'records':[{'global_step':0,'qd_quality_applicable':False,'qd_quality_reason':'unsupported_provider', 'selected_reward':'DO_NOT_COPY'}]}
    item['stage_rows']=[{'global_step':0,'raw_response':'PROSE_SENTINEL','prompt':'FORBIDDEN','query_status':'ok'}]
    for name in ('run','selected_quality','keypoint_link'):
        monkeypatch.setattr(h,name,lambda *a,**k:pytest.fail('forbidden helper'))
    out=r.extract(item,r.Inputs(root),h)
    assert out['matrix_applicability_context_only'][0]['qd_quality_reason']=='unsupported_provider'
    assert 'PROSE_SENTINEL' not in json.dumps(out) and 'DO_NOT_COPY' not in json.dumps(out)
    for dtype in (torch.bfloat16,torch.float32,torch.float64):
        value=h.tensor_record(torch.tensor([.123],dtype=dtype)); assert value['dtype']==str(dtype)
    with pytest.raises(ValueError,match='nonfinite'):
        h.tensor_record(torch.tensor([float('nan')]))


def test_failed_read_records_incomplete_not_new_outcome(universe):
    root,_,report,manifest=universe; auth=auth_fixture(root,manifest)
    bundle=Path(manifest['cells'][0]['index']['path']).parent/'bundle_000001.pt';bundle.write_bytes(b'corrupt')
    out=root/'continuation_20260923/full-dev-closed-loop-analysis/failed'
    with pytest.raises(ValueError,match='bundle_sha'):
        r.run(auth['path'],auth['sha256'],out)
    status=r.parse((out/'status.json').read_bytes())
    assert status['complete'] is False and status['cell']=='t00-c0' and status['error_code']=='bundle_sha_mismatch_before_audit'
    assert report['cells'][0]['attempts'][0]['terminal']['success'] is True
    assert not (out/'index.json').exists()


def test_input_hash_drift_and_absent_source_appearance_fail(universe):
    root,_,_,manifest=universe; inputs=r.Inputs(root);r.admit(manifest,inputs,deps)
    Path(manifest['cells'][0]['stage_events']['path']).write_text('')
    with pytest.raises(ValueError,match='absent_source'):
        inputs.finish()
    inputs.absent.clear();path=Path(manifest['cells'][0]['metadata']['path']);path.write_text('[]')
    with pytest.raises(ValueError,match='input_changed'):
        inputs.finish()


def test_separate_authorization_is_required_before_admission(universe,monkeypatch):
    root,_,_,manifest=universe; ref=auth_fixture(root,manifest)
    auth=r.parse(Path(ref['path']).read_bytes());auth['status']='PENDING_ROOT_REVIEW'
    ref=put(Path(ref['path']),auth)
    monkeypatch.setattr(r,'admit',lambda *a:pytest.fail('not authorized'))
    with pytest.raises(ValueError,match='read_not_authorized'):
        r.run(ref['path'],ref['sha256'],root/'continuation_20260923/full-dev-closed-loop-analysis/denied')
    assert not (root/'continuation_20260923/full-dev-closed-loop-analysis/denied').exists()
