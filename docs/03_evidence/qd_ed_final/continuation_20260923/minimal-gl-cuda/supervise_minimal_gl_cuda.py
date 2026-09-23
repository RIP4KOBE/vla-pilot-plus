#!/usr/bin/env python3
"""Freeze on CPU; --run explicitly admits one GPU3-only minimal diagnostic."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
import xml.etree.ElementTree as ET

import minimal_gl_cuda_worker as worker

HERE = Path(__file__).resolve().parent
ROOT = next(path for path in HERE.parents if (path / 'scripts/qd_ed_final_runner.py').is_file())
PYTHON = Path('/home/hynx/miniconda3/envs/vla-pilot/bin/python')
PROTOCOL = ROOT / 'experiments/iteration_001_execution_intent/gpu3-minimal-gl-cuda-control.md'
METADATA = HERE.parent / 'gpu3-current-egl-metadata.json'
TIMEOUT = 120
KIND = 'minimal_gl_cuda_diagnostic'


def helpers():
    sys.path.insert(0, str(ROOT / 'scripts'))
    import qd_ed_final_runner as r
    import qd_ed_available_gpu_queue as q
    return r, q


def git_head():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def boot_id():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def dependencies():
    """Read distribution metadata and actual relevant files, never import GPU libraries."""
    files, versions = set(), {}
    for name in ('torch', 'mujoco', 'numpy', 'PyOpenGL', 'robosuite'):
        dist = importlib.metadata.distribution(name)
        versions[name] = dist.version
        for entry in dist.files or ():
            relative = str(entry)
            selected = relative.endswith(('.dist-info/METADATA', '.dist-info/RECORD'))
            if name == 'mujoco':
                selected |= relative.startswith('mujoco/') and (relative.endswith('.py') or '.so' in relative)
            elif name == 'PyOpenGL':
                selected |= relative.startswith('OpenGL/') and relative.endswith('.py')
            elif name == 'numpy':
                selected |= relative in ('numpy/__init__.py', 'numpy/version.py') or ('/core/' in relative or '/_core/' in relative) and '.so' in relative
            elif name == 'torch':
                selected |= relative in ('torch/__init__.py', 'torch/cuda/__init__.py', 'torch/version.py')
                selected |= relative.startswith(('torch/_C.', 'torch/lib/')) and '.so' in relative
            elif name == 'robosuite':
                selected |= relative == 'robosuite/renderers/context/egl_context.py'
            path = Path(dist.locate_file(entry))
            if selected and path.is_file():
                files.add(path.resolve())
    # CUDA wheels may provide cuBLAS/runtime outside torch/lib.
    for name in ('nvidia-cublas-cu12', 'nvidia-cuda-runtime-cu12'):
        try:
            dist = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        versions[name] = dist.version
        files.update(Path(dist.locate_file(p)).resolve() for p in (dist.files or ())
                     if ('.so' in str(p) or str(p).endswith(('.dist-info/METADATA', '.dist-info/RECORD')))
                     and Path(dist.locate_file(p)).is_file())
    for pattern in ('libEGL*.so*', 'libOpenGL*.so*', 'libGLdispatch*.so*', 'libGLX*.so*',
                    'libcuda.so*', 'libnvidia-eglcore.so*', 'libnvidia-glcore.so*', 'libnvidia-glsi.so*'):
        files.update(path.resolve() for path in Path('/usr/lib/x86_64-linux-gnu').glob(pattern) if path.is_file())
    production = Path(importlib.metadata.distribution('robosuite').locate_file(
        'robosuite/renderers/context/egl_context.py')).resolve()
    worker.require(production in files, 'production EGL source missing')
    return sorted(files), versions, production


def validate_mapping(mapping):
    worker.require(mapping.get('physical_gpu') == 3 and mapping.get('egl_device_index') == 0
                   and mapping.get('uuid') == worker.EXPECTED_UUID
                   and mapping.get('pci_bus_id', '').lower().endswith('61:00.0')
                   and mapping.get('metadata_mapping_verified') is True
                   and mapping.get('metadata_cuda_ordinal_namespace') == 'unmasked_pci_bus_id'
                   and mapping.get('display_or_context_calls') is False,
                   'fresh metadata does not bind physical GPU3 to EGL0')


def freeze(output_root, metadata_path):
    """CPU-only input freeze; no NVIDIA query, imports, journal writes, or context."""
    worker.require(Path(sys.executable).resolve() == PYTHON.resolve(), 'use frozen vla-pilot Python')
    mapping = json.loads(metadata_path.read_text()); validate_mapping(mapping)
    source = git_head()
    relative = str(PROTOCOL.relative_to(ROOT))
    committed = subprocess.check_output(['git', 'show', source + ':' + relative], cwd=ROOT)
    worker.require(committed == PROTOCOL.read_bytes(), 'protocol must be committed at source HEAD')
    inputs, versions, production = dependencies()
    inputs += [Path(__file__).resolve(), HERE / 'minimal_gl_cuda_worker.py', HERE / 'scene.xml',
               PROTOCOL, metadata_path.resolve(), PYTHON.resolve()]
    inputs += [ROOT / 'scripts' / name for name in ('qd_ed_final_runner.py',
               'qd_ed_available_gpu_queue.py', 'qd_ed_gpu_probe.py', 'qd_ed_runtime_setup.py')]
    identities = {str(path): worker.sha256(path) for path in sorted(set(inputs))}
    resource_id = uuid.uuid4().hex[:12]
    output = output_root.resolve() / ('gpu3-minimal-gl-cuda__' + resource_id)
    output.mkdir(parents=True, exist_ok=False)
    runtime = {'schema': 'minimal-gl-cuda-runtime-v1', 'gpu_mapping': mapping,
               'cuda_egl_verified': False, 'metadata_mapping_verified': True,
               'actual_cuda_uuid_verified_by_child_after_explicit_init': False,
               'boot_id': boot_id(), 'dependency_versions': versions,
               'production_egl_source': str(production), 'environment': worker.EXPECTED_ENV,
               'scope': 'independent tiny scene; no application/models/provider'}
    runtime_path = output / 'runtime-manifest.json'; worker.write_json(runtime_path, runtime)
    identities[str(runtime_path)] = worker.sha256(runtime_path)
    contract = {'schema': 'minimal-gl-cuda-v1', 'resource_id': resource_id, 'kind': KIND,
                'physical_gpu': 3, 'egl_device_index': 0, 'uuid': worker.EXPECTED_UUID,
                'source_commit': source, 'boot_id': runtime['boot_id'],
                'output_dir': str(output), 'runtime_path': str(runtime_path),
                'metadata_path': str(metadata_path.resolve()), 'protocol': str(PROTOCOL),
                'production_egl_source': str(production), 'scene_xml': str(HERE / 'scene.xml'),
                'fingerprints': identities, 'dependency_versions': versions,
                'stages': list(worker.STAGES), 'frames_per_stage': 2, 'max_frames': 10,
                'readback_validity': worker.READBACK_VALIDITY,
                'width': 96, 'height': 96, 'timeout_seconds': TIMEOUT,
                'idle_seconds': 120, 'budget_bucket': 'recovery',
                'protected_hours': {'validation': 14, 'formal': 10},
                'supervisor_pid': os.getpid(), 'python': str(PYTHON),
                'worker': str(HERE / 'minimal_gl_cuda_worker.py')}
    contract_path = output / 'frozen-contract.json'; worker.write_json(contract_path, contract)
    return contract, contract_path


def verify_frozen(contract):
    worker.require(git_head() == contract['source_commit'], 'source HEAD changed')
    worker.require(boot_id() == contract['boot_id'], 'boot changed')
    for path, digest in contract['fingerprints'].items():
        worker.require(worker.sha256(path) == digest, f'frozen file changed: {path}')


def kernel_rows(extra):
    done = subprocess.run(['journalctl', '-k', '-b', '--no-pager', '-o', 'json', *extra],
                          capture_output=True, text=True, timeout=2, check=True)
    return [json.loads(line) for line in done.stdout.splitlines() if line.startswith('{')]


def owned_xids(rows, pid, expected_boot):
    owned = []
    for row in rows:
        worker.require(row.get('_BOOT_ID', '').replace('-', '') == expected_boot.replace('-', ''),
                       'kernel boot identity changed')
        message = row.get('MESSAGE', '')
        if re.search(r'NVRM: Xid \(PCI:0000:61:00\): (31|109),', message) and re.search(rf'\bpid={pid}(?:,|\s|$)', message):
            owned.append({'cursor': row['__CURSOR'], 'message': message})
    return owned


def check_graphics_exclusive(xml, owned_pid):
    devices = ET.fromstring(xml).findall('gpu')
    worker.require(len(devices) == 1 and devices[0].findtext('uuid') == worker.EXPECTED_UUID,
                   'GPU3 XML UUID mismatch')
    entries = devices[0].find('processes')
    worker.require(entries is not None and not (entries.text or '').strip(), 'GPU process metadata unavailable')
    for entry in entries.findall('process_info'):
        pid = entry.findtext('pid', '')
        worker.require(pid.isdigit() and int(pid) == owned_pid, 'external graphics/compute process on GPU3')


def gpu_processes(owned_pid):
    xml = subprocess.check_output(['nvidia-smi', '-q', '-x', '-i', '3'], text=True, timeout=2)
    check_graphics_exclusive(xml, owned_pid)


def kill_owned(process):
    """Single-process worker: never signal a PID/group that is not this Popen child."""
    if process is not None and process.poll() is None:
        try:
            worker.require(os.getpgid(process.pid) == process.pid, 'owned child lost its process group')
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process is not None:
        process.wait(timeout=5)


def watchdog(process, deadline, stopped, expired):
    if not stopped.wait(max(0, deadline - time.monotonic())) and process.poll() is None:
        expired.set()
        kill_owned(process)


def validate_result(output):
    import numpy as np  # CPU array reading only; parent never imports torch or GL.
    value = json.loads((output / 'result.json').read_text())
    worker.require(value['status'] == 'passed' and value['frame_count'] == 8
                   and value['render_calls'] == 8 and value['forward_calls'] == 1
                   and value['step_calls'] == 0 and value['context_creations'] == 1
                   and value['make_current_calls'] == 1 and value['cuda_uuid'] == worker.EXPECTED_UUID,
                   'child result scope mismatch')
    worker.require(len(value['frames']) == 8, 'incomplete raw frame manifest')
    reference = None
    for index, record in enumerate(value['frames']):
        worker.require(record['index'] == index and record['stage'] == worker.STAGES[index // 2]
                       and record['within_stage'] == index % 2, 'frame ordering mismatch')
        arrays = []
        for name, shape, dtype in (('rgb', (96, 96, 3), np.uint8), ('depth', (96, 96), np.float32)):
            path = Path(record[name]['path'])
            worker.require(path.parent.resolve() == output.resolve() and not path.is_symlink(), 'unowned raw array')
            worker.require(worker.sha256(path) == record[name]['npy_sha256'], 'raw array hash mismatch')
            array = np.load(path, allow_pickle=False)
            worker.require(array.shape == shape and array.dtype == dtype and np.isfinite(array).all(), 'raw array invalid')
            worker.require(worker.compare_arrays(array, array)['array_sha256'] == record[name]['array_sha256'], 'array-byte hash mismatch')
            arrays.append(array)
        if reference is None:
            reference = arrays[0]
        validity = worker.readback_validity(*arrays)
        worker.require_readback_validity(validity, baseline=index == 0)
        worker.require(record['readback_validity'] == validity, 'readback validity evidence mismatch')
        worker.require(np.array_equal(arrays[0], reference), 'independent RGB equality failed')
    return {'status': 'passed', 'frame_count': 8, 'result_sha256': worker.sha256(output / 'result.json')}


def evidence_hashes(output):
    """Freeze available evidence on success and failure, including native-abort logs."""
    evidence = {}
    for path in sorted(output.iterdir()):
        if path.suffix not in {'.json', '.jsonl', '.log', '.npy'} or path.name == 'supervisor-result.json':
            continue
        worker.require(path.is_file() and not path.is_symlink(), 'unowned evidence file')
        evidence[path.name] = worker.sha256(path)
    return evidence


def run_admitted(contract, contract_path, r, admission):
    output = Path(contract['output_dir'])
    digest = worker.sha256(contract_path)
    command = [str(PYTHON), contract['worker'], '--contract', str(contract_path), '--contract-sha256', digest]
    environment = {'PATH': str(PYTHON.parent) + ':/usr/bin:/bin', 'HOME': str(Path.home()),
                   'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1',
                   'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', **worker.EXPECTED_ENV}
    baseline = kernel_rows(['-n', '1'])
    worker.require(len(baseline) == 1, 'kernel cursor unavailable')
    worker.require(baseline[0]['_BOOT_ID'].replace('-', '') == contract['boot_id'].replace('-', ''), 'kernel boot mismatch')
    cursor = baseline[0]['__CURSOR']
    worker.write_json(output / 'dispatch.json', {'command': command, 'environment': environment,
                       'kernel_cursor': cursor, 'boot_id': contract['boot_id'], 'admission': admission})
    base = {'resource_id': contract['resource_id'], 'kind': KIND, 'physical_gpu': 3,
            'budget_bucket': 'recovery', 'output_dir': str(output), 'source_commit': contract['source_commit'],
            'source_script_sha256': worker.sha256(contract['worker']), 'contract_sha256': digest,
            'boot_id': contract['boot_id'], 'timeout_seconds': TIMEOUT}
    r.append_healthcheck_event(ROOT, {**base, 'event': 'reserved', 'time_unix': time.time()})
    process = None; started = None; outcome = None; failure = None
    stopped, expired = threading.Event(), threading.Event()
    monitor = None; faults = []
    try:
        verify_frozen(contract)
        gpu_processes(-1)  # Fail if any graphics process already occupies GPU3.
        r.append_healthcheck_event(ROOT, {**base, 'event': 'dispatched', 'time_unix': time.time()})
        with (output / 'worker.log').open('x') as log:
            started = time.monotonic()
            process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            monitor = threading.Thread(target=watchdog, args=(process, started + TIMEOUT, stopped, expired), daemon=True)
            monitor.start()
            start_ticks = Path(f'/proc/{process.pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
            worker.write_json(output / 'process.json', {'pid': process.pid, 'start_ticks': start_ticks,
                               'supervisor_pid': os.getpid(), 'boot_id': contract['boot_id']})
            while True:
                rows = kernel_rows(['--after-cursor', cursor])
                if rows:
                    cursor = rows[-1]['__CURSOR']
                found = owned_xids(rows, process.pid, contract['boot_id']); faults.extend(found)
                worker.require(not found, 'owned GPU3 Xid31/109')
                worker.require(not expired.is_set(), '120-second child timeout')
                gpu_processes(process.pid)
                code = process.poll()
                if code is not None:
                    worker.require(code == 0, f'child native/ordinary exit {code}')
                    break
                time.sleep(0.25)
        # Include faults emitted at process exit; no second worker or retry.
        rows = kernel_rows(['--after-cursor', cursor]); faults.extend(owned_xids(rows, process.pid, contract['boot_id']))
        worker.require(not faults and not expired.is_set(), 'owned Xid or timeout at child exit')
        outcome = validate_result(output)
    except BaseException as exc:
        failure = {'error': type(exc).__name__, 'message': str(exc)}
    finally:
        # Watchdog remains live during cleanup. Charge until the owned child is reaped.
        try:
            kill_owned(process)
        except BaseException as exc:
            failure = failure or {'error': type(exc).__name__, 'message': 'owned cleanup failed: ' + str(exc)}
        elapsed = 0.0 if started is None else time.monotonic() - started
        stopped.set()
        if monitor is not None:
            monitor.join(timeout=6)
        if process is not None and process.poll() is None:
            # Do not release the journal reservation while a child may still live.
            worker.write_json(output / 'cleanup-unresolved.json', {'failure': failure,
                              'pid': process.pid, 'elapsed_seconds_lower_bound': elapsed,
                              'requires_explicit_reconciliation': True})
            raise RuntimeError('owned child termination unresolved; health resource remains inflight')
        try:
            hashes = evidence_hashes(output)
        except BaseException as exc:
            hashes = None
            failure = failure or {'error': type(exc).__name__, 'message': 'evidence hashing failed: ' + str(exc)}
        terminal = {**base, 'event': 'completed' if failure is None else 'aborted', 'time_unix': time.time(),
                    'gpu_process_wall_seconds': elapsed, 'child_returncode': process.returncode if process else None,
                    'failure': failure, 'outcome': outcome, 'owned_kernel_faults': faults,
                    'scientific_episode_count': 0, 'timeout_watchdog_expired': expired.is_set(),
                    'evidence_files_sha256': hashes}
        try:
            worker.write_json(output / 'supervisor-result.json', terminal)
        except BaseException as exc:
            terminal['event'] = 'aborted'
            terminal['evidence_write_error'] = {'error': type(exc).__name__, 'message': str(exc)}
            # Cost journaling must still happen if the output directory cannot be written.
        r.append_healthcheck_event(ROOT, terminal)
    return terminal


def supervise(contract, contract_path):
    r, q = helpers()
    with r.locked(ROOT / 'data/qd-ed-runner.lock', nonblocking=True):
        q.no_unfinished(ROOT)
        with r.locked(ROOT / 'data/qd-ed-state.lock'):
            r.sync_state_from_journal(ROOT, r.read_events(ROOT / 'data/attempt-ledger.jsonl'))
        windows = {}
        while True:
            state = r.read_state(ROOT / 'research-state.yaml')
            worker.require(q.candidate_indices(state) == [3] and r.authorized_gpu(state) == 3, 'GPU3-only authorization changed')
            verify_frozen(contract)
            devices = q.inventory()
            worker.require(devices[3]['uuid'] == worker.EXPECTED_UUID, 'GPU3 inventory UUID changed')
            # Inventory checks CUDA masks and compute apps; XML also covers graphics.
            try:
                gpu_processes(-1)
            except RuntimeError:
                windows.pop(3, None)
            else:
                q.update_idle_windows(devices, windows, time.monotonic(), 120)
                if q.choose_device(devices, [3], 3):
                    break
            print(json.dumps({'status': 'waiting_gpu3_stable_idle', 'idle_seconds': devices[3].get('idle_observed_seconds', 0)}), flush=True)
            time.sleep(10)
        q.reservation_admission(devices[3])
        events, resources = q.no_unfinished(ROOT)
        state = r.read_state(ROOT / 'research-state.yaml')
        worker.require(state['budget'].get('gpu_hour_reservations', {'validation': 14., 'formal': 10.}) == {'validation': 14., 'formal': 10.}, 'protected hour reservations changed')
        allowed = r.check_budget(state, events, {'budget_bucket': 'recovery', 'timeout_seconds': TIMEOUT},
                                 resources, r.read_events(ROOT / 'data/gpu-hour-reservation-ledger.jsonl'), physical_gpu=3)
        worker.require(allowed == TIMEOUT, 'budget cannot admit full frozen 120-second diagnostic')
        fresh = q.current_metadata(3, root=ROOT); validate_mapping(fresh)
        prior = json.loads(Path(contract['metadata_path']).read_text())
        worker.require(q.same_mapping(fresh, prior), 'GPU/EGL mapping changed since freeze')
        worker.write_json(Path(contract['output_dir']) / 'predispatch-metadata.json', fresh)
        admission = r.gpu_admission(physical_gpu=3, expected_uuid=worker.EXPECTED_UUID)
        return run_admitted(contract, contract_path, r, admission)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--plan', action='store_true', help='CPU-only freeze; never query/initialize GPU or change state')
    mode.add_argument('--run', action='store_true', help='explicitly admit one diagnostic; no retries')
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--metadata', type=Path, default=METADATA)
    args = parser.parse_args()
    def interrupted(signum, frame):
        raise InterruptedError(f'supervisor interrupted by signal {signum}')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    contract, path = freeze(args.output_root, args.metadata)
    print(json.dumps({'contract': str(path), 'resource_id': contract['resource_id'], 'mode': 'run' if args.run else 'plan'}), flush=True)
    if args.run:
        result = supervise(contract, path)
        print(json.dumps(result), flush=True)
        return 0 if result['event'] == 'completed' else 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
