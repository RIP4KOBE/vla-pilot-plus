#!/usr/bin/env python3
"""Explicit, accounted GPU7 CUDA/EGL admission probe; never runs on import.

Only `run` can dispatch. The child uses a synthetic static scene, not LIBERO,
and performs no episode rollout, policy loading, provider call, or download.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

import qd_ed_final_runner as runner


ROOT = Path(__file__).resolve().parents[1]


def normalized_uuid(value):
    return str(value).lower().removeprefix('gpu-')


def validate_probe_evidence(evidence, mapping):
    require = runner.require
    require(evidence.get('schema') == 'qd-ed-gpu7-context-probe-v1', 'probe evidence schema mismatch')
    require(mapping.get('physical_gpu') == 7 and mapping.get('metadata_mapping_verified') is True,
            'probe requires the verified physical GPU7 metadata mapping')
    require(evidence.get('physical_gpu') == 7 and evidence.get('torch_logical_device') == 0,
            'probe selected the wrong CUDA device')
    require(evidence.get('cuda_visible_devices') == '7' and
            evidence.get('cuda_device_order') == 'PCI_BUS_ID' and
            evidence.get('egl_cuda_ordinal_namespace') == 'process_visible',
            'probe CUDA ordinal namespace is not the frozen GPU7 mask')
    require(normalized_uuid(evidence.get('torch_uuid')) == normalized_uuid(mapping['uuid']),
            'Torch logical0 UUID differs from physical GPU7')
    require(evidence.get('torch_visible_device_count') == 1 and evidence.get('cuda_kernel_result') == 2.0,
            'CUDA visibility/kernel probe failed')
    # EGL_CUDA_DEVICE_NV is a CUDA ordinal in this process's visible namespace.
    # With CUDA_VISIBLE_DEVICES=7, physical GPU7 is CUDA logical0. Bind the
    # actual current display to that ordinal, whose Torch UUID was checked
    # above, and also retain the independently enumerated EGL index binding.
    require(evidence.get('display_egl_device_index') == mapping['egl_device_index'] and
            evidence.get('display_cuda_ordinal') == 0, 'actual EGL display is not bound to visible CUDA logical0')
    require(evidence.get('cuda_associated_egl_devices') == [
                {'egl_device_index': mapping['egl_device_index'], 'cuda_ordinal': 0}],
            'EGL CUDA association is absent, conflicting, or ambiguous under the GPU7 mask')
    require('nvidia' in evidence.get('gl_vendor', '').lower(), 'EGL renderer is not NVIDIA')
    require(bool(evidence.get('gl_renderer')) and bool(evidence.get('gl_version')), 'OpenGL identity missing')
    require(evidence.get('frame_shape') == [64, 64, 3] and evidence.get('frame_dtype') == 'uint8',
            'unexpected render frame format')
    require(evidence.get('frame_nonzero_values', 0) > 0 and evidence.get('frame_std', 0) > 0,
            'offscreen frame is empty or uniform')
    require(evidence.get('simulation_steps') == 0, 'probe must not perform simulation transitions')


def persist_and_validate_probe_evidence(evidence, mapping, output):
    """Keep raw observations even if an identity/render assertion rejects them."""
    path = Path(output) / 'probe-evidence.json'
    evidence['validation_status'] = 'pending'
    runner.durable_json(path, evidence)
    try:
        validate_probe_evidence(evidence, mapping)
    except runner.GateError as exc:
        evidence['validation_status'] = 'rejected'
        evidence['validation_error'] = str(exc)
        runner.durable_json(path, evidence)
        raise
    evidence['validation_status'] = 'passed'
    runner.durable_json(path, evidence)


def current_egl_device_identity():
    """Inspect the actual current display after the admitted render call."""
    egl = ctypes.CDLL('libEGL.so.1')
    egl.eglGetCurrentDisplay.argtypes = []
    egl.eglGetCurrentDisplay.restype = ctypes.c_void_p
    egl.eglGetProcAddress.argtypes = [ctypes.c_char_p]
    egl.eglGetProcAddress.restype = ctypes.c_void_p

    def extension(name, result, args):
        address = egl.eglGetProcAddress(name.encode())
        runner.require(bool(address), 'required EGL display-query extension missing')
        return ctypes.CFUNCTYPE(result, *args)(address)

    display = egl.eglGetCurrentDisplay()
    runner.require(bool(display), 'offscreen rendering did not leave a current EGL display')
    display_query = extension('eglQueryDisplayAttribEXT', ctypes.c_uint,
                              [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_ssize_t)])
    device_query = extension('eglQueryDeviceAttribEXT', ctypes.c_uint,
                             [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_ssize_t)])
    enumerate_devices = extension('eglQueryDevicesEXT', ctypes.c_uint,
                                  [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_int)])
    device = ctypes.c_ssize_t()
    runner.require(bool(display_query(display, 0x322C, ctypes.byref(device))), 'cannot bind EGL display to its device')
    ordinal = ctypes.c_ssize_t()
    runner.require(bool(device_query(ctypes.c_void_p(device.value), 0x323A, ctypes.byref(ordinal))),
                   'EGL display device has no CUDA association')
    count = ctypes.c_int()
    runner.require(bool(enumerate_devices(0, None, ctypes.byref(count))) and 0 < count.value <= 128,
                   'EGL enumeration failed after rendering')
    devices = (ctypes.c_void_p * count.value)()
    runner.require(bool(enumerate_devices(count.value, devices, ctypes.byref(count))), 'EGL enumeration failed')
    indices = [i for i in range(count.value) if devices[i] == device.value]
    runner.require(len(indices) == 1, 'current EGL display device is ambiguous')
    associations = []
    for index in range(count.value):
        visible_ordinal = ctypes.c_ssize_t()
        if device_query(devices[index], 0x323A, ctypes.byref(visible_ordinal)):
            associations.append({'egl_device_index': index, 'cuda_ordinal': visible_ordinal.value})
    return {'display_egl_device_index': indices[0], 'display_cuda_ordinal': ordinal.value,
            'egl_cuda_ordinal_namespace': 'process_visible', 'cuda_associated_egl_devices': associations}


def child_probe(manifest_path, output, resource_id):
    # Prevent accidental direct child invocation. GPU code is imported only
    # after the admitted parent has launched this process and journaled it.
    runner.require(os.environ.get('QD_ED_GPU_PROBE_PARENT_PID') == str(os.getppid()),
                   'probe child requires an admitted parent')
    runner.require(os.environ.get('QD_ED_GPU_PROBE_RESOURCE_ID') == resource_id, 'probe resource identity mismatch')
    runtime = runner.read_json(manifest_path)
    mapping = runtime['gpu_mapping']
    runner.require(os.environ.get('CUDA_VISIBLE_DEVICES') == '7' and
                   os.environ.get('CUDA_DEVICE_ORDER') == 'PCI_BUS_ID' and
                   os.environ.get('MUJOCO_EGL_DEVICE_ID') == str(mapping['egl_device_index']) and
                   os.environ.get('MUJOCO_GL') == 'egl' and os.environ.get('PYOPENGL_PLATFORM') == 'egl',
                   'probe child device environment mismatch')
    runner.gpu_admission(expected_uuid=mapping['uuid'])

    import torch
    runner.require(torch.cuda.device_count() == 1, 'probe expected exactly one visible CUDA device')
    properties = torch.cuda.get_device_properties(0)
    runner.require(normalized_uuid(properties.uuid) == normalized_uuid(mapping['uuid']),
                   'visible Torch logical0 is not physical GPU7')
    tensor = torch.ones(1, device='cuda:0') + 1
    torch.cuda.synchronize(0)
    cuda_result = float(tensor.item())

    import mujoco
    import numpy as np
    from OpenGL import GL
    from PIL import Image
    xml = '''<mujoco><visual><global offwidth="64" offheight="64"/></visual>
    <worldbody><light pos="0 0 3"/><camera name="probe" pos="0 -2 1" xyaxes="1 0 0 0 0.447 0.894"/>
    <geom type="plane" size="1 1 0.1" rgba="0.25 0.35 0.45 1"/>
    <geom type="sphere" pos="0 0 0.3" size="0.25" rgba="0.8 0.15 0.1 1"/>
    </worldbody></mujoco>'''
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)  # Static transforms only; no mj_step/rollout.
    renderer = mujoco.Renderer(model, height=64, width=64)
    try:
        renderer.update_scene(data, camera='probe')
        frame = renderer.render()
        egl_identity = current_egl_device_identity()
        def gl_string(name):
            value = GL.glGetString(name)
            return value.decode() if isinstance(value, bytes) else str(value or '')
        evidence = {
            'schema': 'qd-ed-gpu7-context-probe-v1', 'resource_id': resource_id,
            'physical_gpu': 7, 'torch_logical_device': 0, 'torch_visible_device_count': torch.cuda.device_count(),
            'cuda_visible_devices': os.environ.get('CUDA_VISIBLE_DEVICES'),
            'cuda_device_order': os.environ.get('CUDA_DEVICE_ORDER'),
            'torch_uuid': str(properties.uuid), 'torch_device_name': properties.name,
            'torch_version': str(torch.__version__), 'torch_cuda_runtime_version': str(torch.version.cuda),
            'mujoco_version': mujoco.__version__, 'cuda_kernel_result': cuda_result,
            **egl_identity, 'gl_vendor': gl_string(GL.GL_VENDOR),
            'gl_renderer': gl_string(GL.GL_RENDERER), 'gl_version': gl_string(GL.GL_VERSION),
            'frame_shape': list(frame.shape), 'frame_dtype': str(frame.dtype),
            'frame_nonzero_values': int(np.count_nonzero(frame)), 'frame_std': float(frame.std()),
            'frame_sha256': hashlib.sha256(frame.tobytes()).hexdigest(),
            'simulation_steps': 0, 'time_unix': time.time(),
        }
        persist_and_validate_probe_evidence(evidence, mapping, output)
        frame_path = Path(output) / 'probe-frame.png'
        Image.fromarray(frame).save(frame_path)
        evidence['frame_png_sha256'] = runner.digest(frame_path)
        runner.durable_json(Path(output) / 'probe-evidence.json', evidence)
    finally:
        renderer.close()
    return evidence


def run_probe(manifest_path, *, root=ROOT, timeout=120):
    root = Path(root).resolve()
    runner.require(type(timeout) is int and 0 < timeout <= 120, 'probe timeout must be1..120 seconds')
    with runner.locked(root / 'data/qd-ed-runner.lock', nonblocking=True):
        state = runner.read_state(root / 'research-state.yaml')
        runtime = runner.read_json(manifest_path)
        runner.require(Path(runtime['worktree']).resolve() == root and
                       Path(runtime['artifact_root']).resolve() == Path(state['artifacts']).resolve(), 'probe runtime ownership mismatch')
        runner.owned(manifest_path, runtime['artifact_root'])
        runner.require(state['gpu_pool'] == [7] and state['max_concurrent_gpu_workers'] == 1, 'probe GPU authorization mismatch')
        mapping = runtime['gpu_mapping']
        runner.require(mapping['physical_gpu'] == 7 and runtime.get('metadata_mapping_verified') is True,
                       'metadata mapping must be verified before the real probe')
        episode_events = runner.read_events(root / 'data/attempt-ledger.jsonl')
        resources = runner.read_events(root / 'data/gpu-healthcheck-ledger.jsonl')
        snapshot = runner.budget_snapshot(episode_events, resources)
        runner.require(snapshot['running'] == 0 and snapshot['gpu_healthcheck_inflight'] == 0,
                       'unfinished episode/healthcheck must be reconciled first')
        budget = state['budget']
        runner.require(0 < budget['max_gpu_hours'] <= 48 and
                       abs(budget['gpu_hours_consumed'] - snapshot['gpu_hours_consumed']) < 1e-8,
                       'probe GPU budget disagrees with ledger/authorization')
        timeout = runner.check_budget(
            state, episode_events, {'budget_bucket': 'recovery', 'timeout_seconds': timeout}, resources,
            reservation_events=runner.read_events(root / 'data/gpu-hour-reservation-ledger.jsonl'),
        )
        admission = runner.gpu_admission(expected_uuid=mapping['uuid'])
        resource_id = state['run_name'] + '__gpu7_cuda_egl__' + uuid.uuid4().hex[:12]
        output = runner.owned(Path(runtime['artifact_root']) / 'runtime/probes' / resource_id, runtime['artifact_root'])
        output.mkdir(parents=True, exist_ok=False)
        base = {'resource_id': resource_id, 'kind': 'gpu7_cuda_egl_probe', 'physical_gpu': 7,
                'output_dir': str(output), 'runtime_manifest_sha256': runner.digest(manifest_path),
                'source_script_sha256': runner.digest(Path(__file__))}
        process, started, finished, dispatched = None, time.monotonic(), None, False
        result, event = {}, 'aborted'
        runner.append_healthcheck_event(root, {**base, 'event': 'reserved', 'time_unix': time.time(), 'admission': admission})
        try:
            runner.gpu_admission(expected_uuid=mapping['uuid'])
            env = runner.child_environment(runtime)
            env.update(QD_ED_GPU_PROBE_PARENT_PID=str(os.getpid()), QD_ED_GPU_PROBE_RESOURCE_ID=resource_id)
            command = [str(runner.PYTHON), str(Path(__file__).resolve()), '_child',
                       '--manifest', str(Path(manifest_path).resolve()), '--output', str(output), '--resource-id', resource_id]
            runner.durable_json(output / 'command.json', {'argv': command, 'gpu_mapping': mapping})
            runner.append_healthcheck_event(root, {**base, 'event': 'dispatched', 'time_unix': time.time(), 'timeout_seconds': timeout})
            dispatched, started = True, time.monotonic()
            with (output / 'probe.log').open('w') as log:
                process = subprocess.Popen(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    start_ticks = Path(f'/proc/{process.pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
                except OSError:
                    start_ticks = None
                runner.durable_json(output / 'process.json', {'pid': process.pid, 'resource_id': resource_id,
                    'proc_start_ticks': start_ticks, 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(), 'time_unix': time.time()})
                code = runner.wait_exclusively(process, timeout)
                finished = time.monotonic()
            runner.require(code == 0, f'GPU probe child exit code{code}')
            result = runner.read_json(output / 'probe-evidence.json')
            runner.require(result.get('resource_id') == resource_id, 'probe evidence resource mismatch')
            validate_probe_evidence(result, mapping)
            runner.require(runner.digest(output / 'probe-frame.png') == result['frame_png_sha256'], 'probe frame fingerprint mismatch')
            event = 'completed'
        except BaseException as exc:
            result = {'reason': str(exc) if isinstance(exc, runner.GateError) else type(exc).__name__}
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
        finally:
            runner.terminate_owned(process)
            elapsed = (finished or time.monotonic()) - started if dispatched else 0.0
            terminal = {**result, **base, 'event': event, 'time_unix': time.time(), 'gpu_process_wall_seconds': elapsed,
                        'measurement': 'exclusive GPU7 child process wall time including abort/cleanup'}
            runner.append_healthcheck_event(root, terminal)
            runner.durable_json(output / 'healthcheck-result.json', terminal)
        runner.require(event == 'completed', 'GPU probe failed; runtime readiness remains unchanged')
        # No readiness mutation until the admitted child and evidence validation
        # both succeed. Never change provider_ready in this independent probe.
        fresh = runner.read_json(manifest_path)
        runner.require(runner.digest(manifest_path) == base['runtime_manifest_sha256'], 'runtime manifest changed during GPU probe')
        fresh['cuda_egl_verified'] = True
        fresh['gpu_mapping']['cuda_egl_verified'] = True
        fresh['cuda_egl_probe'] = {'resource_id': resource_id, 'evidence_path': str(output / 'probe-evidence.json'),
                                 'evidence_sha256': runner.digest(output / 'probe-evidence.json')}
        runner.durable_json(manifest_path, fresh)
        return terminal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run', help='Run only after exclusive GPU7 admission; records GPU-healthcheck usage')
    run.add_argument('--manifest', type=Path, required=True)
    run.add_argument('--timeout', type=int, default=120)
    child = commands.add_parser('_child', help=argparse.SUPPRESS)
    child.add_argument('--manifest', type=Path, required=True)
    child.add_argument('--output', type=Path, required=True)
    child.add_argument('--resource-id', required=True)
    args = parser.parse_args()
    def interrupted(signum, frame):
        raise KeyboardInterrupt('probe process interrupted')
    signal.signal(signal.SIGTERM, interrupted)
    if args.command == 'run':
        print(json.dumps(run_probe(args.manifest, timeout=args.timeout), indent=2))
    else:
        child_probe(args.manifest, args.output, args.resource_id)


if __name__ == '__main__':
    main()
