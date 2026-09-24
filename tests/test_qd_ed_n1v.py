"""CPU protocol tests: never launch a model, GPU episode or provider request."""
import copy
import json
from pathlib import Path
import sys

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import qd_ed_final_runner as r
import qd_ed_n1v as p
import qd_ed_n1v_supervise as s
import qd_ed_available_gpu_queue as q
from test_qd_ed_final_runner import codex_compute_case, events_for, row, synced_state, state


@pytest.fixture
def timeout_case(tmp_path, monkeypatch):
    episode, profile, runtime, path, record = codex_compute_case(tmp_path, monkeypatch, calls=1)
    episode.update(iteration='N1V', init_row_sha256='init-row')
    frozen = runtime['frozen_stage_provider']
    frozen.update(output_format='json_schema_v1', event_policy='completed_reconnect_v1', timeout_seconds=180)
    frozen['public_config_sha256'] = r.codex_public_config_sha256(frozen)
    config_path = tmp_path / '.hydra/config.yaml'
    config = yaml.safe_load(config_path.read_text())
    for key, value in r.stage_overrides(runtime).items():
        current = config; parts = key.lstrip('+').split('.')
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value
    config_path.write_text(yaml.safe_dump(config))
    record['stage_transport'].update({k: frozen[k] for k in r.CODEX_CONFIG_KEYS})
    record['stage_transport'].update(public_config_sha256=frozen['public_config_sha256'],
        output_format='json_schema_v1', event_policy='completed_reconnect_v1',
        output_schema_sha256=r.codex_public_config(frozen)['output_schema_sha256'])
    record.update(outcome='execution_error', provider_token_usage_complete=False)
    for prefix in ('stage_codex_', 'provider_'):
        record.update({prefix + suffix: 0 for suffix in r.CODEX_COUNT_SUFFIXES})
        record.update({prefix + 'logical_call_attempts': 1, prefix + 'failed_calls': 1,
                       prefix + 'call_latency_s': 180.2})
    path.write_text(json.dumps(record) + '\n')
    event = dict(episode_id=0, task_id=episode['task_id'], episode_seed=episode['env_seed'],
        query_status='error', query_ok=False, error='codex_timeout', raw_response=None,
        api_request_attempts=None, api_sdk_retry_attempts=None, api_request_counter_available=False,
        transport={**record['stage_transport'], 'completed_turns': 0,
                   'process_timed_out': True, 'diagnostics_version': 'redacted_cli_v1'},
        codex_call_latency_s=180.2)
    event.update({'codex_' + suffix: record['provider_' + suffix] for suffix in r.CODEX_COUNT_SUFFIXES})
    stage = tmp_path / 'eds_eval/stage_events.jsonl'; stage.write_text(json.dumps(event) + '\n')
    (tmp_path / 'gpu-kernel-xid.json').write_text(json.dumps({
        'schema': 'qd-ed-kernel-xid-monitor-v1', 'physical_gpu': 2, 'records': []}))
    (tmp_path / 'episode_1/error.txt').write_text('RuntimeError: stage_json_query_failed: codex_timeout\n')
    (tmp_path / 'episode_1/episode_1_fail_error.txt').write_text(
        'Episode failed due to execution error: stage_json_query_failed: codex_timeout\n')
    return episode, profile, runtime, path, record, stage, event


def test_prospective_timeout_keeps_unknown_costs_and_never_alters_old_eligibility(tmp_path, timeout_case):
    episode, profile, runtime, *_ = timeout_case
    result = p.timeout_outcome(r, {'n1v_recovery': p.CONTRACT}, tmp_path, episode, profile, runtime)
    assert result['failure_detail'] == 'n1v_stage_timeout' and result['retryable_infrastructure']
    assert result['failed_call_token_usage'] is None and not result['required_cost_telemetry_complete']
    assert result['outcome_valid'] is False and result['task_failure'] is False
    assert p.timeout_outcome(r, {}, tmp_path, episode, profile, runtime) is None
    episode['iteration'] = 'N1U'
    assert p.timeout_outcome(r, {'n1v_recovery': p.CONTRACT}, tmp_path, episode, profile, runtime) is None
    event, old = r.failed_outcome(r.GateError('episode error artifact'), tmp_path, episode, runtime=runtime)
    assert event == 'valid' and not old['retryable_infrastructure']


