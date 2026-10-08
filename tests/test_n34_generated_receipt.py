"""CPU parent-consumption fixtures; no dispatch, models, or simulation episodes."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import qd_ed_n34_source as source, qd_ed_n34_worker as worker
from test_n34_generated_runtime import prospective, record, inert_module, live, PYTHON, ROOT


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return record(path)


def child(mode, request_path):
    request = json.loads(request_path.read_text())
    manifest = Path(request['closure'])
    closure = json.loads(manifest.read_text())
    name = request['controller']
    sys.modules[name] = inert_module(name, closure['modules'][name]['path'])
    process = worker.w.process_identity()
    binding = worker.runtime_receipt_binding(request['context'],
        {'runtime_closure': record(manifest)}, process, 'runtime_before')
    if mode != 'discover':
        before = source.attest_runtime_receipt(closure, closure['runtime'], binding=binding)
    import torch.distributed.nn.api.remote_module
    if mode == 'discover':
        for name, module in list(sys.modules.items()):
            file = getattr(module, '__file__', None)
            if file is not None and name not in (source.GENERATED_NAME, 'torch.ops', 'torch.classes'):
                path = Path(file).resolve()
                if not path.is_relative_to(ROOT):
                    closure['modules'][name] = record(path)
        write(manifest, closure)
    else:
        after = source.attest_runtime_receipt(closure, closure['runtime'], after=True,
            binding={**binding, 'phase': 'runtime_after'})
        # Also attest a before snapshot with the module already loaded.
        loaded_before = source.attest_runtime_receipt(closure, closure['runtime'], binding=binding)
        write(Path(request['result']), {'before': before, 'after': after,
                                      'loaded_before': loaded_before, 'process': process})
    assert not sys.modules['torch'].cuda.is_initialized()


def run_child(mode, request):
    result = subprocess.run([PYTHON, '-B', str(Path(__file__).resolve()), mode, str(request)],
        cwd=ROOT, env={**os.environ, 'PYTHONPATH': str(ROOT) + os.pathsep + str(ROOT / 'tests'),
            'CUDA_VISIBLE_DEVICES': '', 'PYTHONDONTWRITEBYTECODE': '1',
            'OMP_NUM_THREADS': '2', 'MKL_NUM_THREADS': '2', 'OPENBLAS_NUM_THREADS': '2',
            'NUMEXPR_NUM_THREADS': '2'}, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture(scope='module')
def retained(tmp_path_factory):
    root = tmp_path_factory.mktemp('generated-parent')
    cl = prospective()
    osc = root / 'osc.py'
    osc.write_text('# synthetic source for controller receipt gate; no deployment claim\n')
    name = 'robosuite.controllers.osc'
    cl['modules'][name] = record(osc)
    cl['required_after'].append(name)
    context_ref = write(root / 'context.json', {'fixture': 'parent-consumption'})
    closure_path = root / 'closure.json'
    write(closure_path, cl)
    request = {'closure': str(closure_path), 'controller': name, 'context': context_ref,
               'result': str(root / 'child.json')}
    request_ref = write(root / 'request.json', request)
    run_child('discover', Path(request_ref['path']))
    snapshots = []
    for _ in range(2):
        run_child('valid', Path(request_ref['path']))
        snapshot = json.loads(Path(request['result']).read_text())
        path = Path(snapshot['after']['generated_modules'][source.GENERATED_NAME]['record']['path'])
        assert not path.exists() and not path.parent.exists()  # real atexit cleanup
        snapshots.append(snapshot)
    assert snapshots[0]['process'] != snapshots[1]['process']
    assert (snapshots[0]['after']['generated_modules'][source.GENERATED_NAME]['record']['path'] !=
            snapshots[1]['after']['generated_modules'][source.GENERATED_NAME]['record']['path'])
    return root, context_ref, record(closure_path), snapshots


@pytest.fixture
def parent(retained, monkeypatch, tmp_path):
    root, context_ref, closure_ref, snapshots = retained
    cl = worker.w.read_ref(closure_ref)
    name = 'robosuite.controllers.osc'
    review = write(tmp_path / 'review.json', {'kind': 'deployed_source_review',
                    'runtime': cl['runtime'], 'fixture_only': False})
    # Synthetic documents test the unchanged validator, never release authority.
    proof = {'schema': 'n34-deployed-controller-semantics-v1', 'runtime': cl['runtime'],
        'status': 'ROOT_REVIEWED', 'physical_gain_certified': False, 'module': name,
        'class': 'OperationalSpaceController', 'source': cl['modules'][name],
        'instance': dict(control_delta=True, control_ori=True, control_dim=6, impedance_mode='fixed',
            input_min=[-1]*6, input_max=[1]*6, output_min=[-.05]*3+[-.5]*3,
            output_max=[.05]*3+[.5]*3, policy_freq=20, uncouple_pos_ori=True,
            interpolator_pos=None, interpolator_ori=None),
        'semantics': {'translation': 'scaled_world_delta', 'rotation': 'scaled_axis_angle_delta',
            'zero_rotation': 'zero_increment_not_absolute_pose', 'gripper': 'minus_open_plus_close',
            'projector_0_01': 'convention_not_measured_gain'},
        'review_evidence': {key: review for key in ('set_goal', 'scale_action', 'wrapper_and_gripper')}}
    names = {'scripts.qd_ed_n34_worker', 'scripts.qd_ed_n34_bridge', 'scripts.qd_ed_n34_contract',
        'scripts.qd_ed_n23_worker', 'scripts.audit_decision_evidence', 'scripts.qd_ed_n34_native',
        'scripts.qd_ed_n31_native', 'scripts.qd_ed_n34_controller', 'scripts.qd_ed_n34_source',
        'scripts.maniskill_model', 'core.env_adapters.libero_adapter', 'models.rdt_runner',
        'models.multimodal_encoder.siglip_encoder', 'models.multimodal_encoder.t5_encoder', 'configs.state_vec'}
    names |= {p.removesuffix('.py').replace('/', '.') for p in worker.b.RUNTIME_SOURCES if p != 'main.py'}
    loaded = {n: {'path': n.replace('.', '/') + '.py', 'sha256': 'a'*64} for n in names}
    plan = {'worktree': str(ROOT), 'source': {'files': list(copy.deepcopy(loaded).values())},
            'scientific_source': {'fixture': True}, 'runtime_closure': closure_ref,
            'runtime': cl['runtime'], 'controller_semantics': write(tmp_path / 'proof.json', proof)}
    wn = 'scripts.qd_ed_n34_worker'
    loaded[wn].update(module_name=wn, spec_name=wn, origin=str(ROOT / loaded[wn]['path']))
    context = {'plan': {'fixture': True}, 'expected_manifest': {'fixture': True}, 'attempt_id': 'fixture'}
    row = {'profile': 'N34'}
    expected = {'binding': {'task_id': 0}}
    manifest = {'output_dir': str(tmp_path), 'expected_runtime': expected}
    # Only dispatch/context setup is stubbed. Every verify_receipt gate executes.
    monkeypatch.setattr(worker, 'validate_context', lambda _: (context, plan, {}, row, manifest))
    backend = {'kind': 'cpu', 'logical_device': 'cpu'}
    gate = {'schema': 'n34-independent-observed-jaw-v1', 'profile': 'N34',
            'runtime_identity': expected, 'guided_decisions': 1, 'compute_expected': {'guided_chunks': 1}}
    report = {'accepted': True, 'evidence_complete': True, worker.n34.GATE: gate,
              'n23_arithmetic_backend': backend}
    out = tmp_path / 'eds_eval'
    write(out / 'eds_metrics.jsonl', {'capture_dwell_proposal': {
        'schema': 'n34-observed-jaw-scalar-v1', 'mode': worker.b.MODE}})
    write(out / 'episode_compute.jsonl', {'guided_chunks': 1, 'policy_counters_available': True, 'task_id': 0})
    write(out / 'decision_evidence/episode_000/status.json', {})
    (out / 'decision_evidence/episode_000/events.jsonl').write_text('')
    receipt = {'schema': 'n34-worker-receipt-v2', 'context': context_ref, 'plan': context['plan'],
        'expected_manifest': context['expected_manifest'], 'source': plan['source'],
        'scientific_source': plan['scientific_source'], 'row': row, 'attempt_id': context['attempt_id'],
        'accepted': True, 'process_unchanged': True, 'main_exit_code': 0,
        'evidence': worker.evidence(tmp_path), 'audit_backend': backend,
        'worker_cuda': {'physical_gpu': 7, 'uuid': worker.c.GPU_UUID, 'logical_device': 'cuda:0',
            'physical_uuid': worker.c.GPU_UUID, 'actual_uuid': worker.c.GPU_UUID,
            'actual_uuid_type': 'builtins.str', 'actual_uuid_bytes_hex': None},
        'loaded_before': loaded, 'loaded_after': loaded,
        'controller_instances': [{k: proof[k] for k in ('source', 'module', 'class', 'instance')}],
        'audit_report': write(out / 'decision-evidence-audit.json', report),
        'native_counts': gate, 'auxiliary': {'http_counters': 'Unknown'},
        'worker_wall_seconds': 1., 'audit_seconds': .1}
    def consume(snapshot, mutate=None, loaded_before=False):
        r = copy.deepcopy(receipt)
        r.update(process=snapshot['process'], runtime_before=copy.deepcopy(
            snapshot['loaded_before' if loaded_before else 'before']), runtime_after=copy.deepcopy(snapshot['after']))
        write(out / 'n34-worker-start.json', {'context': context_ref, 'process': r['process']})
        if mutate: mutate(r)
        ref = write(out / 'n34-worker-receipt.json', r)
        return worker.verify_receipt(context_ref, ref, {**snapshot['process'], 'attempt_id': 'fixture'})
    return consume, snapshots, plan, report


def test_actual_parent_after_independent_worker_cleanup(parent):
    consume, snapshots, _, report = parent
    for snapshot in snapshots:
        assert consume(snapshot) == report
        assert consume(snapshot, loaded_before=True) == report


@pytest.mark.parametrize('fault', ['content', 'hash', 'rule', 'generator', 'template', 'origin',
    'loader', 'cached', 'owner', 'finalizer', 'name', 'record_path', 'unknown', 'missing',
    'ordinary', 'ordinary_extra', 'owner_missing', 'phase', 'process', 'closure', 'context',
    'controller', 'native', 'before_swap', 'extra_field', 'ordinary_record_extra',
    'required_ordinary_missing', 'schema', 'legacy', 'generated_in_ordinary',
    'generator_origin', 'template_origin', 'relative_path', 'owner_type', 'finalizer_args'])
def test_actual_parent_rejects_tampered_retained_evidence(parent, fault):
    consume, snapshots, _, _ = parent
    def mutate(r):
        after = r['runtime_after']
        evidence = after['generated_modules'][source.GENERATED_NAME]
        if fault == 'content': evidence['source_utf8'] += '\n# tamper'
        elif fault == 'hash': evidence['record']['sha256'] = '0'*64
        elif fault == 'rule': evidence['rule']['rule'] = 'wrong'
        elif fault in ('generator', 'template'): evidence['rule'][fault]['sha256'] = '0'*64
        elif fault == 'origin': evidence['origin']['spec']['origin'] += '.wrong'
        elif fault == 'loader': evidence['origin']['loader']['name'] = 'wrong'
        elif fault == 'cached': evidence['origin']['cached'] += '.wrong'
        elif fault == 'owner': evidence['owner']['exported_directory'] += '.wrong'
        elif fault == 'finalizer': evidence['owner']['finalizer_owner_identity'] = False
        elif fault == 'name': evidence['origin']['module_name'] = 'wrong'
        elif fault == 'record_path': evidence['record']['path'] = '/another/' + source.GENERATED_NAME + '.py'
        elif fault == 'unknown': after['generated_modules']['wrong'] = evidence
        elif fault == 'missing': after['generated_modules'].clear()
        elif fault == 'ordinary': after['modules'][source.GENERATOR_NAME]['sha256'] = '0'*64
        elif fault == 'ordinary_extra': after['modules']['unknown'] = {'path': '/tmp/unfrozen', 'sha256': '0'*64}
        elif fault == 'owner_missing': del after['modules'][source.GENERATOR_NAME]
        elif fault in ('phase', 'process', 'closure', 'context'):
            after['binding']['runtime_closure' if fault == 'closure' else fault] = 'wrong'
        elif fault == 'controller': r['controller_instances'][0]['instance']['control_delta'] = False
        elif fault == 'native': r['native_counts'] = {}
        elif fault == 'before_swap':
            r['runtime_before'] = copy.deepcopy(snapshots[1]['loaded_before'])
            r['runtime_before']['binding'] = copy.deepcopy(snapshots[0]['before']['binding'])
        elif fault == 'extra_field': evidence['unreviewed'] = True
        elif fault == 'ordinary_record_extra': after['modules'][source.GENERATOR_NAME]['extra'] = True
        elif fault == 'required_ordinary_missing': del after['modules']['robosuite.controllers.osc']
        elif fault == 'schema': after['schema'] = 'n34-runtime-receipt-v1'
        elif fault == 'legacy': r['schema'] = 'n34-worker-receipt-v1'
        elif fault == 'generated_in_ordinary': after['modules'][source.GENERATED_NAME] = evidence['record']
        elif fault in ('generator_origin', 'template_origin'): evidence[fault]['spec']['name'] = 'wrong'
        elif fault == 'relative_path': evidence['record']['path'] = source.GENERATED_NAME + '.py'
        elif fault == 'owner_type': evidence['owner']['type'] = 'arbitrary directory'
        elif fault == 'finalizer_args': evidence['owner']['finalizer_args'] = ['/wrong']
    with pytest.raises(ValueError):
        consume(snapshots[0], mutate)


@pytest.mark.parametrize('fault', ['rule', 'content', 'generator', 'template', 'name', 'overlap'])
def test_actual_parent_rejects_rehashed_bad_prospective_rule(parent, tmp_path, fault):
    consume, snapshots, plan, _ = parent
    cl = copy.deepcopy(worker.w.read_ref(plan['runtime_closure']))
    rule = cl['generated_modules'][source.GENERATED_NAME]
    if fault == 'rule': rule['rule'] = 'wrong'
    elif fault == 'content': rule['sha256'] = '0'*64
    elif fault in ('generator', 'template'): rule[fault]['sha256'] = '0'*64
    elif fault == 'name': cl['generated_modules'] = {'wrong': rule}
    elif fault == 'overlap': cl['modules'][source.GENERATED_NAME] = rule['generator']
    plan['runtime_closure'] = write(tmp_path / 'bad-closure.json', cl)
    with pytest.raises(ValueError): consume(snapshots[0])


@pytest.mark.parametrize('version', [1, 2])
def test_runtime_receipt_supports_ordinary_and_generated_closures(live, version):
    cl, modules, _ = live
    if version == 1:
        cl['schema'] = 'n34-runtime-source-closure-v1'
        del cl['generated_modules']
        cl['required_after'].remove(source.GENERATED_NAME)
        del modules[source.GENERATED_NAME]
    binding = {'fixture': 'ordinary-or-generated'}
    receipt = source.attest_runtime_receipt(cl, cl['runtime'], binding=binding, after=True)
    source.verify_runtime_receipt(source.verify_runtime(cl, cl['runtime']), receipt,
                                  binding=binding, after=True)
    assert bool(receipt['generated_modules']) == (version == 2)


if __name__ == '__main__':
    child(sys.argv[1], Path(sys.argv[2]))
