"""N36 metered worker and hash-only parent receipt verification.

The public launch requires a detached root release. Draft contexts remain closed.
Every execution and receipt consumer requires the same detached release closure.
"""
import sys
if __name__ == '__main__' and '_n36_source_bootstrap' not in sys.modules:
    raise RuntimeError('Launch N36 worker through qd_ed_n36_bootstrap.py')
import os
import json
from pathlib import Path
import time

# Emit before project imports so import/setup stalls leave phase evidence.
if __name__ == '__main__':
    _imports_started = time.perf_counter()
    print(json.dumps({'schema': 'n36-verification-phase-v1', 'phase': 'worker_imports',
                      'event': 'begin', 'pid': os.getpid(),
                      'monotonic_seconds': time.perf_counter()}), file=sys.stderr, flush=True)

from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n36_bridge as b, qd_ed_n36_contract as c
from scripts import qd_ed_n36_native as n36, qd_ed_n31_native as controls
from scripts import audit_decision_evidence as generic
from scripts import qd_ed_n34_source as closure, qd_ed_n34_controller as controller
from scripts import qd_ed_n34_worker as n34_worker
from scripts import qd_ed_n36_build as native_build
from scripts import qd_ed_n36_source as source_execution
from scripts.qd_ed_audit_backend import create_backend, assigned_cuda_identity, canonical_cuda_uuid

if __name__ == '__main__':
    print(json.dumps({'schema': 'n36-verification-phase-v1', 'phase': 'worker_imports',
                      'event': 'end', 'pid': os.getpid(),
                      'monotonic_seconds': time.perf_counter(),
                      'elapsed_seconds': time.perf_counter() - _imports_started}),
          file=sys.stderr, flush=True)


def attest_worker_loaded(root, source):
    """Bind the executing worker, including Python's -m __main__, to frozen bytes.

    Do not import a second worker or register an alias: attest this function's
    actual module. Main's temporary __main__ is restored by runpy before the
    post-run inventory. The separate source_execution receipt binds compilation.
    """
    loaded = b.attest_loaded(root, source)
    canonical = 'scripts.qd_ed_n36_worker'
    relative = 'scripts/qd_ed_n36_worker.py'
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


def release_api(plan_ref):
    """Use only the N36 detached release family, never a predecessor release."""
    plan = w.read_ref(plan_ref)
    if plan.get('schema') == 'n36-engineering-execution-plan-v1':
        from scripts import qd_ed_n36_engineering as release
    else:
        w.require(plan.get('schema') == 'n36-released-plan-v1', 'unsupported worker release schema')
        from scripts import qd_ed_n36_release as release
    return release


def validate_context(reference, *, admission=False):
    with closure.verification_phase('context'):
        return _validate_context(reference, admission=admission)


def _validate_context(reference, *, admission=False):
    context = w.read_ref(reference)
    engineering = context.get('schema') == 'n36-engineering-worker-context-v1'
    fields = {'schema', 'plan', 'release', 'expected_manifest', 'episode_key', 'attempt_id', 'main_argv', 'worker_contract'}
    if engineering:
        fields |= {'purpose', 'scope', 'audit_plan'}
    w.require(set(context) == fields, 'worker context fields: explicit detached release required')
    w.require(context['schema'] in ('n36-worker-context-v1', 'n36-engineering-worker-context-v1')
              and context['worker_contract'] == c.WORKER_CONTRACT, 'worker contract')
    release = release_api(context['plan'])
    plan, runtime, authority, manifests = release._verify_release_transaction(context['plan'], context['release'])
    w.require(engineering == (plan['schema'] == 'n36-engineering-execution-plan-v1'), 'worker context/release family cross-use')
    if engineering:
        w.require(all(context[key] == plan[key] for key in ('purpose', 'scope', 'audit_plan')), 'engineering context bindings')
    rows = [r for r in plan['episodes'] if r['episode_key'] == context['episode_key']]
    w.require(len(rows) == 1 and context['attempt_id'] == context['episode_key'], 'exact primary attempt')
    row = rows[0]
    w.require(context['expected_manifest'] == plan['expected_manifests'][row['episode_key']], 'plan/command external anchor')
    manifest = manifests[row['episode_key']]
    w.require(context['main_argv'] == manifest['argv'][1:], 'exact candidate command')
    w.require(runtime['gpu_mapping']['physical_gpu'] == 7 and runtime['gpu_mapping']['uuid'] == c.GPU_UUID, 'assigned GPU mapping')
    if admission:
        (release.launch_guard if engineering else c.launch_guard)(plan, authority)
    return context, plan, runtime, row, manifest


