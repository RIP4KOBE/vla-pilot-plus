"""CPU-only prospective rule tests; fixture inventories never authorize production."""
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
from types import SimpleNamespace

import pytest

from scripts import qd_ed_n34_source as source

PYTHON = '/home/hynx/miniconda3/envs/vla-pilot/bin/python'
SITE = Path(PYTHON).parent.parent / 'lib/python3.12/site-packages'
CONTENT_SHA = '8205b16956fb264841ecd8644784a0d157f87df79b17c16825dc1163433ce5d8'
ROOT = Path(__file__).resolve().parents[1]


def record(path):
    return {'path': str(path), 'sha256': source.w.sha(path)}


def prospective():
    generator = record(SITE / 'torch/distributed/nn/jit/instantiator.py')
    template = record(SITE / 'torch/distributed/nn/jit/templates/remote_module_template.py')
    return {
        'schema': 'n34-runtime-source-closure-v2', 'runtime': {'fixture': True},
        'modules': {source.GENERATOR_NAME: generator, source.TEMPLATE_NAME: template},
        'generated_modules': {source.GENERATED_NAME: {
            'rule': source.GENERATED_RULE, 'generator': generator,
            'template': template, 'sha256': CONTENT_SHA}},
        'required_after': [source.GENERATOR_NAME, source.TEMPLATE_NAME, source.GENERATED_NAME],
        'interpreter': {**record(Path(sys.executable).resolve()), 'version': sys.version},
        'versions': {name: 'test-only' for name in ('python', 'torch', 'libero', 'robosuite', 'mujoco')},
        'distribution_versions': {name: importlib.metadata.version(name)
                                  for name in ('torch', 'numpy', 'robosuite', 'mujoco', 'transformers')},
    }


def inert_module(name, path):
    return importlib.util.module_from_spec(importlib.util.spec_from_file_location(name, path))


@pytest.fixture
def live(monkeypatch):
    closure = prospective()
    rule = closure['generated_modules'][source.GENERATED_NAME]
    template = runpy.run_path(rule['template']['path'])
    content = template['get_remote_module_template'](True).format(
        assign_module_interface_cls='module_interface_cls = None', args='*args',
        kwargs='**kwargs', arg_types='*args, **kwargs', arrow_and_return_type='',
        arrow_and_future_return_type='', jit_script_decorator='')
    with tempfile.TemporaryDirectory() as parent:
        owner = tempfile.TemporaryDirectory(dir=parent)
        original_name = owner.name
        try:
            path = Path(owner.name) / (source.GENERATED_NAME + '.py')
            path.write_text(content)
            assert source.w.sha(path) == CONTENT_SHA
            modules = {name: inert_module(name, row['path']) for name, row in closure['modules'].items()}
            modules[source.GENERATOR_NAME]._TEMP_DIR = owner
            modules[source.GENERATOR_NAME].INSTANTIATED_TEMPLATE_DIR_PATH = owner.name
            modules[source.GENERATED_NAME] = inert_module(source.GENERATED_NAME, path)
            monkeypatch.setattr(source, 'sys', SimpleNamespace(
                modules=modules, executable=sys.executable, version=sys.version))
            yield closure, modules, path
        finally:
            owner.name = original_name
            owner.cleanup()


def test_prospective_before_and_after(live):
    closure, modules, path = live
    generated = modules.pop(source.GENERATED_NAME)
    assert source.verify_runtime(closure, closure['runtime']) == closure
    source.attest_runtime(closure, closure['runtime'])
    with pytest.raises(ValueError, match='required runtime modules not loaded'):
        source.attest_runtime(closure, closure['runtime'], after=True)
    modules[source.GENERATED_NAME] = generated
    assert source.attest_runtime(closure, closure['runtime'], after=True)[source.GENERATED_NAME] == record(path)


