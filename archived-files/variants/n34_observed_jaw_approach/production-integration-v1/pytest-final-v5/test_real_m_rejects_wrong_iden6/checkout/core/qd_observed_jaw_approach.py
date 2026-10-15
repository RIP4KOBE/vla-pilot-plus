"""N34 decision-local observed jaw approach. No predicted arrival or memory."""
from dataclasses import asdict, replace
import copy
import hashlib
import json
import math
from pathlib import Path
import time
import torch
from core.qd_capture_dwell import CaptureDwellDecision, MODE as N31, validate_config as validate_n31
from core.qd_capture_dwell_proposal import CaptureDwellProposal, _native, _geometry_vector, _same_native_bytes
from core.rdt_libero_action_converter import encode_libero_prefix

MODE = 'observed_jaw_approach_v1'
SOURCE_FILES = ('core/qd_observed_jaw_approach.py', 'core/qd_capture_dwell.py',
    'core/qd_capture_dwell_proposal.py', 'core/rdt_libero_action_converter.py',
    'core/qd_ed.py', 'core/qd_executed_quality.py', 'core/rdt_policy_steer.py', 'core/env_adapters/libero_adapter.py',
    'core/decision_evidence.py', 'main.py')


def validate_config(cfg, horizon):
    if cfg.observed_jaw_approach_mode == 'off':
        return
    if (cfg.observed_jaw_approach_mode != MODE or cfg.capture_dwell_proposal_mode != 'off'
            or cfg.archive_eligible_capture_mode != 'off'):
        raise ValueError('N34 requires exclusive explicit mode')
    validate_n31(replace(cfg, capture_dwell_proposal_mode=N31), horizon)
    binding = cfg.n34_runtime_binding
    if (not isinstance(binding, dict) or set(binding) != {'task_id', 'source_commit', 'run_id'}
            or type(binding['task_id']) is not int or binding['task_id'] < 0
            or not isinstance(binding['source_commit'], str) or len(binding['source_commit']) != 40
            or any(c not in '0123456789abcdef' for c in binding['source_commit'])
            or not isinstance(binding['run_id'], str) or not binding['run_id']):
        raise ValueError('N34 explicit task/source/run binding required')


def capture_context(observation, keypoints, tracking, episode):
    # Same cached raw fields as N31; preserve nonfinite evidence for a no-op.
    robot = observation.get('observation.robot_state', {})
    def get(group, key, n):
        value = robot.get(group, {}).get(key)
        if value is None:
            return None
        value = torch.as_tensor(value).detach().cpu()
        if value.shape not in ((n,), (1, n)) or not value.is_floating_point():
            raise ValueError('N34 malformed raw observation')
        return value.reshape(n).clone()
    return dict(episode=episode, tracker=copy.deepcopy(tracking),
        keypoints=None if keypoints is None else torch.as_tensor(keypoints).detach().cpu().clone(),
        observed_eef=get('eef', 'pos', 3), hand_quaternion_xyzw=get('eef', 'quat', 4),
        gripper_qpos=get('gripper', 'qpos', 2))


@torch.no_grad()
def propose(plan, *, target, observed_eef, hand_quaternion_xyzw, gripper_qpos, target_recognized):
    _native(plan, (64, 128), 'plan')
    if type(target_recognized) is not bool:
        raise ValueError('N34 explicit recognition required')
    if not target_recognized:
        return CaptureDwellProposal(None, None, 'unrecognized_target')
    vectors = []
    for value, n, name in ((target, 3, 'target'), (observed_eef, 3, 'EEF'),
            (hand_quaternion_xyzw, 4, 'quaternion'), (gripper_qpos, 2, 'jaw')):
        if torch.is_tensor(value) and not bool(torch.isfinite(value).all()):
            return CaptureDwellProposal(None, None, 'nonfinite_observation')
        vectors.append(_geometry_vector(value, n, name))
    point, eef, quat, jaw = vectors
    if any(v is None for v in vectors):
        return CaptureDwellProposal(None, None, 'observation_unavailable')
    norm = math.hypot(*quat)
    if not math.isfinite(norm) or norm == 0:
        return CaptureDwellProposal(None, None, 'invalid_quaternion')
    # Same binary64 normalized xyzw convention and operation order as N31.
    try:
        norm = math.sqrt(math.fsum(v*v for v in quat))
    except (OverflowError, ValueError):
        return CaptureDwellProposal(None, None, 'invalid_quaternion')
    if not math.isfinite(norm) or norm == 0:
        return CaptureDwellProposal(None, None, 'invalid_quaternion')
    x, y, z, w = (v/norm for v in quat)
    r = ((1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)),
         (2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)),
         (2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)))
    lower, upper = jaw[1]+.0005, jaw[0]-.0005
    if lower > upper:
        return CaptureDwellProposal(None, None, 'empty_inner_gap')
    delta = [point[k]-eef[k] for k in range(3)]
    if not all(math.isfinite(v) for v in delta):
        return CaptureDwellProposal(None, None, 'nonfinite_observation')
    local = [math.fsum(r[k][axis]*delta[k] for k in range(3)) for axis in range(3)]
    inside = -.008 <= local[0] <= .008 and lower <= local[1] <= upper and -.0116 <= local[2] <= .0044
    command = torch.zeros((8, 7), dtype=plan.dtype, device=plan.device)
    command[:, 6] = 1 if inside else -1
    if not inside:
        center = (0., (lower+upper)/2, -.0036)
        world = [math.fsum(r[k][axis]*center[axis] for axis in range(3)) for k in range(3)]
        command[:, :3] = torch.tensor([max(-1., min(1., (delta[k]-world[k])/(8*.01)))
                                      for k in range(3)], dtype=plan.dtype, device=plan.device)
    candidate = encode_libero_prefix(plan, command)
    reason = 'observed_close_dwell' if inside else 'observed_open_approach'
    if _same_native_bytes(candidate, plan):
        return CaptureDwellProposal(None, 0 if inside else None, 'no_native_change')
    return CaptureDwellProposal(candidate, 0 if inside else None, reason)


