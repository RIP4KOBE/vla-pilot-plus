"""N32 metered worker and hash-only parent receipt verification.

The public launch requires a detached root release. Draft contexts remain closed.
`_run_in_process` provides the same-PID implementation tested on synthetic CPU data.
"""
import os
from pathlib import Path
import runpy
import sys
import time

from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n32_bridge as b, qd_ed_n32_contract as c
from scripts import qd_ed_n32_native as n32, qd_ed_n31_native as controls
from scripts import audit_decision_evidence as generic
from scripts.qd_ed_audit_backend import create_backend, assigned_cuda_identity, canonical_cuda_uuid


def attest_worker_loaded(root, source):
    """Bind the executing worker, including Python's -m __main__, to frozen bytes.

    Do not import a second worker or register an alias: attest this function's
    actual module. Main's temporary __main__ is restored by runpy before the
    post-run inventory. This is source attestation, not bytecode attestation.
    """
    loaded = b.attest_loaded(root, source)
    canonical = 'scripts.qd_ed_n32_worker'
    relative = 'scripts/qd_ed_n32_worker.py'
    module = sys.modules.get(__name__)
    spec = getattr(module, '__spec__', None)
    w.require(module is not None and vars(module) is globals()
              and __name__ in ('__main__', canonical)
              and getattr(spec, 'name', None) == canonical
              and getattr(spec, 'has_location', False), 'worker module spec differs')
    expected = Path(root).resolve() / relative
    file, origin = getattr(module, '__file__', None), getattr(spec, 'origin', None)
    w.require(file and origin and expected.is_file() and not expected.is_symlink()
              and Path(file).resolve() == expected and Path(origin).resolve() == expected,
              'worker module origin differs')
    actual = w.sha(expected)
    index = {v['path']: v['sha256'] for v in source['files']}
    w.require(index.get(relative) == actual, 'worker source not frozen')
    record = {'path': relative, 'sha256': actual, 'module_name': __name__,
              'spec_name': spec.name, 'origin': str(expected)}
    # Any separately imported canonical copy must already pass the generic
    # origin/hash checks and agree with this executing module's source.
    if canonical in loaded:
        w.require(loaded[canonical] == {'path': relative, 'sha256': actual},
                  'worker canonical source differs')
    loaded[canonical] = record
    return loaded


def validate_context(reference):
    context = w.read_ref(reference)
    w.require(set(context) == {'schema', 'plan', 'expected_manifest', 'episode_key', 'attempt_id', 'main_argv', 'worker_contract'} | ({'release'} if 'release' in context else set()), 'worker context fields')
    w.require(context['schema'] == 'n32-worker-context-v1' and context['worker_contract'] == c.WORKER_CONTRACT, 'worker contract')
    plan = w.read_ref(context['plan'])
    if 'release' in context:
        from scripts import qd_ed_n32_release as release
        released, _, _ = release.validate_release(context['plan'], context['release'])
        w.require(released == plan, 'released worker plan differs')
    else:
        c.validate_draft(plan)
    rows = [r for r in plan['episodes'] if r['episode_key'] == context['episode_key']]
    w.require(len(rows) == 1 and context['attempt_id'] == context['episode_key'], 'exact primary attempt')
    row = rows[0]
    w.require(context['expected_manifest'] == plan['expected_manifests'][row['episode_key']], 'plan/command external anchor')
    runtime = w.read_ref(plan['runtime'])
    manifest = b.verify_manifest(context['expected_manifest'], plan, runtime, row)
    w.require(context['main_argv'] == manifest['argv'][1:], 'exact candidate command')
    w.require(runtime['gpu_mapping']['physical_gpu'] == 7 and runtime['gpu_mapping']['uuid'] == c.GPU_UUID, 'assigned GPU mapping')
    return context, plan, runtime, row, manifest


