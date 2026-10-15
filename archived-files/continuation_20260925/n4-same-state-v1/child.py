#!/usr/bin/env python3
"""One N4 first-decision, same-state branch diagnostic; never reports official SR."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

import numpy as np
import torch
from omegaconf import OmegaConf

W = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
sys.path.insert(0, str(W))
from core.rdt_libero_action_converter import decode_rdt_libero_action_chunk
from main import Main


class DiagnosticFinished(BaseException):
    pass


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def array_record(value):
    array = np.asarray(value)
    assert array.dtype.kind in 'biufc', f'non-numeric observation dtype {array.dtype}'
    assert np.isfinite(array).all(), 'nonfinite simulator observation/state'
    canonical = np.ascontiguousarray(array)
    return {'shape': list(canonical.shape), 'dtype': str(canonical.dtype),
            'sha256': hashlib.sha256(canonical.tobytes()).hexdigest()}


def numeric_list(value):
    array = np.asarray(value)
    assert array.dtype.kind in 'biufc' and np.isfinite(array).all()
    return array.astype(np.float64).tolist()


CONTROLLER_FIELDS = ('goal_pos', 'goal_ori', 'ee_pos', 'ee_ori_mat',
                     'joint_pos', 'joint_vel', 'initial_joint')
RAW_FIELDS = ('agentview_image', 'robot0_eye_in_hand_image', 'robot0_eef_pos',
              'robot0_eef_quat', 'robot0_gripper_qpos', 'robot0_gripper_qvel',
              'robot0_joint_pos', 'robot0_joint_vel')


def snapshot(env):
    control = env._env
    underlying = control.env
    sim = control.sim
    state = np.asarray(control.get_sim_state()).copy()
    assert np.isfinite(state).all()
    raw = underlying._get_observations()
    assert set(RAW_FIELDS) <= set(raw), 'required raw observation missing'
    controller = control.robots[0].controller
    controller_record = {}
    for field in CONTROLLER_FIELDS:
        value = getattr(controller, field, None)
        controller_record[field] = None if value is None else array_record(value)
    body_ids = underlying.obj_body_id
    assert 'orange_juice_1' in body_ids and 'basket_1' in body_ids
    obj = {name: {'xyz': numeric_list(sim.data.body_xpos[body_ids[name]]),
                  'wxyz': numeric_list(sim.data.body_xquat[body_ids[name]])}
           for name in ('orange_juice_1', 'basket_1')}
    contacts = []
    for index in range(int(sim.data.ncon)):
        contact = sim.data.contact[index]
        contacts.append({'geom1': sim.model.geom_id2name(contact.geom1),
                         'geom2': sim.model.geom_id2name(contact.geom2),
                         'distance': float(contact.dist)})
    obs = {field: array_record(raw[field]) for field in RAW_FIELDS}
    result = {'sim_state': array_record(state), 'raw_observations': obs,
              'controller': controller_record,
              'timestep': int(underlying.timestep),
              'sim_time': float(sim.data.time),
              'success': bool(control.check_success()),
              'object_pose': obj,
              'eef_xyz': numeric_list(raw['robot0_eef_pos']),
              'gripper_qpos': numeric_list(raw['robot0_gripper_qpos']),
              'contacts': contacts}
    assert math.isfinite(result['sim_time'])
    assert all(math.isfinite(x['distance']) for x in contacts)
    return result


def signature(record):
    return {key: record[key] for key in ('sim_state', 'raw_observations', 'controller',
                                        'timestep', 'sim_time', 'success',
                                        'object_pose', 'eef_xyz', 'gripper_qpos',
                                        'contacts')}


def exact(left, right):
    return signature(left) == signature(right)


def to_numpy_action(adapter, tensor):
    transition = adapter.env_postprocessor({'action': tensor})
    action = transition['action'].clone()
    assert tuple(action.shape) == (7,)
    action[-1] = 1 if action[-1] > 0 else -1
    result = action.float().to('cpu').numpy()
    assert np.isfinite(result).all()
    return result


def command_prefix(adapter, chunk):
    assert tuple(chunk.shape) == (1, 8, 7) or (len(chunk.shape) == 3 and
                                               chunk.shape[0] == 1 and
                                               chunk.shape[1] >= 8 and
                                               chunk.shape[2] == 7)
    return [to_numpy_action(adapter, chunk[0, index]) for index in range(8)]


def run_prefix(env, actions, limit):
    trace = [snapshot(env)]
    for index, action in enumerate(actions):
        assert index < 8 and limit['transitions'] < 32
        env._env.step(action)
        limit['transitions'] += 1
        trace.append(snapshot(env))
        if trace[-1]['success']:
            break
    return trace


def reset_to_initial(env, seed, initial, limit):
    assert limit['resets'] < 4
    env.reset(seed=seed)
    limit['resets'] += 1
    limit['settling_steps'] += int(env.num_steps_wait)
    assert limit['settling_steps'] <= 40
    current = snapshot(env)
    if not exact(current, initial):
        raise StateMismatch('reset did not reproduce complete initial signature')
    return current


class StateMismatch(RuntimeError):
    pass


def write_result(path, payload):
    assert not path.exists()
    with path.open('x') as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def main():
    assert len(sys.argv) == 2
    plan_path = Path(sys.argv[1]).resolve()
    plan = json.loads(plan_path.read_text())
    assert plan['schema'] == 'n4-same-state-diagnostic-plan-v1'
    assert digest(Path(__file__)) == plan['child_sha256']
    assert digest(Path(plan['source_config'])) == plan['source_config_sha256']
    assert digest(Path(plan['protocol'])) == plan['protocol_sha256']
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == '3'
    assert os.environ.get('MUJOCO_EGL_DEVICE_ID') == str(plan['egl_device_index'])
    assert os.environ.get('MUJOCO_GL') == 'egl'
    assert plan['task_id'] == 9 and plan['env_seed'] == plan['policy_seed'] == 1045350852
    output = Path(plan['output_dir'])
    output.mkdir(parents=True, exist_ok=False)
    cfg = OmegaConf.load(plan['source_config'])
    assert cfg.seed == plan['policy_seed']
    assert list(cfg.main.episode_seed_schedule) == [plan['env_seed']]
    assert list(cfg.backend.libero.task_ids_filter) == [9]
    assert cfg.main.eds_config.qd_final_selection_mode == 'terminal_population_v1'
    assert cfg.main.episode_num == 1 and cfg.main.episode_start_index == 0
    assert cfg.backend.libero.num_steps_wait == 5
    cfg.main.output_dir = str(output)
    cfg.main.eds_eval.output_dir = str(output / 'eds_eval')
    cfg.main.eds_eval.report_dir = str(output / 'diagnostic_report_only')
    cfg.main.eds_eval.job_id = plan['attempt_id']
    cfg.main.eds_eval.method_label = 'N4_DIAGNOSTIC_ONLY_NO_OFFICIAL_SR'
    cfg.main.eds_mechanism_pretest.output_dir = str(output / 'mechanism')
    cfg.main.eds_mechanism_pretest.run_id = plan['attempt_id']
    (output / 'resolved-config.yaml').write_text(OmegaConf.to_yaml(cfg, resolve=True))
    started = time.monotonic()
    app = Main(cfg)
    holder = {'called': False}

    def first_step_hook(action):
        assert not holder['called'], 'diagnostic step hook invoked more than once'
        holder['called'] = True
        evidence = getattr(app, '_decision_evidence', None)
        # The ordinary loop flushes action_dispatch immediately before this hook,
        # so bundle 2 is already present; the committed choice is in bundle 1.
        assert evidence is not None and evidence._committed == 1 and evidence._bundle == 2
        bundle_path = evidence.root / 'bundle_000001.pt'
        assert bundle_path.is_file()
        bundle = torch.load(bundle_path, map_location='cpu', weights_only=True)
        events = bundle['events']
        selected_events = [row for row in events if row['event'] == 'final_selection']
        committed_events = [row for row in events if row['event'] == 'decision_committed']
        context_events = [row for row in events if row['event'] == 'decision_context']
        assert len(selected_events) == len(committed_events) == len(context_events) == 1
        selection = selected_events[0]['values']
        committed = committed_events[0]['values']
        context = context_events[0]
        assert context['global_step'] == 0
        assert context['values']['use_guidance'] is True and context['values']['stage'] == 1
        assert selection['selection_rule'] == 'terminal_population_first_argmin'
        assert selection['qd_final_selection_mode'] == 'terminal_population_v1'
        assert selection['archive_reference']['selected_latent'].shape == (1, 64, 128)
        assert selection['terminal_population']['population_size'] == 16
        assert committed['execution_horizon'] == 8
        selected_chunk = committed['action_chunk']
        archive_latent = selection['archive_reference']['selected_latent'].to(app.policy.device)
        archive_chunk = decode_rdt_libero_action_chunk(archive_latent, 8)
        archive_chunk = app.adapter.env_postprocessor({'action': archive_chunk})['action']
        selected_actions = command_prefix(app.adapter, selected_chunk)
        archive_actions = command_prefix(app.adapter, archive_chunk)
        assert np.array_equal(selected_actions[0], to_numpy_action(app.adapter, action))
        differences = [index for index, (left, right) in enumerate(zip(selected_actions, archive_actions))
                       if not np.array_equal(left, right)]
        env = app.adapter._env[app.adapter.current_task_idx]
        assert env.task_id == 9 and env.num_steps_wait == 5
        limit = {'transitions': 0, 'resets': 1, 'settling_steps': 5}
        initial = snapshot(env)
        payload = {
            'schema': 'n4-same-state-diagnostic-result-v1',
            'diagnostic_only': True, 'official_task_success_rate': None,
            'attempt_id': plan['attempt_id'], 'task_id': 9, 'seed': plan['env_seed'],
            'initial': initial, 'selected_prefix': [x.tolist() for x in selected_actions],
            'archive_prefix': [x.tolist() for x in archive_actions],
            'different_command_indices': differences,
            'selection': {'selected_index': selection['selected_index'],
                          'selected_fingerprint': selection['selected_fingerprint'],
                          'archive_fingerprint': selection['archive_reference']['selected_fingerprint'],
                          'selected_cost': selection['selected_cost'],
                          'archive_cost': selection['archive_reference']['selected_cost']},
            'decision_bundle': {'path': str(bundle_path), 'sha256': digest(bundle_path)},
            'limits': {'diagnostic_transitions_max': 32, 'settling_steps_max': 40,
                       'branches_max': 2, 'decision_count_max': 1},
        }
        if not differences:
            payload.update(status='NO_SELECTION_CONTRAST', resources=limit,
                           diagnostic_wall_seconds=time.monotonic() - started)
            write_result(output / 'result.json', payload)
            raise DiagnosticFinished()
        try:
            dry_a = run_prefix(env, selected_actions, limit)
            reset_to_initial(env, plan['env_seed'], initial, limit)
            dry_b = run_prefix(env, selected_actions, limit)
            if len(dry_a) != len(dry_b) or any(not exact(a, b) for a, b in zip(dry_a, dry_b)):
                raise StateMismatch('identical selected-action dry runs diverged')
            reset_to_initial(env, plan['env_seed'], initial, limit)
            chosen = run_prefix(env, selected_actions, limit)
            if len(chosen) != len(dry_a) or any(not exact(a, b) for a, b in zip(chosen, dry_a)):
                raise StateMismatch('selected branch diverged from parity dry run')
            reset_to_initial(env, plan['env_seed'], initial, limit)
            reference = run_prefix(env, archive_actions, limit)
        except StateMismatch as error:
            payload.update(status='INFEASIBLE_STATE_RESTORE', reason=str(error), resources=limit,
                           diagnostic_wall_seconds=time.monotonic() - started)
            write_result(output / 'result.json', payload)
            raise DiagnosticFinished()
        assert limit['transitions'] <= 32 and limit['resets'] == 4 and limit['settling_steps'] == 20
        payload.update(status='COMPLETED_CONTRAST', resources=limit,
                       dry_run_a=dry_a, dry_run_b=dry_b,
                       selected_branch=chosen, archive_branch=reference,
                       diagnostic_wall_seconds=time.monotonic() - started)
        write_result(output / 'result.json', payload)
        raise DiagnosticFinished()

    app.adapter.step = first_step_hook
    try:
        app.run()
    except DiagnosticFinished:
        app._append_episode_compute(episode=0, episode_seed=plan['env_seed'],
                                    outcome='diagnostic_only_no_official_sr')
    finally:
        try:
            app.adapter.close()
        except Exception:
            pass
    assert holder['called'] and (output / 'result.json').is_file()
    print(json.dumps({'status': json.loads((output / 'result.json').read_text())['status'],
                      'result': str(output / 'result.json')}))


if __name__ == '__main__':
    main()
