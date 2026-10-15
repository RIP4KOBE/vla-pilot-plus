#!/usr/bin/env python3
"""Explicit post-cohort chosen-GPU numeric diagnostic; never a task/performance result.

Prepared only: executing main initializes CUDA. Use the current runner's lock and
finished cohort status. No provider, simulator, model weights, or network calls.
"""
from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

ALLOCATOR_LIMIT_BYTES = 2 * 1024 ** 3
SEED = 20261013
PROFILE = {'population_size': 16, 'quantiles': [.05, .95], 'expand_fraction': .1,
           'min_axis_span_m': .08, 'grid_shape': [4, 4],
           'descriptor': 'target_relative_endpoint_xy', 'input_dtype': 'float32'}


def utc():
    return datetime.now(timezone.utc).isoformat()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def save_report(path, report):
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    with temporary.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    temporary.replace(path)


def smi(*args):
    command = ['nvidia-smi', *args]
    process = subprocess.run(command, check=True, text=True, capture_output=True, timeout=30)
    return [list(map(str.strip, row)) for row in csv.reader(io.StringIO(process.stdout)) if row]


def process_rows():
    rows = smi('--query-compute-apps=pid,gpu_uuid,used_gpu_memory', '--format=csv,noheader,nounits')
    return [{'pid': int(row[0]), 'gpu_uuid': row[1], 'used_gpu_memory_mib': row[2]}
            for row in rows if len(row) == 3 and row[0].isdigit()]


def own_pids():
    values = {os.getpid()}
    status = Path('/proc/self/status')
    if status.is_file():
        for line in status.read_text().splitlines():
            if line.startswith('NSpid:'):
                values.update(int(value) for value in line.split()[1:])
    return sorted(values)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Cannot import source: {path}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def float_record(tensor):
    value = tensor.detach().to(device='cpu').float().contiguous()
    raw = value.numpy().astype('<f4', copy=False).tobytes()
    bits = [f'{int(item) & 0xffffffff:08x}' for item in value.view(-1).view(dtype=__import__('torch').int32).tolist()]
    return {'shape': list(value.shape), 'values': value.tolist(),
            'float32_le_sha256': hashlib.sha256(raw).hexdigest(), 'ieee754_hex': bits}