@pytest.mark.parametrize('fault', [
    'content', 'file', 'relative_file', 'spec_origin', 'spec_name', 'spec_missing',
    'spec_package', 'spec_location', 'spec_cached', 'spec_state', 'loader', 'loader_path',
    'loader_name', 'module_loader', 'module_name', 'module_package', 'module_cached',
    'none_module', 'owner_absent', 'owner_fake', 'owner_dead', 'directory', 'owner_name', 'directory_symlink',
    'generator_absent', 'template_absent', 'generator_origin', 'template_origin',
    'generator_spec', 'template_spec', 'wrong_name', 'adjacent', 'alias', 'linked_file',
    'ordinary_bytes', 'unexpected_ordinary',
])
def test_live_adversaries(live, fault):
    closure, modules, path = live
    module = modules[source.GENERATED_NAME]
    generator = modules[source.GENERATOR_NAME]
    if fault == 'content': path.write_text('tampered\n')
    elif fault == 'file': module.__file__ = str(path.parent.parent / path.name)
    elif fault == 'relative_file': module.__file__ = './' + str(path).lstrip('/')
    elif fault == 'spec_origin': module.__spec__.origin = str(path) + '.wrong'
    elif fault == 'spec_name': module.__spec__.name = 'wrong'
    elif fault == 'spec_missing': module.__spec__ = None
    elif fault == 'spec_package': module.__spec__.submodule_search_locations = []
    elif fault == 'spec_location': module.__spec__.has_location = False
    elif fault == 'spec_cached': module.__spec__.cached = 'wrong'
    elif fault == 'spec_state': module.__spec__.loader_state = {'unexpected': True}
    elif fault == 'loader': module.__spec__.loader = object()
    elif fault == 'loader_path': module.__loader__.path = str(path) + '.wrong'
    elif fault == 'loader_name': module.__loader__.name = 'wrong'
    elif fault == 'module_loader': module.__loader__ = object()
    elif fault == 'module_name': module.__name__ = 'wrong'
    elif fault == 'module_package': module.__package__ = 'wrong'
    elif fault == 'module_cached': module.__cached__ = 'wrong'
    elif fault == 'none_module': modules[source.GENERATED_NAME] = None
    elif fault == 'owner_absent': del generator._TEMP_DIR
    elif fault == 'owner_fake': generator._TEMP_DIR = SimpleNamespace(name=str(path.parent))
    elif fault == 'owner_dead': generator._TEMP_DIR._finalizer.detach()
    elif fault == 'directory': generator.INSTANTIATED_TEMPLATE_DIR_PATH = str(path.parent.parent)
    elif fault == 'owner_name':
        generator._TEMP_DIR.name = str(path.parent.parent)
        generator.INSTANTIATED_TEMPLATE_DIR_PATH = generator._TEMP_DIR.name
    elif fault == 'directory_symlink':
        alias = path.parent.parent / 'alias'; alias.symlink_to(path.parent, target_is_directory=True)
        generator._TEMP_DIR.name = str(alias)
        generator.INSTANTIATED_TEMPLATE_DIR_PATH = str(alias)
    elif fault == 'generator_absent': del modules[source.GENERATOR_NAME]
    elif fault == 'template_absent': del modules[source.TEMPLATE_NAME]
    elif fault == 'generator_origin': generator.__file__ += '.wrong'
    elif fault == 'template_origin': modules[source.TEMPLATE_NAME].__file__ += '.wrong'
    elif fault == 'generator_spec': generator.__spec__.origin += '.wrong'
    elif fault == 'template_spec': modules[source.TEMPLATE_NAME].__spec__.name = 'wrong'
    elif fault == 'wrong_name': modules['_remote_module_wrong'] = modules.pop(source.GENERATED_NAME)
    elif fault == 'adjacent':
        adjacent = path.with_name('neighbor.py'); adjacent.write_text('pass\n')
        modules['neighbor'] = inert_module('neighbor', adjacent)
        closure['modules']['neighbor'] = record(adjacent)  # even an ordinary entry cannot authorize it
    elif fault == 'alias': modules['another_name'] = module
    elif fault == 'linked_file':
        target = path.parent.parent / 'target.py'; path.rename(target); path.symlink_to(target)
    elif fault in ('ordinary_bytes', 'unexpected_ordinary'):
        ordinary = path.parent.parent / 'ordinary.py'; ordinary.write_text('pass\n')
        modules['ordinary'] = inert_module('ordinary', ordinary)
        if fault == 'ordinary_bytes':
            closure['modules']['ordinary'] = record(ordinary); ordinary.write_text('changed\n')
    with pytest.raises(ValueError):
        source.attest_runtime(closure, closure['runtime'], after=True)