def context_for(plan_ref, row, release_ref=None):
    release = release_api(plan_ref)
    plan, _, _ = release.validate_release(plan_ref, release_ref)
    manifest_ref = plan['expected_manifests'][row['episode_key']]
    manifest = w.read_ref(manifest_ref)
    w.require(row in plan['episodes'] and manifest['row'] == row, 'context row')
    tags = ({'schema': 'n36-engineering-worker-context-v1',
             **{key: plan[key] for key in ('purpose', 'scope', 'audit_plan')}}
            if plan['schema'] == 'n36-engineering-execution-plan-v1' else {})
    return {'schema': 'n36-worker-context-v1', **tags, 'plan': plan_ref, 'expected_manifest': manifest_ref,
            'episode_key': row['episode_key'], 'attempt_id': row['episode_key'],
            'main_argv': manifest['argv'][1:], 'worker_contract': c.WORKER_CONTRACT,
            'release': release_ref}



def operational_binding(plan):
    if plan.get('schema') == 'n36-engineering-execution-plan-v1':
        from scripts.qd_ed_n36_engineering import operational_binding as binding
        return binding(plan)
    return c.operational_binding(plan)

def native_counts(profile, output, report, expected, guided=None):
    """Parent verifies bound scalar/compute receipts; no tensor replay or CUDA."""
    w.require(profile in c.ARMS and report.get('accepted') is True
              and report.get('evidence_complete') is True, 'generic gate/profile required')
    output = Path(output)
    if profile != 'N36':
        w.require(n36.GATE not in report and report.get('n36_control_absence') == {'profile':profile,'events':0,'metrics':0}, 'N36 memory absent in controls')
        arithmetic=report.get('n36_control_arithmetic',{})
        w.require(arithmetic.get('kind')=='native_recomputation' and arithmetic.get('device')=='cuda:0'
            and arithmetic.get('gpu_attested') is True,'mandatory control native arithmetic')
        return n34_worker.native_counts(profile, output, report, expected, guided=guided)
    gate = report.get(n36.GATE, {})
    w.require(gate.get('schema') == 'n36-independent-nonprogress-tangent-v1' and gate.get('profile') == 'N36'
              and expected is not None and gate.get('runtime_identity') == expected, 'mandatory N36 independent gate/runtime')
    mp = output / 'eds_eval/eds_metrics.jsonl'
    cp = output / 'eds_eval/episode_compute.jsonl'
    w.require(mp.is_file() and not mp.is_symlink() and cp.is_file() and not cp.is_symlink(), 'N36 metrics/compute paths')
    metrics = [json.loads(x) for x in mp.read_text().splitlines() if x.strip()]
    rows = [json.loads(x) for x in cp.read_text().splitlines() if x.strip()]
    w.require(len(rows) == 1, 'one compute record')
    compute = rows[0]; n = len(metrics)
    w.require(gate.get('guided_decisions') == n == compute.get('guided_chunks')
              and (guided is None or guided == n) and compute.get('policy_counters_available') is True
              and compute.get('task_id') == expected['binding']['task_id'], 'N36 compute identity/coverage')
    costs = gate.get('compute_expected')
    w.require(isinstance(costs, dict) and costs.get('guided_chunks') == n
              and all(compute.get(k) == v for k,v in costs.items()), 'N36 bound cost gate')
    w.require(all(m.get('capture_dwell_proposal', {}).get('schema') == 'n36-nonprogress-tangent-scalar-v1'
                  and m['capture_dwell_proposal'].get('mode') == b.MODE for m in metrics), 'N36 scalar profile')
    arithmetic=gate.get('arithmetic',{})
    w.require(arithmetic.get('kind')=='native_recomputation' and arithmetic.get('device')=='cuda:0'
        and arithmetic.get('gpu_attested') is True and arithmetic.get('batches')==costs['reward_scoring_batches'], 'mandatory actual device arithmetic')
    lifecycle=gate.get('lifecycle',{})
    w.require(lifecycle.get('expiries')==n and lifecycle.get('acknowledgements')==gate.get('executed_actions_verified')
        and type(lifecycle.get('eligible_boundaries')) is int and 0<=lifecycle['eligible_boundaries']<=n
        and lifecycle.get('consumptions')==lifecycle['eligible_boundaries']
        and isinstance(lifecycle.get('exclusions'),dict), 'mandatory lifecycle counts')
    for name in ('native_delta_count_total','decoded_delta_count_total','zero_decoded_delta_memory_opportunities','memory_proposals_retained_after_update','eligible_opportunities','detour_insertions'):
        w.require(type(gate.get(name)) is int and gate[name]>=0, 'mandatory N36 delta/survival counts')
    response=gate.get('physical_response',{})
    w.require(response.get('selected_detours')==lifecycle.get('detour_selections')
        and response.get('unknown_responses',-1)+response.get('observed_responses',-1)==response.get('selected_detours')
        and isinstance(response.get('responses'),list),'mandatory physical-response denominators')
    return gate, {'http_counters': 'Unknown'}


