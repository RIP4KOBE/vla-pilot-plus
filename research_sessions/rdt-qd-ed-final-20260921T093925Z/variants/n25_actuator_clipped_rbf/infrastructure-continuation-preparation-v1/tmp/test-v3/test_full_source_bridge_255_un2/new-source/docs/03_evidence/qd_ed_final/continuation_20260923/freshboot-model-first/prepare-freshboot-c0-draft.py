#!/usr/bin/env python3
"""CPU-only prospective C0 draft preparation; never freezes or dispatches.

Run only after the separately frozen fresh-boot model-first resource completes.
This is a new engineering condition, not an N1 retry or a replacement outcome.
"""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
ARTIFACT = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')
BOOT = '2a1fa95f-ab0d-488c-a298-fc488ddd2af7'
PROTOCOL = 'experiments/iteration_001_execution_intent/gpu3-freshboot-c0-common-condition.md'
ITERATION = 'FRESHBOOT_C0_20260923'
KEY = 'freshboot_c0_t00_20260923'
WORKER_SHA = '63d0acaed3b5c1a3088dab79f49c2f224374406a0d9078c4c3aeeb2364eb2519'


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-head', required=True)
    p.add_argument('--pass-result', type=Path, required=True)
    p.add_argument('--pass-contract', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(argv)
    sys.path.insert(0, str(ROOT / 'scripts'))
    import qd_ed_final_runner as r
    import qd_ed_available_gpu_queue as q
    r.require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT, 'fresh boot differs')
    for path in (args.pass_result, args.pass_contract, args.output):
        r.owned(path, ARTIFACT / 'continuation_20260923')
    r.require(not args.output.exists(), 'refusing to overwrite a draft')
    result, contract = r.read_json(args.pass_result), r.read_json(args.pass_contract)
    r.require(result.get('event') == 'completed' and not result.get('faults'), 'fresh-boot prerequisite did not pass')
    r.require(result['resource_id'] == contract['resource_id'] and result['contract_sha256'] == r.digest(args.pass_contract), 'prerequisite linkage differs')
    r.require(Path(contract['output_dir']).resolve() == args.pass_result.parent.resolve(), 'prerequisite output path differs')
    r.require(contract['boot_id'] == result['boot_id'] == BOOT and contract['physical_gpu'] == 3, 'prerequisite boot/GPU differs')
    r.require(contract['source_script_sha256'] == WORKER_SHA and result['source_script_sha256'] == WORKER_SHA, 'prerequisite worker changed')
    r.require(result['diagnostic_evidence']['model_loaded_before_scene'] is True and result['frame_count'] == 10, 'prerequisite original completion missing')
    with r.locked(ROOT / 'data/qd-ed-runner.lock', nonblocking=True):
        events, resources = q.no_unfinished(ROOT)
        state = r.read_state(ROOT / 'research-state.yaml')
        r.require(q.candidate_indices(state) == [3] and r.authorized_gpu(state) == 3, 'GPU3-only authorization required')
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        r.require(head == args.source_head, 'source HEAD differs')
        base_path = ROOT / 'data/qd-ed-gpu3-c0-render-plan.json'
        plan = copy.deepcopy(r.read_json(base_path))
        r.require(len(plan['episodes']) == 1, 'base plan row set differs')
        row = copy.deepcopy(plan['episodes'][0])
        r.require(all(row[k] == v for k, v in {'profile': 'C0', 'task_id': 0, 'split': 'dev', 'seed_block': 'dev', 'env_seed': 1969522881, 'policy_seed': 1969522881, 'init_index': 0, 'timeout_seconds': 1800}.items()), 'base C0 identity differs')
        row.pop('retry_of', None)
        row.update(iteration=ITERATION, episode_key=KEY, budget_bucket='development')
        r.require(not any(e.get('episode_key') == KEY for e in events), 'prospective key already consumed/reserved')
        r.check_retry(events, row)
        timeout = r.check_budget(state, events, row, resources,
            r.read_events(ROOT / 'data/gpu-hour-reservation-ledger.jsonl'), physical_gpu=3)
        r.require(timeout == 1800, 'remaining unprotected budget cannot preserve full timeout')
        r.require(state['budget'].get('gpu_hour_reservations', {'validation': 14., 'formal': 10.}) == {'validation': 14., 'formal': 10.}, 'protected 24 GPU-hour policy differs')
        runtime = r.read_json(plan['runtime_manifest_path'])
        r.require(r.digest(plan['runtime_manifest_path']) == plan['runtime_manifest_sha256'], 'base runtime changed')
        r.require(r.runtime_gpu(runtime, state) == 3, 'base runtime is not GPU3')
        for label in ('profiles', 'runtime_inventory', 'seed_plan'):
            r.require(r.digest(plan[label + '_path']) == plan[label + '_sha256'], label + ' identity differs')
            r.require(plan[label + '_sha256'] == contract[label + '_sha256'], label + ' differs from fresh-boot prerequisite')
        for record in contract['source_files']:
            r.require(r.digest(r.owned(ROOT / record['path'], ROOT)) == record['sha256'],
                'prerequisite source changed: ' + record['path'])
        for key in ('recovery_note', 'recovery_protocol', 'recovery_provenance', 'ordering_amendment', 'preflight_index', 'preflight_index_sha256', 'frozen_at', 'diagnostic_only', 'native_probe_contract', 'queue_contract', 'hardware_selection', 'candidate_profiles'):
            plan.pop(key, None)
        scientific = set(plan['scientific_config_files']) | {PROTOCOL,
            'experiments/iteration_001_execution_intent/gpu3-model-first-diagnostic.md',
            'experiments/iteration_001_execution_intent/gpu3-freshboot-model-first-control.md'}
        paths = {row['path'] for row in plan['code_files']} | scientific | r.REQUIRED_CODE | {
            'scripts/qd_ed_available_gpu_queue.py', 'scripts/qd_ed_gpu_probe.py', 'scripts/qd_ed_runtime_setup.py',
            'docs/03_evidence/qd_ed_final/continuation_20260923/freshboot-model-first/prepare-freshboot-c0-draft.py',
            'docs/03_evidence/qd_ed_final/continuation_20260923/freshboot-model-first/native-dependency-freeze.json',
            'docs/03_evidence/qd_ed_final/continuation_20260923/freshboot-model-first/supervise-freshboot-c0.py'}
        for relative in sorted(paths):
            file = r.owned(ROOT / relative, ROOT)
            committed = subprocess.check_output(['git', 'show', head + ':' + relative], cwd=ROOT)
            r.require(file.read_bytes() == committed, 'source is not exactly committed: ' + relative)
        plan.update(frozen=False, source_commit=head, episodes=[row],
            phase_authorization={'dev': True, 'validation': False, 'formal': False},
            scientific_config_files=sorted(scientific),
            code_files=[{'path': path, 'sha256': r.digest(ROOT / path)} for path in sorted(paths)],
            diagnostic_scope='One prospective fresh-boot production C0 dev episode; not an N1 retry, promotion sample or algorithm score',
            resource_amendment=PROTOCOL, boot_id=BOOT,
            engineering_prerequisite={'result_path': str(args.pass_result.resolve()), 'result_sha256': r.digest(args.pass_result),
                'contract_path': str(args.pass_contract.resolve()), 'contract_sha256': r.digest(args.pass_contract),
                'resource_id': result['resource_id'], 'boot_id': BOOT},
            preparation_provenance={'base_plan_path': str(base_path), 'base_plan_sha256': r.digest(base_path),
                'builder_path': str(Path(__file__).resolve()), 'builder_sha256': r.digest(__file__)})
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as stream:
            json.dump(plan, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write('\n')
        r.validate_plan(args.output, root=ROOT, require_frozen=False)
    print(json.dumps({'draft': str(args.output), 'frozen': False, 'GPU_dispatches': 0, 'episode_key': KEY, 'iteration': ITERATION}))


if __name__ == '__main__': main()