@pytest.mark.parametrize('case', ['wrong_task', 'wrong_seed', 'unknown_error', 'bad_json', 'full_reply',
    'not_timed_out', 'usage_complete', 'token_mismatch', 'missing_metadata', 'missing_compute',
    'missing_faults', 'xid', 'wrong_config', 'metric_nonfinite', 'wrong_count', 'safety', 'other_exception'])
def test_conflicting_or_missing_evidence_is_not_recoverable(tmp_path, timeout_case, case):
    episode, profile, runtime, path, record, stage, event = timeout_case
    if case == 'wrong_task': event['task_id'] += 1
    elif case == 'wrong_seed': event['episode_seed'] += 1
    elif case in {'unknown_error', 'bad_json'}: event['error'] = case
    elif case == 'full_reply': event['raw_response'] = 'complete'
    elif case == 'not_timed_out': event['transport']['process_timed_out'] = False
    elif case == 'usage_complete': event['codex_usage_complete_calls'] = 1
    elif case == 'token_mismatch': event['codex_input_tokens'] = 9
    elif case == 'missing_metadata': (tmp_path / 'eds_eval/episode_metadata.jsonl').unlink()
    elif case == 'missing_compute': path.unlink()
    elif case == 'missing_faults': (tmp_path / 'gpu-kernel-xid.json').unlink()
    elif case == 'xid':
        (tmp_path / 'gpu-kernel-xid.json').write_text(json.dumps({'schema':'qd-ed-kernel-xid-monitor-v1',
            'physical_gpu':2,'records':[{'xid':31}]}))
    elif case == 'wrong_config':
        conf = tmp_path / '.hydra/config.yaml'; data = yaml.safe_load(conf.read_text())
        data['seed'] += 1; conf.write_text(yaml.safe_dump(data))
    elif case == 'metric_nonfinite': (tmp_path / 'eds_eval/eds_metrics.jsonl').write_text('{"bad":NaN}\n')
    elif case == 'wrong_count':
        record['guided_chunks'] = 1; path.write_text(json.dumps(record) + '\n')
    elif case == 'safety':
        (tmp_path / 'eds_eval/safety_events.jsonl').write_text('{"count":1}\n')
    elif case == 'other_exception':
        (tmp_path / 'episode_1/error.txt').write_text('RuntimeError: nonfinite tensor\n')
    stage.write_text(json.dumps(event) + '\n')
    assert p.timeout_outcome(r, {'n1v_recovery':p.CONTRACT}, tmp_path, episode, profile, runtime) is None
    assert (tmp_path / 'n1v-recovery-rejected.json').exists()


def n1v_events(attempt='primary', task=8, **updates):
    episode = row(); episode.update(iteration='N1V', task_id=task)
    events = events_for(attempt, terminal='aborted', bucket='development', retryable=True,
                        identity=r.episode_identity(episode))
    for e in events:
        e.update(source_commit='source', runtime_manifest_sha256='runtime', init_row_sha256='init-row',
                 n1v_authorization_sha256=p.AUTH_SHA, retry_of=None)
        e.update(updates)
    events[-1]['failure_detail'] = 'n1v_stage_timeout'
    return events


def test_retry_is_one_per_cell_and_six_total_and_never_legal_failure():
    episode = row(); episode.update(iteration='N1V', retry_of='primary', budget_bucket='recovery')
    events = n1v_events(); r.check_retry(events, episode)
    second = n1v_events('recovery', retry_of='primary')
    with pytest.raises(r.GateError, match='one recovery'):
        r.check_retry(events + second, {**episode, 'retry_of':'recovery'})
    valid = copy.deepcopy(events); valid[-1].update(event='valid', outcome_valid=True, success=False)
    with pytest.raises(r.GateError): r.check_retry(valid, episode)
    wrong = copy.deepcopy(events); wrong[-1]['failure_detail'] = 'gpu_monitor_timeout'
    with pytest.raises(r.GateError): r.check_retry(wrong, episode)
    many = events[:]
    for task in range(6):
        many += n1v_events(f'p{task}', task=task)
        many += n1v_events(f'r{task}', task=task, retry_of=f'p{task}')
    with pytest.raises(r.GateError, match='six-recovery'): r.check_retry(many, episode)


