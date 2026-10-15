"""Real source-only CPU import and retained provenance, never a release fixture."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

from scripts import qd_ed_n34_source as runtime, qd_ed_n36_source as execution
from scripts import qd_ed_n36_generated as admission

ROOT = Path(__file__).resolve().parents[1]


def child(output):
    import importlib
    import tempfile
    import torch.distributed.nn.api.remote_module
    import torch
    from scripts import qd_ed_n36_worker, qd_ed_n36_native, qd_ed_n36_arithmetic
    from scripts import audit_decision_evidence

    assert not torch.cuda.is_initialized()
    torch.set_num_threads(2)
    state = execution.active()
    generated = sys.modules[runtime.GENERATED_NAME]
    path = Path(generated.__file__)
    original = path.read_bytes()
    assert execution.sha(path) == admission.CONTENT_SHA
    rejected = []

    def reject(label, action):
        try:
            action()
        except (ImportError, ValueError):
            rejected.append(label)
        else:
            raise AssertionError('accepted ' + label)

    with tempfile.TemporaryDirectory() as foreign:
        sys.path.append(foreign)
        reject('foreign-search', execution.active)
        sys.path.pop()
        wrong = Path(foreign) / path.name
        wrong.write_bytes(original)
        reject('copied-generated', lambda: state.validate_origin(runtime.GENERATED_NAME, str(wrong)))
        link = Path(foreign) / 'link'
        link.symlink_to(path.parent, target_is_directory=True)
        sys.path.append(str(link))
        reject('symlink-search', execution.active)
        sys.path.pop()
    path.write_bytes(original + b'\n# tampered\n')
    reject('tampered-source', execution.active)
    path.write_bytes(original)
    reject('compile-byte-mismatch', lambda: state.validate_origin(runtime.GENERATED_NAME, str(path), '0'*64))
    old = generated.__spec__.origin
    generated.__spec__.origin = old + '.wrong'
    reject('tampered-spec', execution.active)
    generated.__spec__.origin = old
    owner = sys.modules[runtime.GENERATOR_NAME]
    old = owner.INSTANTIATED_TEMPLATE_DIR_PATH
    owner.INSTANTIATED_TEMPLATE_DIR_PATH = old + '.wrong'
    reject('tampered-owner', execution.active)
    owner.INSTANTIATED_TEMPLATE_DIR_PATH = old
    key = (runtime.GENERATOR_NAME, owner.__file__)
    old = state.compiled[key]
    state.compiled[key] = '0'*64
    reject('unbound-generator-execution', execution.active)
    state.compiled[key] = old
    for filename, module in [('foreign_generated_probe.py', 'foreign_generated_probe'),
                             ('foreign_native_probe.so', 'foreign_native_probe')]:
        extra = path.parent / filename
        extra.write_bytes(b'raise AssertionError("must never execute")\n')
        importlib.invalidate_caches()
        reject(filename, lambda: importlib.import_module(module))
        extra.unlink()
    reject('wrong-module-name', lambda: state.validate_origin('foreign', str(path)))
    execution.active()

    # Test-only ordinary inventory. Generated trust is the fixed prospective
    # commitment, not a learned source hash; no production graph is refreshed.
    modules = {}
    for name, module in list(sys.modules.items()):
        file = getattr(module, '__file__', None)
        if file and name not in (runtime.GENERATED_NAME, 'torch.ops', 'torch.classes'):
            p = Path(file).resolve()
            if not p.is_relative_to(ROOT):
                modules[name] = {'path': str(p), 'sha256': execution.sha(p)}
    # Torch can replace a Python module with a native-backed namespace (e.g.
    # _VF). Preserve its executed source in this test inventory as well.
    for (name, filename), digest in state.compiled.items():
        p = Path(filename).resolve()
        if not p.is_relative_to(ROOT) and name != runtime.GENERATED_NAME:
            modules[name + '.cpu_test_source'] = {'path': str(p), 'sha256': digest}
    rule = {'rule': runtime.GENERATED_RULE, 'generator': modules[runtime.GENERATOR_NAME],
            'template': modules[runtime.TEMPLATE_NAME], 'sha256': admission.CONTENT_SHA}
    closure = {'schema': 'n34-runtime-source-closure-v2', 'modules': modules,
               'runtime': {'cpu_test_only': True}, 'generated_modules': {runtime.GENERATED_NAME: rule},
               'required_after': [runtime.GENERATED_NAME], 'interpreter': execution.interpreter_identity(),
               'versions': {name: 'cpu-test-only' for name in ('python', 'torch', 'libero', 'robosuite', 'mujoco')},
               'distribution_versions': {name: runtime.importlib.metadata.version(name)
                   for name in ('torch', 'numpy', 'robosuite', 'mujoco', 'transformers')}}
    binding = {'context': {'path': str(output), 'sha256': 'c'*64},
               'runtime_closure': {'path': str(output), 'sha256': 'd'*64},
               'process': {'pid': os.getpid(), 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                           'proc_start_ticks': Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]},
               'phase': 'runtime_before'}
    files = {str(ROOT / 'scripts/qd_ed_n36_bootstrap.py'): state.bootstrap_digest}
    for (name, filename), digest in state.compiled.items():
        if Path(filename).resolve().is_relative_to(ROOT):
            files[str(Path(filename).resolve())] = digest
    source = {'files': [{'path': str(Path(p).relative_to(ROOT)), 'sha256': h} for p, h in files.items()]}
    observed = runtime.attest_runtime_receipt(closure, closure['runtime'], binding=binding, after=True)
    receipt = execution.attest(ROOT, source, closure, binding=binding)
    # Unsuppressed full CPU producer-consumer gate; retain every ordinary row.
    execution.verify_receipt(receipt, ROOT, source, closure, runtime_receipt=observed, binding=binding)
    output.write_text(json.dumps({'closure': closure, 'source': source, 'runtime': observed,
                                 'execution': receipt, 'binding': binding, 'rejected': rejected}))
    print(json.dumps({'generated_path': str(path), 'sha256': execution.sha(path), 'rejected': rejected,
                      'full_consumer_passed': True, 'ordinary_modules': len(observed['modules'])}))


def test_real_bootstrap_and_retained_receipt(tmp_path, monkeypatch):
    import pytest
    output = tmp_path / 'cpu-receipts.json'
    command = execution.command(sys.executable, ROOT, 'scripts.test_n36_generated_import', '--child', str(output))
    result = subprocess.run(command, cwd=ROOT, env={**os.environ, 'CUDA_VISIBLE_DEVICES': '',
        'OMP_NUM_THREADS': '2', 'MKL_NUM_THREADS': '2', 'OPENBLAS_NUM_THREADS': '2',
        'NUMEXPR_NUM_THREADS': '2'}, capture_output=True, text=True, timeout=70)
    assert result.returncode == 0, result.stdout + result.stderr
    print(result.stdout)
    value = json.loads(output.read_text())
    receipt, observed = value['execution'], value['runtime']
    closure, source, binding = value['closure'], value['source'], value['binding']
    generated_path = Path(observed['generated_modules'][runtime.GENERATED_NAME]['record']['path'])
    assert not generated_path.exists()  # verifier must consume retained evidence
    # The production receipt consumer uses the same source-only cache prefix.
    monkeypatch.setattr(sys, 'pycache_prefix', '/dev/null')
    execution.verify_receipt(receipt, ROOT, source, closure, runtime_receipt=observed, binding=binding)
    for fault in ('missing-receipt', 'foreign-search', 'content', 'owner', 'binding', 'compiled-origin'):
        bad, bad_observed = copy.deepcopy(receipt), copy.deepcopy(observed)
        evidence = bad_observed['generated_modules'][runtime.GENERATED_NAME]
        if fault == 'missing-receipt': bad_observed = None
        elif fault == 'foreign-search': bad['search_path'].append(str(tmp_path / 'foreign'))
        elif fault == 'content': evidence['source_utf8'] += '\n# tampered'
        elif fault == 'owner': evidence['owner']['name'] += '.wrong'
        elif fault == 'binding': bad_observed['binding']['process']['pid'] += 1
        else:
            next(r for r in bad['compiled'] if r['module'] == runtime.GENERATED_NAME)['path'] += '.wrong'
        with pytest.raises(ValueError):
            execution.verify_receipt(bad, ROOT, source, closure, runtime_receipt=bad_observed, binding=binding)
    # Exercise each new proof through the complete consumer, preserving all
    # ordinary rows (including unrelated Python execution coverage).
    assert set(observed['modules']) >= {n for pair in execution.IMPORTLIB_FROZEN_PAIRS for n in pair}
    for alias, canonical in execution.IMPORTLIB_FROZEN_PAIRS:
        for fault in ('object', 'loader', 'spec', 'name', 'path', 'hash', 'interpreter',
                      'context', 'runtime_closure', 'process', 'phase',
                      'canonical_frozen', 'canonical_evidence', 'missing_proof', 'ordinary_execution'):
            bad, bad_observed = copy.deepcopy(receipt), copy.deepcopy(observed)
            claim = bad['frozen_importlib_aliases'][alias]
            if fault == 'object': claim['same_module_object'] = False
            elif fault == 'loader': claim['loader'] = 'wrong'
            elif fault == 'spec': claim['spec_name'] = alias
            elif fault == 'name': claim['module_name'] = canonical
            elif fault in ('path', 'hash'):
                claim['records'][alias]['path' if fault == 'path' else 'sha256'] = 'wrong'
            elif fault == 'interpreter': claim['interpreter']['sha256'] = '0'*64
            elif fault in ('context', 'runtime_closure'): claim['binding'][fault]['sha256'] = '0'*64
            elif fault == 'process': claim['binding']['process']['pid'] += 1
            elif fault == 'phase': claim['binding']['phase'] = 'runtime_after'
            elif fault == 'canonical_frozen': bad['frozen_modules'].remove(canonical)
            elif fault == 'canonical_evidence': del bad_observed['modules'][canonical]
            elif fault == 'missing_proof': del bad['frozen_importlib_aliases'][alias]
            else:
                # Same-path aliases do not become a broad exemption.
                bad['compiled'] = [r for r in bad['compiled'] if r['module'] != runtime.TEMPLATE_NAME]
            with pytest.raises(ValueError):
                execution.verify_receipt(bad, ROOT, source, closure, runtime_receipt=bad_observed, binding=binding)
        bad_closure, bad_observed = copy.deepcopy(closure), copy.deepcopy(observed)
        bad_closure['modules']['arbitrary_alias'] = copy.deepcopy(closure['modules'][alias])
        bad_observed['modules']['arbitrary_alias'] = copy.deepcopy(observed['modules'][alias])
        with pytest.raises(ValueError, match='N36 module missing executable receipt:'):
            execution.verify_receipt(receipt, ROOT, source, bad_closure,
                                     runtime_receipt=bad_observed, binding=binding)
    assert len(value['rejected']) == 11


if __name__ == '__main__':
    assert sys.argv[1] == '--child'
    child(Path(sys.argv[2]))