@pytest.mark.parametrize('fault', [
    'v1', 'unknown_schema', 'rule', 'extra_rule_key', 'wrong_name', 'extra_name',
    'content_sha', 'missing_required', 'overlap', 'generator_hash', 'template_hash',
    'generator_stale', 'template_stale', 'generator_unfrozen', 'template_unfrozen',
])
def test_manifest_adversaries(live, fault):
    closure, modules, path = live
    modules.clear()  # all these fail before Torch import
    rule = closure['generated_modules'][source.GENERATED_NAME]
    if fault == 'v1': closure['schema'] = 'n34-runtime-source-closure-v1'
    elif fault == 'unknown_schema': closure['schema'] = 'n34-runtime-source-closure-v3'
    elif fault == 'rule': rule['rule'] = 'anything-under-tmp'
    elif fault == 'extra_rule_key': rule['path'] = str(path)
    elif fault == 'wrong_name': closure['generated_modules'] = {'wrong': rule}
    elif fault == 'extra_name': closure['generated_modules']['_remote_module_extra'] = rule
    elif fault == 'content_sha': rule['sha256'] = '0' * 64
    elif fault == 'missing_required': closure['required_after'].remove(source.GENERATED_NAME)
    elif fault == 'overlap': closure['modules'][source.GENERATED_NAME] = record(path)
    else:
        key, kind = fault.split('_')
        name = source.GENERATOR_NAME if key == 'generator' else source.TEMPLATE_NAME
        if kind == 'hash': rule[key]['sha256'] = '0' * 64
        elif kind == 'unfrozen': del closure['modules'][name]
        else:
            stale = path.parent.parent / (key + '.py')
            stale.write_bytes(Path(rule[key]['path']).read_bytes() + b'\n# stale\n')
            rule[key] = record(stale)
            closure['modules'][name] = rule[key]  # rehashing stale bytes is still forbidden
    with pytest.raises(ValueError):
        source.verify_runtime(closure, closure['runtime'])


def child(mode, manifest):
    """Discover ordinary TEST inventory once, then verify in fresh interpreters."""
    closure = prospective() if mode == 'discover' else json.loads(manifest.read_text())
    source.verify_runtime(closure, closure['runtime'])
    if mode != 'discover':
        source.attest_runtime(closure, closure['runtime'])
        assert source.GENERATED_NAME not in sys.modules
    import torch.distributed.nn.api.remote_module  # actual installed generation/import, no model
    generated_path = Path(sys.modules[source.GENERATED_NAME].__file__)
    if mode == 'discover':
        # Only ordinary records are observed here. Generated trust was fixed above
        # before imports. This ephemeral test fixture is NOT a production closure.
        for name, module in list(sys.modules.items()):
            file = getattr(module, '__file__', None)
            if file is not None and name != source.GENERATED_NAME and name not in ('torch.ops', 'torch.classes'):
                path = Path(file).resolve()
                if not path.is_relative_to(ROOT): closure['modules'][name] = record(path)
        manifest.write_text(json.dumps(closure))
    source.attest_runtime(closure, closure['runtime'], after=True)
    rejected = []
    if mode == 'tamper':
        module = sys.modules[source.GENERATED_NAME]
        old = module.__spec__.origin
        module.__spec__.origin = old + '.wrong'
        try:
            source.attest_runtime(closure, closure['runtime'], after=True)
        except ValueError: rejected.append('spec')
        finally: module.__spec__.origin = old
        original = generated_path.read_bytes()
        generated_path.write_bytes(original + b'\n# tampered\n')
        try:
            source.attest_runtime(closure, closure['runtime'], after=True)
        except ValueError: rejected.append('bytes')
        finally: generated_path.write_bytes(original)
        with tempfile.TemporaryDirectory() as other:
            wrong_path = Path(other) / generated_path.name
            wrong_path.write_bytes(original)
            sys.modules[source.GENERATED_NAME] = inert_module(source.GENERATED_NAME, wrong_path)
            try:
                source.attest_runtime(closure, closure['runtime'], after=True)
            except ValueError: rejected.append('origin')
            finally: sys.modules[source.GENERATED_NAME] = module
        assert rejected == ['spec', 'bytes', 'origin']
        source.attest_runtime(closure, closure['runtime'], after=True)
    print(json.dumps({'mode': mode, 'path': str(generated_path), 'sha256': source.w.sha(generated_path),
                      'rejected': rejected}))


def test_real_installed_torch_separate_processes(tmp_path):
    manifest = tmp_path / 'test-only-closure.json'
    results = []
    for mode in ('discover', 'valid', 'valid', 'tamper'):
        result = subprocess.run([PYTHON, '-B', str(Path(__file__).resolve()),
                                 '--child', mode, str(manifest)], cwd=ROOT,
                                env={**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'PYTHONDONTWRITEBYTECODE': '1',
                                     'PYTHONPATH': str(ROOT)},
                                capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
        results.append(json.loads(result.stdout.strip().splitlines()[-1]))
    assert len({row['path'] for row in results}) == 4
    assert {row['sha256'] for row in results} == {CONTENT_SHA}
    assert results[-1]['rejected'] == ['spec', 'bytes', 'origin']
    print('\nREAL_TORCH_RESULTS=' + json.dumps(results, sort_keys=True))


if __name__ == '__main__':
    assert sys.argv[1] == '--child'
    child(sys.argv[2], Path(sys.argv[3]))
