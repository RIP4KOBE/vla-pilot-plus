#!/usr/bin/env python3
"""Closed N23 matched Dev and recovery admission contract; no adoption authority."""
from __future__ import annotations
from contextlib import contextmanager
import json
import os
from pathlib import Path
import threading
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from scripts import qd_ed_n23_worker as worker
from scripts import qd_ed_n23_backend_preflight as backend

ROOT = Path(__file__).resolve().parents[1]
SESSION = ROOT.parent if ROOT.name == 'study_worktree' else ROOT.parents[2]
RUN_DIR = SESSION / 'variants/n23_actuator_clipped_quality'
SOURCE_PLAN = SESSION / 'variants/n22_hold_conditioned_lift/plan.frozen.v1.gpu7.json'
GPU7_RUNTIME = Path(json.loads(SOURCE_PLAN.read_text())['runtime_manifest_path'])
PROTOCOL = RUN_DIR / 'protocol-dev-conditional-v1.md'
PROTOCOL_SHA = '638e43e8a7ab2b7accd13d7e772ed54e21b10ad84ac80c6decdee36a02066ed2'
BACKEND_PROTOCOL = RUN_DIR / 'backend-arithmetic-protocol-v1.md'
PREDECESSOR_REVIEW = RUN_DIR / 'predecessor-review-v1.json'
FINAL_REVIEW = RUN_DIR / 'final-source-runtime-review-v1.json'
BUDGET_AMENDMENT = SESSION / 'budget-autonomous-amendment-20260930-n23.md'
AMENDMENT_SHA = '921d1e319d6ce7f3a9b8d79358c986b1640d31f8590d8abaf720ddea5b15cfb9'
AUTONOMOUS_REPLY = '继续完成满足目标且无需我介入的autoresearch'
GPU7_UUID = 'GPU-48473162-9548-1a19-04aa-ea86c5349187'
GPU7_PROOF = 'rdt-qd-ed-final-20260921T093925Z__gpu7_cuda_egl__4fafff3673e5'
COHORT = 'N23_CLIPPED_QUALITY_DEV_20260930'
PREFLIGHT = 'N23_BACKEND_PREFLIGHT_20260930'
TASKS = tuple(range(10))
ARMS = ('C0', 'Q0', 'N7', 'N23')
LIMITS = {'dispatches': 40, 'gpu_hours': 21., 'episode_timeout_seconds': 1800,
          'cleanup_seconds': 40, 'physical_gpu': 7}
EXTRA_SOURCE = {'scripts/qd_ed_n23_dev_contract.py', 'scripts/qd_ed_n23_dev_prepare.py',
                'scripts/qd_ed_n23_dev_supervise.py', 'scripts/qd_ed_n23_preflight_admit.py',
                'tests/test_qd_ed_n23_dev.py', 'configs/qd_ed_final/candidate_n7.json',
                'experiments/iteration_023_actuator_clipped_quality/protocol-dev-conditional-v1.md',
                'experiments/iteration_023_actuator_clipped_quality/budget-amendment-v1.md',
                'experiments/iteration_023_actuator_clipped_quality/closed-runtime-admission-v1.md'}
_SCOPE = None
sha = worker.sha
ref = lambda path: {'path': str(Path(path).resolve()), 'sha256': sha(path)}


def source_paths(r):
    return ({v['path'] for v in r['read_json'](SOURCE_PLAN)['code_files']} | r['REQUIRED_CODE']
            | worker.REQUIRED_SOURCE | backend.EXTRA_SOURCE | EXTRA_SOURCE)


def expected_rows():
    parent = json.loads(SOURCE_PLAN.read_text()); seed = Path(parent['seed_plan_path'])
    worker.require(sha(seed) == parent['seed_plan_sha256'], 'N23 original frozen seed hash differs')
    seeds = json.loads(seed.read_text()); original = {r['task_id']: r for r in seeds['blocks']['dev']}
    worker.require(tuple(seeds['backend_task_order']) == TASKS and set(original) == set(TASKS)
                   and len(seeds['blocks']['dev']) == 10, 'N23 original ten-task identities differ')
    fields = ('task_id', 'env_seed', 'policy_seed', 'init_index', 'init_row_sha256', 'init_file_sha256', 'bddl_sha256')
    return [{**{k: original[t][k] for k in fields}, 'split': 'dev', 'seed_block': 'dev',
             'iteration': COHORT, 'profile': a, 'timeout_seconds': 1800,
             'episode_key': f'n23_dev_t{t:02d}_{a.lower()}_20260930',
             'budget_bucket': 'baseline' if a == 'C0' else 'development'} for t in TASKS for a in ARMS]


