#!/usr/bin/env python3
"""N23 v2 admission identity; arithmetic reuses unchanged v1 implementation."""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts import qd_ed_n23_backend_preflight as legacy
from scripts import qd_ed_n23_worker as worker
from scripts import qd_ed_n23_v2_contract as contract
PROTOCOL_SHA=contract.BACKEND_PROTOCOL_SHA
LIMITS=legacy.LIMITS
EXTRA_SOURCE=legacy.EXTRA_SOURCE|contract.EXTRA_SOURCE
corpus_from_index=legacy.corpus_from_index
verify_corpus_files=legacy.verify_corpus_files
iter_batches=legacy.iter_batches
check_batch=legacy.check_batch
synthetic_batches=legacy.synthetic_batches
wrong_bounds_rejected=legacy.wrong_bounds_rejected
create_backend=legacy.create_backend


def predecessor_gate(reference):
    from scripts import qd_ed_n23_v2_predecessor as predecessor
    return predecessor.gate(reference)


def build_plan(*, root, protocol, runtime, corpus_index, source_paths, artifact_root, predecessor_review=None):
    """Pure non-executable draft; no GPU, runtime, ledger or release mutation."""
    root = Path(root).resolve(); protocol = Path(protocol).resolve()
    worker.require(worker.sha(protocol) == PROTOCOL_SHA, 'preflight frozen protocol changed')
    source = worker.source_record(root, set(source_paths) | worker.REQUIRED_SOURCE | EXTRA_SOURCE)
    runtime_data = worker.read_ref(runtime)
    worker.require(worker.cuda_binding(runtime_data)['physical_gpu'] == 7, 'preflight requires frozen GPU7 runtime')
    return {'schema': 'n23-backend-preflight-plan-v2', 'worktree': str(root), 'limits': LIMITS,
            'artifact_root': str(Path(artifact_root).resolve()),
            'protocol': {'path': str(protocol), 'sha256': PROTOCOL_SHA}, 'runtime': runtime,
            'source': source, 'corpus': corpus_from_index(corpus_index),
            'predecessor_review': predecessor_review, 'timeout_observability':contract.ref(contract.OBSERVABILITY), 'synthetic_cases': 'fp32_bf16_native_seven_point_v1',
            'task_outcome': False, 'requires_separate_release': True}


def validate_plan(plan):
    worker.require(set(plan) == {'schema', 'worktree', 'artifact_root', 'limits', 'protocol', 'runtime', 'source', 'corpus',
                                'predecessor_review', 'timeout_observability', 'synthetic_cases', 'task_outcome', 'requires_separate_release'}
                   | ({'uuid_repair'} if plan.get('uuid_repair') is not None else set())
                   and plan['schema'] == 'n23-backend-preflight-plan-v2' and plan['limits'] == LIMITS
                   and plan['worktree'] == str(ROOT.resolve()) and plan['task_outcome'] is False
                   and plan['requires_separate_release'] is True
                   and plan['synthetic_cases'] == 'fp32_bf16_native_seven_point_v1', 'preflight finite scope differs')
    worker.require(plan.get('timeout_observability')==contract.ref(contract.OBSERVABILITY)
        and worker.sha(contract.OBSERVABILITY)==contract.OBSERVABILITY_SHA,'preflight timeout observability differs')
    worker.require(plan['protocol']['sha256'] == PROTOCOL_SHA and worker.sha(plan['protocol']['path']) == PROTOCOL_SHA,
                   'preflight protocol source changed')
    worker.verify_source(ROOT, plan['source'])
    worker.require(EXTRA_SOURCE <= {r['path'] for r in plan['source']['files']}, 'preflight required source absent')
    worker.require(plan['corpus'] == corpus_from_index(plan['corpus']['index']), 'preflight corpus changed')
    if plan.get('uuid_repair') is not None:
        from scripts import qd_ed_n23_uuid_repair as repair
        repair.validate_plan(plan)
    predecessor_gate(plan['predecessor_review'])
    return worker.read_ref(plan['runtime'])


def artifact_name(plan,kind):
    prefix='n23-backend-uuid-repair' if plan.get('uuid_repair') is not None else 'n23-backend-preflight'
    return prefix+'-'+kind+('-v1.json' if plan.get('uuid_repair') is not None else '.json')