def audit_native(profile, output, report, backend, expected, *, arithmetic_device="cuda:0"):
    w.require(report.get('accepted') is True and report.get('evidence_complete') is True
              and backend.report()['kind'] == 'cpu', 'generic audit must pass first on CPU')
    w.require(profile in c.ARMS, 'closed N36 profile')
    if profile == 'N36':
        return n36.audit_output(output, report, expected_runtime=expected, arithmetic_device=arithmetic_device)
    root = Path(output) / 'eds_eval/decision_evidence/episode_000'
    events = generic.load_events(root, json.loads((root / 'status.json').read_text()))
    w.require(not any(e['event'].startswith(('n35_','n36_')) for e in events), 'control N36 evidence')
    mp=Path(output)/'eds_eval/eds_metrics.jsonl'
    metrics=[json.loads(x) for x in mp.read_text().splitlines() if x.strip()] if mp.exists() else []
    w.require(not any(m.get('capture_dwell_proposal',{}).get('mode')==b.MODE or any(k.startswith('n36_') for k in m) for m in metrics), 'control N36 metrics')
    from scripts.qd_ed_n36_arithmetic import verify_scores
    arithmetic=verify_scores(events,device=arithmetic_device)
    result=n34_worker.audit_native(profile,output,report,backend,expected)
    result['n36_control_arithmetic']=arithmetic
    result['n36_control_absence']={'profile':profile,'events':0,'metrics':0}
    return result


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


def runtime_receipt_binding(context_ref, plan, process, phase):
    return {'context': context_ref, 'runtime_closure': plan['runtime_closure'],
            'process': process, 'phase': phase}


