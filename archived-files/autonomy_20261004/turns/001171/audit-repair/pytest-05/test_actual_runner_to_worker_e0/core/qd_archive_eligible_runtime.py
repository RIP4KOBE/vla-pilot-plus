"""N32 runtime: CPU selector over native copies, at the existing N31 boundary.

No scoring, projection, provider or RNG draws. Device transfer is synchronous
and timed; CPU validation does not establish CUDA latency or efficacy.
"""
from dataclasses import asdict, replace
import copy
import hashlib
import json
from pathlib import Path
import time
import torch
from core.qd_capture_dwell import CaptureDwellDecision, native_id, validate_config as validate_n31, MODE as N31
from core.qd_archive_eligible_capture import CanonicalCache, select_eligible_parent

MODE = 'archive_eligible_capture_v1'


def validate_config(cfg, horizon):
    mode = cfg.archive_eligible_capture_mode
    if mode == 'off':
        return
    if mode != MODE or cfg.capture_dwell_proposal_mode != 'off':
        raise ValueError('N32 mode invalid or mixed with N31')
    validate_n31(replace(cfg, capture_dwell_proposal_mode=N31), horizon)
    binding = cfg.n32_runtime_binding
    if (not isinstance(binding, dict) or set(binding) != {'task_id', 'source_commit', 'run_id'}
            or type(binding['task_id']) is not int or binding['task_id'] < 0
            or not isinstance(binding['source_commit'], str) or len(binding['source_commit']) != 40
            or any(c not in '0123456789abcdef' for c in binding['source_commit'])
            or not isinstance(binding['run_id'], str) or not binding['run_id']):
        raise ValueError('N32 explicit task/source/run binding required')


