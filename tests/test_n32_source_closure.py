"""CPU source-only regression; never import Main, model or simulator modules."""
import ast
import hashlib
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from scripts import qd_ed_n32_bridge as b


PARENT = 'c427e7acdef0a42fa56c53460dd8587ca3489b1d'
RDT_SOURCE = 'third_party/rdt/scripts/maniskill_model.py'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=b.ROOT, text=True)


def old_paths():
    """Execute only the old inventory function, not the old bridge module."""
    tree = ast.parse(git('show', PARENT + ':scripts/qd_ed_n32_bridge.py'))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == 'source_paths')
    namespace = vars(b).copy()
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<old-inventory>', 'exec'), namespace)
    return namespace['source_paths']()


@pytest.fixture(scope='module')
def real_sources():
    """Read pinned local Git objects when the RDT worktree is uninitialized.

    No fetch, checkout, submodule initialization or owning-source mutation.
    """
    commit = git('ls-tree', 'HEAD', 'third_party/rdt').split()[2]
    common = Path(git('rev-parse', '--git-common-dir').strip())
    if not common.is_absolute():
        common = b.ROOT / common
    database = common / 'modules/third_party/rdt'
    if not database.is_dir():
        pytest.fail('Pinned local RDT Git objects required for real-source closure review')
    files = git('--git-dir=' + str(database), 'ls-tree', '-r', '--name-only', commit).splitlines()
    rdt = {name: git('--git-dir=' + str(database), 'show', commit + ':' + name)
           for name in files if name.endswith('.py')}

    def read(relative):
        if relative.startswith('third_party/rdt/'):
            return rdt.get(relative.removeprefix('third_party/rdt/'))
        path = b.ROOT / relative
        return path.read_text() if path.is_file() else None

    return read


def static_closure(read):
    """Follow literal imports, including relative imports and package init files.

    Both import roots match Main/RDT. Conditional imports are conservatively
    included. Dynamic imports and third-party site packages are not certified.
    """
    def resolve(name):
        for base in ('', 'third_party/rdt/'):
            stem = base + name.replace('.', '/')
            for path in (stem + '.py', stem + '/__init__.py'):
                if read(path) is not None:
                    return path

    pending = [('main', 'main.py')]
    seen = {}
    while pending:
        name, path = pending.pop()
        if name in seen:
            continue
        seen[name] = path
        package = name if path.endswith('/__init__.py') else name.rpartition('.')[0]
        for node in ast.walk(ast.parse(read(path), filename=path)):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                prefix = node.module or ''
                if node.level:
                    parts = package.split('.')
                    prefix = '.'.join(parts[:len(parts) - node.level + 1]
                                      + ([prefix] if prefix else []))
                names = [prefix] + [prefix + '.' + a.name for a in node.names if a.name != '*']
            for dependency in names:
                parts = dependency.split('.')
                for length in range(1, len(parts) + 1):
                    candidate = '.'.join(parts[:length])
                    target = resolve(candidate)
                    if target is not None:
                        pending.append((candidate, target))
    return seen


def test_real_main_transitive_attested_closure(real_sources):
    closure = static_closure(real_sources)
    attested = {path for name, path in closure.items()
                if name.startswith(('core.', 'scripts.', 'utils.'))}
    assert closure['scripts.maniskill_model'] == RDT_SOURCE
    assert closure['core.rdt_policy_steer'] == 'core/rdt_policy_steer.py'
    assert closure['models.rdt_runner'] == 'third_party/rdt/models/rdt_runner.py'
    assert closure['configs.state_vec'] == 'third_party/rdt/configs/state_vec.py'
    assert attested - old_paths() == {RDT_SOURCE}
    assert attested <= b.source_paths()
    assert b.source_paths() - old_paths() == {RDT_SOURCE}
    print('Static literal-import closure:', sorted(closure.items()))


def test_required_rdt_source_not_silently_globbed_away():
    assert RDT_SOURCE in b.source_paths()


@pytest.fixture
def frozen(tmp_path, monkeypatch, real_sources):
    root = tmp_path / 'checkout'
    path = root / RDT_SOURCE
    path.parent.mkdir(parents=True)
    path.write_text(real_sources(RDT_SOURCE))
    record = {'path': RDT_SOURCE, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    # Representative loaded records exercise the real attestor without executing
    # the source (which would import models and potentially initialize devices).
    monkeypatch.setattr(b, 'sys', SimpleNamespace(modules={
        'scripts.maniskill_model': SimpleNamespace(__file__=str(path))}))
    return root, path, {'files': [record]}


def test_old_inventory_reproduces_terminal_failure(frozen):
    root, _, source = frozen
    source['files'] = [r for r in source['files'] if r['path'] in old_paths()]
    with pytest.raises(ValueError, match='loaded source not frozen: scripts.maniskill_model'):
        b.attest_loaded(root, source)


def test_correct_frozen_new_inventory_accepts(frozen):
    root, _, source = frozen
    assert all(r['path'] in b.source_paths() for r in source['files'])
    assert b.attest_loaded(root, source) == {'scripts.maniskill_model': source['files'][0]}


@pytest.mark.parametrize('fault', ['omitted', 'modified', 'wrong_hash', 'wrong_root', 'unknown'])
def test_attestation_still_rejects_unfrozen_sources(frozen, fault):
    root, path, source = frozen
    if fault == 'omitted':
        source['files'].clear()
    elif fault == 'modified':
        path.write_text(path.read_text() + '\n# changed after freeze\n')
    elif fault == 'wrong_hash':
        source['files'][0]['sha256'] = '0' * 64
    elif fault == 'wrong_root':
        root = root.parent / 'adjacent-checkout'
    elif fault == 'unknown':
        extra = root / 'scripts/unreviewed.py'
        extra.parent.mkdir()
        extra.write_text('VALUE = 1\n')
        b.sys.modules['scripts.unreviewed'] = SimpleNamespace(__file__=str(extra))
    reason = 'loaded adjacent checkout' if fault == 'wrong_root' else 'loaded source not frozen'
    with pytest.raises(ValueError, match=reason):
        b.attest_loaded(root, source)


def test_attestor_unchanged_from_terminal_attempt():
    before = ast.parse(git('show', PARENT + ':scripts/qd_ed_n32_bridge.py'))
    after = ast.parse((b.ROOT / 'scripts/qd_ed_n32_bridge.py').read_text())
    def attestor(tree):
        return ast.dump(next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                             and n.name == 'attest_loaded'))
    assert attestor(before) == attestor(after)
