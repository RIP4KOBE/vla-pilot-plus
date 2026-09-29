#!/usr/bin/env python3
"""Serial GPU3 N17 passive physics Dev supervisor; stop on first invalid cell."""
import hashlib
import json
from pathlib import Path
import signal

import audit_decision_evidence as native_audit
import qd_ed_available_gpu_queue as queue
import qd_ed_final_runner as runner


ROOT = Path(__file__).resolve().parents[1]
SESSION = ROOT.parent
PLAN = SESSION / 'variants/n17_passive_physics/plan.frozen.v2.json'
STATUS = SESSION / 'variants/n17_passive_physics/supervisor-status.json'
RELEASE = SESSION / 'variants/n17_passive_physics/execution-release.json'
COHORT = 'N17_PASSIVE_PHYSICS_DEV_20260929'


def verify_physics(path, *, max_steps=720):
    h = hashlib.sha256()
    count = 0
    valid_targets = 0
    contact_steps = 0
    previous_time = None
    with Path(path).open('rb') as stream:
        for raw in stream:
            h.update(raw)
            row = json.loads(raw)
            runner.require(row['schema'] == 'n17-passive-physics-step-v1'
                           and row['global_step'] == count and len(row['sent_action']) == 7
                           and row['object_bodies'], 'N17 physics row malformed')
            runner.require(previous_time is None or row['sim_time'] > previous_time,
                           'N17 simulator time not monotonic')
            previous_time = row['sim_time']
            valid_targets += int(row['target_tracker_valid'])
            contact_steps += int(bool(row['contacts_at_action_boundary']))
            count += 1
    runner.require(0 < count <= max_steps and valid_targets > 0,
                   'N17 physics trace missing steps or tracked target')
    return {'sha256': h.hexdigest(), 'steps': count,
            'tracked_target_steps': valid_targets, 'any_contact_steps': contact_steps}


def main():
    plan, _, _ = runner.validate_plan(PLAN, root=ROOT)
    runner.require(not STATUS.exists() and not RELEASE.exists(), 'N17 supervisor already started')
    devices = queue.inventory()
    runner.require(3 in devices and devices[3]['uuid'] == 'GPU-62052fa1-37e0-79dc-21aa-5c0f25c0c315',
                   'N17 physical GPU3 identity differs')
    queue.reservation_admission(devices[3])
    runner.gpu_admission(physical_gpu=3, expected_uuid=devices[3]['uuid'])
    runner.durable_json(RELEASE, {'schema': 'n17-passive-physics-release-v1',
                                 'plan_path': str(PLAN), 'plan_sha256': runner.digest(PLAN),
                                 'source_commit': plan['source_commit'],
                                 'physical_gpu': 3, 'episode_keys': [r['episode_key'] for r in plan['episodes']],
                                 'validation_authorized': False, 'formal_authorized': False})
    completed = []
    runner.durable_json(STATUS, {'status': 'started', 'completed': completed, 'physical_gpu': 3})
    try:
        for row in plan['episodes']:
            devices = queue.inventory()
            runner.require(3 in devices and devices[3]['uuid'] == 'GPU-62052fa1-37e0-79dc-21aa-5c0f25c0c315',
                           'N17 GPU3 disappeared')
            queue.reservation_admission(devices[3])
            runner.gpu_admission(physical_gpu=3, expected_uuid=devices[3]['uuid'])
            summaries = runner.run_plan(PLAN, split='dev', iteration=COHORT,
                                        episode_keys=[row['episode_key']], root=ROOT)
            runner.require(len(summaries) == 1, 'N17 one-cell result missing')
            result = summaries[0]
            output = Path(result['output_dir'])
            runner.require(result['event'] == 'valid' and result['outcome_valid'] is True,
                           'N17 Stage/evidence invalid; no automatic retry')
            native = native_audit.audit_episode(output / 'eds_eval/decision_evidence/episode_000',
                                                output / 'eds_eval/episode_compute.jsonl')
            runner.durable_json(output / 'eds_eval/decision-evidence-audit.json', native)
            runner.require(native.get('accepted') is True and native.get('evidence_complete') is True,
                           'N17 native evidence failed')
            witness = verify_physics(output / 'eds_eval/passive_physics_episode_000.jsonl')
            runner.durable_json(output / 'eds_eval/passive-physics-audit.json', witness)
            link_dir = SESSION / 'variants/n17_passive_physics/attempts'
            link_dir.mkdir(parents=True, exist_ok=True)
            (link_dir / result['attempt_id']).symlink_to(output, target_is_directory=True)
            completed.append({'attempt_id': result['attempt_id'], 'task_id': row['task_id'],
                              'success': result['success'], 'physics': witness})
            runner.durable_json(STATUS, {'status': 'cell_audited', 'completed': completed,
                                        'physical_gpu': 3})
        runner.durable_json(STATUS, {'status': 'completed_two_audited',
                                    'completed': completed, 'physical_gpu': 3})
    except BaseException as error:
        runner.durable_json(STATUS, {'status': 'interrupted' if isinstance(error, (KeyboardInterrupt, SystemExit)) else 'failed',
                                    'completed': completed, 'reason': type(error).__name__,
                                    'physical_gpu': 3})
        raise


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    main()
