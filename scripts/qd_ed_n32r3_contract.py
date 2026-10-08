"""N32R3 operational continuation, separate from the immutable N32R2 contract."""
import datetime as dt
from pathlib import Path
from scripts import qd_ed_n23_worker as w, qd_ed_n32_contract as parent

ROOT = parent.ROOT
ARMS = parent.ARMS
DEADLINE = parent.DEADLINE
GPU_UUID = parent.GPU_UUID
COHORT = 'N32R3_ARCHIVE_ELIGIBLE_CAPTURE_CONTINUATION_DEV_20261008'
OLD_INVALID = 'n32r2_dev_t04_n32_20261004'
RECOVERY = 'n32r3_recovery_t04_n32_20261008'
BASE_SOURCE = '1065f38122379a515b60a9a424f574330405b66f'
LIMITS = {'new_attempts': 16, 'baseline': 5, 'development': 10, 'recovery': 1,
          'automatic_recoveries': 0, 'continuation_gpu_seconds': 30600,
          'episode_seconds': 1800, 'cleanup_seconds': 40, 'physical_gpu': 7, 'gpu_uuid': GPU_UUID}
WORKER_CONTRACT = {**parent.WORKER_CONTRACT, 'schema': 'n32r3-same-process-audit-v1'}
PROMOTION = {'all_valid_cells': 30, 'n32_min_successes': 5, 'matched_controls_required': True}
SEMANTIC_FIELDS = ('task_id', 'profile', 'split', 'seed_block', 'env_seed', 'policy_seed',
                   'init_index', 'init_row_sha256', 'init_file_sha256', 'bddl_sha256')
ref, finite, stop_path = parent.ref, parent.finite, parent.stop_path


def read_ref(reference):
    """Preparation references may additionally commit exact byte length."""
    w.require(isinstance(reference, dict) and set(reference) in
              ({'path', 'sha256'}, {'path', 'sha256', 'bytes'}), 'reference fields')
    result = w.read_ref({k: reference[k] for k in ('path', 'sha256')})
    if 'bytes' in reference:
        w.require(type(reference['bytes']) is int and Path(reference['path']).stat().st_size == reference['bytes'], 'reference length')
    return result


def same_ref(a, b):
    return all(a[k] == b[k] for k in ('path', 'sha256'))


def expected_rows(root=ROOT):
    rows = []
    for old in parent.expected_rows(root)[14:]:
        recovery = old['episode_key'] == OLD_INVALID
        rows.append({**old, 'iteration': COHORT,
                     'episode_key': RECOVERY if recovery else f'n32r3_dev_t{old["task_id"]:02d}_{old["profile"].lower()}_20261008',
                     'budget_bucket': 'recovery' if recovery else old['budget_bucket']})
    return rows


def recovery_of(row):
    return OLD_INVALID if row['episode_key'] == RECOVERY else None


def require_recovery_row(plan, row):
    w.require(plan['schema'] == 'n32r3-released-plan-v1' and plan['episodes'] == expected_rows(plan['worktree'])
              and row == plan['episodes'][0] and row['episode_key'] == RECOVERY
              and not row.get('retry_of'), 'exact versioned explicit recovery')


def commitments(plan, row):
    w.require(row in expected_rows(plan['worktree']), 'continuation row')
    return {**{k: plan[k] for k in ('parent_plan', 'parent_release', 'parent_review', 'carry_forward_map',
                                   'command_candidates', 'source_continuity', 'scientific_source', 'preparation_review')},
            **({'command_path_amendment': plan['command_path_amendment']}
               if 'command_path_amendment' in plan else {}),
            'semantic_row': {k: row[k] for k in SEMANTIC_FIELDS},
            'recovery_of': recovery_of(row), 'retry_of': None}


def require_release(_):
    raise ValueError('N32R3 requires a separately adopted plan and detached root release')


def pre_dispatch(row, allowance, *, now, stop_path):
    w.require(not Path(stop_path).exists() and not Path(stop_path).is_symlink(), 'STOP pre-dispatch')
    w.require(now.tzinfo is not None, 'timezone-aware admission time')
    starts = dt.datetime.fromisoformat(allowance['authority_starts_at'].replace('Z', '+00:00'))
    ends = min(dt.datetime.fromisoformat(x.replace('Z', '+00:00')) for x in (allowance['authority_ends_at'], DEADLINE))
    w.require(starts <= now and now + dt.timedelta(seconds=1840) <= ends, 'deadline/authority full1840s unavailable')
    w.require(row in expected_rows(), 'exact continuation identity')
    w.require(allowance['private_budget'] is True and allowance['gpu_idle'] is True
              and allowance['physical_gpu'] == 7 and allowance['gpu_uuid'] == GPU_UUID
              and allowance['live_handles'] == [] and allowance['unsettled_reservations'] == 0, 'private idle settled GPU')
    for key in ('global_seconds_remaining', 'private_seconds_remaining', 'cohort_seconds_remaining'):
        w.require(finite(allowance[key], key) >= 1840, key + ' insufficient')
    w.require(allowance['cohort_seconds_remaining'] <= 30600, 'continuation seconds ceiling')
    w.require(allowance['global_seconds_remaining'] - finite(allowance['protected_seconds_remaining'], 'protected seconds') >= 1840, 'protected seconds')
    for key in ('global_attempts_remaining', 'cohort_attempts_remaining', 'protected_attempts_remaining'):
        w.require(type(allowance[key]) is int and allowance[key] >= 0, 'unknown attempt balance')
    w.require(1 <= allowance['cohort_attempts_remaining'] <= 16 and
              allowance['global_attempts_remaining'] - allowance['protected_attempts_remaining'] >= 1, 'attempt reserve/cap')
    bucket = row['budget_bucket']
    for field in ('bucket_attempts_remaining', 'local_bucket_attempts_remaining'):
        value = allowance[field][bucket]
        w.require(type(value) is int and value >= 1, 'bucket exhausted/unknown')
    w.require(allowance['local_bucket_attempts_remaining'][bucket] <= LIMITS[bucket], 'local bucket cap')
    return 1840
