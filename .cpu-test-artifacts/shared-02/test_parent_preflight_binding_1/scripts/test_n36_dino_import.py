"""CPU-only real torch.hub reproduction using a tiny, weight-free local repo."""
import copy
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from scripts import qd_ed_n36_source as execution
from scripts.qd_ed_n36_dino import DinoSources

ROOT = Path(__file__).resolve().parents[1]


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def child():
    import torch
    torch.set_num_threads(2)
    assert not torch.cuda.is_initialized()
    state = execution.active()
    rejected = []

    def reject(label, action):
        try:
            action()
        except (ImportError, ValueError):
            rejected.append(label)
        else:
            raise AssertionError('accepted ' + label)

    with tempfile.TemporaryDirectory() as temp:
        home = Path(temp) / 'torch'
        root = home / 'hub/facebookresearch_dinov2_main'
        (root / 'dinov2/namespace').mkdir(parents=True)
        contents = {'hubconf.py': 'from dinov2.namespace.probe import value\ndef probe(): return value\n',
                    'dinov2/__init__.py': '', 'dinov2/namespace/probe.py': 'value = 42\n'}
        for relative, source in contents.items():
            (root / relative).write_text(source)
        manifest = {'schema': 'qd-ed-runtime-setup-v1', 'environment': {'TORCH_HOME': str(home)},
                    'files': [{'path': str(root / p), 'resolved_path': str(root / p),
                               'size_bytes': len(s.encode()), 'sha256': hashlib.sha256(s.encode()).hexdigest()}
                              for p, s in contents.items()]}
        path = Path(temp) / 'runtime.json'
        path.write_text(json.dumps(manifest))
        reference = ref(path)
        reject('unbound-local-hub', lambda: torch.hub.load(str(root), 'probe', source='local'))
        reject('manifest-hash', lambda: DinoSources({**reference, 'sha256': '0' * 64}))
        dino = execution.bind_dino(reference)
        # Valid stale pyc must never execute, even when its size/mtime match.
        import py_compile
        source_path = root / 'dinov2/namespace/probe.py'
        timestamp = source_path.stat().st_mtime_ns
        source_path.write_text('value = 99\n')
        os.utime(source_path, ns=(timestamp, timestamp))
        cache = source_path.parent / '__pycache__' / ('probe.' + sys.implementation.cache_tag + '.pyc')
        py_compile.compile(str(source_path), cfile=str(cache), doraise=True)
        source_path.write_text(contents['dinov2/namespace/probe.py'])
        os.utime(source_path, ns=(timestamp, timestamp))
        assert torch.hub.load(str(root), 'probe', source='local') == 42
        first = dino.audit(state.compiled)
        assert {r['module'] for r in first['compiled']} == {'hubconf.py', 'dinov2', 'dinov2.namespace.probe'}
        assert 'hubconf.py' not in sys.modules
        assert torch.hub.load(str(root), 'probe', source='local') == 42  # sys.modules cache
        assert dino.audit(state.compiled) == first
        dino.verify(first, first['compiled'])
        execution.validate_search_path(ROOT, [str(root)], sys.prefix, dino=dino)
        for field in ('root', 'runtime_manifest', 'compiled'):
            bad = copy.deepcopy(first)
            bad[field] = [] if field == 'compiled' else 'wrong'
            reject('receipt-' + field, lambda: dino.verify(bad, first['compiled']))
        for relative in ('hubconf.py', 'dinov2/namespace/probe.py'):
            file = root / relative
            file.write_text(contents[relative] + '\n# changed')
            reject('changed-' + relative, lambda: torch.hub.load(str(root), 'probe', source='local'))
            reject('audit-changed-' + relative, lambda: dino.audit(state.compiled))
            file.write_text(contents[relative])
        module = sys.modules['dinov2.namespace.probe']
        origin = module.__spec__.origin
        module.__spec__.origin = str(root / 'wrong.py')
        reject('cached-origin', lambda: torch.hub.load(str(root), 'probe', source='local'))
        module.__spec__.origin = origin
        key = ('dinov2.namespace.probe', str(source_path))
        recorded = state.compiled.pop(key)
        reject('cached-unrecorded', lambda: dino.audit(state.compiled))
        state.compiled[key] = recorded
        package = sys.modules['dinov2']
        package.__path__.append(temp)
        reject('cached-package-path', lambda: dino.audit(state.compiled))
        package.__path__.pop()
        extra = root / 'dinov2/unlisted.py'
        extra.write_text('raise AssertionError("unlisted executed")\n')
        reject('unlisted-source', lambda: importlib.import_module('dinov2.unlisted'))
        native = root / 'dinov2/unlisted_native.so'
        native.write_bytes(b'not a library')
        reject('unlisted-native', lambda: importlib.import_module('dinov2.unlisted_native'))
        foreign = Path(temp) / 'foreign'
        foreign.mkdir()
        copied = foreign / 'probe.py'
        copied.write_text(contents['dinov2/namespace/probe.py'])
        reject('copied-source', lambda: state.validate_origin('dinov2.namespace.probe', str(copied)))
        alias = Path(temp) / 'alias'
        alias.symlink_to(root, target_is_directory=True)
        for label, entry in [('foreign-path', str(foreign)), ('symlink-root', str(alias)),
                             ('subdirectory-path', str(root / 'dinov2')), ('noncanonical-path', str(root) + '/.')]:
            sys.path.insert(0, entry)
            try:
                reject(label, execution.active)
            finally:
                sys.path.pop(0)
        reject('wrong-module-name', lambda: state.validate_origin('wrong', str(source_path)))
        reject('compiled-hash', lambda: state.validate_origin('dinov2.namespace.probe', str(source_path), '0' * 64))
        reject('sourceless-cache', lambda: importlib.machinery.SourcelessFileLoader('dinov2.namespace.probe', str(cache)).get_code('dinov2.namespace.probe'))
        source_path.unlink()
        source_path.symlink_to(copied)
        reject('symlink-source', lambda: dino.audit(state.compiled))
        source_path.unlink()
        source_path.write_text(contents['dinov2/namespace/probe.py'])
        # Direct SourceFileLoader execution (torch's route) is also guarded.
        reject('direct-unlisted', lambda: importlib.machinery.SourceFileLoader('dinov2.unlisted', str(extra)).get_code('dinov2.unlisted'))
        claim = dino.audit(state.compiled)
        assert claim == first
        full_count = full_receipt(reference, path)
        assert not torch.cuda.is_initialized()
        print(json.dumps({'local_hub_result': 42, 'repeated_cached_result': 42,
                          'compiled': claim['compiled'], 'rejected': rejected,
                          'full_consumer_passed': True, 'full_receipt_compiled_count': full_count,
                          'threads': torch.get_num_threads(), 'cuda_initialized': False}, sort_keys=True))