def predecessor_review():
    reference = ref(PREDECESSOR_REVIEW)
    review = backend.predecessor_gate(reference)
    worker.require(review['source_plan'] == ref(SOURCE_PLAN), 'N23 exact predecessor plan differs')
    return reference


def final_review(source, runtime_ref):
    reference = ref(FINAL_REVIEW); review = worker.read_ref(reference)
    worker.require(sha(PROTOCOL) == PROTOCOL_SHA and sha(BACKEND_PROTOCOL) == backend.PROTOCOL_SHA
                   and sha(BUDGET_AMENDMENT) == AMENDMENT_SHA, 'N23 frozen protocols/amendment differ')
    worker.require(review == {'schema': 'n23-final-source-runtime-review-v1', 'disposition': 'accepted',
        'source': source, 'runtime': runtime_ref, 'dev_protocol': ref(PROTOCOL),
        'backend_protocol': ref(BACKEND_PROTOCOL), 'amendment': ref(BUDGET_AMENDMENT),
        'no_gpu_release': True}, 'N23 root final source/runtime review missing or differs')
    return reference


def require_state(state, r):
    r['require'](state['resource_isolation']['status'] == 'ACTIVE'
        and state['resource_isolation']['validation_status'] == 'PASS'
        and state['resource_isolation']['private_budget'] is True
        and state['budget'].get('amendment') == r['GPU7_N23_AMENDMENT']
        and state['budget']['max_episode_attempts'] == 478 and state['budget']['max_gpu_hours'] == 100.
        and state['budget']['reserved'] == r['N23_BUCKETS']
        and state['budget']['gpu_hour_reservations'] == {'validation': 32., 'formal': 12.}
        and r['authorized_gpu'](state) == 7
        and state.get('n23_gpu7_binding') == {'scope': COHORT + '_and_backend_preflight_only',
            'user_reply': AUTONOMOUS_REPLY, 'selected_gpu': 7,
            'addendum_path': str(PROTOCOL), 'addendum_sha256': PROTOCOL_SHA},
        'N23 adopted private budget/device authority differs')
    r['require'](not state.get('external_resource_hold', {}).get('do_not_auto_resume', False),
                 'N23 external resource hold is active')


def validate_runtime(runtime, root, r):
    r['require'](runtime == r['read_json'](GPU7_RUNTIME)
        and Path(runtime['worktree']).resolve() == Path(root).resolve()
        and runtime.get('schema') == 'qd-ed-runtime-setup-v1'
        and r['runtime_gpu'](runtime) == 7 and runtime['gpu_mapping']['uuid'] == GPU7_UUID
        and runtime['gpu_mapping']['egl_device_index'] == 4
        and runtime.get('cuda_egl_verified') is True
        and runtime.get('cuda_egl_probe', {}).get('resource_id') == GPU7_PROOF
        and runtime.get('stage_recovered_error_condition') == r['E2_STAGE_CONDITION']
        and runtime.get('stage_engineering_condition') == r['n4e1_support']().engineering_condition()
        and runtime['frozen_stage_provider'].get('allow_recovered_error_events') is True,
        'N23 frozen runtime/GPU7/Stage identity differs')
    r['verify_files'](runtime['files'], allowed_roots=(Path(root), runtime['artifact_root']))


def backend_proof(reference, source, root, r):
    r['require'](isinstance(reference, dict) and set(reference) == {'plan', 'report', 'attempt_id'},
                 'N23 actual backend proof is missing')
    plan = worker.read_ref(reference['plan']); worker.read_ref(reference['report'])
    r['require'](plan['runtime'] == ref(GPU7_RUNTIME) and plan['source'] == source
                 and plan['predecessor_review'] == predecessor_review(), 'N23 preflight runtime/source/predecessor differs')
    events = r['read_events'](Path(root) / 'data/attempt-ledger.jsonl')
    local = [e for e in events if e.get('identity', {}).get('iteration') == PREFLIGHT]
    r['require'](len({e['attempt_id'] for e in local}) == 1
                 and local[0]['event'] == 'reserved' and local[-1]['event'] == 'valid'
                 and local[-1]['attempt_id'] == reference['attempt_id']
                 and local[-1].get('n23_final_review') == final_review(source, ref(GPU7_RUNTIME))
                 and len([e for e in local if e['event'] == 'dispatched']) == 1,
                 'N23 proof requires its single actual recovery ledger attempt')
    r['require'](backend.verify_preflight_proof(reference['plan']['path'], reference['report']['path'],
                                               local[-1], source) == reference['report'],
                 'N23 backend proof hash differs')
    return reference


