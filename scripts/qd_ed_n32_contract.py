"""Draft-only N32 identity, finite admission and closed release boundary."""
import datetime as dt
import json
import math
from pathlib import Path
from scripts import qd_ed_n23_worker as w

ROOT = Path(__file__).resolve().parents[1]
# Fresh engineering-recovery primaries; prior N32 events remain globally charged.
COHORT = 'N32R2_ARCHIVE_ELIGIBLE_CAPTURE_DEV_20261004'
ARMS = ('C0', 'Q0', 'N32')
DEADLINE = '2026-10-10T17:42:00Z'
GPU_UUID = 'GPU-48473162-9548-1a19-04aa-ea86c5349187'
LIMITS = {'primary_cells': 30, 'baseline': 10, 'development': 20, 'automatic_recoveries': 0,
          'cohort_gpu_seconds': 18000, 'episode_seconds': 1800, 'cleanup_seconds': 40,
          'physical_gpu': 7, 'gpu_uuid': GPU_UUID}
WORKER_CONTRACT = {'schema': 'n32-same-process-audit-v1', 'arms': list(ARMS),
                   'candidate_audits': ['generic', 'n32_native'], 'control_audits': ['generic', 'n31_native'],
                   'timeout_includes_audit': True, 'external_manifest_required': True,
                   'automatic_recoveries': 0}


def ref(path):
    return {'path': str(Path(path).resolve()), 'sha256': w.sha(path)}


def stop_path(root=ROOT):
    """Locate the session STOP in supported checkouts; layout grants no release."""
    root = Path(root).resolve()
    if root.name == 'study_worktree':
        session = root.parent
    elif (root.name == 'implementation_worktree'
          and root.parent.parent.name == 'variants'):
        session = root.parent.parent.parent
    else:
        raise ValueError('unsupported N32 worktree layout: ' + str(root))
    # Do not resolve STOP itself: even a dangling symlink must stop admission.
    return str(session / 'autonomy_20261004/STOP')


def expected_rows(root=ROOT):
    tasks = json.loads((Path(root) / 'configs/qd_ed_final/n31_dev_task_identities.json').read_text())['tasks']
    w.require([x['task_id'] for x in tasks] == list(range(10)) and all(x['split'] == 'dev' for x in tasks), 'ten exposed Dev tasks')
    return [{**task, 'iteration': COHORT, 'profile': arm, 'timeout_seconds': 1800,
             'episode_key': f'n32r2_dev_t{task["task_id"]:02d}_{arm.lower()}_20261004',
             'budget_bucket': 'baseline' if arm == 'C0' else 'development'} for task in tasks for arm in ARMS]


def validate_draft(plan):
    w.require(plan['schema'] == 'n32-release-draft-v1' and plan['frozen'] is False
              and plan['release_enabled'] is False and plan['episodes'] == expected_rows(plan['worktree'])
              and plan['limits'] == LIMITS and plan['worker_contract'] == WORKER_CONTRACT
              and plan['deadline'] == DEADLINE and plan['stop_path'] == stop_path(plan['worktree'])
              and plan['phase_authorization'] == {'dev': False, 'validation': False, 'formal': False}
              and all(plan[k] is None for k in ('root_review', 'protocol', 'authority', 'execution_release')),
              'draft cannot claim authority/release')
    w.require(set(plan['expected_manifests']) == {r['episode_key'] for r in plan['episodes']}, 'manifest coverage')


def require_release(plan):
    # Deliberately no permissive interpretation of placeholder/root-like documents.
    # Root must review source, freeze protocol and integrate exact owning arithmetic.
    raise ValueError('N32 draft only: prospective root protocol/source/budget/release integration required')


def finite(value, label):
    w.require(type(value) in (int, float) and math.isfinite(value) and value >= 0, 'unknown/nonfinite ' + label)
    return value


def pre_dispatch(row, allowance, *, now, stop_path):
    """Pure guard over an authoritative snapshot; never changes charges/reserves.

    All *_remaining values must already include prior reservations, health costs
    and charges. Exact owning ledger-to-snapshot arithmetic is a root prerequisite.
    """
    w.require(not Path(stop_path).exists() and not Path(stop_path).is_symlink(), 'STOP pre-dispatch')
    w.require(now.tzinfo is not None, 'timezone-aware admission time')
    ends = dt.datetime.fromisoformat(allowance['authority_ends_at'].replace('Z', '+00:00'))
    starts = dt.datetime.fromisoformat(allowance['authority_starts_at'].replace('Z', '+00:00'))
    deadline = min(ends, dt.datetime.fromisoformat(DEADLINE.replace('Z', '+00:00')))
    need = 1840  # Both same-worker audits are inside the 1800s episode bound.
    w.require(starts <= now and now + dt.timedelta(seconds=need) <= deadline, 'deadline/authority full attempt unavailable')
    w.require(allowance['private_budget'] is True and allowance['gpu_idle'] is True
              and allowance['physical_gpu'] == 7 and allowance['gpu_uuid'] == GPU_UUID
              and allowance['live_handles'] == [] and allowance['unsettled_reservations'] == 0,
              'private GPU/settled snapshot required')
    w.require(row['iteration'] == COHORT and row['profile'] in ARMS and row['timeout_seconds'] == 1800
              and row['budget_bucket'] == ('baseline' if row['profile'] == 'C0' else 'development'), 'primary identity')
    for name in ('global_seconds_remaining', 'private_seconds_remaining', 'cohort_seconds_remaining'):
        w.require(finite(allowance[name], name) >= need, name + ' insufficient')
    protected = finite(allowance['protected_seconds_remaining'], 'protected seconds')
    w.require(allowance['global_seconds_remaining'] - protected >= need, 'protected reserve unavailable')
    w.require(allowance['cohort_seconds_remaining'] <= LIMITS['cohort_gpu_seconds'], 'cohort ceiling')
    bucket = row['budget_bucket']
    for name, value in (('bucket', allowance['bucket_attempts_remaining'][bucket]),
                        ('global', allowance['global_attempts_remaining']),
                        ('cohort', allowance['cohort_attempts_remaining']),
                        ('protected', allowance['protected_attempts_remaining'])):
        w.require(type(value) is int and value >= 0, 'unknown attempt allowance ' + name)
    w.require(allowance['bucket_attempts_remaining'][bucket] >= 1
              and allowance['global_attempts_remaining'] - allowance['protected_attempts_remaining'] >= 1
              and 1 <= allowance['cohort_attempts_remaining'] <= 30, 'attempt/protected cap')
    return need