def full_receipt(reference, output):
    """Exercise the unmodified complete source producer/consumer, with a synthetic
    ordinary dependency inventory. DINO authority is only the supplied manifest.
    """
    from scripts import qd_ed_n34_source as runtime, qd_ed_n36_generated as admission
    from scripts import qd_ed_n36_worker, qd_ed_n36_native, qd_ed_n36_arithmetic
    from scripts import audit_decision_evidence
    import torch.distributed.nn.api.remote_module
    state = execution.active()
    modules = {}
    for name, module in list(sys.modules.items()):
        file = getattr(module, '__file__', None)
        if file and name not in (runtime.GENERATED_NAME, 'torch.ops', 'torch.classes'):
            p = Path(file).resolve()
            if not p.is_relative_to(ROOT):
                modules[name] = {'path': str(p), 'sha256': execution.sha(p)}
    for (name, filename), value in state.compiled.items():
        p = Path(filename).resolve()
        if not p.is_relative_to(ROOT) and name != runtime.GENERATED_NAME and not state.dino_sources.contains(str(p)):
            modules[name + '.cpu_test_source'] = {'path': str(p), 'sha256': value}
    assert not any(r['path'].endswith('/hubconf.py') for r in modules.values())
    rule = {'rule': runtime.GENERATED_RULE, 'generator': modules[runtime.GENERATOR_NAME],
            'template': modules[runtime.TEMPLATE_NAME], 'sha256': admission.CONTENT_SHA}
    closure = {'schema': 'n34-runtime-source-closure-v2', 'modules': modules,
               'runtime': reference, 'generated_modules': {runtime.GENERATED_NAME: rule},
               'required_after': [runtime.GENERATED_NAME], 'interpreter': execution.interpreter_identity(),
               'versions': {name: 'cpu-test-only' for name in ('python', 'torch', 'libero', 'robosuite', 'mujoco')},
               'distribution_versions': {name: runtime.importlib.metadata.version(name)
                   for name in ('torch', 'numpy', 'robosuite', 'mujoco', 'transformers')}}
    binding = {'context': {'path': str(output), 'sha256': 'c'*64},
               'runtime_closure': {'path': str(output), 'sha256': 'd'*64},
               'process': {'pid': os.getpid(), 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                           'proc_start_ticks': Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]},
               'phase': 'runtime_after'}
    files = {str(ROOT / 'scripts/qd_ed_n36_bootstrap.py'): state.bootstrap_digest}
    for (name, filename), value in state.compiled.items():
        if Path(filename).resolve().is_relative_to(ROOT):
            files[str(Path(filename).resolve())] = value
    source = {'files': [{'path': str(Path(p).relative_to(ROOT)), 'sha256': h} for p, h in files.items()]}
    observed = runtime.attest_runtime_receipt(closure, reference, binding=binding, after=True)
    receipt = execution.attest(ROOT, source, closure, binding=binding)
    execution.verify_receipt(receipt, ROOT, source, closure, runtime_receipt=observed,
                             binding=binding, dino_required=True)
    for fault in ('missing-claim', 'missing-hubconf', 'omitted-hubconf', 'wrong-hubconf-origin', 'wrong-manifest'):
        bad = copy.deepcopy(receipt)
        if fault == 'missing-claim':
            del bad['dino_sources']
        elif fault == 'missing-hubconf':
            bad['compiled'] = [r for r in bad['compiled'] if r['module'] != 'hubconf.py']
        elif fault == 'omitted-hubconf':
            bad['compiled'] = [r for r in bad['compiled'] if r['module'] != 'hubconf.py']
            bad['dino_sources']['compiled'] = [r for r in bad['dino_sources']['compiled'] if r['module'] != 'hubconf.py']
        elif fault == 'wrong-hubconf-origin':
            next(r for r in bad['compiled'] if r['module'] == 'hubconf.py')['path'] += '.wrong'
        else:
            bad['dino_sources']['runtime_manifest']['sha256'] = '0' * 64
        try:
            execution.verify_receipt(bad, ROOT, source, closure, runtime_receipt=observed,
                                     binding=binding, dino_required=True)
        except (ValueError, ImportError):
            pass
        else:
            raise AssertionError('accepted complete receipt fault: ' + fault)
    return len(receipt['compiled'])


