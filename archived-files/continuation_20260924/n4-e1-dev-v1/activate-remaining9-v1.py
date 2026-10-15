#!/usr/bin/env python3
"""Atomically activate the reviewed remaining-nine GPU3 release in W only."""
import json
import os
from pathlib import Path
import sys
import tempfile
import yaml

W = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
B = Path(__file__).resolve().parent
D = B / 'first3-release-v1'
sys.path.insert(0, str(W / 'scripts'))
import qd_ed_final_runner as r
import qd_ed_n4e1_plan as n


def ref(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': r.digest(path)}


review = r.read_json(D / 'remaining9-resource-preflight.json')
release_path = D / 'remaining9-execution-release.json'
plan_path = D / 'plan.checkpoint.frozen.json'
plan = r.read_json(plan_path)
runtime = r.read_json(plan['runtime_manifest_path'])
release = r.read_json(release_path)
r.require(review['status'] == 'PASS_CPU_SOURCE_RESOURCE' and review['release'] == ref(release_path),
          'reviewed remaining-nine release differs')
n.execution_release(ref(release_path), plan_path, plan, runtime, release['episode_keys'], W, r)
first_status = r.read_json(B / 'first3-v1/status.json')
first_result = r.read_json(B / 'first3-v1/launch-result.json')
r.require(first_status['status'] == 'completed' and first_result['exit_code'] == 0
          and first_status['completed_keys'] == [row['episode_key'] for row in plan['episodes'][:3]],
          'first-three supervisor did not complete cleanly')
with r.locked(W / 'data/qd-ed-runner.lock', nonblocking=True):
    with r.locked(W / 'data/qd-ed-state.lock'):
        state = r.read_state(W / 'research-state.yaml')
        events = r.read_events(W / 'data/attempt-ledger.jsonl')
        resources = r.read_events(W / 'data/gpu-healthcheck-ledger.jsonl')
        r.require(state['candidate']['active_execution_release'] == ref(B / 'execution-release.json')
                  and state['candidate']['online_dispatch_authorized'] is True,
                  'first-three state authorization changed')
        r.require(not state.get('external_resource_hold', {}).get('active') and
                  not state.get('external_resource_hold', {}).get('do_not_auto_resume'),
                  'new external resource hold')
        r.require(r.budget_snapshot(events, resources) == review['budget_snapshot'],
                  'post-review private budget changed')
        r.check_budget(state, events, plan['episodes'][3], resources)
        n.protected_budget(state, events, resources, plan['episodes'][3], 1800, r, plan=plan)
        n.admission(plan, runtime, plan['episodes'][3], events, resources, W, r)
        candidate = state['candidate']
        candidate['original_correctness_checkpoint'] = candidate['correctness_checkpoint']
        candidate['original_first3_root_review'] = candidate['first3_root_review']
        candidate['correctness_checkpoint'] = ref(D / 'correctness-checkpoint.json')
        candidate['first3_root_review'] = ref(D / 'root-review.json')
        candidate['latest_report'] = ref(Path(plan['artifact_root']) /
                                         'continuation_20260923/n4-e1-first3-report-v1/report.json')
        candidate['active_execution_release'] = ref(release_path)
        candidate['n4e1_checkpoint_plan'] = ref(plan_path)
        candidate['n4e1_remaining9_resource_preflight'] = ref(D / 'remaining9-resource-preflight.json')
        candidate['status'] = 'N4E1_DEV_REMAINING9_RELEASED'
        candidate['engineering_dependency']['status'] = 'DEV_REMAINING9_RELEASED'
        owned = state['resource_isolation']['owned_supervisor']
        r.require(owned['pid'] == first_result['supervisor_pid'], 'prior owned supervisor differs')
        owned['terminal_status'] = 'EXIT_0_COMPLETED'
        owned['launch_result'] = ref(B / 'first3-v1/launch-result.json')
        path = W / 'research-state.yaml'
        handle, temporary = tempfile.mkstemp(prefix='.research-state.n4e1-', suffix='.yaml', dir=W)
        try:
            with os.fdopen(handle, 'w') as stream:
                yaml.safe_dump(state, stream, sort_keys=False, allow_unicode=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            descriptor = os.open(W, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
print(json.dumps({'status': 'N4E1_DEV_REMAINING9_RELEASED', 'active_release': ref(release_path)}))
