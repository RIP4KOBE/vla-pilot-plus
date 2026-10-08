"""N34 identity, disabled drafts, finite admission and bare-plan rejection."""
import copy
import datetime as dt
import json
import math
from pathlib import Path
from scripts import qd_ed_n23_worker as w

ROOT = Path(__file__).resolve().parents[1]
# Fresh matched primaries; all historical attempts remain globally charged.
COHORT = 'N34R1_OBSERVED_JAW_APPROACH_DEV_20261008'
OLD_COHORT = 'N34_OBSERVED_JAW_APPROACH_DEV_20261008'
OLD_EPISODE = 'n34_dev_t00_c0_20261008'
RECOVERY_EPISODE = 'n34r1_dev_t00_c0_20261008'
# Fixed prospective provenance, taken from authority-v1.json. This is not approval.
REPLACEMENT = {
    'old_episode_key': OLD_EPISODE, 'new_episode_key': RECOVERY_EPISODE,
    'budget_bucket': 'recovery',
    'terminal_closure': {
        'path': '/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000610/terminal-closure-v1.json',
        'sha256': '212ed90e3cb06c5797175cf772f5808d09f024fbe3f398e7ba079154e092bff1'},
    'automatic': False,
}
ARMS = ('C0', 'Q0', 'N34')
DEADLINE = '2026-10-11T11:13:13Z'
GPU_UUID = 'GPU-48473162-9548-1a19-04aa-ea86c5349187'
LIMITS = {'primary_cells': 30, 'baseline': 9, 'development': 20, 'recovery': 1, 'automatic_recoveries': 0,
          'cohort_gpu_seconds': 18000, 'episode_seconds': 1800, 'cleanup_seconds': 40,
          'physical_gpu': 7, 'gpu_uuid': GPU_UUID}
CAPS = {'attempts': 1800, 'gpu_hours': 224.0,
        'buckets': {'baseline': 400, 'development': 1120, 'validation': 180, 'formal': 40, 'recovery': 60},
        'protected_gpu_hours': {'validation': 32.0, 'formal': 12.0}}
WORKER_CONTRACT = {'schema': 'n34-same-process-audit-v1', 'arms': list(ARMS),
                   'candidate_audits': ['generic', 'n34_observed_jaw_audit'], 'control_audits': ['generic', 'n31_native', 'no_n34_evidence'],
                   'timeout_includes_audit': True, 'external_manifest_required': True,
                   'automatic_recoveries': 0}


def ref(path):
    return {'path': str(Path(path).resolve()), 'sha256': w.sha(path)}


def stop_path(root=ROOT):
    """Locate the session STOP in supported checkouts; layout grants no release."""
    root = Path(root).resolve()
    if root.name == 'study_worktree':
        session = root.parent
    elif (root.name in ('implementation_worktree', 'production_worktree')
          and root.parent.parent.name == 'variants'):
        session = root.parent.parent.parent
    else:
        raise ValueError('unsupported N34 worktree layout: ' + str(root))
    # Do not resolve STOP itself: even a dangling symlink must stop admission.
    return str(session / 'autonomy_20261004/STOP')


def expected_rows(root=ROOT):
    tasks = json.loads((Path(root) / 'configs/qd_ed_final/n31_dev_task_identities.json').read_text())['tasks']
    w.require([x['task_id'] for x in tasks] == list(range(10)) and all(x['split'] == 'dev' for x in tasks), 'ten exposed Dev tasks')
    return [{**task, 'iteration': COHORT, 'profile': arm, 'timeout_seconds': 1800,
             'episode_key': f'n34r1_dev_t{task["task_id"]:02d}_{arm.lower()}_20261008',
             'budget_bucket': ('recovery' if task['task_id'] == 0 else 'baseline') if arm == 'C0' else 'development',
             'replacement': copy.deepcopy(REPLACEMENT) if task['task_id'] == 0 and arm == 'C0' else None} for task in tasks for arm in ARMS]