def production_sources(reference):
    import torch
    torch.set_num_threads(2)
    dino = execution.bind_dino(reference)
    # Import the real hubconf twice; never call an entrypoint or construct a model.
    for _ in range(2):
        with torch.hub._add_to_sys_path(dino.root):
            module = torch.hub._import_module('hubconf.py', dino.root + '/hubconf.py')
        assert callable(module.dinov2_vitb14)
    claim = dino.audit(execution.active().compiled)
    count = full_receipt(reference, Path(reference['path']))
    assert not torch.cuda.is_initialized()
    print(json.dumps({'production_source_import_only': True, 'manifest': reference,
                      'compiled_dino': claim['compiled'], 'full_receipt_compiled_count': count,
                      'full_consumer_passed': True, 'threads': 2, 'cuda_initialized': False}))


def test_local_hub_and_rejections():
    result = subprocess.run(execution.command(sys.executable, ROOT, 'scripts.test_n36_dino_import', '--child'),
        cwd=ROOT, env={**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'OMP_NUM_THREADS': '2',
                      'MKL_NUM_THREADS': '2', 'OPENBLAS_NUM_THREADS': '2', 'NUMEXPR_NUM_THREADS': '2'},
        capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    print(result.stdout)
    value = json.loads(result.stdout.splitlines()[-1])
    assert len(value['rejected']) == 24


if __name__ == '__main__':
    if sys.argv[1:] == ['--child']:
        child()
    else:
        assert len(sys.argv) == 4 and sys.argv[1] == '--production-sources'
        production_sources({'path': sys.argv[2], 'sha256': sys.argv[3]})