def context_for(plan_ref, row, release_ref=None):
    plan = w.read_ref(plan_ref)
    manifest_ref = plan['expected_manifests'][row['episode_key']]
    manifest = w.read_ref(manifest_ref)
    w.require(row in plan['episodes'] and manifest['row'] == row, 'context row')
    return {'schema': 'n32-worker-context-v1', 'plan': plan_ref, 'expected_manifest': manifest_ref,
            'episode_key': row['episode_key'], 'attempt_id': row['episode_key'],
            'main_argv': manifest['argv'][1:], 'worker_contract': c.WORKER_CONTRACT,
            **({'release': release_ref} if release_ref is not None else {})}


def native_counts(profile, output, report, expected, guided=None):
    if profile == 'N32':
        return n32.from_output(profile, output, report, guided, expected_runtime=expected)
    return controls.from_output(profile, output, report, guided)


def evidence(output):
    result = w.evidence_record(output)
    metrics = Path(output) / 'eds_eval/eds_metrics.jsonl'
    w.require(not metrics.is_symlink(), 'linked metrics')
    result['metrics'] = {'present': metrics.is_file(), 'sha256': w.sha(metrics) if metrics.is_file() else None}
    return result


def verify_dispatch_record(context_ref, context, output, identity):
    """A released child must match the parent's durable record before Main."""
    record = w.read_ref(c.ref(Path(output) / 'process.json'))
    w.require({k: record[k] for k in ('pid', 'proc_start_ticks', 'boot_id')} == identity
              and record['attempt_id'] == context['attempt_id']
              and record['context'] == context_ref and record['release'] == context['release'],
              'parent dispatch process/context/release differs')


def _run_in_process(context_ref):
    """Internal implementation, to be called only by a root-released bounded runner."""
    context, plan, runtime, row, manifest = validate_context(context_ref)
    root, output = Path(plan['worktree']), Path(manifest['output_dir'])
    identity = w.process_identity()
    if 'release' in context:
        verify_dispatch_record(context_ref, context, output, identity)
    started = time.perf_counter()
    receipt_path = output / 'eds_eval/n32-worker-receipt.json'
    start_path = output / 'eds_eval/n32-worker-start.json'
    report_path = output / 'eds_eval/decision-evidence-audit.json'
    w.require(not any(p.exists() for p in (receipt_path, start_path, report_path)), 'replay/duplicate worker artifacts')
    w.atomic_json(start_path, {'context': context_ref, 'process': identity})
    receipt = {'schema': 'n32-worker-receipt-v1', 'context': context_ref, 'plan': context['plan'],
               'expected_manifest': context['expected_manifest'], 'source': plan['source'], 'row': row,
               'attempt_id': context['attempt_id'], 'process': identity, 'accepted': False,
               'main_exit_code': None, 'http_counters': 'Unknown'}
    old_argv, old_cwd = sys.argv, Path.cwd()
    try:
        receipt['loaded_before'] = attest_worker_loaded(root, plan['source'])
        sys.argv = context['main_argv']
        os.chdir(root)
        try:
            runpy.run_path(sys.argv[0], run_name='__main__')
        except SystemExit as exc:
            w.require(exc.code is None or type(exc.code) is int and exc.code == 0, 'main nonzero exit')
        receipt['main_exit_code'] = 0
        validate_context(context_ref)
        w.require(w.process_identity() == identity, 'worker process changed')
        receipt['loaded_after'] = attest_worker_loaded(root, plan['source'])
        receipt['worker_cuda'] = assigned_cuda_identity(w.cuda_binding(runtime))
        backend = create_backend('cpu')
        before = evidence(output)
        audit_started = time.perf_counter()
        report = generic.audit_episode(output / 'eds_eval/decision_evidence/episode_000',
                                       output / 'eds_eval/episode_compute.jsonl',
                                       arithmetic_backend=backend, n31_empty_provider_search=True)
        w.require(report.get('accepted') is True and report.get('evidence_complete') is True, 'generic evidence INVALID')
        if row['profile'] == 'N32':
            report = n32.audit_output('N32', output, report, backend, expected_runtime=manifest['expected_runtime'])
        else:
            report = controls.audit_output(row['profile'], output, report, backend)
        counts, auxiliary = native_counts(row['profile'], output, report, manifest['expected_runtime'])
        w.require(before == evidence(output), 'evidence changed during audit')
        validate_context(context_ref)
        receipt.update(audit_seconds=time.perf_counter() - audit_started, native_counts=counts, auxiliary=auxiliary,
                       evidence=before, audit_backend=backend.report())
        w.atomic_json(report_path, report)
        receipt.update(audit_report=c.ref(report_path), accepted=True)
    except BaseException as exc:
        receipt.update(accepted=False, classification='INVALID', error_type=type(exc).__name__, error=str(exc))
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)
        receipt.update(worker_wall_seconds=time.perf_counter() - started, process_unchanged=w.process_identity() == identity)
        w.atomic_json(receipt_path, receipt)
    return 0 if receipt['accepted'] and receipt['process_unchanged'] else 2