def persist_runtime_observation(output, phase, receipt):
    """Create once; parent hashes verify retained bytes after process exit."""
    import json
    path = Path(output) / 'eds_eval' / ('n36-runtime-' + phase + '.json')
    value = {key: receipt[key] for key in
             ('runtime_' + phase, 'execution_' + phase, 'loaded_' + phase, 'native_build_' + phase)}
    # No overwrite, including symlink aliases. Final receipt binds these bytes.
    with path.open('x') as stream:
        json.dump(value, stream, sort_keys=True, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    path.chmod(0o444)
    return c.ref(path)


def _run_in_process(context_ref):
    """Internal implementation, to be called only by a root-released bounded runner."""
    source_execution.active()
    context, plan, runtime, row, manifest = validate_context(context_ref, admission=True)
    root, output = Path(plan['worktree']), Path(manifest['output_dir'])
    identity = w.process_identity()
    verify_dispatch_record(context_ref, context, output, identity)
    source_execution.bind_dino(plan['runtime'])
    started = time.perf_counter()
    receipt_path = output / 'eds_eval/n36-worker-receipt.json'
    start_path = output / 'eds_eval/n36-worker-start.json'
    report_path = output / 'eds_eval/decision-evidence-audit.json'
    w.require(not any(p.exists() for p in (receipt_path, start_path, report_path)), 'replay/duplicate worker artifacts')
    w.atomic_json(start_path, {'context': context_ref, 'process': identity})
    receipt = {**(operational_binding(plan) if plan['schema'] == 'n36-engineering-execution-plan-v1' else {}), 'schema': 'n36-worker-receipt-v2', 'context': context_ref, 'plan': context['plan'],
               'expected_manifest': context['expected_manifest'], 'source': plan['source'], 'scientific_source': plan['scientific_source'], 'row': row,
               'attempt_id': context['attempt_id'], 'process': identity, 'accepted': False,
               'main_exit_code': None, 'http_counters': 'Unknown'}
    old_argv, old_cwd = sys.argv, Path.cwd()
    try:
        runtime_closure = w.read_ref(plan['runtime_closure'])
        proof = controller.verify_semantics(plan['controller_semantics'], plan['runtime'], runtime_closure)
        receipt['runtime_before'] = closure.attest_runtime_receipt(runtime_closure, plan['runtime'],
            binding=runtime_receipt_binding(context_ref, plan, identity, 'runtime_before'))
        receipt['native_build_before']=native_build.attest(plan['native_build'])
        receipt['loaded_before'] = attest_worker_loaded(root, plan['source'])
        receipt['execution_before'] = source_execution.attest(root, plan['source'], runtime_closure,
            binding=runtime_receipt_binding(context_ref, plan, identity, 'runtime_before'))
        receipt['observation_before'] = persist_runtime_observation(output, 'before', receipt)
        sys.argv = context['main_argv']
        os.chdir(root)
        with controller.observe_instances(proof) as observed:
            try:
                # Use the same source-only loader as worker/auditor dependencies.
                w.require(Path(sys.argv[0]).resolve() == root.resolve() / 'main.py', 'Main source entry')
                validate_context(context_ref, admission=True)
                source_execution.run_main(sys.argv[0])
            except SystemExit as exc:
                w.require(exc.code is None or type(exc.code) is int and exc.code == 0, 'main nonzero exit')
        receipt['controller_instances'] = observed
        receipt['main_exit_code'] = 0
        validate_context(context_ref)
        w.require(w.process_identity() == identity, 'worker process changed')
        receipt['loaded_after'] = attest_worker_loaded(root, plan['source'])
        receipt['runtime_after'] = closure.attest_runtime_receipt(runtime_closure, plan['runtime'], after=True,
            binding=runtime_receipt_binding(context_ref, plan, identity, 'runtime_after'))
        receipt['worker_cuda'] = assigned_cuda_identity(w.cuda_binding(runtime))
        backend = create_backend('cpu')
        before = evidence(output)
        audit_started = time.perf_counter()
        report = generic.audit_episode(output / 'eds_eval/decision_evidence/episode_000',
                                       output / 'eds_eval/episode_compute.jsonl',
                                       arithmetic_backend=backend, n31_empty_provider_search=True)
        w.require(report.get('accepted') is True and report.get('evidence_complete') is True, 'generic evidence INVALID')
        report = audit_native(row['profile'], output, report, backend, manifest['expected_runtime'])
        counts, auxiliary = native_counts(row['profile'], output, report, manifest['expected_runtime'])
        w.require(before == evidence(output), 'evidence changed during audit')
        validate_context(context_ref)
        receipt['loaded_after'] = attest_worker_loaded(root, plan['source'])
        receipt['runtime_after'] = closure.attest_runtime_receipt(runtime_closure, plan['runtime'], after=True,
            binding=runtime_receipt_binding(context_ref, plan, identity, 'runtime_after'))
        receipt['native_build_after']=native_build.attest(plan['native_build'],after=True)
        receipt['execution_after'] = source_execution.attest(root, plan['source'], runtime_closure,
            binding=runtime_receipt_binding(context_ref, plan, identity, 'runtime_after'))
        receipt['observation_after'] = persist_runtime_observation(output, 'after', receipt)
        receipt.update(audit_seconds=time.perf_counter() - audit_started, native_counts=counts, auxiliary=auxiliary,
                       evidence=before, audit_backend=backend.report())
        w.atomic_json(report_path, report)
        receipt.update(audit_report=c.ref(report_path), accepted=True)
    except BaseException as exc:
        receipt.update(accepted=False, classification='INVALID', error_type=type(exc).__name__, error=str(exc))
        if isinstance(exc, closure.RuntimeOriginError):
            receipt['runtime_failure_origin'] = exc.runtime_failure_origin
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
    w.require(receipt_ref['path'] == str(output / 'eds_eval/n36-worker-receipt.json'), 'receipt path')
    if plan['schema'] == 'n36-engineering-execution-plan-v1':
        w.require(all(receipt.get(key) == value for key, value in operational_binding(plan).items()),
                  'engineering receipt scope binding')
    process = {key: process_record[key] for key in ('pid', 'proc_start_ticks', 'boot_id')}
    w.require(process_record['attempt_id'] == context['attempt_id'] and receipt.get('process') == process
              and receipt.get('process_unchanged') is True and receipt.get('accepted') is True
              and receipt.get('main_exit_code') == 0 and receipt.get('schema') == 'n36-worker-receipt-v2', 'receipt process/outcome')
    for key, expected in {'context': context_ref, 'plan': context['plan'], 'expected_manifest': context['expected_manifest'],
                          'source': plan['source'], 'scientific_source': plan['scientific_source'], 'row': row, 'attempt_id': context['attempt_id'], 'evidence': evidence(output)}.items():
        w.require(receipt.get(key) == expected, 'receipt binding ' + key)
    w.require(w.read_ref(c.ref(output / 'eds_eval/n36-worker-start.json')) == {'context': context_ref, 'process': process}, 'start identity')
    cuda = receipt['worker_cuda']
    w.require(cuda['physical_gpu'] == 7 and cuda['uuid'] == c.GPU_UUID and cuda['logical_device'] == 'cuda:0'
              and cuda['physical_uuid'] == canonical_cuda_uuid(c.GPU_UUID)
              and canonical_cuda_uuid(cuda['actual_uuid']) == canonical_cuda_uuid(c.GPU_UUID), 'worker device attestation')
    expected_hex = canonical_cuda_uuid(c.GPU_UUID)[4:].replace('-', '')
    w.require((cuda.get('actual_uuid_type') == 'builtins.str' and cuda.get('actual_uuid_bytes_hex') is None)
              or (cuda.get('actual_uuid_type') == 'torch._C._CUuuid' and cuda.get('actual_uuid_bytes_hex') == expected_hex),
              'native UUID serialization')
    w.require(receipt['audit_backend']['kind'] == 'cpu' and receipt['audit_backend']['logical_device'] == 'cpu', 'CPU audit backend')
    for phase in ('before', 'after'):
        reference = receipt['observation_' + phase]
        w.require(reference['path'] == str(output / 'eds_eval' / ('n36-runtime-' + phase + '.json')),
                  'immutable runtime observation path')
        w.require(w.read_ref(reference) == {key: receipt[key] for key in
            ('runtime_' + phase, 'execution_' + phase, 'loaded_' + phase, 'native_build_' + phase)},
            'immutable runtime observation differs')
    native_build.verify_receipt(plan['native_build'],receipt['native_build_before'])
    native_build.verify_receipt(plan['native_build'],receipt['native_build_after'],after=True)
    w.require(all(row in receipt['native_build_after']['libraries'] for row in receipt['native_build_before']['libraries']), 'native library unloaded/replaced')
    for phase in ('loaded_before', 'loaded_after'):
        inventory = receipt[phase]
        required = {'scripts.qd_ed_n36_worker', 'scripts.qd_ed_n36_bridge', 'scripts.qd_ed_n36_contract',
                    'scripts.qd_ed_n23_worker', 'scripts.audit_decision_evidence',
                    'scripts.qd_ed_n36_native', 'scripts.qd_ed_n31_native',
                    'scripts.qd_ed_n34_controller', 'scripts.qd_ed_n34_source',
                    'scripts.qd_ed_n36_build','scripts.qd_ed_n36_lifecycle','scripts.qd_ed_n36_arithmetic','scripts.qd_ed_n36_reference', 'scripts.qd_ed_n34_worker', 'scripts.qd_ed_n34_native'}
        if plan['schema'] == 'n36-engineering-execution-plan-v1':
            required |= {'scripts.qd_ed_n36_engineering', 'scripts.qd_ed_n36_release',
                         'scripts.qd_ed_n36_accounting', 'scripts.qd_ed_n36_stop',
                         'scripts.qd_ed_n36_source'}
        if phase == 'loaded_after' and row['profile']=='N36':
            required.add('scripts.qd_ed_n36_response')
        if phase == 'loaded_after':
            required |= {name.removesuffix('.py').replace('/', '.') for name in b.RUNTIME_SOURCES if name != 'main.py'} | {'scripts.maniskill_model', 'core.env_adapters.libero_adapter', 'models.rdt_runner',
                    'models.multimodal_encoder.siglip_encoder', 'models.multimodal_encoder.t5_encoder', 'configs.state_vec'}
        w.require(isinstance(inventory, dict) and required <= set(inventory), 'loaded source attestation absent')
        index = {v['path']: v['sha256'] for v in plan['source']['files']}
        w.require(all(index.get(v['path']) == v['sha256'] for v in inventory.values()), 'loaded source receipt mismatch')
        worker = inventory['scripts.qd_ed_n36_worker']
        w.require(worker == {'path': 'scripts/qd_ed_n36_worker.py',
                            'sha256': index.get('scripts/qd_ed_n36_worker.py'),
                            'module_name': worker.get('module_name'),
                            'spec_name': 'scripts.qd_ed_n36_worker',
                            'origin': str(Path(plan['worktree']).resolve() / 'scripts/qd_ed_n36_worker.py')}
                  and worker.get('module_name') in ('__main__', 'scripts.qd_ed_n36_worker'),
                  'worker source receipt identity differs')
    w.require(receipt['loaded_before']['scripts.qd_ed_n36_worker']
              == receipt['loaded_after']['scripts.qd_ed_n36_worker'], 'worker source identity changed')
    w.require(receipt['audit_report']['path'] == str(output / 'eds_eval/decision-evidence-audit.json'), 'audit path')
    runtime_closure = closure.verify_runtime(w.read_ref(plan['runtime_closure']), plan['runtime'])
    for phase in ('execution_before', 'execution_after'):
        suffix = phase.removeprefix('execution_')
        source_execution.verify_receipt(receipt[phase], plan['worktree'], plan['source'], runtime_closure,
            loaded=receipt['loaded_' + suffix], runtime_receipt=receipt['runtime_' + suffix], dino_required=True,
            binding=runtime_receipt_binding(context_ref, plan, process, 'runtime_' + suffix))
    w.require(all(row in receipt['execution_after']['compiled'] for row in receipt['execution_before']['compiled']),
              'N36 executable inventory changed')
    w.require('main' in {r['module'] for r in receipt['execution_after']['compiled']}, 'N36 Main executable absent')
    proof = controller.verify_semantics(plan['controller_semantics'], plan['runtime'], runtime_closure)
    expected_controller = {k: proof[k] for k in ('source', 'module', 'class', 'instance')}
    w.require(receipt.get('controller_instances') and all(x == expected_controller for x in receipt['controller_instances']), 'deployed controller receipt differs')
    for phase in ('runtime_before', 'runtime_after'):
        closure.verify_runtime_receipt(runtime_closure, receipt[phase],
            binding=runtime_receipt_binding(context_ref, plan, process, phase),
            after=phase == 'runtime_after')
    before_generated = receipt['runtime_before']['generated_modules']
    after_generated = receipt['runtime_after']['generated_modules']
    w.require(all(after_generated.get(k) == v for k, v in before_generated.items()),
              'generated runtime identity changed')
    report = w.read_ref(receipt['audit_report'])
    w.require(report.get('n23_arithmetic_backend') == receipt['audit_backend'], 'generic backend receipt')
    counts, auxiliary = native_counts(row['profile'], output, report, manifest['expected_runtime'])
    w.require((counts, auxiliary) == (receipt['native_counts'], receipt['auxiliary']), 'native receipt mismatch')
    for key in ('worker_wall_seconds', 'audit_seconds'):
        c.finite(receipt[key], key)
    return report


def verify_terminal(plan_ref, row, terminal, release_ref=None):
    """Parent binds generic terminal identity and telemetry to the metered receipt."""
    from scripts import qd_ed_n36_supervise as s
    release = release_api(plan_ref)
    plan, _, _ = release.validate_release(plan_ref, release_ref)
    manifest = w.read_ref(plan['expected_manifests'][row['episode_key']])
    output = Path(manifest['output_dir'])
    w.require(terminal['identity'] == s.c_identity(row) and terminal['episode_key'] == row['episode_key']
              and terminal['attempt_id'] == row['episode_key'] and terminal['source_commit'] == plan['source']['commit']
              and terminal['plan_sha256'] == plan_ref['sha256'] and terminal['runtime_manifest_sha256'] == plan['runtime']['sha256']
              and terminal['init_row_sha256'] == row['init_row_sha256'] and terminal['physical_gpu'] == 7
              and terminal['output_dir'] == str(output) and terminal['outcome_valid'] is True
              and terminal['required_cost_telemetry_complete'] is True and type(terminal['success']) is bool,
              'generic terminal identity/cost differs')
    c.event_binding(row, terminal)
    if plan.get('schema') == 'n36-engineering-execution-plan-v1':
        from scripts.qd_ed_n36_engineering import operational_binding as terminal_binding, require_row
        require_row(row)
    else:
        terminal_binding = c.operational_binding
    w.require(all(terminal.get(k) == v for k, v in terminal_binding(plan).items()),
              'terminal protocol/accounting binding')
    c.finite(terminal['gpu_process_wall_seconds'], 'terminal charge')
    context_ref = c.ref(output / 'n36-worker-context.json')
    context = w.read_ref(context_ref)
    w.require(context['plan'] == plan_ref and context['episode_key'] == row['episode_key'], 'terminal context binding')
    w.require(context.get('release') == release_ref and terminal.get('release') == release_ref
              and terminal.get('context') == context_ref
              and terminal.get('runtime_inventory_sha256') == plan['runtime_inventory_sha256'], 'terminal release binding')
    record = w.read_ref(c.ref(output / 'process.json'))
    w.require(record.get('context') == context_ref and record.get('release') == release_ref, 'process context/release binding')
    command = w.read_ref(c.ref(output / 'command.json'))
    w.require(command == {'argv': source_execution.command(manifest['argv'][0], plan['worktree'],
              'scripts.qd_ed_n36_worker', '--context', context_ref['path'], '--context-sha256', context_ref['sha256']),
              'main_argv': manifest['argv'], 'context': context_ref}, 'worker command receipt differs')
    report = verify_receipt(context_ref, terminal['n36_worker_receipt'], w.read_ref(c.ref(output / 'process.json')))
    native_counts(row['profile'], output, report, manifest['expected_runtime'], guided=terminal['guided_chunks'])
    # Retain the original generic result/video/Stage/token/counter gates. A receipt
    # is necessary, not sufficient to classify an episode as valid.
    generic_outcome = b.runner.validate_result(output, row, b.profiles(plan['worktree'])['profiles'][row['profile']],
                                                w.read_ref(plan['runtime']))
    w.require(all(key in terminal and terminal[key] == value for key, value in generic_outcome.items()),
              'terminal generic result/cost telemetry differs')
    return report


def run_worker(context_ref):
    # _run_in_process owns this transaction, including standalone calls.
    return _run_in_process(context_ref)


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', required=True)
    parser.add_argument('--context-sha256', required=True)
    args = parser.parse_args()
    context_ref = {'path': args.context, 'sha256': args.context_sha256}
    # Reject missing/draft/tampered authority before waiting on the parent gate.
    # The in-process consumer starts a fresh full transaction after that wait.
    validate_context(context_ref)
    # The parent durably records PID/boot/start identity before opening this gate.
    w.require(sys.stdin.buffer.read(1) == b'G', 'parent dispatch gate absent')
    return run_worker(context_ref)


if __name__ == '__main__':
    raise SystemExit(main())