def validate_contract(plan, manifest, runtime, seeds, root, r):
    source = worker.source_record(root, [v['path'] for v in plan['code_files']])
    meta = plan.get('n23_cohort', {})
    r['require'](sha(Path(root) / 'experiments/iteration_023_actuator_clipped_quality/protocol-dev-conditional-v1.md') == PROTOCOL_SHA
        and sha(Path(root) / 'experiments/iteration_023_actuator_clipped_quality/backend-arithmetic-protocol-v1.md') == backend.PROTOCOL_SHA
        and sha(Path(root) / 'experiments/iteration_023_actuator_clipped_quality/budget-amendment-v1.md') == AMENDMENT_SHA,
        'N23 tracked protocols or amendment differ')
    r['require'](source['commit'] == plan['source_commit'] and source['files'] == plan['code_files']
        and source_paths(r) <= {v['path'] for v in plan['code_files']}, 'N23 complete sorted committed source differs')
    r['require'](meta == {'schema': 'n23-clipped-quality-dev-v1', 'cohort_id': COHORT, 'limits': LIMITS,
        'n7_role': 'ablation_control_only_no_promotion', 'predecessor_review': predecessor_review(),
        'budget_amendment': ref(BUDGET_AMENDMENT), 'protocol': ref(PROTOCOL), 'source_plan': ref(SOURCE_PLAN),
        'final_review': final_review(source, ref(GPU7_RUNTIME)),
        'worker_audit': worker.WORKER_CONTRACT,
        'early_stop': 'numeric_futility_after_complete_task_quadruple',
        'backend_proof': backend_proof(meta.get('backend_proof'), source, root, r)},
        'N23 prospective cohort, source review or backend proof differs')
    r['require'](plan['episodes'] == expected_rows() and set(plan['candidate_profiles']) == {'N7', 'N23'}
        and set(manifest['profiles']) == set(ARMS)
        and plan.get('phase_authorization') == {'dev': True, 'validation': False, 'formal': False}
        and plan.get('stage_condition') == r['E2_STAGE_CONDITION']
        and not any(plan.get(k) is not None for k in ('n7_cohort','n9_cohort','n11_cohort','n17_passive_physics',
             'n18_cohort','n19_cohort','n20_cohort','n21_cohort','n22_cohort','n7_validation',
             'n7_validation_continuation','n7_passive_diagnostic','n7_e2_passive_diagnostic')),
        'N23 closed matrix/profile/phase gate differs')
    for arm in ('N7', 'N23'):
        path = Path(root) / f'configs/qd_ed_final/candidate_{arm.lower()}.json'
        r['require'](plan['candidate_profiles'][arm] == ref(path) and str(path.relative_to(root)) in plan['scientific_config_files'],
                     'N23 scientific profile fingerprint differs')
    n7 = manifest['profiles']['N7']['resolved_eds_config']; n23 = manifest['profiles']['N23']['resolved_eds_config']
    r['require'](n23 == {**n7, 'qd_quality_mode': 'actuator_clipped_provider_v1'}
        and n7 == {**manifest['profiles']['Q0']['resolved_eds_config'],
                   'qd_descriptor': 'target_xy_quadrant_signed_height_v1',
                   'qd_final_selection_mode': 'terminal_grasp_proximity_v1'}, 'N23 sole quality delta differs')
    r['require'](plan['runtime_manifest_path'] == str(GPU7_RUNTIME)
                 and plan['runtime_manifest_sha256'] == sha(GPU7_RUNTIME), 'N23 runtime reference differs')
    validate_runtime(runtime, root, r)
    require_state(r['read_state'](Path(root) / 'research-state.yaml'), r)


@contextmanager
def supervised_scope(plan, root, episode_key):
    global _SCOPE
    if _SCOPE is not None: raise RuntimeError('nested N23 supervisor scope')
    _SCOPE = (str(Path(root).resolve()), plan['source_commit'], episode_key, os.getpid(), threading.get_ident())
    try: yield
    finally: _SCOPE = None


def require_scope(plan, root, r, row=None):
    r['require'](_SCOPE is not None and _SCOPE[0] == str(Path(root).resolve())
        and _SCOPE[1] == plan['source_commit'] and _SCOPE[3:] == (os.getpid(), threading.get_ident())
        and (row is None or _SCOPE[2] == row['episode_key']), 'N23 requires its one-cell supervisor')