def verify_receipt(context_ref, receipt_ref, process_record):
    context, plan, runtime, row, manifest = validate_context(context_ref)
    output = Path(manifest['output_dir'])
    receipt = w.read_ref(receipt_ref)
    w.require(receipt_ref['path'] == str(output / 'eds_eval/n32-worker-receipt.json'), 'receipt path')
    process = {key: process_record[key] for key in ('pid', 'proc_start_ticks', 'boot_id')}
    w.require(process_record['attempt_id'] == context['attempt_id'] and receipt.get('process') == process
              and receipt.get('process_unchanged') is True and receipt.get('accepted') is True
              and receipt.get('main_exit_code') == 0 and receipt.get('schema') == 'n32-worker-receipt-v1', 'receipt process/outcome')
    for key, expected in {'context': context_ref, 'plan': context['plan'], 'expected_manifest': context['expected_manifest'],
                          'source': plan['source'], 'row': row, 'attempt_id': context['attempt_id'], 'evidence': evidence(output)}.items():
        w.require(receipt.get(key) == expected, 'receipt binding ' + key)
    w.require(w.read_ref(c.ref(output / 'eds_eval/n32-worker-start.json')) == {'context': context_ref, 'process': process}, 'start identity')
    cuda = receipt['worker_cuda']
    w.require(cuda['physical_gpu'] == 7 and cuda['uuid'] == c.GPU_UUID and cuda['logical_device'] == 'cuda:0'
              and cuda['physical_uuid'] == canonical_cuda_uuid(c.GPU_UUID)
              and canonical_cuda_uuid(cuda['actual_uuid']) == canonical_cuda_uuid(c.GPU_UUID), 'worker device attestation')
    expected_hex = canonical_cuda_uuid(c.GPU_UUID)[4:].replace('-', '')
    w.require((cuda.get('actual_uuid_type') == 'builtins.str' and cuda.get('actual_uuid_bytes_hex') is None)
              or (cuda.get('actual_uuid_type') == 'torch._C._CUuuid' and cuda.get('actual_uuid_bytes_hex') == expected_hex),
              'native UUID serialization')
    w.require(receipt['audit_backend']['kind'] == 'cpu' and receipt['audit_backend']['logical_device'] == 'cpu', 'CPU audit backend')
    for phase in ('loaded_before', 'loaded_after'):
        inventory = receipt[phase]
        required = {'scripts.qd_ed_n32_worker', 'scripts.qd_ed_n32_bridge', 'scripts.qd_ed_n32_contract',
                    'scripts.qd_ed_n23_worker', 'scripts.audit_decision_evidence',
                    'scripts.qd_ed_n32_native', 'scripts.qd_ed_n31_native'}
        if phase == 'loaded_after':
            required |= {'core.' + name.removesuffix('.py') for name in b.RUNTIME_SOURCES}
        w.require(isinstance(inventory, dict) and required <= set(inventory), 'loaded source attestation absent')
        index = {v['path']: v['sha256'] for v in plan['source']['files']}
        w.require(all(index.get(v['path']) == v['sha256'] for v in inventory.values()), 'loaded source receipt mismatch')
        worker = inventory['scripts.qd_ed_n32_worker']
        w.require(worker == {'path': 'scripts/qd_ed_n32_worker.py',
                            'sha256': index.get('scripts/qd_ed_n32_worker.py'),
                            'module_name': worker.get('module_name'),
                            'spec_name': 'scripts.qd_ed_n32_worker',
                            'origin': str(Path(plan['worktree']).resolve() / 'scripts/qd_ed_n32_worker.py')}
                  and worker.get('module_name') in ('__main__', 'scripts.qd_ed_n32_worker'),
                  'worker source receipt identity differs')
    w.require(receipt['loaded_before']['scripts.qd_ed_n32_worker']
              == receipt['loaded_after']['scripts.qd_ed_n32_worker'], 'worker source identity changed')
    w.require(receipt['audit_report']['path'] == str(output / 'eds_eval/decision-evidence-audit.json'), 'audit path')
    report = w.read_ref(receipt['audit_report'])
    w.require(report.get('n23_arithmetic_backend') == receipt['audit_backend'], 'generic backend receipt')
    counts, auxiliary = native_counts(row['profile'], output, report, manifest['expected_runtime'])
    w.require((counts, auxiliary) == (receipt['native_counts'], receipt['auxiliary']), 'native receipt mismatch')
    for key in ('worker_wall_seconds', 'audit_seconds'):
        c.finite(receipt[key], key)
    return report


