#!/usr/bin/env python3
"""N23-cohort owned main.py wrapper; audit completes inside the same metered PID.

This module does not grant dispatch authority. Its context must be emitted by the
separately released cohort runner, whose timeout includes main and this audit.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import subprocess
import math
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import audit_decision_evidence as audit
from scripts.qd_ed_audit_backend import assigned_cuda_identity, canonical_cuda_uuid, create_backend

WORKER_CONTRACT = {"schema": "n23-same-process-native-audit-v1", "arms": ["C0", "Q0", "N7", "N23"],
                   "n23_backend": "cuda", "other_arm_backend": "cpu", "timeout_includes_audit": True}
REQUIRED_SOURCE = {"main.py", "scripts/qd_ed_n23_worker.py", "scripts/qd_ed_audit_backend.py",
                   "scripts/audit_decision_evidence.py", "core/qd_actuator_clipped_quality.py",
                   "core/rdt_policy_steer.py", "core/env_adapters/libero_adapter.py",
                   "core/rdt_libero_action_converter.py", "core/qd_executed_quality.py", "configs/qd_ed_final/candidate_n23.json"}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def read_ref(reference):
    require(isinstance(reference, dict) and set(reference) == {"path", "sha256"}, "invalid file reference")
    path = Path(reference["path"])
    require(path.is_absolute() and path.is_file() and not path.is_symlink()
            and sha(path) == reference["sha256"], "file reference hash/path differs")
    return json.loads(path.read_text())


def source_record(root, paths):
    root = Path(root).resolve()
    paths = sorted(set(paths))
    require(REQUIRED_SOURCE <= set(paths), "N23 source manifest incomplete")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    files = []
    for relative in paths:
        name = Path(relative)
        require(not name.is_absolute() and ".." not in name.parts, "unsafe source path")
        path = root / name
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root), "source path missing or linked")
        committed = subprocess.check_output(["git", "show", commit + ":" + relative], cwd=root)
        require(path.read_bytes() == committed, "uncommitted source bytes")
        files.append({"path": relative, "sha256": sha(path)})
    return {"commit": commit, "files": files, "sha256": canonical_sha(files)}


def verify_source(root, record):
    require(isinstance(record, dict) and set(record) == {"commit", "files", "sha256"}, "source record invalid")
    require(source_record(root, [x["path"] for x in record["files"]]) == record, "source bytes differ")
    return record["sha256"]


def process_identity():
    return {"pid": os.getpid(), "proc_start_ticks": Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19],
            "boot_id": Path('/proc/sys/kernel/random/boot_id').read_text().strip()}


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), "refusing to overwrite worker artifact")
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
    os.replace(temp, path)


def evidence_record(output):
    output = Path(output).resolve()
    episode = output / "eds_eval/decision_evidence/episode_000"
    required = [output / "eds_eval/episode_compute.jsonl", episode / "status.json", episode / "events.jsonl"]
    index = [json.loads(line) for line in required[-1].read_text().splitlines()]
    required += [episode / row['bundle'] for row in index]
    rows = []
    for path in required:
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(output), "evidence path missing or unsafe")
        rows.append({"path": str(path.relative_to(output)), "sha256": sha(path)})
    return {"files": rows, "sha256": canonical_sha(rows)}


def cuda_binding(runtime):
    mapping = runtime['gpu_mapping']
    return {"physical_gpu": mapping['physical_gpu'], "uuid": mapping['uuid'], "logical_device": "cuda:0"}


def build_context(plan_path, runtime_path, row, attempt_id, output, command):
    """Pure draft construction; creates no files and grants no dispatch authority."""
    plan_path, runtime_path = Path(plan_path).resolve(), Path(runtime_path).resolve()
    plan = json.loads(plan_path.read_text()); root = Path(plan['worktree']).resolve()
    return {"schema": "n23-metered-worker-context-v1", "attempt_id": attempt_id,
            "episode_key": row['episode_key'], "profile": row['profile'], "output_dir": str(Path(output).resolve()),
            "worktree": str(root), "main_argv": list(command[1:]),
            "plan": {"path": str(plan_path), "sha256": sha(plan_path)},
            "runtime": {"path": str(runtime_path), "sha256": sha(runtime_path)},
            "source": source_record(root, [x['path'] for x in plan['code_files']])}


def wrapped_command(command, context_path):
    """main.py remains an actual OS argv token for existing ownership checks."""
    require(len(command) >= 2 and Path(command[1]).name == "main.py", "original main command invalid")
    return [command[0], str(Path(command[1]).parent / "scripts/qd_ed_n23_worker.py"),
            "--context", str(Path(context_path).resolve()), "--main", command[1], "--", *command[2:]]


def validate_context(context, main_argv):
    require(set(context) == {"schema", "attempt_id", "episode_key", "profile", "output_dir", "worktree",
                             "main_argv", "plan", "runtime", "source"}
            and context['schema'] == 'n23-metered-worker-context-v1', "worker context schema differs")
    root, output = Path(context['worktree']).resolve(), Path(context['output_dir']).resolve()
    require(root == ROOT.resolve() and context['main_argv'] == list(main_argv)
            and main_argv[0] == str(root / 'main.py') and output.name == context['attempt_id'], "worker command/root/attempt differs")
    plan, runtime = read_ref(context['plan']), read_ref(context['runtime'])
    if plan.get('n30_r1_cohort') is not None:
        from scripts import qd_ed_n30_r1_contract as n30r1
        return n30r1.validate_worker_context(context, main_argv, root, output, plan, runtime)
    if plan.get('n30_cohort') is not None or 'N30' in plan.get('candidate_profiles', {}):
        from scripts import qd_ed_n30_contract as n30
        return n30.validate_worker_context(context, main_argv, root, output, plan, runtime)
    if plan.get('n29_cohort') is not None or 'N29' in plan.get('candidate_profiles', {}):
        from scripts import qd_ed_n29_contract as n29
        return n29.validate_worker_context(context, main_argv, root, output, plan, runtime)
    if plan.get('n28_cohort') is not None or 'N28' in plan.get('candidate_profiles', {}):
        from scripts import qd_ed_n28_contract as n28
        return n28.validate_worker_context(context, main_argv, root, output, plan, runtime)
    if plan.get("n27_hydra_continuation") is not None:
        from scripts import qd_ed_n27_cont_contract as n27c
        return n27c.validate_worker_context(context, main_argv, root, output, plan, runtime)
    if plan.get('n27_cohort') is not None or 'N27' in plan.get('candidate_profiles', {}):
        from scripts import qd_ed_n27_contract as n27
        return n27.validate_worker_context(context, main_argv, root, output, plan, runtime)
    if plan.get('n25_infrastructure_continuation') is not None:
        from scripts import qd_ed_n25_cont_contract as n25c
        return n25c.validate_worker_context(context, main_argv, root, output, plan, runtime)
    if plan.get('n26_cohort') is not None:
        from scripts import qd_ed_n26_contract as n26
        return n26.validate_worker_context(context, main_argv, root, output, plan, runtime)
    if plan.get('n25_cohort') is not None:
        from scripts import qd_ed_n25_contract as n25
        return n25.validate_worker_context(context, main_argv, root, output, plan, runtime)
    if plan.get('n24_cohort') is not None:
        from scripts import qd_ed_n24_contract as n24
        return n24.validate_worker_context(context, main_argv, root, output, plan, runtime)
    require(plan.get('n23_cohort', {}).get('worker_audit') == WORKER_CONTRACT
            and plan['worktree'] == str(root) and context['profile'] in WORKER_CONTRACT['arms']
            and output == Path(plan['artifact_root']).resolve() / 'attempts' / context['attempt_id']
            and plan['runtime_manifest_path'] == context['runtime']['path']
            and plan['runtime_manifest_sha256'] == context['runtime']['sha256'], "worker plan/runtime/arm differs")
    rows = [r for r in plan['episodes'] if r['episode_key'] == context['episode_key']]
    require(len(rows) == 1 and rows[0]['profile'] == context['profile'] and rows[0]['split'] == 'dev'
            and rows[0]['timeout_seconds'] == 1800, "worker frozen episode differs")
    require(context['source']['files'] == plan['code_files']
            and context['source']['commit'] == plan['source_commit'], "worker plan/source records differ")
    verify_source(root, context['source'])
    require(cuda_binding(runtime)['physical_gpu'] == 7, "worker assigned GPU differs")
    return root, output, runtime


def run_worker(context_path, main_argv):
    started = time.perf_counter()
    context_path = Path(context_path).resolve()
    context_sha = sha(context_path)
    context = json.loads(context_path.read_text())
    root, output, runtime = validate_context(context, main_argv)
    identity = process_identity()
    receipt_path = output / 'eds_eval/in-worker-audit-receipt.json'
    report_path = output / 'eds_eval/decision-evidence-audit.json'
    require(not receipt_path.exists() and not report_path.exists(), "worker audit output already exists")
    start_path = output / 'eds_eval/in-worker-audit-start.json'
    atomic_json(start_path, {'schema': 'n23-worker-start-v1', 'process': identity,
                            'context': {'path': str(context_path), 'sha256': context_sha}})
    receipt = {"schema": "n23-in-worker-audit-receipt-v1", "attempt_id": context['attempt_id'],
               "episode_key": context['episode_key'], "profile": context['profile'], "process": identity,
               "context": {"path": str(context_path), "sha256": context_sha},
               "plan": context['plan'], "runtime": context['runtime'], "source": context['source'],
               "main_argv_sha256": canonical_sha(main_argv), "accepted": False,
               "main_exit_code": None, "audit_seconds": 0., "audit_report": None, "evidence": None}
    old_argv, old_cwd = sys.argv, Path.cwd()
    failure = None
    try:
        sys.argv = list(main_argv)
        os.chdir(root)
        try:
            runpy.run_path(main_argv[0], run_name='__main__')
            receipt['main_exit_code'] = 0
        except SystemExit as exc:
            receipt['main_exit_code'] = exc.code if isinstance(exc.code, (int, str)) else (0 if exc.code is None else 1)
            if receipt['main_exit_code'] != 0:
                failure = exc
        except BaseException as exc:
            receipt['main_exit_code'] = 130 if isinstance(exc, KeyboardInterrupt) else 1
            failure = exc
        if failure is None:
            require(process_identity() == identity and sha(context_path) == context_sha, "worker identity/context changed during main")
            verify_source(root, context['source']); read_ref(context['runtime']); read_ref(context['plan'])
            receipt['worker_cuda'] = assigned_cuda_identity(cuda_binding(runtime))
            backend = create_backend('cuda', binding=cuda_binding(runtime)) if context['profile'] in {'N23', 'N24', 'N25', 'N26', 'N27', 'N28', 'N29'} else create_backend('cpu')
            backend.synchronize()
            audit_started = time.perf_counter()
            before = evidence_record(output)
            report = audit.audit_episode(output / 'eds_eval/decision_evidence/episode_000',
                                         output / 'eds_eval/episode_compute.jsonl', arithmetic_backend=backend)
            if read_ref(context['plan']).get('n30_cohort') is not None or read_ref(context['plan']).get('n30_r1_cohort') is not None:
                from scripts import qd_ed_n30_native as n30_native
                report = n30_native.audit_output(context['profile'], output, report, backend)
            if read_ref(context['plan']).get('n29_cohort') is not None:
                from scripts import qd_ed_n29_native as n29_native
                report = n29_native.audit_output(context['profile'], output, report, backend)
            if read_ref(context['plan']).get('n28_cohort') is not None:
                from scripts import qd_ed_n28_native as n28_native
                report = n28_native.audit_output(context['profile'], output, report, backend)
            if read_ref(context['plan']).get('n27_cohort') is not None:
                from scripts import qd_ed_n27_native as n27_native
                report = n27_native.audit_output(context['profile'], output, report, backend)
            if read_ref(context['plan']).get('n26_cohort') is not None:
                from scripts import qd_ed_n26_native as n26_native
                report = n26_native.audit_output(context['profile'], output, report, backend)
            if read_ref(context['plan']).get('n25_cohort') is not None:
                from scripts import qd_ed_n25_native as n25_native
                report = n25_native.audit_output(context['profile'], output, report, backend)
            backend.synchronize()
            after = evidence_record(output)
            receipt['audit_seconds'] = time.perf_counter() - audit_started
            require(before == after, "worker evidence mutated during audit")
            receipt['evidence'] = after
            if context['profile'] == 'N24' or read_ref(context['plan']).get('n24_cohort') is not None:
                from scripts import qd_ed_n24_native as n24_native
                receipt['n24_native_counts'], receipt['n24_auxiliary'] = n24_native.from_output(context['profile'], output, report)
                metric_path = output / 'eds_eval/eds_metrics.jsonl'
                receipt['n24_metrics'] = {'path': str(metric_path), 'present': metric_path.is_file(),
                    'sha256': sha(metric_path) if metric_path.is_file() else None}
            if read_ref(context['plan']).get('n30_cohort') is not None or read_ref(context['plan']).get('n30_r1_cohort') is not None:
                from scripts import qd_ed_n30_native as n30_native
                receipt['n30_native_counts'], receipt['n30_auxiliary'] = n30_native.from_output(context['profile'], output, report)
                metric_path = output / 'eds_eval/eds_metrics.jsonl'
                receipt['n30_metrics'] = {'path': str(metric_path), 'present': metric_path.is_file(),
                    'sha256': sha(metric_path) if metric_path.is_file() else None}
            if read_ref(context['plan']).get('n29_cohort') is not None:
                from scripts import qd_ed_n29_native as n29_native
                receipt['n29_native_counts'], receipt['n29_auxiliary'] = n29_native.from_output(context['profile'], output, report)
                metric_path = output / 'eds_eval/eds_metrics.jsonl'
                receipt['n29_metrics'] = {'path': str(metric_path), 'present': metric_path.is_file(),
                    'sha256': sha(metric_path) if metric_path.is_file() else None}
            if read_ref(context['plan']).get('n28_cohort') is not None:
                from scripts import qd_ed_n28_native as n28_native
                receipt['n28_native_counts'], receipt['n28_auxiliary'] = n28_native.from_output(context['profile'], output, report)
                metric_path = output / 'eds_eval/eds_metrics.jsonl'
                receipt['n28_metrics'] = {'path': str(metric_path), 'present': metric_path.is_file(),
                    'sha256': sha(metric_path) if metric_path.is_file() else None}
            if read_ref(context['plan']).get('n27_cohort') is not None:
                from scripts import qd_ed_n27_native as n27_native
                receipt['n27_native_counts'], receipt['n27_auxiliary'] = n27_native.from_output(context['profile'], output, report)
                metric_path = output / 'eds_eval/eds_metrics.jsonl'
                receipt['n27_metrics'] = {'path': str(metric_path), 'present': metric_path.is_file(),
                    'sha256': sha(metric_path) if metric_path.is_file() else None}
            if read_ref(context['plan']).get('n26_cohort') is not None:
                from scripts import qd_ed_n26_native as n26_native
                receipt['n26_native_counts'], receipt['n26_auxiliary'] = n26_native.from_output(context['profile'], output, report)
                metric_path = output / 'eds_eval/eds_metrics.jsonl'
                receipt['n26_metrics'] = {'path': str(metric_path), 'present': metric_path.is_file(),
                    'sha256': sha(metric_path) if metric_path.is_file() else None}
            if read_ref(context['plan']).get('n25_cohort') is not None:
                from scripts import qd_ed_n25_native as n25_native
                receipt['n25_native_counts'], receipt['n25_auxiliary'] = n25_native.from_output(context['profile'], output, report)
                metric_path = output / 'eds_eval/eds_metrics.jsonl'
                receipt['n25_metrics'] = {'path': str(metric_path), 'present': metric_path.is_file(),
                    'sha256': sha(metric_path) if metric_path.is_file() else None}
            atomic_json(report_path, report)
            receipt['audit_report'] = {"path": str(report_path), "sha256": sha(report_path)}
            receipt['accepted'] = report.get('accepted') is True
            receipt['audit_backend'] = backend.report()
    except BaseException as exc:
        failure = failure or exc
        receipt['worker_error_type'] = type(exc).__name__
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)
        receipt['worker_wall_seconds'] = time.perf_counter() - started
        receipt['process_unchanged'] = process_identity() == identity
        try:
            atomic_json(receipt_path, receipt)
        except BaseException as exc:
            failure = failure or exc  # Never mask the original main exit/failure.
    if failure is not None:
        raise failure
    return 0 if receipt['accepted'] and receipt['process_unchanged'] else 2


def verify_receipt(context_path, process_record):
    """Supervisor-side verification: hashes/JSON only, never reruns CUDA audit."""
    context_path = Path(context_path).resolve()
    context = json.loads(context_path.read_text())
    _, output, runtime = validate_context(context, context['main_argv'])
    receipt = json.loads((output / 'eds_eval/in-worker-audit-receipt.json').read_text())
    start = json.loads((output / 'eds_eval/in-worker-audit-start.json').read_text())
    require(start == {'schema': 'n23-worker-start-v1', 'process': receipt.get('process'),
                      'context': receipt.get('context')}, 'worker start/process association differs')
    expected_process = {key: process_record[key] for key in ('pid', 'proc_start_ticks', 'boot_id')}
    require(process_record['attempt_id'] == context['attempt_id']
            and receipt.get('schema') == 'n23-in-worker-audit-receipt-v1'
            and receipt.get('process') == expected_process and receipt.get('process_unchanged') is True
            and receipt.get('attempt_id') == context['attempt_id'] and receipt.get('episode_key') == context['episode_key']
            and receipt.get('profile') == context['profile'] and receipt.get('accepted') is True
            and receipt.get('main_exit_code') == 0, "worker outcome/process/attempt differs")
    require(receipt.get('context') == {'path': str(context_path), 'sha256': sha(context_path)}
            and all(receipt.get(k) == context[k] for k in ('plan', 'runtime', 'source'))
            and receipt.get('main_argv_sha256') == canonical_sha(context['main_argv'])
            and receipt.get('evidence') == evidence_record(output), "worker source/runtime/evidence binding differs")
    backend = receipt.get('audit_backend', {})
    kind = 'cuda' if context['profile'] in {'N23', 'N24', 'N25', 'N26', 'N27', 'N28', 'N29'} else 'cpu'
    require(backend.get('kind') == kind and backend.get('logical_device') == ('cuda:0' if kind == 'cuda' else 'cpu'), "worker audit backend differs")
    actual = receipt.get('worker_cuda', {})
    expected_uuid=canonical_cuda_uuid(runtime['gpu_mapping']['uuid'])
    require(actual.get('physical_gpu') == 7 and actual.get('uuid') == runtime['gpu_mapping']['uuid']
            and actual.get('physical_uuid') == expected_uuid
            and canonical_cuda_uuid(actual.get('actual_uuid')) == expected_uuid and actual.get('logical_device') == 'cuda:0',
            "worker runtime physical UUID differs")
    require(actual.get('actual_uuid_type') in {'builtins.str','torch._C._CUuuid'},'worker public UUID type missing')
    native_hex=actual.get('actual_uuid_bytes_hex')
    require((actual['actual_uuid_type']=='builtins.str' and native_hex is None)
        or (actual['actual_uuid_type']=='torch._C._CUuuid' and native_hex==expected_uuid[4:].replace('-','')),
        'worker serialized native UUID bytes differ')
    if kind == 'cuda':
        require(backend.get('physical_uuid') == actual['physical_uuid'] and isinstance(backend.get('dtype_coverage'), list)
                and backend.get('torch_version') == actual.get('torch_version')
                and backend.get('cuda_version') == actual.get('cuda_version'), "worker CUDA audit proof differs")
    report = read_ref(receipt['audit_report'])
    require(receipt['audit_report']['path'] == str(output / 'eds_eval/decision-evidence-audit.json')
            and report.get('accepted') is True and report.get('n23_arithmetic_backend') == backend,
            "worker independent audit result differs")
    if kind == 'cuda':
        gate = report.get('n23_actuator_clipped_quality_audit')
        if gate is None:
            require(report.get('observed_counts', {}).get('canonical_candidate_batch', 0) == 0
                    and backend['dtype_coverage'] == [], 'worker N23 native arithmetic missing')
        else:
            require(gate.get('candidate_scores_verified', 0) > 0 and backend['dtype_coverage'],
                    'worker N23 native arithmetic missing')
    require(type(receipt.get('audit_seconds')) in (int, float) and math.isfinite(receipt['audit_seconds']) and math.isfinite(receipt['worker_wall_seconds'])
            and 0 <= receipt['audit_seconds'] <= receipt['worker_wall_seconds'],
            "worker audit metering missing")
    if read_ref(context['plan']).get('n24_cohort') is not None:
        from scripts import qd_ed_n24_native as n24_native
        metric_path=output/'eds_eval/eds_metrics.jsonl'
        require(receipt.get('n24_metrics') == {'path':str(metric_path),'present':metric_path.is_file(),
            'sha256':sha(metric_path) if metric_path.is_file() else None}, 'N24 serialized metrics binding differs')
        counts,aux=n24_native.from_output(context['profile'],output,report)
        require(receipt.get('n24_native_counts')==counts and receipt.get('n24_auxiliary')==aux,
                'N24 profile-bound native counters differ')
    if read_ref(context['plan']).get('n30_cohort') is not None or read_ref(context['plan']).get('n30_r1_cohort') is not None:
        from scripts import qd_ed_n30_native as n30_native
        metric_path = output / 'eds_eval/eds_metrics.jsonl'
        require(receipt.get('n30_metrics') == {'path':str(metric_path),'present':metric_path.is_file(),
            'sha256':sha(metric_path) if metric_path.is_file() else None}, 'N30 serialized metrics binding differs')
        counts,aux = n30_native.from_output(context['profile'],output,report)
        require(receipt.get('n30_native_counts')==counts and receipt.get('n30_auxiliary')==aux,
                'N30 profile-bound native counters differ')
    if read_ref(context['plan']).get('n29_cohort') is not None:
        from scripts import qd_ed_n29_native as n29_native
        metric_path = output / 'eds_eval/eds_metrics.jsonl'
        require(receipt.get('n29_metrics') == {'path':str(metric_path),'present':metric_path.is_file(),
            'sha256':sha(metric_path) if metric_path.is_file() else None}, 'N29 serialized metrics binding differs')
        counts,aux = n29_native.from_output(context['profile'],output,report)
        require(receipt.get('n29_native_counts')==counts and receipt.get('n29_auxiliary')==aux,
                'N29 profile-bound native counters differ')
    if read_ref(context['plan']).get('n28_cohort') is not None:
        from scripts import qd_ed_n28_native as n28_native
        metric_path = output / 'eds_eval/eds_metrics.jsonl'
        require(receipt.get('n28_metrics') == {'path':str(metric_path),'present':metric_path.is_file(),
            'sha256':sha(metric_path) if metric_path.is_file() else None}, 'N28 serialized metrics binding differs')
        counts,aux = n28_native.from_output(context['profile'],output,report)
        require(receipt.get('n28_native_counts')==counts and receipt.get('n28_auxiliary')==aux,
                'N28 profile-bound native counters differ')
    if read_ref(context['plan']).get('n27_cohort') is not None:
        from scripts import qd_ed_n27_native as n27_native
        metric_path = output / 'eds_eval/eds_metrics.jsonl'
        require(receipt.get('n27_metrics') == {'path':str(metric_path),'present':metric_path.is_file(),
            'sha256':sha(metric_path) if metric_path.is_file() else None}, 'N27 serialized metrics binding differs')
        counts,aux = n27_native.from_output(context['profile'],output,report)
        require(receipt.get('n27_native_counts')==counts and receipt.get('n27_auxiliary')==aux,
                'N27 profile-bound native counters differ')
    if read_ref(context['plan']).get('n26_cohort') is not None:
        from scripts import qd_ed_n26_native as n26_native
        metric_path = output / 'eds_eval/eds_metrics.jsonl'
        require(receipt.get('n26_metrics') == {'path':str(metric_path),'present':metric_path.is_file(),
            'sha256':sha(metric_path) if metric_path.is_file() else None}, 'N26 serialized metrics binding differs')
        counts,aux = n26_native.from_output(context['profile'],output,report)
        require(receipt.get('n26_native_counts')==counts and receipt.get('n26_auxiliary')==aux,
                'N26 profile-bound native counters differ')
    if read_ref(context['plan']).get('n25_cohort') is not None:
        from scripts import qd_ed_n25_native as n25_native
        metric_path = output / 'eds_eval/eds_metrics.jsonl'
        require(receipt.get('n25_metrics') == {'path':str(metric_path),'present':metric_path.is_file(),
            'sha256':sha(metric_path) if metric_path.is_file() else None}, 'N25 serialized metrics binding differs')
        counts,aux = n25_native.from_output(context['profile'],output,report)
        require(receipt.get('n25_native_counts')==counts and receipt.get('n25_auxiliary')==aux,
                'N25 profile-bound native counters differ')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', type=Path, required=True)
    parser.add_argument('--main', type=Path, required=True)
    parser.add_argument('hydra_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    tail = args.hydra_args[1:] if args.hydra_args[:1] == ['--'] else args.hydra_args
    return run_worker(args.context, [str(args.main.resolve()), *tail])


if __name__ == '__main__':
    raise SystemExit(main())