def run_preflight(plan_path, release_path, attempt_context_path):
    started = time.perf_counter()
    plan_ref = {'path': str(Path(plan_path).resolve()), 'sha256': worker.sha(plan_path)}
    plan = worker.read_ref(plan_ref)
    runtime = validate_plan(plan)
    release = json.loads(Path(release_path).read_text())
    context = json.loads(Path(attempt_context_path).read_text())
    retry={'retry_of':plan['uuid_repair']['retry_of']} if plan.get('uuid_repair') is not None else {}
    worker.require(set(context) == {'schema', 'attempt_id', 'output_dir', 'budget_bucket', 'plan', 'timeout_seconds', 'cleanup_seconds'}|set(retry)
                   and all(context.get(k)==v for k,v in retry.items())
                   and context['schema'] == 'n23-recovery-attempt-context-v2' and context['budget_bucket'] == 'recovery'
                   and context['plan'] == plan_ref and context['timeout_seconds'] == 120 and context['cleanup_seconds'] == 40,
                   'preflight requires separately charged recovery attempt context')
    worker.require(release == {'schema': 'n23-backend-preflight-release-v2', 'plan': plan_ref,
                               'source': plan['source'], 'runtime': plan['runtime'], 'limits': LIMITS,
                               'attempt_id': context['attempt_id'], 'predecessor_review': plan['predecessor_review'],**retry},
                   'preflight release differs from finite plan')
    output = Path(context['output_dir']).resolve()
    worker.require(output.name == context['attempt_id']
                   and output == Path(plan['artifact_root']).resolve() / 'attempts' / context['attempt_id'],
                   'preflight attempt/output identity differs')
    report_path = output / artifact_name(plan,'report')
    worker.require(not report_path.exists(), 'preflight cannot retry or overwrite output')
    identity = worker.process_identity()
    worker.atomic_json(output / artifact_name(plan,'start'), {
        'schema': 'n23-backend-preflight-start-v2', 'process': identity, 'plan': plan_ref,
        'attempt_id': context['attempt_id'], 'source': plan['source']})
    report = {'schema': 'n23-backend-preflight-proof-v2', 'accepted': False, 'task_outcome': False,
              'plan': plan_ref, 'release': {'path': str(Path(release_path).resolve()), 'sha256': worker.sha(release_path)},
              'attempt_context': {'path': str(Path(attempt_context_path).resolve()), 'sha256': worker.sha(attempt_context_path)},
              'attempt_id': context['attempt_id'], 'process': identity, 'source': plan['source'],
              'runtime': plan['runtime'], 'limits': LIMITS, 'batches': [], 'synthetic': [], 'errors': []}
    if retry:report['uuid_repair']=plan['uuid_repair'];report.update(retry)
    try:
        backend = create_backend('cuda', binding=worker.cuda_binding(runtime))
        for batch in iter_batches(plan['corpus']):
            report['batches'].append(check_batch(batch, backend))
        for batch in synthetic_batches(backend):
            report['synthetic'].append(check_batch(batch, backend))
        report['wrong_bounds_rejected'] = wrong_bounds_rejected()
        backend.synchronize()
        report['backend'] = backend.report()
        worker.verify_source(ROOT, plan['source'])
        worker.require(worker.process_identity() == identity, 'preflight process identity changed')
        worker.require(len(report['batches']) == plan['corpus']['expected_batches']
                       and sum(r['candidates'] for r in report['batches']) == plan['corpus']['expected_candidates'],
                       'preflight corpus batch/candidate coverage differs')
        report['accepted'] = (all(r['accepted'] for r in report['batches'] + report['synthetic'])
                              and report['wrong_bounds_rejected'] and len(report['synthetic']) == 2)
    except Exception as exc:
        report['errors'].append(type(exc).__name__ + ':' + str(exc))
        if isinstance(getattr(exc,'identity_diagnostic',None),dict):
            report['identity_diagnostic']=exc.identity_diagnostic
    finally:
        report['worker_wall_seconds'] = time.perf_counter() - started
        if report['worker_wall_seconds'] > 120:
            report['accepted'] = False; report['errors'].append('preflight_worker_timeout_bound')
        worker.atomic_json(report_path, report)
    return 0 if report['accepted'] else 2


