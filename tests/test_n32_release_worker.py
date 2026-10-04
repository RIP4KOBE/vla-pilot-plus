"""Real recorder, generic/native audits, external anchors and metered receipts."""
import copy
from dataclasses import asdict
import json
from pathlib import Path
import pytest
import torch
from scripts import qd_ed_n32_worker as worker, qd_ed_n32_bridge as b, qd_ed_n32_contract as c
from scripts import qd_ed_n23_worker as w
from test_n32_release import draft, trusted, write
from test_n32_worker_entrypoint import worker_entrypoint_inventory
from test_rdt_steer import _patch_core_imports, stub_adapter, mock_batch, stub_steer


@pytest.mark.parametrize('arm', ['C0', 'Q0', 'N32'])
def test_exact_constructor_matches_full_policy_resolver(trusted, stub_steer, arm):
    plan, _, _ = trusted
    row = next(r for r in plan['episodes'] if r['profile'] == arm)
    manifest = w.read_ref(plan['expected_manifests'][row['episode_key']])
    # Constructor output itself is valid input; also compare Main's unnormalized
    # composed fields to catch defaults, types, pretest output paths and bindings.
    cfg, expected = b.compose_launch(manifest['argv'])
    raw = cfg['main']['eds_config']
    raw.update(reward_mode=cfg['main']['eds_eval']['reward_mode'], shuffle_seed=cfg['main']['eds_eval']['shuffle_seed'],
               mechanism_pretest=cfg['main']['eds_mechanism_pretest'])
    actual = asdict(stub_steer._resolve_eds_config_with_reference_defaults(raw))
    assert actual == expected