def verify_terminal(plan_ref, row, terminal, release_ref=None):
    """Parent binds generic terminal identity and telemetry to the metered receipt."""
    from scripts import qd_ed_n32_supervise as s
    plan = w.read_ref(plan_ref)
    manifest = w.read_ref(plan['expected_manifests'][row['episode_key']])
    output = Path(manifest['output_dir'])
    w.require(terminal['identity'] == s.c_identity(row) and terminal['episode_key'] == row['episode_key']
              and terminal['attempt_id'] == row['episode_key'] and terminal['source_commit'] == plan['source']['commit']
              and terminal['plan_sha256'] == plan_ref['sha256'] and terminal['runtime_manifest_sha256'] == plan['runtime']['sha256']
              and terminal['init_row_sha256'] == row['init_row_sha256'] and terminal['physical_gpu'] == 7
              and terminal['output_dir'] == str(output) and terminal['outcome_valid'] is True
              and terminal['required_cost_telemetry_complete'] is True and type(terminal['success']) is bool,
              'generic terminal identity/cost differs')
    c.finite(terminal['gpu_process_wall_seconds'], 'terminal charge')
    context_ref = c.ref(output / 'n32-worker-context.json')
    context = w.read_ref(context_ref)
    w.require(context['plan'] == plan_ref and context['episode_key'] == row['episode_key'], 'terminal context binding')
    if release_ref is not None:
        w.require(context.get('release') == release_ref and terminal.get('release') == release_ref
                  and terminal.get('context') == context_ref
                  and terminal.get('runtime_inventory_sha256') == plan['runtime_inventory_sha256'], 'terminal release binding')
        record = w.read_ref(c.ref(output / 'process.json'))
        w.require(record.get('context') == context_ref and record.get('release') == release_ref, 'process context/release binding')
    report = verify_receipt(context_ref, terminal['n32_worker_receipt'], w.read_ref(c.ref(output / 'process.json')))
    native_counts(row['profile'], output, report, manifest['expected_runtime'], terminal['guided_chunks'])
    # Retain the original generic result/video/Stage/token/counter gates. A receipt
    # is necessary, not sufficient to classify an episode as valid.
    generic_outcome = b.runner.validate_result(output, row, b.profiles(plan['worktree'])['profiles'][row['profile']],
                                                w.read_ref(plan['runtime']))
    w.require(all(key in terminal and terminal[key] == value for key, value in generic_outcome.items()),
              'terminal generic result/cost telemetry differs')
    return report


def run_worker(context_ref):
    context = w.read_ref(context_ref)
    if 'release' not in context:
        c.require_release(w.read_ref(context['plan']))
    validate_context(context_ref)
    return _run_in_process(context_ref)


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', required=True)
    parser.add_argument('--context-sha256', required=True)
    args = parser.parse_args()
    # The parent durably records PID/boot/start identity before opening this gate.
    w.require(sys.stdin.buffer.read(1) == b'G', 'parent dispatch gate absent')
    return run_worker({'path': args.context, 'sha256': args.context_sha256})


if __name__ == '__main__':
    raise SystemExit(main())