def verify_preflight_proof(plan_path, report_path, attempt_result, future_source):
    """Hash/JSON-only readiness check; never executes CUDA in a supervisor."""
    plan = json.loads(Path(plan_path).read_text())
    validate_plan(plan)
    report = json.loads(Path(report_path).read_text())
    worker.require(report.get('schema') == 'n23-backend-preflight-proof-v2' and report.get('accepted') is True
                   and report.get('task_outcome') is False and report.get('plan') == {
                       'path': str(Path(plan_path).resolve()), 'sha256': worker.sha(plan_path)}
                   and report.get('source') == plan['source'] == future_source
                   and report.get('runtime') == plan['runtime'] and report.get('limits') == LIMITS,
                   'preflight proof/source/finite scope differs from future Dev')
    worker.require(json.loads((Path(report_path).parent / artifact_name(plan,'start')).read_text()) == {
        'schema': 'n23-backend-preflight-start-v2', 'process': report['process'], 'plan': report['plan'],
        'attempt_id': report['attempt_id'], 'source': report['source']}, 'preflight start/process binding differs')
    release=worker.read_ref(report['release']);context=worker.read_ref(report['attempt_context'])
    if plan.get('uuid_repair') is not None:
        worker.require(report.get('uuid_repair')==plan['uuid_repair'] and report.get('retry_of')==plan['uuid_repair']['retry_of']
            and attempt_result.get('retry_of')==report['retry_of'] and release.get('retry_of')==report['retry_of']
            and context.get('retry_of')==report['retry_of'],'UUID repair report/context/terminal lineage differs')
    worker.require(attempt_result.get('budget_bucket') == 'recovery'
                   and attempt_result.get('attempt_id') == report.get('attempt_id')
                   and attempt_result.get('outcome_valid') is True
                   and attempt_result.get('event') == 'valid'
                   and type(attempt_result.get('gpu_process_wall_seconds')) in (int, float)
                   and math.isfinite(attempt_result['gpu_process_wall_seconds'])
                   and 0 <= report['worker_wall_seconds'] <= 120
                   and report['worker_wall_seconds'] <= attempt_result['gpu_process_wall_seconds'] <= 160
                   and attempt_result.get('backend_preflight_report') == {'path': str(Path(report_path).resolve()), 'sha256': worker.sha(report_path)}
                   and attempt_result.get('process') == report['process'], 'preflight metered terminal proof differs')
    verify_corpus_files(plan['corpus'])
    runtime = worker.read_ref(plan['runtime']); backend = report.get('backend', {})
    worker.require(backend.get('kind') == 'cuda' and backend.get('logical_device') == 'cuda:0'
                   and backend.get('physical_uuid') == runtime['gpu_mapping']['uuid']
                   and isinstance(backend.get('torch_version'), str) and bool(backend['torch_version'])
                   and isinstance(backend.get('cuda_version'), str) and bool(backend['cuda_version'])
                   and {'torch.float32', 'torch.bfloat16'} <= set(backend.get('dtype_coverage', []))
                   and len(report['batches']) == 176 and sum(r['candidates'] for r in report['batches']) == 2816
                   and len(report['synthetic']) == 2 and all(r['accepted'] and not r['mismatches'] for r in report['batches'] + report['synthetic'])
                   and report.get('wrong_bounds_rejected') is True, 'preflight CUDA coverage or strict arithmetic proof missing')
    return {'path': str(Path(report_path).resolve()), 'sha256': worker.sha(report_path)}


def command(python, plan_path, release_path, attempt_context_path, *, root=ROOT):
    return [str(python), str(Path(root) / 'scripts/qd_ed_n23_v2_backend.py'),
            '--plan', str(Path(plan_path).resolve()), '--release', str(Path(release_path).resolve()),
            '--attempt-context', str(Path(attempt_context_path).resolve()),
            '--ownership-main', str(Path(root) / 'main.py')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--attempt-context', type=Path, required=True)
    parser.add_argument('--ownership-main', type=Path, required=True)
    args = parser.parse_args()
    worker.require(args.ownership_main.resolve() == ROOT / 'main.py', 'preflight ownership marker differs')
    return run_preflight(args.plan, args.release, args.attempt_context)

if __name__=='__main__':raise SystemExit(main())