def cpu(value):
    if torch.is_tensor(value):
        return value.detach().cpu().clone()
    if isinstance(value, dict):
        return {k: cpu(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(cpu(v) for v in value)
    return copy.deepcopy(value)


def rng_state(device):
    return {'cpu': torch.random.get_rng_state().clone(),
            'device': None if device.type == 'cpu' else torch.cuda.get_rng_state(device).cpu().clone()}


class _CacheRecorder:
    def __init__(self, recorder, owner):
        self.recorder, self.owner = recorder, owner
        self.scoring_batch_id = recorder.scoring_batch_id

    def record(self, event, **values):
        start = time.perf_counter()
        self.recorder.record(event.replace('n31_', 'n32_', 1), **values)
        self.owner.costs['recording_seconds'] += time.perf_counter() - start


class ArchiveEligibleDecision(CaptureDwellDecision):
    event_prefix = 'n32'

    def __init__(self, *args, config, **kwargs):
        super().__init__(*args, **kwargs)
        # Required provenance is never turned into geometric ineligibility.
        if self.reason is not None or any(self.packet.get(k) is None for k in
                ('observed_eef', 'hand_quaternion_xyzw', 'gripper_qpos')):
            raise ValueError('N32 missing required packet/provider/tracker provenance')
        self.config = asdict(config)
        self.binding = copy.deepcopy(config.n32_runtime_binding)
        if type(self.packet.get('task_id')) is not int or self.packet['task_id'] != self.binding['task_id']:
            raise ValueError('N32 observed/configured task mismatch')
        self.config_sha256 = hashlib.sha256(json.dumps(self.config, sort_keys=True, allow_nan=False).encode()).hexdigest()
        root = Path(__file__).resolve().parent
        self.source_hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in
            ('qd_archive_eligible_runtime.py', 'qd_archive_eligible_capture.py', 'qd_capture_dwell.py',
             'qd_capture_dwell_proposal.py', 'qd_ed.py', 'rdt_policy_steer.py')}
        self.source_hashes['main.py'] = hashlib.sha256((root.parent / 'main.py').read_bytes()).hexdigest()
        self.costs = dict(selector_cpu_seconds=0., transfer_sync_seconds=0., recording_seconds=0.)


    def record_score(self, samples, projection, rewards, costs, evidence, **kwargs):
        super().record_score(samples, projection, rewards, costs,
            None if evidence is None else _CacheRecorder(evidence, self), **kwargs)

    def prepare(self, archive, iteration, providers, keypoints, evidence):
        start = time.perf_counter()
        self.validate(keypoints, providers)
        if self.pending is not None or iteration != len(self.opportunities) or self.batches != iteration + 1:
            raise RuntimeError('N32 opportunity order')
        rng = rng_state(self.mask.device)
        transfer = time.perf_counter()
        occupied = {cell: replace(entry, action=cpu(entry.action), descriptor_xy_m=cpu(entry.descriptor_xy_m))
                    for cell, entry in archive.entries.items()}
        cache = CanonicalCache(tuple(self.identity[k] for k in ('episode', 'stage', 'step')), cpu(self.entries))
        mask = cpu(self.mask)
        self.costs['transfer_sync_seconds'] += time.perf_counter() - transfer
        selector = time.process_time()
        result = select_eligible_parent(occupied, cache, decision_id=cache.decision_id, iteration=iteration,
            action_mask=mask, target=self.target, hand_quaternion_xyzw=self.packet['hand_quaternion_xyzw'],
            gripper_qpos=self.packet['gripper_qpos'], target_recognized=True)
        self.costs['selector_cpu_seconds'] += time.process_time() - selector
        parents = []
        for p in result.parents:
            entry = occupied[p.cell_id]
            parents.append({**asdict(p), 'matching_occurrences': list(p.matching_occurrences),
                'archive': {'cell': p.cell_id, 'source_iter': entry.source_iter,
                    'insert_sequence': entry.insert_sequence, 'fingerprint': entry.fingerprint,
                    'native_identity': native_id(entry.action)},
                'source': cache.entries[p.matching_occurrences[0]]})
        selected = result.selected
        self.pending = {'iteration': iteration, 'identity': copy.deepcopy(self.identity), 'slot': 15,
            'parents': parents, 'selected_cell': None if selected is None else selected.cell_id,
            'candidate': result.candidate, 'arrival_index': None if selected is None else selected.arrival_index,
            'reason': 'no_eligible_parent' if selected is None else selected.reason,
            'binding': self.binding, 'config': self.config, 'config_sha256': self.config_sha256,
            'source_hashes': self.source_hashes, 'prepare_rng_before': rng,
            'prepare_rng_after': rng_state(self.mask.device)}
        self.overhead_seconds += time.perf_counter() - start

    def apply(self, population, evidence):
        start = time.perf_counter()
        record = self.pending
        if record is None or tuple(population.shape) != (16, 64, 128) or population.dtype != self.mask.dtype or population.device != self.mask.device:
            raise ValueError('N32 missing opportunity or malformed population')
        rng = rng_state(population.device)
        transfer = time.perf_counter()
        before = cpu(population)
        candidate = record['candidate']
        if candidate is not None:
            population = population.clone()
            population[15] = candidate.to(population.device)
        # Explicit synchronous evidence copy accounts for transfer completion.
        after = cpu(population)
        self.costs['transfer_sync_seconds'] += time.perf_counter() - transfer
        self.opportunities.append({'changed': candidate is not None, 'reason': record['reason']})
        self.pending = None
        if evidence is not None:
            recording = time.perf_counter()
            evidence.record('n32_archive_eligible_opportunity', **record, observation=self.packet,
                original_post_rollout_population=before, actual_scored_population=after,
                apply_rng_before=rng, apply_rng_after=rng_state(population.device))
            self.costs['recording_seconds'] += time.perf_counter() - recording
        self.overhead_seconds += time.perf_counter() - start
        return population

    def close(self):
        result = super().close()
        result.update(schema='n32-archive-eligible-scalar-v1', mode=MODE, costs=self.costs,
            overhead_excludes=result['overhead_excludes'] + ['source_hashing', 'CUDA_cost_not_measured_on_CPU'],
            provider_http_telemetry='Unknown')
        return result
