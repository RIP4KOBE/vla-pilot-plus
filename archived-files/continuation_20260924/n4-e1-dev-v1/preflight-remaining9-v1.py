#!/usr/bin/env python3
"""CPU/source/resource admission for the independently released E1 remaining nine."""
import datetime
import json
from pathlib import Path
import os
import sys

os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
W = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
B = Path(__file__).resolve().parent
D = B / 'first3-release-v1'
sys.path.insert(0, str(W / 'scripts'))
import qd_ed_final_runner as r
import qd_ed_n4e1_plan as n
import qd_ed_n4e1_supervise as supervisor


def ref(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': r.digest(path)}


plan_path = D / 'plan.checkpoint.frozen.json'
release_path = D / 'remaining9-execution-release.json'
review_path = D / 'remaining9-resource-preflight.json'
r.require(not review_path.exists(), 'preserve prior preflight')
plan, manifest, runtime = r.validate_plan(plan_path, root=W, require_frozen=True)
release = r.read_json(release_path)
n.execution_release(ref(release_path), plan_path, plan, runtime, release['episode_keys'], W, r)
supervisor.prerequisite(r, n, plan, runtime, W)
row = plan['episodes'][3]
r.require(row['episode_key'] == release['episode_keys'][0], 'remaining-nine first row differs')
with r.locked(W / 'data/qd-ed-runner.lock', nonblocking=True):
    events = r.read_events(W / 'data/attempt-ledger.jsonl')
    resources = r.read_events(W / 'data/gpu-healthcheck-ledger.jsonl')
    state = r.read_state(W / 'research-state.yaml')
    r.require(state['candidate']['active_execution_release'] == ref(B / 'execution-release.json'),
              'current state no longer names finished first-three release')
    r.require(not state.get('external_resource_hold', {}).get('active') and
              not state.get('external_resource_hold', {}).get('do_not_auto_resume'),
              'external resource hold active')
    r.require(r.authorized_gpu(state) == 3 and state['budget']['max_episode_attempts'] == 240
              and state['budget']['max_gpu_hours'] == 48, 'private GPU/budget differs')
    r.check_budget(state, events, row, resources)
    n.protected_budget(state, events, resources, row, 1800, r, plan=plan)
    n.admission(plan, runtime, row, events, resources, W, r)
    budget = r.budget_snapshot(events, resources)
    r.require(budget['running'] == 0, 'another owned worker remains')
result = {
    'schema': 'n4e1-remaining9-resource-preflight-v1', 'status': 'PASS_CPU_SOURCE_RESOURCE',
    'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'plan': ref(plan_path), 'release': ref(release_path),
    'checkpoint': plan['n4e1_cohort']['checkpoint_release'],
    'first3_root_review': ref(D / 'root-review.json'),
    'budget_snapshot': budget, 'first_remaining_row': row['episode_key'],
    'remaining_keys': release['episode_keys'], 'physical_gpu': 3,
    'protected_validation_formal_attempts': 100, 'protected_validation_formal_hours': 24,
    'CPU_source_model_inputs_verified': True, 'GPU_dispatches': 0,
    'scientific_promotion': False, 'protected_phase_authorized': False,
}
with review_path.open('x') as stream:
    json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write('\n')
print(json.dumps({'status': result['status'], 'review': ref(review_path),
                  'remaining_keys': len(release['episode_keys']), 'budget': budget}))