def test_resume_preserves_valid_failure_and_rejects_identity_drift():
    episode = row(); episode.update(iteration='N1V', init_row_sha256='init-row')
    plan = {'source_commit':'source','runtime_manifest_sha256':'runtime'}
    events = n1v_events()
    assert s.cell_action([], episode, plan)[0] == 'primary'
    assert s.cell_action(events, episode, plan)[0] == 'recovery'
    events[-1].update(event='valid', outcome_valid=True, success=False)
    action, result = s.cell_action(events, episode, plan)
    assert action == 'completed' and result['success'] is False
    with pytest.raises(r.GateError, match='source/runtime/input'):
        s.cell_action(events, episode, {**plan, 'source_commit':'different'})
    with pytest.raises(r.GateError, match='unfinished'):
        s.cell_action(events[:-1], episode, plan)


def test_budget_requires_immutable_approval_and_preserves_protected_hundred(tmp_path, monkeypatch):
    current = state(); current['budget']['max_episode_attempts'] = 250
    with pytest.raises(r.GateError, match='authorization'): r.check_budget(current, [], row())
    auth = tmp_path / 'auth.json'
    auth.write_text(json.dumps({'approved':True,'caps':p.CAPS,'max_episode_attempts':250,'max_gpu_hours':48}))
    monkeypatch.setattr(p, 'AUTH_SHA', r.digest(auth))
    current['budget'].update(reserved=p.CAPS, gpu_hour_reservations={'validation':14.,'formal':10.},
        n1v_authorization={'path':str(auth),'sha256':r.digest(auth)})
    assert r.check_budget(current, [], row()) == 100
    events = []
    # Other baseline use cannot eat protected slots even if the requested
    # development bucket itself remains available.
    for i in range(150): events += events_for(str(i), bucket='baseline')
    snap = r.budget_snapshot(events)
    current['budget'].update(dispatched=snap['dispatched'],gpu_hours_consumed=snap['gpu_hours_consumed'])
    episode = row(); episode['budget_bucket'] = 'development'
    with pytest.raises(r.GateError, match='protected'): r.check_budget(current, events, episode)
    auth.write_text('{}')
    with pytest.raises(r.GateError, match='fingerprint'): r.check_budget(current, events, episode)


def test_shared_lease_is_reentrant_only_for_same_lock_and_restores_on_error(tmp_path):
    lock = tmp_path / 'run.lock'; other = tmp_path / 'state.lock'; original = r.locked
    with pytest.raises(RuntimeError):
        with s.held_runner_lease(lock):
            with r.locked(lock, nonblocking=True), r.locked(other): pass
            with pytest.raises(r.LockBusyError):
                with original(lock, nonblocking=True): pass
            raise RuntimeError()
    assert r.locked is original
    with original(lock, nonblocking=True): pass


def test_primary_order_is_task_interleaved_and_cannot_be_success_selected():
    rows = [{'task_id':t,'profile':profile,'iteration':'N1V'} for t in range(10)
            for profile in (('Q0','C0','N1') if t % 2 == 0 else ('C0','Q0','N1'))]
    plan = {'episodes':rows,'n1v_recovery':p.CONTRACT}; s.validate_cohort(plan)
    plan['episodes'] = rows[:-1]
    with pytest.raises(r.GateError, match='order changed'): s.validate_cohort(plan)


