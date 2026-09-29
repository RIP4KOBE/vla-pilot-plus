#!/usr/bin/env python3
"""Freeze hardware-only GPU7 child of N18 Dev; never dispatch."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess

import qd_ed_final_runner as runner
import qd_ed_available_gpu_queue as queue
import qd_ed_n18_dev_contract as contract

ROOT = Path(__file__).resolve().parents[1]
PARENT = contract.RUN_DIR / 'plan.frozen.v1.json'
OUTPUT = contract.RUN_DIR / 'plan.frozen.v3.gpu7.json'
# Runtime fingerprints require the physical owned root, not its archival symlink.
ARTIFACT_DIR = (Path(json.loads(PARENT.read_text())['artifact_root']) /
                'continuation_20260929/n18-close-then-lift-dev-v1/gpu7-rebind')


def committed_record(relative, head):
    actual = (ROOT / relative).read_bytes()
    committed = subprocess.check_output(['git', 'show', head + ':' + relative], cwd=ROOT)
    runner.require(actual == committed, 'uncommitted N18 GPU7 source: ' + relative)
    return {'path': relative, 'sha256': hashlib.sha256(actual).hexdigest()}


def main():
    runner.require(not OUTPUT.exists(), 'N18 GPU7 child already frozen')
    parent = runner.read_json(PARENT)
    runner.require(len(parent['episodes']) == 12
                   and parent['n18_cohort']['cohort_id'] == contract.COHORT,
                   'N18 GPU3 parent identities changed')
    state = runner.read_state(ROOT / 'research-state.yaml')
    snapshot = runner.budget_snapshot(
        runner.read_events(ROOT / 'data/attempt-ledger.jsonl'),
        runner.read_events(ROOT / 'data/gpu-healthcheck-ledger.jsonl'))
    runner.require(runner.authorized_gpu(state) == 7 and snapshot['running'] == 0
                   and not any(event.get('event') == 'dispatched'
                               and event.get('identity', {}).get('iteration') == contract.COHORT
                               for event in runner.read_events(ROOT / 'data/attempt-ledger.jsonl')),
                   'N18 GPU7 rebind requires zero prior cohort dispatches')
    devices = queue.inventory()
    runner.require(7 in devices and devices[7]['uuid'] == contract.GPU7_UUID,
                   'GPU7 identity differs')
    queue.reservation_admission(devices[7])
    runner.gpu_admission(physical_gpu=7, expected_uuid=contract.GPU7_UUID)
    mapping = queue.current_metadata(7, root=ROOT)
    runner.require(mapping['uuid'] == contract.GPU7_UUID
                   and mapping['egl_device_index'] == 4
                   and mapping['metadata_mapping_verified'] is True,
                   'GPU7 EGL mapping differs')
    original_runtime = runner.read_json(contract.E2_RUNTIME)
    proof = queue.find_probe(original_runtime, mapping,
        runner.read_events(ROOT / 'data/gpu-healthcheck-ledger.jsonl'), root=ROOT)
    runner.require(isinstance(proof, dict)
                   and proof.get('resource_id') == contract.GPU7_PROOF,
                   'N18 GPU7 reusable CUDA/EGL proof unavailable')
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    metadata_path = ARTIFACT_DIR / 'egl-device-metadata.gpu7.v2.json'
    runtime_path = ARTIFACT_DIR / 'runtime-manifest.gpu7.frozen.v2.json'
    runner.require(not metadata_path.exists() and not runtime_path.exists(),
                   'N18 GPU7 runtime already frozen')
    runner.durable_json(metadata_path, mapping)
    runtime = queue.clone_runtime(original_runtime, mapping, metadata_path, proof)
    runner.durable_json(runtime_path, runtime)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    plan = copy.deepcopy(parent)
    code = {record['path'] for record in parent['code_files']}
    code |= runner.REQUIRED_CODE
    code |= {'scripts/qd_ed_n18_gpu7_prepare.py', 'scripts/qd_ed_available_gpu_queue.py',
             'scripts/qd_ed_n18_dev_contract.py', 'scripts/qd_ed_n18_dev_supervise.py',
             'scripts/qd_ed_final_runner.py'}
    plan['code_files'] = [committed_record(relative, head) for relative in sorted(code)]
    plan.update(source_commit=head,
                runtime_manifest_path=str(runtime_path),
                runtime_manifest_sha256=runner.digest(runtime_path),
                egl_mapping_verified=True,
                derived_from={'path': str(PARENT), 'sha256': runner.digest(PARENT)},
                n18_gpu7_rebind={
                    'schema': 'n18-gpu7-hardware-only-rebind-v1',
                    'parent_plan': {'path': str(PARENT), 'sha256': runner.digest(PARENT)},
                    'addendum': {'path': str(contract.GPU7_ADDENDUM),
                                 'sha256': runner.digest(contract.GPU7_ADDENDUM)},
                    'runtime': {'path': str(runtime_path), 'sha256': runner.digest(runtime_path)},
                    'physical_gpu': 7, 'uuid': contract.GPU7_UUID,
                    'egl_device_index': 4,
                    'reused_probe_resource_id': contract.GPU7_PROOF})
    runner.durable_json(OUTPUT, plan)
    runner.validate_plan(OUTPUT, root=ROOT)
    print(json.dumps({'schema': 'n18-gpu7-plan-frozen-v1',
                      'plan': str(OUTPUT), 'sha256': runner.digest(OUTPUT),
                      'source_commit': head, 'gpu': 7,
                      'gpu_dispatched': False}, sort_keys=True))


if __name__ == '__main__':
    main()