def require_row(row, root=ROOT):
    w.require(row in expected_rows(root), 'exact N34R1 identity/bucket/replacement')


def require_recovery_row(plan, row):
    """Narrow exception to the shared Dev/budget gate; grants no release."""
    w.require(plan['schema'] == 'n34-released-plan-v1'
              and plan['episodes'] == expected_rows(plan['worktree'])
              and row == plan['episodes'][0], 'exact N34R1 explicit recovery')


def event_binding(row, event):
    w.require(event.get('budget_bucket') == row['budget_bucket']
              and 'replacement' in event and event['replacement'] == row['replacement'],
              'N34R1 accounting/replacement binding')
    w.require(all(event.get(k) is None for k in ('retry_of', 'recovery_of')),
              'zero automatic recovery; arbitrary pointers forbidden')


def cohort_events(rows, events):
    """Select by either key or cohort, then reject spoofed identities/buckets."""
    index = {row['episode_key']: row for row in rows}
    local = []
    for event in events:
        identity = event.get('identity', {})
        w.require(isinstance(identity, dict), 'malformed journal identity')
        if (identity.get('iteration') == COHORT or event.get('attempt_id') in index
                or event.get('episode_key') in index):
            row = index.get(event.get('attempt_id'))
            w.require(row is not None and event.get('episode_key') == row['episode_key']
                      and identity == {k: row[k] for k in
                          ('split', 'iteration', 'profile', 'task_id', 'env_seed', 'policy_seed', 'init_index')},
                      'exact N34R1 journal identity')
            event_binding(row, event)
            local.append(event)
    return local


def require_replacement_history(events):
    """The old invalid remains charged in the global journal, never carried."""
    from scripts import qd_ed_final_runner as runner
    group = runner.event_groups(events).get(OLD_EPISODE, [])
    w.require([e['event'] for e in group] in
              (['reserved', 'dispatched', 'valid'], ['reserved', 'dispatched', 'aborted']),
              'old terminal invalid closure missing')
    w.require(all(e.get('episode_key') == OLD_EPISODE
                  and e.get('identity', {}).get('iteration') == OLD_COHORT
                  and e.get('budget_bucket') == 'baseline' for e in group)
              and group[-1].get('outcome_valid') is False
              and group[-1].get('success') is None
              and group[-1].get('required_cost_telemetry_complete') is not True,
              'old terminal invalid charge must remain unchanged')
    finite(group[-1]['gpu_process_wall_seconds'], 'old invalid charge')


def validate_draft(plan):
    w.require(plan['schema'] == 'n34-release-draft-v1' and plan['frozen'] is False
              and plan['release_enabled'] is False and plan['episodes'] == expected_rows(plan['worktree'])
              and plan['limits'] == LIMITS and plan['worker_contract'] == WORKER_CONTRACT
              and plan['deadline'] == DEADLINE and plan['stop_path'] == stop_path(plan['worktree'])
              and plan['phase_authorization'] == {'dev': False, 'validation': False, 'formal': False}
              and all(plan[k] is None for k in ('root_review', 'protocol', 'authority', 'execution_release')),
              'draft cannot claim authority/release')
    w.require(set(plan['expected_manifests']) == {r['episode_key'] for r in plan['episodes']}, 'manifest coverage')


def require_release(plan):
    # A bare plan can never confer authority. Consumers with caller-supplied
    # plan/release references must use qd_ed_n34_release.validate_release.
    raise ValueError('N34 draft only: explicit externally hashed plan and detached root release required')


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
    require_row(row)
    for name in ('global_seconds_remaining', 'private_seconds_remaining', 'cohort_seconds_remaining'):
        w.require(finite(allowance[name], name) >= need, name + ' insufficient')
    protected = finite(allowance['protected_seconds_remaining'], 'protected seconds')
    w.require(min(allowance['global_seconds_remaining'], allowance['private_seconds_remaining']) - protected >= need, 'protected reserve unavailable')
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