@pytest.mark.parametrize('iteration', ['N1V', 'N1W'])
@pytest.mark.parametrize('recovery_also_times_out', [False, True])
def test_supervisor_end_to_end_bounded_recovery_and_resume(tmp_path, monkeypatch, recovery_also_times_out, iteration):
    cfg = p.settings(iteration)
    root = tmp_path / 'worktree'; (root / 'data').mkdir(parents=True)
    artifact = tmp_path / 'artifact'; artifact.mkdir()
    rows = []
    for task in range(10):
        for profile in (('Q0','C0','N1') if task % 2 == 0 else ('C0','Q0','N1')):
            item = row(); item.update(task_id=task,profile=profile,iteration=iteration,
                episode_key=f'{iteration.lower()}_dev_t{task:02d}_{profile.lower()}',init_row_sha256='init-row',budget_bucket='development')
            rows.append(item)
    plan = {'episodes':rows,cfg['key'] + '_recovery':cfg['contract'],'artifact_root':str(artifact),
            'source_commit':'source','runtime_manifest_sha256':'runtime'}
    path = root / 'plan.json'; r.durable_json(path, plan)
    runtime = {'gpu_mapping':{'physical_gpu':2,'egl_device_index':1},'cuda_egl_probe':{'resource_id':'proven'}}
    monkeypatch.setattr(r, 'validate_plan', lambda *a,**k:(plan,{},runtime))
    monkeypatch.setattr(q, 'current_metadata', lambda *a,**k:runtime['gpu_mapping'])
    monkeypatch.setattr(q, 'find_probe', lambda *a,**k:runtime['cuda_egl_probe'])
    monkeypatch.setattr(q, 'same_mapping', lambda *a:True)
    monkeypatch.setattr(s, 'mechanism_audit', lambda terminal:{'attempt_id':terminal['attempt_id']})
    calls = []
    def queue(plan_path, keys, **kwargs):
        item = next(row for row in r.read_json(plan_path)['episodes'] if row['episode_key'] == keys[0])
        ledger = root / 'data/attempt-ledger.jsonl'
        events = r.read_events(ledger); r.check_retry(events, item)
        calls.append(item)
        timeout = item['task_id'] == 0 and item['profile'] == 'Q0' and (
            not item.get('retry_of') or recovery_also_times_out)
        attempt = f'a{len(calls)}'
        fresh = events_for(attempt, terminal='aborted' if timeout else 'valid',
            retryable=timeout,bucket=item['budget_bucket'],identity=r.episode_identity(item))
        for e in fresh:
            e.update(source_commit='source',runtime_manifest_sha256='runtime',init_row_sha256='init-row',
                retry_of=item.get('retry_of'))
            e.update({cfg['key'] + '_authorization_sha256':cfg['sha']})
        if timeout: fresh[-1]['failure_detail'] = cfg['key'] + '_stage_timeout'
        with ledger.open('a') as stream:
            for e in fresh: stream.write(json.dumps(e) + '\n')
        if timeout: raise r.GateError('attempt stopped after failure; no automatic retry: ' + attempt)
    monkeypatch.setattr(q, 'run_queue', queue)
    status = artifact / 'status.json'
    if recovery_also_times_out:
        with pytest.raises(r.GateError, match='one recovery'): s.run(path,status,root=root)
        assert len(calls) == 2 and r.read_json(status)['status'] == 'stopped_incomplete'
    else:
        result = s.run(path,status,root=root)
        assert result['status'] == 'development_completed' and len(result['completed_keys']) == 30
        assert len(calls) == 31 and calls[1]['retry_of'] == 'a1' and calls[1]['budget_bucket'] == 'recovery'
        assert all(not item.get('retry_of') for item in calls[2:])  # every valid failure is retained
        s.run(path,status,root=root)
        assert len(calls) == 31  # administrative resume cannot replay completed cells