def generate_cases(torch, seed):
    """All randomness uses this private CPU generator; no CUDA RNG is used."""
    generator = torch.Generator(device='cpu').manual_seed(seed)
    cases = []
    scales = [1e-6, 1e-4, .002, .01, .02, .04, .08, .2, .5, 1., 2., 10.]
    centers = [(0., 0.), (.25, -.5), (1., 1.), (10., -10.)]
    for scale in scales:
        for repeat in range(16):
            mode = repeat % 4
            if mode == 1:
                values = 2 * torch.rand((16, 2), generator=generator, dtype=torch.float32) - 1
            else:
                values = torch.randn((16, 2), generator=generator, dtype=torch.float32)
            if mode == 2:
                values = torch.round(values * 2) / 2
            elif mode == 3:
                values[:, repeat % 2] = 0
            center = torch.tensor(centers[repeat // 4], dtype=torch.float32)
            values = values * scale + center
            cases.append((f'random_s{scale:g}_r{repeat}', {'family': 'random_scale', 'scale': scale,
                          'mode': mode, 'center': center.tolist()}, values))
    for center in [0., .25, -.75, 10.]:
        for kind in range(6):
            values = torch.full((16, 2), center, dtype=torch.float32)
            if kind in (1, 2):
                values[:, kind - 1] += torch.linspace(-.1, .1, 16)
            elif kind in (3, 4, 5):
                split = {3: 1, 4: 8, 5: 15}[kind]
                values[:split] += torch.tensor([-.1, .1])
                values[split:] += torch.tensor([.1, -.1])
            cases.append((f'degenerate_c{center:g}_k{kind}', {'family': 'degenerate_or_tied',
                          'center': center, 'kind': kind}, values))
    # For equally spaced N=16 endpoints: raw .05/.95 span is .9 of full
    # range, then the .1 expansion makes 1.08 * full range. Probe adjacent
    # float32 amplitudes around the .08 minimum-span branch, never epsilon64.
    base = torch.linspace(-.5, .5, 16, dtype=torch.float32)
    threshold = torch.tensor(.08 / 1.08, dtype=torch.float32)
    for offset in range(-8, 9):
        amplitude = threshold.clone()
        direction = torch.tensor(float('-inf') if offset < 0 else float('inf'))
        for _ in range(abs(offset)):
            amplitude = torch.nextafter(amplitude, direction)
        for center in (0., .25):
            for mode in range(3):
                x = base * amplitude + center
                y = (base.flip(0) * amplitude + center if mode == 0 else
                     torch.full((16,), center) if mode == 1 else base * .12 - center)
                values = torch.stack((x, y), dim=1)
                cases.append((f'minspan_u{offset}_c{center:g}_m{mode}',
                              {'family': 'minimum_span_cutoff', 'amplitude_ulp_offset': offset,
                               'amplitude_float32': float(amplitude), 'center': center, 'mode': mode}, values))
    for _, _, values in cases:
        if values.dtype != torch.float32 or tuple(values.shape) != (16, 2) or not bool(torch.isfinite(values).all()):
            raise RuntimeError('Diagnostic generator produced an invalid float32 input')
    return cases


def boundary_probes(torch, descriptors, cpu_bounds):
    lo, hi = torch.tensor(cpu_bounds, dtype=torch.float32)
    mid = (lo + hi) / 2
    points = [row.clone() for row in descriptors]
    levels = [lo + (hi - lo) * (index / 4) for index in range(5)]
    for x in levels:
        for y in levels:
            points.append(torch.stack((x[0], y[1])))
    minus = torch.tensor(float('-inf'), dtype=torch.float32)
    plus = torch.tensor(float('inf'), dtype=torch.float32)
    for axis in range(2):
        for level in levels:
            for direction in (minus, None, plus):
                value = level[axis] if direction is None else torch.nextafter(level[axis], direction)
                point = mid.clone()
                point[axis] = value
                points.append(point)
    # Wider legitimate clipping overflow, and exact signed zeros.
    points.extend((lo - 2 * (hi - lo), hi + 2 * (hi - lo),
                   torch.tensor([0., -0.]), torch.tensor([-0., 0.])))
    return torch.stack(points).float().contiguous()


def compare_case(torch, core, audit, name, metadata, descriptors):
    case = {'name': name, 'generator': metadata, 'input': float_record(descriptors),
            'checks': {}, 'errors': {}}
    cpu_bounds = cpu_checksum = gpu_bounds = None
    try:
        cpu_bounds, cpu_checksum = audit.freeze_bounds(descriptors.tolist())
        case['cpu_bounds'] = {**float_record(torch.tensor(cpu_bounds, dtype=torch.float32)),
                              'checksum': cpu_checksum}
    except Exception as error:
        case['errors']['cpu_bounds'] = {'type': type(error).__name__, 'message': str(error)}
    try:
        gpu_bounds = core.freeze_bounds(descriptors.to(device='cuda:0'),
            quantiles=(.05, .95), expand_fraction=.1, min_axis_span_m=.08)
        case['gpu_bounds'] = {**float_record(torch.stack((gpu_bounds.lo, gpu_bounds.hi))),
                              'checksum': gpu_bounds.checksum}
    except Exception as error:
        case['errors']['gpu_bounds'] = {'type': type(error).__name__, 'message': str(error)}
    if cpu_bounds is not None and gpu_bounds is not None:
        case['checks']['bounds_dtype_shape'] = (gpu_bounds.lo.dtype == torch.float32
            and gpu_bounds.hi.dtype == torch.float32 and tuple(gpu_bounds.lo.shape) == (2,)
            and tuple(gpu_bounds.hi.shape) == (2,))
        case['checks']['bounds_ieee_bits_exact'] = (case['cpu_bounds']['ieee754_hex'] == case['gpu_bounds']['ieee754_hex'])
        case['checks']['bounds_checksum_exact'] = cpu_checksum == gpu_bounds.checksum
        probes = boundary_probes(torch, descriptors, cpu_bounds)
        case['cell_probe_input'] = float_record(probes)
        try:
            cpu_cells, cpu_overflow_count = audit.assign_cells(probes.tolist(), cpu_bounds)
            lo, hi = torch.tensor(cpu_bounds, dtype=torch.float32)
            cpu_mask = ((probes < lo) | (probes > hi)).any(dim=1).tolist()
            case['cpu_cells'] = cpu_cells
            case['cpu_overflow_mask'] = cpu_mask
            case['cpu_overflow_count'] = cpu_overflow_count
            case['checks']['cpu_mask_count_join'] = sum(cpu_mask) == cpu_overflow_count
            gpu_probes = probes.to(device='cuda:0')
            for label, bounds in (
                ('native_bounds', gpu_bounds),
                ('same_cpu_bounds', core.QDBounds(lo.to('cuda:0'), hi.to('cuda:0'), cpu_checksum)),
            ):
                try:
                    cells, overflow = core.cell_ids(gpu_probes, bounds, (4, 4))
                    actual_cells = cells.cpu().tolist()
                    actual_mask = overflow.cpu().tolist()
                    case[label] = {'cells': actual_cells, 'overflow_mask': actual_mask,
                                   'overflow_count': sum(actual_mask)}
                    case['checks'][label + '/cell_ids_exact'] = actual_cells == cpu_cells
                    case['checks'][label + '/overflow_mask_exact'] = actual_mask == cpu_mask
                    case['checks'][label + '/overflow_count_exact'] = sum(actual_mask) == cpu_overflow_count
                except Exception as error:
                    case['errors'][label] = {'type': type(error).__name__, 'message': str(error)}
        except Exception as error:
            case['errors']['cpu_cells'] = {'type': type(error).__name__, 'message': str(error)}
    case['passed'] = bool(case['checks']) and all(case['checks'].values()) and not case['errors']
    return case


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gpu', type=int, required=True, help='Authorized physical NVIDIA index')
    parser.add_argument('--expected-uuid', required=True, help='Independently confirmed physical GPU UUID')
    parser.add_argument('--repo-root', type=Path, required=True, help='Current source checkout; reads core/qd_ed.py')
    parser.add_argument('--auditor', type=Path, required=True, help='Prepared independent audit_qd_mechanism.py')
    parser.add_argument('--cohort-status', type=Path, required=True, help='Existing cohort status.json; state must be finished')
    parser.add_argument('--lock-file', type=Path, required=True, help='Existing runner GPU lock; acquired nonblocking for whole diagnostic')
    parser.add_argument('--report', type=Path, required=True, help='New JSON output under the experiment checks directory')
    parser.add_argument('--seed', type=int, default=SEED, help='Private CPU generator seed, recorded in report')
    args = parser.parse_args()
    expected_uuid = args.expected_uuid
    if args.gpu not in (0, 1, 4, 5, 6, 7) or not re.fullmatch(r'GPU-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', expected_uuid):
        parser.error('Require an authorized idle physical GPU index and canonical GPU UUID; external busy GPUs2/3 excluded')
    if args.lock_file.name != f'gpu-{args.gpu}.lock':
        parser.error('Lock filename must match the physical GPU index')
    report_path = args.report.expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open('x') as stream:
        json.dump({'kind': 'qd_gpu_numeric_diagnostic_not_task', 'status': 'starting', 'pid': os.getpid()}, stream)
    report = {'schema': 'steering_qd_gpu_numeric_v1', 'kind': 'qd_gpu_numeric_diagnostic_not_task',
              'started_at': utc(), 'pid': os.getpid(), 'status': 'running', 'scientific_task_count': 0,
              'cohort_valid': None, 'performance_result': False, 'profile': PROFILE,
              'seed': args.seed, 'allocator_limit_bytes': ALLOCATOR_LIMIT_BYTES,
              'expected_physical_gpu_index': args.gpu, 'expected_gpu_uuid': expected_uuid,
              'limitations': ['The 2 GiB limit covers the PyTorch allocator, not CUDA context/library memory.',
                             'Exact numeric disagreement is diagnostic evidence; this script never relaxes tolerances or changes runtime behavior.',
                             'Finite deterministic samples do not prove every possible CUDA input; no model/task/API/simulation is executed.'],
              'cases': [], 'failures': []}
    lock = None
    torch = None
    sources = {'diagnostic': Path(__file__).resolve(), 'core_qd': args.repo_root.resolve() / 'core/qd_ed.py',
               'independent_auditor': args.auditor.resolve()}
    try:
        if os.environ.get('CUDA_VISIBLE_DEVICES') != str(args.gpu) or os.environ.get('CUDA_DEVICE_ORDER') != 'PCI_BUS_ID':
            raise RuntimeError(f'Require CUDA_VISIBLE_DEVICES={args.gpu} and CUDA_DEVICE_ORDER=PCI_BUS_ID before execution')
        report['required_environment'] = {name: os.environ[name] for name in ('CUDA_VISIBLE_DEVICES', 'CUDA_DEVICE_ORDER')}
        status = json.loads(args.cohort_status.read_text())
        report['cohort_guard'] = {'status_file': str(args.cohort_status.resolve()), 'sha256': file_sha(args.cohort_status),
                                 'state': status.get('state'), 'exit_code': status.get('exit_code')}
        if status.get('state') != 'finished':
            raise RuntimeError('The existing cohort is not finished; no CUDA initialization is permitted')
        lock = args.lock_file.open('r')
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        report['cohort_guard']['runner_lock_acquired'] = True
        device = smi('-i', str(args.gpu), '--query-gpu=index,uuid,name,pci.bus_id,memory.total', '--format=csv,noheader,nounits')
        if len(device) != 1 or len(device[0]) != 5 or device[0][1] != expected_uuid:
            raise RuntimeError('nvidia-smi physical GPU UUID differs from the expected device')
        report['nvidia_device_before_cuda'] = dict(zip(('index','uuid','name','pci_bus_id','memory_total_mib'), device[0]))
        before = process_rows()
        report['gpu_processes_before_cuda'] = [row for row in before if row['gpu_uuid'] == expected_uuid]
        if report['gpu_processes_before_cuda']:
            raise RuntimeError('Selected GPU still has compute processes; no CUDA initialization performed')
        report['sources'] = {key: {'path': str(path), 'sha256': file_sha(path)} for key, path in sources.items()}
        import torch as torch_module
        torch = torch_module
        if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
            raise RuntimeError('Expected exactly one visible CUDA device')
        properties = torch.cuda.get_device_properties(0)
        torch.cuda.set_per_process_memory_fraction(min(1.0, ALLOCATOR_LIMIT_BYTES / properties.total_memory), 0)
        allocation = torch.zeros((1,), device='cuda:0', dtype=torch.float32)
        torch.cuda.synchronize(0)
        identities = own_pids()
        own_rows = [row for row in process_rows() if row['pid'] in identities]
        report['gpu_pid_proof_after_allocation'] = {'pid_candidates': identities, 'matching_process_rows': own_rows}
        if not own_rows or {row['gpu_uuid'] for row in own_rows} != {expected_uuid}:
            raise RuntimeError('Own allocated process could not be bound exclusively to the expected GPU UUID')
        property_uuid = str(getattr(properties, 'uuid', 'unavailable'))
        uuid_match = re.search(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', property_uuid)
        if uuid_match and 'GPU-' + uuid_match.group(0).lower() != expected_uuid:
            raise RuntimeError('CUDA device property UUID differs from nvidia-smi/expected GPU')
        report['runtime'] = {'python': sys.version, 'torch': torch.__version__, 'torch_cuda': torch.version.cuda,
                             'device_name': properties.name, 'device_property_uuid': property_uuid,
                             'visible_cuda_device': 0, 'total_memory_bytes': properties.total_memory}
        core = load_module('_qd_gpu_numeric_core', sources['core_qd'])
        audit = load_module('_qd_gpu_numeric_independent_cpu', sources['independent_auditor'])
        cpu_rng_before = torch.get_rng_state().clone()
        cuda_rng_before = torch.cuda.get_rng_state(0).clone()
        cases = generate_cases(torch, args.seed)
        report['planned_cases'] = len(cases)
        started = time.monotonic()
        torch.cuda.reset_peak_memory_stats(0)
        for index, (name, metadata, descriptors) in enumerate(cases):
            try:
                case = compare_case(torch, core, audit, name, metadata, descriptors)
            except Exception as error:
                case = {'name': name, 'generator': metadata, 'input': float_record(descriptors),
                        'checks': {}, 'passed': False, 'errors': {'unexpected_case_error':
                        {'type': type(error).__name__, 'message': str(error)}}}
            report['cases'].append(case)
            if not case['passed']:
                report['failures'].append({'index': index, 'name': name,
                    'failed_checks': [key for key, value in case['checks'].items() if not value], 'errors': case['errors']})
            if (index + 1) % 32 == 0:
                save_report(report_path, report)
                print(json.dumps({'completed_cases': index + 1, 'planned_cases': len(cases),
                                  'failed_cases': len(report['failures'])}), flush=True)
        torch.cuda.synchronize(0)
        report['elapsed_numeric_seconds'] = time.monotonic() - started
        report['cpu_global_rng_unchanged'] = torch.equal(cpu_rng_before, torch.get_rng_state())
        report['cuda_global_rng_unchanged'] = torch.equal(cuda_rng_before, torch.cuda.get_rng_state(0))
        report['peak_allocated_bytes'] = torch.cuda.max_memory_allocated(0)
        report['peak_reserved_bytes'] = torch.cuda.max_memory_reserved(0)
        report['own_process_rows_final'] = [row for row in process_rows() if row['pid'] in identities]
        report['final_process_uuid_valid'] = bool(report['own_process_rows_final']) and {
            row['gpu_uuid'] for row in report['own_process_rows_final']} == {expected_uuid}
        report['source_unchanged'] = all(file_sha(path) == report['sources'][key]['sha256'] for key, path in sources.items())
        report['case_inputs_sha256'] = json_sha([{'name': row['name'], 'input': row['input']} for row in report['cases']])
        report['passed_cases'] = sum(case['passed'] for case in report['cases'])
        report['completed_cases'] = len(report['cases'])
        report['all_checks_passed'] = (not report['failures'] and report['source_unchanged']
            and report['completed_cases'] == report['planned_cases'] and report['cpu_global_rng_unchanged']
            and report['cuda_global_rng_unchanged'] and report['final_process_uuid_valid'] and report['peak_reserved_bytes'] <= ALLOCATOR_LIMIT_BYTES)
        report['status'] = 'pass' if report['all_checks_passed'] else 'fail'
        del allocation
    except Exception as error:
        report['status'] = 'fail'
        report['all_checks_passed'] = False
        report['fatal_error'] = {'type': type(error).__name__, 'message': str(error)}
    finally:
        report['cuda_initialized'] = bool(torch is not None and torch.cuda.is_initialized())
        report['completed_at'] = utc()
        save_report(report_path, report)
        if lock is not None:
            lock.close()
    print(json.dumps({'report': str(report_path), 'status': report['status'],
                      'completed_cases': len(report['cases']), 'failed_cases': len(report['failures']),
                      'fatal_error': report.get('fatal_error')}), flush=True)
    return 0 if report.get('all_checks_passed') else 2


if __name__ == '__main__':
    raise SystemExit(main())
