"""CPU-only rejection/accounting tests; no model, simulator or GPU is touched."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml


SPEC = importlib.util.spec_from_file_location('qd_ed_final_runner', Path(__file__).resolve().parents[1]/'scripts/qd_ed_final_runner.py')
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def row(**updates):
    return dict(episode_key='dev_task8_q0', split='dev', iteration=0, profile='Q0',
                task_id=8, env_seed=991, policy_seed=993, init_index=0,
                budget_bucket='baseline', timeout_seconds=100, **updates)


def state():
    return {'gpu_pool':[7], 'max_concurrent_gpu_workers':1,
            'budget':{'max_episode_attempts':240,'max_gpu_hours':48.,
                      'reserved':dict(runner.BUCKETS),'dispatched':0,
                      'aborted':0,'valid':0,'running':0,'gpu_hours_consumed':0.}}


def events_for(attempt='a', *, terminal='valid', success=False, bucket='baseline', retryable=False, identity=None):
    base={'attempt_id':attempt,'identity':identity or runner.episode_identity(row()),'budget_bucket':bucket}
    return [{**base,'event':'reserved'},{**base,'event':'dispatched'},
            {**base,'event':terminal,'success':success,'outcome_valid':terminal=='valid',
             'gpu_process_wall_seconds':36.,'retryable_infrastructure':retryable}]


def synced_state(events):
    result=state(); snap=runner.budget_snapshot(events)
    for key in ('dispatched','aborted','valid','running','gpu_hours_consumed'):
        result['budget'][key]=snap[key]
    return result


def test_duplicate_json_and_yaml_keys_are_rejected(tmp_path):
    p=tmp_path/'bad.json'; p.write_text('{"budget":1,"budget":2}')
    with pytest.raises(runner.GateError,match='duplicate key'):
        runner.read_json(p)
    p=tmp_path/'bad.yaml'; p.write_text('budget:\n  valid: 1\n  valid: 2\n')
    with pytest.raises(runner.GateError,match='duplicate key'):
        runner.read_state(p)


@pytest.mark.parametrize('apps,memory,message', [('1234\n','12\n','external'), ('','1024\n','requires'), ('','N/A\n','invalid')])
def test_gpu7_admission_rejects_busy_or_unknown(apps,memory,message):
    calls=[]
    def fake(args,**kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0,stdout=apps if '--query-compute-apps=pid' in args else memory)
    with pytest.raises(runner.GateError,match=message):
        runner.gpu_admission(fake)
    assert all(cmd[cmd.index('-i')+1]=='7' for cmd in calls)


def test_gpu7_idle_threshold_is_strict():
    def fake(args,**kwargs):
        return SimpleNamespace(returncode=0,stdout='' if '--query-compute-apps=pid' in args else '1023\n')
    assert runner.gpu_admission(fake)['physical_gpu']==7


def test_single_task_command_binds_env_and_policy_seed_without_array_sorting(tmp_path):
    profiles=json.loads((Path(__file__).resolve().parents[1]/'configs/qd_ed_final/baseline_profiles.json').read_text())
    plan={'artifact_root':str(tmp_path/'artifacts'),'worktree':str(tmp_path)}
    runtime={'tasks':{'8':{'cache_dir':str(tmp_path/'artifacts/cache8')},'2':{'cache_dir':str(tmp_path/'artifacts/cache2')}},
             'main_overrides':['+main.require_task_cache_identity=true']}
    for task,env_seed,policy_seed in [(8,991,993),(2,2002,2003)]:
        episode=row(); episode.update(task_id=task,env_seed=env_seed,policy_seed=policy_seed)
        command,output=runner.build_command(plan,profiles,runtime,episode,f'task{task}')
        overrides=dict(item.split('=',1) for item in command[2:])
        assert len(overrides)==len(command[2:])
        assert overrides['backend.libero.task_ids_filter']==f'[{task}]'
        assert overrides['main.episode_seed_schedule']==f'[{env_seed}]'
        assert overrides['seed']==str(policy_seed)
        assert overrides['main.episode_num']=='1'
        assert overrides['main.episode_start_index']=='0'
        assert overrides['+main.require_task_cache_identity']=='true'
        assert overrides['backend.libero.camera_name'].startswith('"')
        assert output.parent==tmp_path/'artifacts/attempts'


def test_child_environment_pins_gpu_and_does_not_change_provider(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','unit-test-placeholder')
    monkeypatch.setenv('OPENAI_BASE_URL','https://unit.test/v1')
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES','3')
    env=runner.child_environment({'environment':{'HF_HUB_OFFLINE':'1'},'gpu_mapping':{'physical_gpu':7,'egl_device_index':4}})
    assert env['CUDA_VISIBLE_DEVICES']=='7' and env['MUJOCO_EGL_DEVICE_ID']=='4'
    assert env['OPENAI_API_KEY']=='unit-test-placeholder' and env['OPENAI_BASE_URL']=='https://unit.test/v1'


def test_dispatched_attempts_and_aborted_time_count_once():
    events=events_for('a',terminal='aborted',retryable=True)+events_for('b',bucket='recovery')
    snap=runner.budget_snapshot(events)
    assert snap['dispatched']==2 and snap['aborted']==1 and snap['valid']==1
    assert snap['gpu_hours_consumed']==pytest.approx(.02)
    assert snap['by_bucket']['baseline']==snap['by_bucket']['recovery']==1
    with pytest.raises(runner.GateError,match='terminal'):
        runner.budget_snapshot(events+[events[-1]])


def test_legal_task_failure_is_not_a_retryable_infrastructure_failure():
    episode=row(); episode.update(retry_of='a',budget_bucket='recovery')
    with pytest.raises(runner.GateError,match='legal completed'):
        runner.check_retry(events_for(success=False),episode)


def test_invalid_algorithm_outcome_is_completed_but_not_scientifically_valid():
    events=events_for(success=False)
    events[-1]['outcome_valid']=False
    snapshot=runner.budget_snapshot(events)
    assert snapshot['completed']==snapshot['invalid']==snapshot['dispatched']==1
    assert snapshot['valid']==snapshot['aborted']==0


def test_recovery_requires_matching_explicit_failed_attempt_and_new_identity():
    events=events_for(terminal='aborted',retryable=True)
    with pytest.raises(runner.GateError,match='explicit'):
        runner.check_retry(events,row())
    episode=row(); episode.update(retry_of='a',budget_bucket='recovery')
    runner.check_retry(events,episode)
    episode['env_seed']+=1
    with pytest.raises(runner.GateError,match='no matching'):
        runner.check_retry(events,episode)


def test_budget_preserves_100_validation_formal_attempts():
    events=[]
    for bucket,count in [('baseline',20),('development',100),('recovery',20)]:
        for index in range(count):
            events+=events_for(f'{bucket}{index}',bucket=bucket)
    current=synced_state(events)
    with pytest.raises(runner.GateError,match='reserve exhausted'):
        runner.check_budget(current,events,row())
    validation=row(); validation.update(split='validation',budget_bucket='validation')
    assert runner.check_budget(current,events,validation)==100
    current['budget']['reserved']['validation']=59
    with pytest.raises(runner.GateError,match='reserve was reduced'):
        runner.check_budget(current,events,validation)


def amended_state(events=()):
    current = synced_state(list(events))
    current['gpu_pool'] = [3]
    current['budget'].update(max_episode_attempts=393, max_gpu_hours=100.,
                             reserved=dict(runner.AMENDED_BUCKETS),
                             gpu_hour_reservations={'validation':32.,'formal':12.},
                             amendment=dict(runner.GPU3_AMENDMENT))
    return current


def amended_reservation_event():
    return [{'event':'gpu_hour_reservations_changed',
             'gpu_hour_reservations':{'validation':32.,'formal':12.},
             'rationale':'approved GPU3 N10 prospective amendment', 'time_unix':100.}]


def test_amended_gpu3_budget_requires_exact_authorization_and_audited_reserves():
    current = amended_state()
    episode = row()
    assert runner.check_budget(current,[],episode,
                               reservation_events=amended_reservation_event(),physical_gpu=3) == 100
    for mutation in (
        lambda s: s['budget'].pop('amendment'),
        lambda s: s['budget']['amendment'].update(proposal_sha256='0'*64),
        lambda s: s['budget'].update(max_episode_attempts=394),
        lambda s: s['budget']['reserved'].update(validation=60),
        lambda s: s.update(gpu_pool=[2]),
    ):
        changed=copy.deepcopy(current)
        mutation(changed)
        with pytest.raises(runner.GateError):
            runner.check_budget(changed,[],episode,
                                reservation_events=amended_reservation_event(),physical_gpu=3)
    with pytest.raises(runner.GateError,match='reallocation requires'):
        runner.check_budget(current,[],episode,physical_gpu=3)


def test_amended_budget_preserves_all_220_validation_formal_attempts_and_hours():
    events=[]
    for bucket,count in [('baseline',28),('development',124),('recovery',20)]:
        for index in range(count):
            events += events_for(f'{bucket}{index}',bucket=bucket)
    current=amended_state(events)
    episode=row()
    episode.update(budget_bucket='development')
    assert runner.check_budget(current,events,episode,
                               reservation_events=amended_reservation_event(),physical_gpu=3) == 100
    events += events_for('development124',bucket='development')
    current=amended_state(events)
    with pytest.raises(runner.GateError,match='reserve exhausted|protected'):
        runner.check_budget(current,events,episode,
                            reservation_events=amended_reservation_event(),physical_gpu=3)
    one=events_for('long',bucket='development')
    one[-1]['gpu_process_wall_seconds']=56*3600
    current=amended_state(one)
    with pytest.raises(runner.GateError,match='termination grace'):
        runner.check_budget(current,one,episode,
                            reservation_events=amended_reservation_event(),physical_gpu=3)


def test_budget_uses_remaining_gpu_time_and_refuses_unclosed_attempt():
    events=events_for(); events[-1]['gpu_process_wall_seconds']=24*3600-47
    validation=events_for('v',bucket='validation'); validation[-1]['gpu_process_wall_seconds']=14*3600
    formal=events_for('f',bucket='formal'); formal[-1]['gpu_process_wall_seconds']=10*3600
    events+=validation+formal
    assert runner.check_budget(synced_state(events),events,row()) in (6,7)
    events[2]['gpu_process_wall_seconds'] = 24 * 3600 - 37
    with pytest.raises(runner.GateError, match='termination grace'):
        runner.check_budget(synced_state(events), events, row())
    events=events_for()[:2]
    with pytest.raises(runner.GateError,match='unfinished'):
        runner.check_budget(synced_state(events),events,row())


def test_append_only_event_commit_updates_authoritative_state(tmp_path):
    (tmp_path/'data').mkdir(); p=tmp_path/'research-state.yaml'; p.write_text(yaml.safe_dump(state()))
    for event in events_for(terminal='aborted',retryable=True):
        runner.append_event(tmp_path,event)
    saved=runner.read_state(p)
    assert saved['budget']['dispatched']==1 and saved['budget']['aborted']==1
    assert saved['budget']['running']==0 and saved['budget']['gpu_hours_consumed']==pytest.approx(.01)
    assert len(runner.read_events(tmp_path/'data/attempt-ledger.jsonl'))==3


def test_profile_off_switches_and_algorithm_differences_are_explicit():
    profiles=json.loads((Path(__file__).resolve().parents[1]/'configs/qd_ed_final/baseline_profiles.json').read_text())['profiles']
    a,b=profiles['Q0']['resolved_eds_config'],profiles['C0']['resolved_eds_config']
    assert {key for key in a if a[key]!=b[key]}=={'qd_archive_mode','qd_parent_sampling'}
    for settings in (a,b):
        assert settings['qd_bounds_update_policy']=='fixed_initial'
        assert settings['qd_global_quality_anchor_count']==0
        assert settings['qd_secondary_lane_mode']==settings['qd_degenerate_fallback_policy']=='none'


def test_result_parser_does_not_turn_preparation_errors_into_legal_failures(tmp_path):
    (tmp_path/'episode_1').mkdir(); (tmp_path/'episode_1/error.txt').write_text('synthetic error')
    (tmp_path/'results.txt').write_text('Success count: 0/1\nSuccess rate: 0.00%\n')
    with pytest.raises(runner.GateError,match='error artifact'):
        runner.validate_result(tmp_path,row(),{})


def test_fingerprint_cache_invalidates_after_file_edit(tmp_path):
    p=tmp_path/'input'; p.write_text('first'); old=runner.digest(p)
    p.write_text('second')
    assert runner.digest(p)!=old


def test_provider_binding_rejects_endpoint_and_google_precedence_drift(tmp_path):
    (tmp_path/'configs').mkdir()
    (tmp_path/'configs/perception.yaml').write_text('gemini:\n  model: gemini-2.5-flash\n  api_key: null\n')
    runtime={'provider_ready':True,'frozen_stage_provider':{'base_url':'https://bound.test/v1','model':'gemini-2.5-flash','credential_env_name':'OPENAI_API_KEY'}}
    env={'OPENAI_BASE_URL':'https://bound.test/v1','OPENAI_API_KEY':'unit-test-placeholder'}
    runner.verify_provider(runtime,env,root=tmp_path)
    with pytest.raises(runner.GateError,match='endpoint'):
        runner.verify_provider(runtime,{**env,'OPENAI_BASE_URL':'https://different.test/v1'},root=tmp_path)
    with pytest.raises(runner.GateError,match='precedence'):
        runner.verify_provider(runtime,{**env,'GOOGLE_API_KEY':'different-placeholder'},root=tmp_path)


@pytest.fixture
def tiny_plan(tmp_path, monkeypatch):
    root=tmp_path/'worktree'; root.mkdir(); artifacts=tmp_path/'artifacts'; artifacts.mkdir()
    (root/'data').mkdir()
    for relative in runner.REQUIRED_CODE:
        p=root/relative; p.parent.mkdir(parents=True,exist_ok=True); p.write_text('fixture\n')
    profiles={'profiles':{'Q0':{}}}; profile_path=root/'configs/qd_ed_final/baseline_profiles.json'; profile_path.write_text(json.dumps(profiles))
    base=state(); base.update(run_name='fixture',artifacts=str(artifacts)); (root/'research-state.yaml').write_text(yaml.safe_dump(base))
    bddl=artifacts/'task.bddl'; bddl.write_text('task')
    init=artifacts/'task.init'; init.write_text('init')
    model=artifacts/'model'; model.write_text('weights')
    record=lambda p:{'path':str(p),'sha256':runner.digest(p),'size_bytes':p.stat().st_size}
    runtime={'schema':'qd-ed-runtime-setup-v1','worktree':str(root),'artifact_root':str(artifacts),
             'cuda_egl_verified':True,'provider_ready':True,'files':[record(bddl),record(init)],
             'gpu_mapping':{'physical_gpu':7,'egl_device_index':4,'uuid':'GPU-fixture'},
             'environment':{'LIBERO_CONFIG_PATH':str(artifacts/'libero_config')},
             'tasks':{'8':{'init_index':0,'cache_dir':str(artifacts/'cache'),'bddl_path':str(bddl),'init_path':str(init)}}}
    runtime_path=artifacts/'runtime.json'; runtime_path.write_text(json.dumps(runtime))
    inventory={'schema':'qd-ed-runtime-inventory-v1','checkpoint':[record(model)],'hf_encoders':[{'files':[record(model)]}],
               'dinov2':{'weights':record(model)},'libero_tasks':[{'task_id':8,'used_init_index':0,'used_init_row_sha256':'init-row'}]}
    inventory_path=root/'data/inventory.json'; inventory_path.write_text(json.dumps(inventory))
    episode=row(); episode.update(seed_block='dev',init_row_sha256='init-row',init_file_sha256=runner.digest(init),bddl_sha256=runner.digest(bddl))
    seeds={'schema':'qd-ed-frozen-seed-plan-v1','run_name':'fixture','blocks':{'dev':[episode]}}
    seed_path=root/'data/seeds.json'; seed_path.write_text(json.dumps(seeds))
    plan={'schema':runner.SCHEMA,'frozen':True,'run_name':'fixture','worktree':str(root),'artifact_root':str(artifacts),
          'source_commit':'fixture-commit','profiles_path':str(profile_path),'profiles_sha256':runner.digest(profile_path),
          'runtime_manifest_path':str(runtime_path),'runtime_manifest_sha256':runner.digest(runtime_path),
          'runtime_inventory_path':str(inventory_path),'runtime_inventory_sha256':runner.digest(inventory_path),
          'seed_plan_path':str(seed_path),'seed_plan_sha256':runner.digest(seed_path),
          'input_contract_label':'input_repaired','egl_mapping_verified':True,'episodes':[episode],
          'code_files':[{'path':relative,'sha256':runner.digest(root/relative)} for relative in sorted(runner.REQUIRED_CODE)]}
    path=root/'data/plan.json'; path.write_text(json.dumps(plan))
    monkeypatch.setattr(runner.subprocess,'check_output',lambda *a,**kw:'fixture-commit\n')
    return root,path,plan,runtime_path,runtime


def test_frozen_plan_binds_code_inputs_model_hashes_and_paired_seeds(tiny_plan):
    root,path,plan,runtime_path,runtime=tiny_plan
    assert runner.validate_plan(path,root=root)[0]['frozen'] is True
    plan['episodes'][0]['policy_seed']+=1; path.write_text(json.dumps(plan))
    with pytest.raises(runner.GateError,match='policy_seed'):
        runner.validate_plan(path,root=root)


def test_unready_provider_blocks_dispatch_but_cpu_review_remains_possible(tiny_plan):
    root,path,plan,runtime_path,runtime=tiny_plan
    runtime['provider_ready']=False; runtime_path.write_text(json.dumps(runtime))
    plan['runtime_manifest_sha256']=runner.digest(runtime_path); path.write_text(json.dumps(plan))
    with pytest.raises(runner.GateError,match='provider'):
        runner.validate_plan(path,root=root)
    runner.validate_plan(path,root=root,require_frozen=False)


def test_model_mutation_fails_before_any_dispatch(tiny_plan):
    root,path,plan,runtime_path,runtime=tiny_plan
    model=Path(plan['artifact_root'])/'model'; model.write_text('changed weights')
    with pytest.raises(runner.GateError,match='frozen file changed'):
        runner.validate_plan(path,root=root)


def test_nonfinite_jsonl_cannot_poison_budget_or_metrics(tmp_path):
    path=tmp_path/'events'; path.write_text('{"gpu_process_wall_seconds":NaN}\n')
    with pytest.raises(runner.GateError,match='nonfinite'):
        runner.read_events(path)


def test_external_gpu_process_is_detected_without_signalling_it(monkeypatch):
    process=SimpleNamespace(pid=500)
    monkeypatch.setattr(runner.os,'getpgid',lambda pid:500 if pid==501 else 600)
    def probe(args,**kw):
        return SimpleNamespace(returncode=0,stdout='500\n501\n')
    runner.check_exclusive_gpu(process,probe)
    def shared(args,**kw):
        return SimpleNamespace(returncode=0,stdout='500\n700\n')
    with pytest.raises(runner.GateError,match='external GPU7'):
        runner.check_exclusive_gpu(process,shared)


def test_terminal_journal_can_repair_state_without_double_counting(tmp_path):
    (tmp_path/'data').mkdir(); path=tmp_path/'research-state.yaml'; path.write_text(yaml.safe_dump(state()))
    events=events_for('a',terminal='aborted',retryable=True)
    runner.sync_state_from_journal(tmp_path,events)
    runner.sync_state_from_journal(tmp_path,events)
    saved=runner.read_state(path)
    assert saved['budget']['dispatched']==1 and saved['budget']['gpu_hours_consumed']==pytest.approx(.01)


def test_healthcheck_time_counts_without_episode_and_open_reservation_blocks(tmp_path):
    (tmp_path/'data').mkdir(); path=tmp_path/'research-state.yaml'; path.write_text(yaml.safe_dump(state()))
    events=[{'resource_id':'probe','event':'reserved','time_unix':0.},
            {'resource_id':'probe','event':'dispatched','time_unix':1.},
            {'resource_id':'probe','event':'completed','time_unix':61.,'gpu_process_wall_seconds':60.}]
    with pytest.raises(runner.GateError,match='unfinished GPU healthcheck'):
        runner.check_budget(state(),[],row(),events[:1])
    for event in events:
        runner.append_healthcheck_event(tmp_path,event)
    saved=runner.read_state(path)
    assert saved['budget']['dispatched']==0
    assert saved['budget']['gpu_hours_consumed']==pytest.approx(1/60)
    assert runner.check_budget(saved,[],row(),events)==100


def test_wall_timeout_and_missing_results_are_task_failures_not_retryable(tmp_path):
    for exc in [runner.subprocess.TimeoutExpired('owned episode',100),FileNotFoundError('results missing'),runner.GateError('nonfinite metric')]:
        event,outcome=runner.failed_outcome(exc,tmp_path,row())
        assert event=='valid' and outcome['success'] is False
        assert outcome['task_failure'] is True and outcome['retryable_infrastructure'] is False
    event,outcome=runner.failed_outcome(OSError('cannot launch child'),tmp_path,row(),launch_failed=True)
    assert event=='aborted' and outcome['retryable_infrastructure'] is True


def test_exclusivity_monitor_waits_fifteen_seconds_once_and_timeout_stays_infrastructure(tmp_path):
    calls = []
    def timed_out(args, **kwargs):
        calls.append((args, kwargs))
        raise runner.subprocess.TimeoutExpired(args, kwargs['timeout'],
                                               output=b'private subprocess output', stderr=b'private stderr')
    with pytest.raises(runner.subprocess.TimeoutExpired) as caught:
        runner.check_exclusive_gpu(SimpleNamespace(pid=500), timed_out, physical_gpu=5)
    assert len(calls) == 1
    assert calls[0][1]['timeout'] == 15
    assert calls[0][0][calls[0][0].index('-i') + 1] == '5'
    event, outcome = runner.failed_outcome(caught.value, tmp_path, row())
    assert event == 'aborted'
    assert outcome['retryable_infrastructure'] is True
    assert outcome['task_failure'] is False and outcome['outcome_valid'] is False
    assert outcome['failure_detail'] == 'gpu_monitor_timeout'
    assert outcome['gpu_monitor_timeout'] == {'physical_gpu': 5, 'timeout_seconds': 15}
    assert outcome['reason'] == 'GPU5 nvidia-smi monitor query timed out after 15 seconds'
    assert 'private' not in json.dumps(outcome)


@pytest.mark.parametrize('gpu,timeout,expected', [
    ('5', 5, {'physical_gpu': 5, 'timeout_seconds': 5}),
    ('private-index', 'private-timeout', {'physical_gpu': None, 'timeout_seconds': None}),
    ('5', float('nan'), {'physical_gpu': 5, 'timeout_seconds': None}),
])
def test_monitor_timeout_details_never_serialize_arbitrary_command_or_output(tmp_path, gpu, timeout, expected):
    error = runner.subprocess.TimeoutExpired(['nvidia-smi', '-i', gpu, 'private-argument'], timeout,
                                             output='private-stdout', stderr='private-stderr')
    event, outcome = runner.failed_outcome(error, tmp_path, row())
    assert event == 'aborted' and outcome['retryable_infrastructure'] is True
    assert outcome['gpu_monitor_timeout'] == expected
    assert 'private' not in json.dumps(outcome, allow_nan=False)


def test_actual_episode_deadline_remains_nonretryable_scientific_failure(tmp_path):
    episode = row()
    episode['timeout_seconds'] = 1800
    error = runner.subprocess.TimeoutExpired('owned episode', 1800, output='private output')
    event, outcome = runner.failed_outcome(error, tmp_path, episode)
    assert event == 'valid' and outcome['failure_class'] == 'task_failure'
    assert outcome['reason'] == 'TimeoutExpired'
    assert outcome['task_failure'] is True and outcome['retryable_infrastructure'] is False
    assert 'gpu_monitor_timeout' not in outcome
    assert runner.check_budget(state(), [], episode) == 1800
    assert runner.TERMINATION_GRACE_SECONDS >= runner.GPU_MONITOR_QUERY_TIMEOUT_SECONDS + 20


def no_guidance_case(tmp_path,monkeypatch):
    episode=row(); (tmp_path/'.hydra').mkdir(); (tmp_path/'eds_eval').mkdir()
    (tmp_path/'episode_1').mkdir(); (tmp_path/'episode_1/episode_1_fail_fixture.mp4').write_bytes(b'unit-test-decode-boundary')
    monkeypatch.setattr(runner,'validate_video',lambda path:None)
    resolved={'backend':{'backend':'libero','libero':{'task_ids_filter':[8]}},'seed':993,
              'main':{'episode_num':1,'episode_seed_schedule':[991],'require_task_cache_identity':True}}
    (tmp_path/'.hydra/config.yaml').write_text(yaml.safe_dump(resolved))
    (tmp_path/'results.txt').write_text('Success count: 0/1\nSuccess rate: 0.00%\n')
    (tmp_path/'eds_eval/episode_metadata.jsonl').write_text(json.dumps({'episode_id':0,'episode_seed':991,'task_id':8})+'\n')
    compute={key:0 for key in runner.COMPUTE_FIELDS}
    compute.update(schema='qd-ed-episode-compute-v1',episode_id=0,episode_seed=991,task_id=8,
                   outcome='completed',policy_counters_available=True,provider_counters_available=True,
                   perception_counters_available=True,model_forward_batch_sizes=[])
    (tmp_path/'eds_eval/episode_compute.jsonl').write_text(json.dumps(compute)+'\n')
    profile={'static_override_values':{'backend':'libero'},'resolved_eds_config':{'population_size':16,'cem_iters':10,'qd_archive_mode':'grid_archive'}}
    return episode,profile


def test_legal_no_guidance_failure_stays_in_task_denominator(tmp_path,monkeypatch):
    episode,profile=no_guidance_case(tmp_path,monkeypatch)
    outcome=runner.validate_result(tmp_path,episode,profile)
    assert outcome['success'] is False and outcome['task_failure'] is True
    assert outcome['outcome_valid'] is True and outcome['qd_activity_observed'] is False
    assert outcome['required_cost_telemetry_complete'] is True


def test_unobserved_perception_costs_cannot_be_reported_as_complete(tmp_path,monkeypatch):
    episode,profile=no_guidance_case(tmp_path,monkeypatch)
    path=tmp_path/'eds_eval/episode_compute.jsonl'
    record=json.loads(path.read_text());record['perception_counters_available']=False
    path.write_text(json.dumps(record)+'\n')
    with pytest.raises(runner.GateError,match='cost counters unavailable'):
        runner.validate_result(tmp_path,episode,profile)


def test_missing_safety_field_and_missing_video_fail_closed(tmp_path,monkeypatch):
    episode,profile=no_guidance_case(tmp_path,monkeypatch)
    metric={'episode':0,'task_id':8,'global_step':0,'score_call_count':11,'search_evaluation_count':176,'qd_archive_enabled':True}
    (tmp_path/'eds_eval/eds_metrics.jsonl').write_text(json.dumps(metric)+'\n')
    with pytest.raises(runner.GateError,match='missing field: nonfinite_count'):
        runner.validate_result(tmp_path,episode,profile)
    (tmp_path/'episode_1/episode_1_fail_fixture.mp4').unlink()
    with pytest.raises(runner.GateError,match='video missing'):
        runner.validate_result(tmp_path,episode,profile)


def test_n1_candidate_only_changes_frozen_descriptor(tiny_plan):
    root,path,plan,runtime_path,runtime=tiny_plan
    baseline={'restored_profile':{'qd_descriptor':'xy','population_size':16},
              'resolved_eds_config':{'qd_descriptor':'xy'},
              'static_override_values':{'main.eds_config.qd_descriptor':'xy'}}
    profile_path=Path(plan['profiles_path']); profile_path.write_text(json.dumps({'profiles':{'Q0':baseline}}))
    plan['profiles_sha256']=runner.digest(profile_path)
    for record in plan['code_files']:
        if record['path']=='configs/qd_ed_final/baseline_profiles.json': record['sha256']=runner.digest(profile_path)
    candidate_path=root/'configs/qd_ed_final/candidate_n1.json'
    candidate={'baseline_reference':'Q0','label':'N1','profile':{'qd_descriptor':'xz','population_size':16}}
    candidate_path.write_text(json.dumps(candidate))
    relative=str(candidate_path.relative_to(root))
    plan['candidate_profiles']={'N1':{'path':str(candidate_path),'sha256':runner.digest(candidate_path)}}
    plan['scientific_config_files']=[relative]
    plan['code_files'].append({'path':relative,'sha256':runner.digest(candidate_path)})
    plan['episodes'][0]['profile']='N1'; path.write_text(json.dumps(plan))
    _,manifest,_=runner.validate_plan(path,root=root)
    assert manifest['profiles']['N1']['resolved_eds_config']['qd_descriptor']=='xz'
    assert manifest['profiles']['Q0']['resolved_eds_config']['qd_descriptor']=='xy'
    candidate['profile']['population_size']=32; candidate_path.write_text(json.dumps(candidate))
    plan['candidate_profiles']['N1']['sha256']=runner.digest(candidate_path)
    plan['code_files'][-1]['sha256']=runner.digest(candidate_path); path.write_text(json.dumps(plan))
    with pytest.raises(runner.GateError,match='only qd_descriptor'):
        runner.validate_plan(path,root=root)


def test_owned_alias_fingerprints_preserve_lexical_identity_and_reject_escape(tmp_path):
    base=tmp_path/'owned'; base.mkdir(); target=base/'target'; target.write_text('content')
    alias=base/'alias'; alias.symlink_to('target')
    records=[{'path':str(target),'sha256':runner.digest(target)},
             {'path':str(alias),'sha256':runner.digest(target),'resolved_path':str(target),'link_target':'target'}]
    runner.verify_files(records,allowed_roots=(base,))
    outside=tmp_path/'outside'; outside.write_text('content')
    alias.unlink(); alias.symlink_to(outside)
    with pytest.raises(runner.GateError,match='escapes owned'):
        runner.verify_files(records,allowed_roots=(base,))


def test_all_failed_stage_queries_invalidate_without_removing_denominator(tmp_path,monkeypatch):
    episode,profile=no_guidance_case(tmp_path,monkeypatch)
    event={'episode_id':0,'task_id':8,'episode_seed':991,'query_status':'error','query_ok':False,'api_request_attempts':1}
    (tmp_path/'eds_eval/stage_events.jsonl').write_text(json.dumps(event)+'\n')
    with pytest.raises(runner.GateError,match='all actual Stage queries failed') as caught:
        runner.validate_result(tmp_path,episode,profile)
    terminal,outcome=runner.failed_outcome(caught.value,tmp_path,episode)
    assert terminal=='valid' and outcome['task_failure'] is True and outcome['outcome_valid'] is False
    assert outcome['stage_successful_queries']==0 and outcome['stage_failed_queries']==1
    assert outcome['retryable_infrastructure'] is False
    event.update(query_status='ok',query_ok=True)
    with (tmp_path/'eds_eval/stage_events.jsonl').open('a') as stream: stream.write(json.dumps(event)+'\n')
    summary=runner.stage_query_summary(tmp_path,episode)
    assert summary['stage_successful_queries']==summary['stage_failed_queries']==1
    assert summary['stage_all_queries_failed'] is False


def test_gpu_hours_protect_validation_formal_and_reallocation_requires_audit():
    events=events_for('dev',bucket='development'); events[-1]['gpu_process_wall_seconds']=23.9*3600
    current=synced_state(events); episode=row(); episode['timeout_seconds']=1000
    assert 319<=runner.check_budget(current,events,episode)<=320
    current['budget']['gpu_hour_reservations']={'validation':12.,'formal':8.}
    with pytest.raises(runner.GateError,match='reallocation requires'):
        runner.check_budget(current,events,episode)
    policy=[{'event':'gpu_hour_reservations_changed','gpu_hour_reservations':{'validation':12.,'formal':8.},
             'rationale':'prospective paired run cost evidence','time_unix':100.}]
    assert runner.check_budget(current,events,episode,reservation_events=policy)==1000


def codex_runtime(tmp_path):
    cli = tmp_path / 'codex'; cli.write_text('unit-test executable'); cli.chmod(0o700)
    home = tmp_path / 'account'
    skill = home / '.codex/skills/fixture'; skill.mkdir(parents=True)
    (skill / 'SKILL.md').write_text('metadata only; never read by runner')
    frozen = dict(backend='codex_cli', model='gpt-6-astra', auth_mode='chatgpt',
                  reasoning_effort='low', timeout_seconds=90, cli_path=str(cli),
                  cli_version='0.155.1', cli_sha256=runner.digest(cli),
                  disabled_skill_paths=[str(skill)])
    frozen['public_config_sha256'] = runner.codex_public_config_sha256(frozen)
    return dict(provider_ready=True, frozen_stage_provider=frozen,
                environment={}, gpu_mapping={'physical_gpu': 7, 'egl_device_index': 4})


def codex_compute_case(tmp_path, monkeypatch, *, calls=0):
    episode, profile = no_guidance_case(tmp_path, monkeypatch)
    runtime = codex_runtime(tmp_path)
    config_path = tmp_path / '.hydra/config.yaml'
    resolved = yaml.safe_load(config_path.read_text())
    frozen = runtime['frozen_stage_provider']
    resolved['perception'] = {'gemini': {key: frozen[key] for key in runner.CODEX_CONFIG_KEYS}}
    config_path.write_text(yaml.safe_dump(resolved))
    path = tmp_path / 'eds_eval/episode_compute.jsonl'
    record = json.loads(path.read_text())
    record.update(schema='qd-ed-episode-compute-v2', provider_logical_counters_available=True,
                  provider_http_counters_available=False, provider_token_usage_complete=True,
                  stage_transport={**{key: frozen[key] for key in runner.CODEX_CONFIG_KEYS},
                    'auth_mode': 'chatgpt', 'public_config_sha256': frozen['public_config_sha256'],
                    'application_max_attempts': 1, 'internal_http_retry_observation_available': False,
                    'internal_retry_policy': 'cli_managed_unknown'})
    for key in runner.CODEX_UNKNOWN_HTTP_FIELDS:
        record[key] = None
    for prefix in ('stage_codex_', 'provider_'):
        record.update({prefix + suffix: 0 for suffix in runner.CODEX_COUNT_SUFFIXES})
        record.update({prefix + key: calls for key in ('logical_call_attempts', 'completed_turns', 'usage_complete_calls')})
        record.update({prefix + 'input_tokens': calls * 100, prefix + 'cached_input_tokens': calls * 20,
                       prefix + 'output_tokens': calls * 10, prefix + 'reasoning_output_tokens': None,
                       prefix + 'call_latency_s': calls * 1.25})
    path.write_text(json.dumps(record) + '\n')
    return episode, profile, runtime, path, record


def test_codex_child_removes_alternate_api_bindings_only_in_child(tmp_path, monkeypatch):
    runtime = codex_runtime(tmp_path)
    for name in runner.codex_removed_environment():
        monkeypatch.setenv(name, 'unit-test-placeholder')
    monkeypatch.setenv('HOME', str(tmp_path / 'account'))
    monkeypatch.setenv('CODEX_HOME', str(tmp_path / 'account/.codex'))
    env = runner.child_environment(runtime)
    assert not set(env) & runner.codex_removed_environment()
    assert env['HOME'] == str(tmp_path / 'account')
    assert env['CODEX_HOME'] == str(tmp_path / 'account/.codex')
    assert env['CUDA_VISIBLE_DEVICES'] == '7'
    assert runner.os.environ['OPENAI_API_KEY'] == 'unit-test-placeholder'


def test_codex_provider_requires_managed_login_frozen_binary_and_installed_skill_set(tmp_path):
    runtime = codex_runtime(tmp_path)
    (tmp_path / 'configs').mkdir()
    (tmp_path / 'configs/perception.yaml').write_text('gemini:\n  model: gemini-2.5-flash\n  api_key: null\n')
    env = {'HOME': str(tmp_path / 'account')}
    calls = []
    def fake(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout='codex-cli 0.155.1\n' if '--version' in argv else '',
                               stderr='' if '--version' in argv else 'Logged in using ChatGPT\n')
    runner.verify_provider(runtime, env, root=tmp_path, run=fake)
    assert [args[1:] for args in calls] == [['--version'], ['login', 'status']]
    with pytest.raises(runner.GateError, match='alternate authentication'):
        runner.verify_provider(runtime, {**env, 'CODEX_API_KEY': 'placeholder'}, root=tmp_path, run=fake)
    def api_login(argv, **kwargs):
        return SimpleNamespace(returncode=0, stdout='codex-cli 0.155.1' if '--version' in argv else 'Logged in using an API key', stderr='')
    with pytest.raises(runner.GateError, match='managed ChatGPT'):
        runner.verify_provider(runtime, env, root=tmp_path, run=api_login)
    new_skill = tmp_path / 'account/.codex/skills/added'; new_skill.mkdir(); (new_skill / 'SKILL.md').touch()
    with pytest.raises(runner.GateError, match='skill metadata'):
        runner.verify_provider(runtime, env, root=tmp_path, run=fake)


def test_codex_runtime_overrides_are_common_and_public_policy_changes_fail_closed(tmp_path):
    runtime = codex_runtime(tmp_path)
    profiles = {'profiles': {'Q0': {'static_override_values': {'backend': 'libero'}, 'historical_label': 'Q0'}}}
    runtime.update(tasks={'8': {'cache_dir': str(tmp_path / 'artifacts/cache8')}},
                   main_overrides=['+main.require_task_cache_identity=true'])
    plan = {'artifact_root': str(tmp_path / 'artifacts'), 'worktree': str(tmp_path)}
    command, _ = runner.build_command(plan, profiles, runtime, row(), 'fixture')
    expected = runner.stage_overrides(runtime)
    assert all(f'{key}={runner.hydra(value)}' in command for key, value in expected.items())
    profiles['profiles']['Q0']['static_override_values']['perception.gemini.model'] = 'different'
    with pytest.raises(runner.GateError, match='static/runtime'):
        runner.build_command(plan, profiles, runtime, row(), 'fixture')
    runtime['frozen_stage_provider']['public_config_sha256'] = '0' * 64
    with pytest.raises(runner.GateError, match='invocation fingerprint'):
        runner.stage_overrides(runtime)


def test_codex_v2_accepts_explicit_unknown_http_and_optional_reasoning(tmp_path, monkeypatch):
    episode, profile, runtime, path, record = codex_compute_case(tmp_path, monkeypatch)
    outcome = runner.validate_result(tmp_path, episode, profile, runtime)
    assert outcome['required_cost_telemetry_complete'] is True
    assert outcome['provider_request_attempts'] is None
    assert outcome['provider_reasoning_output_tokens'] is None
    assert outcome['provider_http_observation'] == 'not_observable_through_codex_cli'
    with pytest.raises(runner.GateError, match='schema mismatch'):
        runner.episode_compute(tmp_path, episode)
    record['provider_request_attempts'] = 0
    path.write_text(json.dumps(record) + '\n')
    with pytest.raises(runner.GateError, match='must be unknown'):
        runner.episode_compute(tmp_path, episode, runtime)


def test_codex_missing_usage_preserves_observed_subtotals_but_invalidates_costs(tmp_path, monkeypatch):
    episode, profile, runtime, path, record = codex_compute_case(tmp_path, monkeypatch, calls=2)
    record.update(provider_usage_complete_calls=1, stage_codex_usage_complete_calls=1,
                  provider_token_usage_complete=False)
    path.write_text(json.dumps(record) + '\n')
    with pytest.raises(runner.GateError, match='token usage incomplete') as caught:
        runner.validate_result(tmp_path, episode, profile, runtime)
    terminal, outcome = runner.failed_outcome(caught.value, tmp_path, episode, runtime=runtime)
    assert terminal == 'valid' and outcome['success'] is False and outcome['outcome_valid'] is False
    assert outcome['required_cost_telemetry_complete'] is False
    assert outcome['provider_input_tokens'] == 200
    assert outcome['provider_request_attempts'] is None


def test_codex_transport_or_counter_drift_cannot_pass_adjudication(tmp_path, monkeypatch):
    episode, profile, runtime, path, record = codex_compute_case(tmp_path, monkeypatch, calls=1)
    bad = copy.deepcopy(record); bad['stage_transport']['public_config_sha256'] = '0' * 64
    path.write_text(json.dumps(bad) + '\n')
    with pytest.raises(runner.GateError, match='public invocation policy'):
        runner.episode_compute(tmp_path, episode, runtime)
    bad = copy.deepcopy(record); bad['provider_input_tokens'] += 1
    path.write_text(json.dumps(bad) + '\n')
    with pytest.raises(runner.GateError, match='aggregate/Stage'):
        runner.episode_compute(tmp_path, episode, runtime)
    bad = copy.deepcopy(record); bad['provider_failed_calls'] = bad['stage_codex_failed_calls'] = 1
    path.write_text(json.dumps(bad) + '\n')
    with pytest.raises(runner.GateError, match='call failure'):
        runner.validate_result(tmp_path, episode, profile, runtime)


def test_codex_skipped_stage_event_allows_null_http_field(tmp_path):
    (tmp_path / 'eds_eval').mkdir()
    event = dict(episode_id=0, task_id=8, episode_seed=991, query_status='skipped',
                 api_request_attempts=None, query_ok=None)
    (tmp_path / 'eds_eval/stage_events.jsonl').write_text(json.dumps(event) + '\n')
    summary = runner.stage_query_summary(tmp_path, row())
    assert summary['stage_skipped_queries'] == 1 and not summary['stage_all_queries_failed']


def test_codex_actual_events_reconcile_tokens_latency_and_invocation_policy(tmp_path, monkeypatch):
    episode, profile, runtime, path, record = codex_compute_case(tmp_path, monkeypatch, calls=2)
    events = []
    for _ in range(2):
        event = dict(episode_id=0, task_id=8, episode_seed=991, query_status='ok', query_ok=True,
                     api_request_attempts=None, api_sdk_retry_attempts=None,
                     api_request_counter_available=False, transport=record['stage_transport'])
        event.update({'codex_' + suffix: record['provider_' + suffix] // 2
                      for suffix in runner.CODEX_COUNT_SUFFIXES})
        event['codex_call_latency_s'] = 1.25
        events.append(event)
    stage_path = tmp_path / 'eds_eval/stage_events.jsonl'
    stage_path.write_text(''.join(json.dumps(event) + '\n' for event in events))
    result = runner.validate_result(tmp_path, episode, profile, runtime)
    assert result['provider_input_tokens'] == 200 and result['stage_successful_queries'] == 2
    events[0]['codex_input_tokens'] += 1
    stage_path.write_text(''.join(json.dumps(event) + '\n' for event in events))
    with pytest.raises(runner.GateError, match='event/episode call or token'):
        runner.validate_result(tmp_path, episode, profile, runtime)


def test_gpu5_admission_binds_index_and_uuid_without_querying_gpu7():
    calls = []
    def probe(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout=(
            'GPU-five\n' if '--query-gpu=uuid' in args else
            '' if '--query-compute-apps=pid' in args else '0\n'))
    assert runner.gpu_admission(probe, physical_gpu=5, expected_uuid='GPU-five')['physical_gpu'] == 5
    assert len(calls) == 3 and all(args[args.index('-i') + 1] == '5' for args in calls)
    with pytest.raises(runner.GateError, match='GPU5 UUID'):
        runner.gpu_admission(probe, physical_gpu=5, expected_uuid='GPU-seven')


def test_gpu5_exclusivity_and_wait_propagate_selected_device(monkeypatch):
    process = SimpleNamespace(pid=500)
    monkeypatch.setattr(runner.os, 'getpgid', lambda pid: 500 if pid == 501 else 600)
    def shared(args, **kwargs):
        assert args[args.index('-i') + 1] == '5'
        return SimpleNamespace(returncode=0, stdout='500\n700\n')
    with pytest.raises(runner.GateError, match='external GPU5'):
        runner.check_exclusive_gpu(process, shared, physical_gpu=5)
    waits = iter([runner.subprocess.TimeoutExpired('owned episode', 5), 0])
    def wait(**kwargs):
        result = next(waits)
        if isinstance(result, Exception):
            raise result
        return result
    process.wait = wait
    calls = []
    monkeypatch.setattr(runner, 'check_exclusive_gpu', lambda child, **kwargs: calls.append(kwargs))
    assert runner.wait_exclusively(process, 30, physical_gpu=5) == 0
    assert calls == [{'physical_gpu': 5}]


@pytest.mark.parametrize('pool', [[7], [5, 7], [], [True], ['5'], [-1]])
def test_runtime_gpu_refuses_state_mismatch_or_invalid_authorization(pool):
    current = state(); current['gpu_pool'] = pool
    with pytest.raises(runner.GateError, match='GPU policy'):
        runner.runtime_gpu({'gpu_mapping': {'physical_gpu': 5, 'egl_device_index': 2}}, current)


def test_gpu5_runtime_changes_only_hardware_binding_preserving_historical_profile(monkeypatch, tmp_path):
    current = state(); current['gpu_pool'] = [5]
    runtime = {'environment': {}, 'gpu_mapping': {'physical_gpu': 5, 'egl_device_index': 2}}
    assert runner.runtime_gpu(runtime, current) == 5
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', '7')
    env = runner.child_environment(runtime)
    assert env['CUDA_VISIBLE_DEVICES'] == '5' and env['MUJOCO_EGL_DEVICE_ID'] == '2'
    assert runner.os.environ['CUDA_VISIBLE_DEVICES'] == '7'
    profiles = runner.read_json(runner.ROOT / 'configs/qd_ed_final/baseline_profiles.json')
    original = copy.deepcopy(profiles)
    runtime.update(tasks={'8': {'cache_dir': str(tmp_path / 'artifacts/cache')}},
                   main_overrides=['+main.require_task_cache_identity=true'])
    command, _ = runner.build_command({'artifact_root': str(tmp_path / 'artifacts'),
                                      'worktree': str(tmp_path)}, profiles, runtime, row(), 'gpu-five')
    assert not any('render_gpu_index' in arg for arg in command)
    assert profiles == original
    assert profiles['profiles']['Q0']['restored_profile']['p2_render_gpu_index'] == 7


def test_gpu5_budget_includes_historical_gpu7_cost_and_requires_runtime_agreement():
    events = events_for()
    for event in events:
        event['physical_gpu'] = 7
    before = copy.deepcopy(events)
    current = synced_state(events); current['gpu_pool'] = [5]
    assert runner.check_budget(current, events, row(), physical_gpu=5) == 100
    assert runner.budget_snapshot(events)['gpu_hours_consumed'] == pytest.approx(.01)
    assert events == before
    with pytest.raises(runner.GateError, match='GPU policy/runtime'):
        runner.check_budget(current, events, row(), physical_gpu=7)


def test_frozen_plan_gpu5_requires_authoritative_state_agreement(tiny_plan):
    root, path, plan, runtime_path, runtime = tiny_plan
    runtime['gpu_mapping'].update(physical_gpu=5, egl_device_index=2)
    runtime_path.write_text(json.dumps(runtime))
    plan['runtime_manifest_sha256'] = runner.digest(runtime_path)
    path.write_text(json.dumps(plan))
    with pytest.raises(runner.GateError, match='GPU policy/runtime'):
        runner.validate_plan(path, root=root)
    current = runner.read_state(root / 'research-state.yaml'); current['gpu_pool'] = [5]
    (root / 'research-state.yaml').write_text(yaml.safe_dump(current))
    assert runner.validate_plan(path, root=root)[2]['gpu_mapping']['physical_gpu'] == 5


def test_gpu5_monitor_failure_remains_infrastructure_without_reclassifying_algorithm_failures(tmp_path):
    event, outcome = runner.failed_outcome(runner.GateError('external GPU5 process appeared during owned attempt'), tmp_path, row())
    assert event == 'aborted' and outcome['retryable_infrastructure'] is True
    event, outcome = runner.failed_outcome(runner.GateError('nonfinite metric'), tmp_path, row())
    assert event == 'valid' and outcome['retryable_infrastructure'] is False


def test_gpu5_dispatch_records_selected_device_at_all_runtime_boundaries(tiny_plan, monkeypatch):
    root, path, plan, runtime_path, runtime = tiny_plan
    runtime['gpu_mapping'].update(physical_gpu=5, egl_device_index=2, uuid='GPU-five')
    runtime_path.write_text(json.dumps(runtime))
    plan.update(runtime_manifest_sha256=runner.digest(runtime_path), phase_authorization={'dev': True})
    path.write_text(json.dumps(plan))
    current = runner.read_state(root / 'research-state.yaml'); current['gpu_pool'] = [5]
    (root / 'research-state.yaml').write_text(yaml.safe_dump(current))
    admissions = []; waits = []; children = []
    monkeypatch.setattr(runner, 'gpu_admission', lambda **kwargs: admissions.append(kwargs) or {'physical_gpu': kwargs['physical_gpu']})
    monkeypatch.setattr(runner, 'verify_provider', lambda *args, **kwargs: None)
    def command(_plan, _manifest, _runtime, _row, attempt_id):
        return ['owned-main'], Path(_plan['artifact_root']) / 'attempts' / attempt_id
    monkeypatch.setattr(runner, 'build_command', command)
    (Path(plan['artifact_root']) / 'attempts').mkdir()
    def launch(command, **kwargs):
        children.append(kwargs['env'])
        return SimpleNamespace(pid=99999999, poll=lambda: 0)
    monkeypatch.setattr(runner.subprocess, 'Popen', launch)
    monkeypatch.setattr(runner, 'wait_exclusively', lambda child, timeout, **kwargs: waits.append(kwargs) or 0)
    monkeypatch.setattr(runner, 'validate_result', lambda *args: {'success': False, 'outcome_valid': True})
    results = runner.run_plan(path, split='dev', iteration=0, root=root)
    assert admissions == [{'physical_gpu': 5, 'expected_uuid': 'GPU-five'}] * 2
    assert waits == [{'physical_gpu': 5}]
    assert children[0]['CUDA_VISIBLE_DEVICES'] == '5' and children[0]['MUJOCO_EGL_DEVICE_ID'] == '2'
    events = runner.read_events(root / 'data/attempt-ledger.jsonl')
    assert [event['event'] for event in events] == ['reserved', 'dispatched', 'valid']
    assert all(event['physical_gpu'] == 5 for event in events)
    assert 'GPU5' in results[0]['gpu_time_measurement']
    command_record = runner.read_json(Path(results[0]['output_dir']) / 'command.json')
    assert command_record['environment_public']['CUDA_VISIBLE_DEVICES'] == '5'


def test_gpu5_dead_process_reconciliation_uses_frozen_device_and_preserves_identity(tiny_plan, monkeypatch):
    root, path, plan, runtime_path, runtime = tiny_plan
    runtime['gpu_mapping'].update(physical_gpu=5, egl_device_index=7, uuid='GPU-five')
    runtime_path.write_text(json.dumps(runtime))
    plan['runtime_manifest_sha256'] = runner.digest(runtime_path)
    path.write_text(json.dumps(plan))
    current = runner.read_state(root / 'research-state.yaml'); current['gpu_pool'] = [5]
    (root / 'research-state.yaml').write_text(yaml.safe_dump(current))
    output = Path(plan['artifact_root']) / 'attempts' / 'dead_gpu_five'; output.mkdir(parents=True)
    episode = plan['episodes'][0]
    base = {'attempt_id': 'dead_gpu_five', 'identity': runner.episode_identity(episode),
            'episode_key': episode['episode_key'], 'budget_bucket': 'baseline',
            'physical_gpu': 5, 'output_dir': str(output), 'plan_sha256': runner.digest(path)}
    runner.append_event(root, {**base, 'event': 'reserved', 'time_unix': 1.})
    runner.append_event(root, {**base, 'event': 'dispatched', 'time_unix': 2.})
    calls = []
    monkeypatch.setattr(runner, 'gpu_admission', lambda **kwargs: calls.append(kwargs) or {})
    monkeypatch.setattr(runner.time, 'time', lambda: 3.)
    terminal = runner.reconcile_ledger(path, 'dead_gpu_five', root=root)
    assert calls == [{'physical_gpu': 5, 'expected_uuid': 'GPU-five'}]
    assert terminal['physical_gpu'] == 5 and terminal['event'] == 'aborted'
    assert terminal['gpu_process_wall_seconds'] == 1.
    before = (root / 'data/attempt-ledger.jsonl').read_bytes()
    calls.clear()
    assert runner.reconcile_ledger(path, 'dead_gpu_five', root=root)['state_reconciled_from_existing_terminal']
    assert not calls and (root / 'data/attempt-ledger.jsonl').read_bytes() == before