def full_capacity(state, events, resources, r, *, preflight=False):
    """Reserve the entire unspent local ceiling, not just the next cell."""
    require_state(state, r); snap = r['budget_snapshot'](events, resources)
    local = [e for e in events if e.get('identity', {}).get('iteration') == COHORT]
    spent = sum(e['gpu_process_wall_seconds'] for e in local if e['event'] in r['TERMINAL']) / 3600
    charged = [e for e in local if e['event'] == 'dispatched']
    remaining = {b: need - sum(e['budget_bucket'] == b for e in charged)
                 for b, need in (('baseline', 10), ('development', 30))}
    protected = sum(max(0., h - snap['gpu_hours_by_bucket'].get(b, 0.))
                    for b, h in state['budget']['gpu_hour_reservations'].items())
    extra = backend.LIMITS['gpu_hours_reserved'] if preflight else 0.
    r['require'](snap['running'] == snap['gpu_healthcheck_inflight'] == 0
        and all(g[-1]['event'] in r['TERMINAL'] for g in r['event_groups'](events).values())
        and snap['gpu_hours_consumed'] + max(0., 21. - spent) + extra + protected <= 100. + 1e-9,
        'N23 full remaining local ceiling cannot fit protected GPU reserves or ownership is busy')
    r['require'](all(state['budget']['reserved'][b] - snap['by_bucket'][b] >= n for b, n in remaining.items())
        and (not preflight or state['budget']['reserved']['recovery'] > snap['by_bucket']['recovery']),
        'N23 full matched matrix or recovery attempt capacity unavailable')
    protected_attempts = sum(max(0, state['budget']['reserved'][b] - snap['by_bucket'][b]) for b in ('validation','formal'))
    r['require'](snap['dispatched'] + sum(remaining.values()) + int(preflight) + protected_attempts <= 478,
                 'N23 full matrix would borrow protected attempt reserves')


def protected_budget(state, events, resources, row, timeout, r, *, plan):
    r['require'](row in plan['episodes'] and row['iteration'] == COHORT and row['profile'] in ARMS
        and row['budget_bucket'] == ('baseline' if row['profile'] == 'C0' else 'development')
        and timeout == 1800, 'N23 row/bucket/timeout differs')
    local = [e for e in events if e.get('identity', {}).get('iteration') == COHORT]
    r['require'](sum(e['event'] == 'dispatched' for e in local) < 40
        and sum(e.get('gpu_process_wall_seconds', 0.) for e in local if e['event'] in r['TERMINAL']) + 1840 <= 21 * 3600,
        'N23 local dispatch/hour cap exceeded')
    full_capacity(state, events, resources, r)


def read_worker_report(output, r):
    output = Path(output)
    return worker.verify_receipt(output / 'n23-worker-context.json', r['read_json'](output / 'process.json'))


def admission(plan, runtime, row, events, resources, root, r):
    r['require'](row in plan['episodes'], 'N23 row outside matrix')
    index = plan['episodes'].index(row); expected = plan['episodes'][:index]
    local = [e for e in events if e.get('identity', {}).get('iteration') == COHORT]
    r['require'](not any(e.get('episode_key') == row['episode_key'] for e in local), 'N23 cell cannot be retried')
    r['require'](all(e.get('episode_key') in {v['episode_key'] for v in expected} for e in local), 'N23 exact prefix required')
    successes = 0
    for prior in expected:
        final = [e for e in local if e.get('episode_key') == prior['episode_key'] and e['event'] in r['TERMINAL']]
        r['require'](len(final) == 1 and final[0]['event'] == 'valid' and final[0].get('outcome_valid') is True,
                     'N23 all preceding cells must be valid')
        report = read_worker_report(final[0]['output_dir'], r)
        r['require'](report.get('accepted') is True and report.get('evidence_complete') is True, 'N23 preceding native audit failed')
        if prior['profile'] == 'N23': successes += int(final[0].get('success') is True)
    # Called within a task only after its previous complete quadruples passed.
    r['require'](successes + len(TASKS) - index // 4 >= 5, 'N23 numeric futility closes later admission')
    return {'n23_cohort_id': COHORT, 'n23_protocol_sha256': PROTOCOL_SHA,
            'n23_arm_role': 'ablation_control_only' if row['profile'] == 'N7' else 'candidate' if row['profile'] == 'N23' else 'control'}