class _Recorder:
    def __init__(self, recorder):
        self.recorder = recorder
        self.scoring_batch_id = recorder.scoring_batch_id
    def record(self, event, **values):
        self.recorder.record(event.replace('n31_', 'n34_', 1), **values)


class ObservedJawDecision(CaptureDwellDecision):
    event_prefix = 'n34'

    def __init__(self, semantic, packet, keypoints, *, config, **kwargs):
        original = copy.deepcopy(packet)
        safe = copy.deepcopy(packet)
        nonfinite = False
        if safe is not None:
            for name in ('observed_eef', 'hand_quaternion_xyzw', 'gripper_qpos'):
                value = safe.get(name)
                if torch.is_tensor(value) and not bool(torch.isfinite(value).all()):
                    safe[name] = None
                    nonfinite = True
        super().__init__(semantic, safe, keypoints, **kwargs)
        if original is not None:
            for name in ('observed_eef', 'hand_quaternion_xyzw', 'gripper_qpos'):
                value = original.get(name)
                if torch.is_tensor(value): original[name] = value.reshape(-1).clone()
        self.packet = original
        if nonfinite and self.reason is None: self.reason = 'nonfinite_observation'
        self.config = asdict(config)
        self.binding = copy.deepcopy(config.n34_runtime_binding)
        if packet is not None and packet.get('task_id') != self.binding['task_id']:
            raise ValueError('N34 observed/configured task mismatch')
        self.config_sha256 = hashlib.sha256(json.dumps(self.config, sort_keys=True, allow_nan=False).encode()).hexdigest()
        root = Path(__file__).resolve().parents[1]
        self.source_hashes = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in SOURCE_FILES}

    def record_score(self, samples, projection, rewards, costs, evidence, **kwargs):
        super().record_score(samples, projection, rewards, costs,
            None if evidence is None else _Recorder(evidence), **kwargs)

    def prepare(self, archive, iteration, providers, keypoints, evidence):
        # Reuse N31's exact best-template association checks with proposal disabled.
        reason = self.reason
        self.reason = reason or 'n34_template_binding_only'
        try:
            super().prepare(archive, iteration, providers, keypoints, None)
        finally:
            self.reason = reason
        start = time.perf_counter()
        if not reason:
            result = propose(self.pending['source']['plan'], target=self.target,
                observed_eef=self.packet['observed_eef'], hand_quaternion_xyzw=self.packet['hand_quaternion_xyzw'],
                gripper_qpos=self.packet['gripper_qpos'], target_recognized=True)
            self.pending.update(candidate=result.candidate, arrival_index=result.arrival_index, reason=result.reason)
        self.pending.update(binding=self.binding, config=self.config, config_sha256=self.config_sha256,
                            source_hashes=self.source_hashes)
        self.overhead_seconds += time.perf_counter()-start

    def apply(self, population, evidence):
        return super().apply(population, None if evidence is None else _Recorder(evidence))

    def close(self):
        result = super().close()
        result.update(schema='n34-observed-jaw-scalar-v1', mode=MODE,
            overhead_excludes=result['overhead_excludes'] + ['N34_source_hashing'])
        return result