@pytest.mark.parametrize('arm', ['C0', 'Q0', 'N32'])
def test_same_process_external_manifest_native_receipt(trusted, monkeypatch, stub_adapter, mock_batch, worker_entrypoint_inventory, arm):
    import test_n32_runtime_native as synthetic
    plan, runtime, plan_ref = trusted
    row = next(r for r in plan['episodes'] if r['profile'] == arm)
    manifest = w.read_ref(plan['expected_manifests'][row['episode_key']])
    output = Path(manifest['output_dir'])
    context_ref = write(output / 'n32-worker-context.json', worker.context_for(plan_ref, row))
    identity = {'pid': 1234, 'proc_start_ticks': '567', 'boot_id': 'synthetic'}
    monkeypatch.setattr(w, 'process_identity', lambda: identity)
    uuid = c.GPU_UUID
    monkeypatch.setattr(worker, 'assigned_cuda_identity', lambda _: {'physical_gpu': 7, 'uuid': uuid,
        'physical_uuid': uuid, 'actual_uuid': uuid, 'actual_uuid_type': 'builtins.str',
        'actual_uuid_bytes_hex': None, 'logical_device': 'cuda:0'})
    monkeypatch.setattr(synthetic, 'runtime_cfg', lambda _: manifest['resolved_config'])
    def main(*args, **kwargs):
        synthetic.episode(output, monkeypatch, stub_adapter, mock_batch, arm=arm, disk=True)
    monkeypatch.setattr(worker.runpy, 'run_path', main)
    # External manifest was constructed before this call; no emitted trace feeds it.
    assert worker._run_in_process(context_ref) == 0, (output / 'eds_eval/n32-worker-receipt.json').read_text()
    receipt_ref = c.ref(output / 'eds_eval/n32-worker-receipt.json')
    report = worker.verify_receipt(context_ref, receipt_ref, {**identity, 'attempt_id': row['episode_key']})
    gate = 'n32_capture_dwell_audit' if arm == 'N32' else 'n31_capture_dwell_audit'
    assert report['accepted'] and report[gate]['profile'] == arm
    if arm == 'N32': assert report[gate]['runtime_identity'] == manifest['expected_runtime']
    assert not torch.cuda.is_initialized()
    from scripts.qd_ed_n32_supervise import c_identity
    calls = []
    def generic_result(out, got_row, profile, rt):
        calls.append((out, got_row, profile, rt))
        return {'success': False, 'required_cost_telemetry_complete': True}
    monkeypatch.setattr(b.runner, 'validate_result', generic_result)
    write(output / 'process.json', {**identity, 'attempt_id': row['episode_key']})
    terminal = dict(identity=c_identity(row), episode_key=row['episode_key'], attempt_id=row['episode_key'],
                    source_commit=plan['source']['commit'], plan_sha256=plan_ref['sha256'],
                    runtime_manifest_sha256=plan['runtime']['sha256'], init_row_sha256=row['init_row_sha256'],
                    physical_gpu=7, output_dir=str(output), outcome_valid=True, required_cost_telemetry_complete=True,
                    success=False, gpu_process_wall_seconds=1.0, guided_chunks=1, n32_worker_receipt=receipt_ref)
    assert worker.verify_terminal(plan_ref, row, terminal)['accepted']
    assert calls and calls[-1][1] == row and calls[-1][3] == runtime
    with pytest.raises(ValueError, match='generic result/cost'):
        worker.verify_terminal(plan_ref, row, {**terminal, 'success': True})
    with pytest.raises(ValueError, match='replay/duplicate'): worker._run_in_process(context_ref)
    receipt = w.read_ref(receipt_ref)
    # Feed actual -m inventories into the real parent receipt verifier while
    # retaining this fixture's full synthetic generic/native outcome evidence.
    worker_name = 'scripts.qd_ed_n32_worker'
    for phase, child_phase in (('loaded_before', 'before'), ('loaded_after', 'after')):
        receipt[phase][worker_name] = worker_entrypoint_inventory[child_phase][worker_name]
    receipt_ref = write(Path(receipt_ref['path']), receipt)
    assert worker.verify_receipt(context_ref, receipt_ref, {**identity, 'attempt_id': row['episode_key']})['accepted']
    for phase in ('loaded_before', 'loaded_after'):
        for fault in ('missing', 'origin', 'spec_name', 'module_name', 'sha256', 'path', 'metadata', 'phase_drift'):
            bad = copy.deepcopy(receipt)
            record = bad[phase][worker_name]
            if fault == 'missing': del bad[phase][worker_name]
            elif fault == 'metadata': record.pop('spec_name')
            elif fault == 'path': record.update(bad[phase]['scripts.qd_ed_n32_bridge'])
            elif fault == 'phase_drift': record['module_name'] = worker_name
            else: record[fault] = 'wrong'
            bad_ref = write(Path(receipt_ref['path']), bad)
            with pytest.raises(ValueError):
                worker.verify_receipt(context_ref, bad_ref, {**identity, 'attempt_id': row['episode_key']})
    # Exact legacy omission reaches the parent's original strict failure.
    bad = copy.deepcopy(receipt)
    bad['loaded_before'] = worker_entrypoint_inventory['old']
    bad_ref = write(Path(receipt_ref['path']), bad)
    with pytest.raises(ValueError, match='loaded source attestation absent'):
        worker.verify_receipt(context_ref, bad_ref, {**identity, 'attempt_id': row['episode_key']})
    write(Path(receipt_ref['path']), receipt)
    for fault in ('expected_manifest', 'process', 'native_counts', 'source', 'row', 'loaded_after'):
        bad = copy.deepcopy(receipt)
        if fault == 'expected_manifest': bad[fault]['sha256'] = 'b'*64
        if fault == 'process': bad[fault]['pid'] += 1
        if fault == 'native_counts': bad[fault]['guided_decisions'] = 99
        if fault == 'source': bad[fault]['commit'] = 'b'*40
        if fault == 'row': bad[fault]['task_id'] = 9
        if fault == 'loaded_after': bad[fault] = {}
        bad_ref = write(Path(receipt_ref['path']), bad)
        with pytest.raises(ValueError): worker.verify_receipt(context_ref, bad_ref, {**identity, 'attempt_id': row['episode_key']})
    write(Path(receipt_ref['path']), receipt)
    # Parent cannot replace expected process identity with the worker's own claim.
    with pytest.raises(ValueError): worker.verify_receipt(context_ref, receipt_ref, {**identity, 'pid': 4321, 'attempt_id': row['episode_key']})


def test_public_worker_remains_disabled(trusted, tmp_path):
    plan, _, plan_ref = trusted
    row = plan['episodes'][2]
    ref = write(tmp_path / 'context.json', worker.context_for(plan_ref, row))
    with pytest.raises(ValueError, match='draft only'): worker.run_worker(ref)


def test_missing_evidence_is_invalid_receipt(trusted, monkeypatch):
    plan, _, plan_ref = trusted
    row = plan['episodes'][5]
    manifest = w.read_ref(plan['expected_manifests'][row['episode_key']])
    output = Path(manifest['output_dir'])
    context_ref = write(output / 'n32-worker-context.json', worker.context_for(plan_ref, row))
    monkeypatch.setattr(worker.runpy, 'run_path', lambda *args, **kwargs: None)
    monkeypatch.setattr(worker, 'assigned_cuda_identity', lambda _: {})
    assert worker._run_in_process(context_ref) == 2
    receipt_ref = c.ref(output / 'eds_eval/n32-worker-receipt.json')
    receipt = w.read_ref(receipt_ref)
    assert receipt['classification'] == 'INVALID' and receipt['accepted'] is False
    assert receipt['worker_wall_seconds'] > 0 and receipt['http_counters'] == 'Unknown'
    with pytest.raises(ValueError):
        worker.verify_receipt(context_ref, receipt_ref, {**receipt['process'], 'attempt_id': row['episode_key']})