def test_n1w_recoveries_are_separate_and_fifth_is_last():
    def newer(events):
        for event in events:
            event['identity']['iteration'] = 'N1W'
            event['n1w_authorization_sha256'] = p.N1W_AUTH_SHA
            event.pop('n1v_authorization_sha256',None)
            if event.get('failure_detail'): event['failure_detail'] = 'n1w_stage_timeout'
        return events
    original = newer(n1v_events())
    episode = row(); episode.update(iteration='N1W',budget_bucket='recovery',retry_of='primary')
    # All six hypothetical old N1V recoveries must not consume a new N1W slot.
    history = []
    for t in range(6): history += n1v_events(f'old{t}',task=t,retry_of=f'older{t}')
    used = []
    for t in range(4):
        used += newer(n1v_events(f'p{t}',task=t))
        used += newer(n1v_events(f'r{t}',task=t,retry_of=f'p{t}'))
    r.check_retry(history + used + original,episode)
    used += newer(n1v_events('p4',task=4)) + newer(n1v_events('r4',task=4,retry_of='p4'))
    with pytest.raises(r.GateError,match='five-recovery'): r.check_retry(history + used + original,episode)
    wrong = copy.deepcopy(original); wrong[-1]['n1w_authorization_sha256'] = p.AUTH_SHA
    with pytest.raises(r.GateError,match='prospectively'): r.check_retry(wrong,episode)


def test_n1w_timeout_uses_new_binding_and_cannot_reclassify_old_result(tmp_path, timeout_case):
    episode,profile,runtime,path,record,stage,event = timeout_case
    episode['iteration'] = 'N1W'
    frozen = runtime['frozen_stage_provider']; frozen['event_policy'] = 'completed_transport_fallback_v1'
    frozen['public_config_sha256'] = r.codex_public_config_sha256(frozen)
    config_path = tmp_path / '.hydra/config.yaml'; config = yaml.safe_load(config_path.read_text())
    config['perception']['gemini']['event_policy'] = frozen['event_policy']; config_path.write_text(yaml.safe_dump(config))
    for transport in (record['stage_transport'],event['transport']):
        transport.update(event_policy=frozen['event_policy'],public_config_sha256=frozen['public_config_sha256'])
    path.write_text(json.dumps(record)+'\n');stage.write_text(json.dumps(event)+'\n')
    result = p.timeout_outcome(r,{'n1w_recovery':p.N1W_CONTRACT},tmp_path,episode,profile,runtime)
    assert result['failure_detail'] == 'n1w_stage_timeout' and result['n1w_authorization_sha256'] == p.N1W_AUTH_SHA
    assert result['failed_call_token_usage'] is None
    episode['iteration'] = 'N1V'
    assert p.timeout_outcome(r,{'n1w_recovery':p.N1W_CONTRACT},tmp_path,episode,profile,runtime) is None
    with pytest.raises(r.GateError,match='acceptance condition'):
        p.validate_transport_binding(r,{'episodes':[episode]},runtime)


def test_n1x_luna_timeout_is_prospective_and_usage_stays_unknown(tmp_path, timeout_case):
    episode, profile, runtime, path, record, stage, event = timeout_case
    episode['iteration'] = 'N1X'
    frozen = runtime['frozen_stage_provider']
    frozen.update(model='gpt-6-luna', timeout_seconds=90,
                  event_policy='completed_transport_fallback_v1')
    frozen['public_config_sha256'] = r.codex_public_config_sha256(frozen)
    config_path = tmp_path / '.hydra/config.yaml'
    config = yaml.safe_load(config_path.read_text())
    for key, value in r.stage_overrides(runtime).items():
        current = config
        parts = key.lstrip('+').split('.')
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value
    config['main'] = {**config.get('main', {}), 'vlm_query_limit': 14,
                      'stage_min_query_gap_steps': 32}
    config_path.write_text(yaml.safe_dump(config))
    for transport in (record['stage_transport'], event['transport']):
        transport.update({k: frozen[k] for k in r.CODEX_CONFIG_KEYS})
        transport.update(event_policy=frozen['event_policy'],
                         public_config_sha256=frozen['public_config_sha256'])
    path.write_text(json.dumps(record) + '\n')
    stage.write_text(json.dumps(event) + '\n')
    assert r.codex_stage_condition(runtime) == p.settings('N1X')['condition']
    result = p.timeout_outcome(r, {'n1x_recovery': p.N1X_CONTRACT},
                               tmp_path, episode, profile, runtime)
    assert result['failure_detail'] == 'n1x_stage_timeout'
    assert result['n1x_authorization_sha256'] == p.N1X_AUTH_SHA
    assert result['failed_call_token_usage'] is None


def test_n1y_preturn_binding_is_new_and_cannot_be_used_for_n1x():
    runtime = {'frozen_stage_provider': {'backend': 'codex_cli', 'model': 'gpt-6-luna',
        'timeout_seconds': 90, 'output_format': 'json_schema_v1',
        'event_policy': 'completed_transport_fallback_preturn_v2'}}
    assert r.codex_stage_condition(runtime) == p.settings('N1Y')['condition']
    p.validate_transport_binding(r, {'episodes': [{'iteration': 'N1Y'}]}, runtime)
    with pytest.raises(r.GateError, match='acceptance condition'):
        p.validate_transport_binding(r, {'episodes': [{'iteration': 'N1X'}]}, runtime)


def test_n1z_multiline_binding_is_new_and_cannot_be_used_for_n1y():
    runtime = {'frozen_stage_provider': {'backend': 'codex_cli', 'model': 'gpt-6-luna',
        'timeout_seconds': 90, 'output_format': 'json_schema_v1',
        'event_policy': 'completed_transport_fallback_preturn_multiline_v3'}}
    assert r.codex_stage_condition(runtime) == p.settings('N1Z')['condition']
    p.validate_transport_binding(r, {'episodes': [{'iteration': 'N1Z'}]}, runtime)
    with pytest.raises(r.GateError, match='acceptance condition'):
        p.validate_transport_binding(r, {'episodes': [{'iteration': 'N1Y'}]}, runtime)


def test_n1aa_metadata_warning_binding_is_new_and_cannot_be_used_for_n1z():
    runtime = {'frozen_stage_provider': {'backend': 'codex_cli', 'model': 'gpt-6-luna',
        'timeout_seconds': 90, 'output_format': 'json_schema_v1',
        'event_policy': 'completed_known_startup_warnings_v4'}}
    assert r.codex_stage_condition(runtime) == p.settings('N1AA')['condition']
    p.validate_transport_binding(r, {'episodes': [{'iteration': 'N1AA'}]}, runtime)
    with pytest.raises(r.GateError, match='acceptance condition'):
        p.validate_transport_binding(r, {'episodes': [{'iteration': 'N1Z'}]}, runtime)


def test_n1w_new_acceptance_requires_correct_cohort_and_180_seconds():
    runtime = {'frozen_stage_provider':{'output_format':'json_schema_v1',
        'event_policy':'completed_transport_fallback_v1','timeout_seconds':180}}
    p.validate_transport_binding(r,{'episodes':[{'iteration':'N1W'}]},runtime)
    assert r.codex_stage_condition(runtime) == p.settings('N1W')['condition']
    with pytest.raises(r.GateError,match='approved N1W'):
        p.validate_transport_binding(r,{'episodes':[{'iteration':'N1U'}]},runtime)
    runtime['frozen_stage_provider']['timeout_seconds'] = 90
    with pytest.raises(r.GateError,match='180-second'): r.codex_stage_condition(runtime)


def test_n1w_budget_has_one_authority_and_does_not_reuse_n1v_caps(tmp_path,monkeypatch):
    current = state(); auth = tmp_path/'n1w-auth.json'
    auth.write_text(json.dumps({'approved':True,'caps':p.N1W_CAPS,'max_episode_attempts':250,'max_gpu_hours':48}))
    monkeypatch.setattr(p,'N1W_AUTH_SHA',r.digest(auth))
    current['budget'].update(max_episode_attempts=250,reserved=p.N1W_CAPS,
        gpu_hour_reservations={'validation':14.,'formal':10.},
        n1w_authorization={'path':str(auth),'sha256':r.digest(auth)})
    assert r.check_budget(current,[],row()) == 100
    current['budget']['reserved'] = p.CAPS
    with pytest.raises(r.GateError,match='allocations'): r.check_budget(current,[],row())
    current['budget']['reserved'] = p.N1W_CAPS
    current['budget']['n1v_authorization'] = {'path':str(auth),'sha256':p.AUTH_SHA}
    with pytest.raises(r.GateError,match='multiple active'): r.check_budget(current,[],row())
