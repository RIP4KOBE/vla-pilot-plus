"""Build and CPU-validate an unapplied candidate. Writes only this artifact tree."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
WORKTREE = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
GPU6 = Path('/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z')


def patch_sections(text):
    pieces = text.splitlines(keepends=True)
    sections = {}
    index = 0
    while index < len(pieces):
        assert pieces[index].startswith('--- ')
        name = pieces[index + 1].strip()[6:]
        index += 2
        start = index
        while index < len(pieces) and not pieces[index].startswith('--- '):
            index += 1
        sections[name] = pieces[start:index]
    return sections


def apply_in_memory(source, hunks):
    old = source.splitlines(keepends=True)
    output = []
    position = 0
    for line in hunks:
        if line.startswith('@@'):
            start = int(re.match(r'@@ -(\d+)', line).group(1))
            destination = max(0, start - 1)
            assert destination >= position
            output.extend(old[position:destination])
            position = destination
        elif line.startswith(' '):
            assert old[position] == line[1:]
            output.append(old[position])
            position += 1
        elif line.startswith('-'):
            assert old[position] == line[1:]
            position += 1
        elif line.startswith('+'):
            output.append(line[1:])
        else:
            raise ValueError('Unexpected patch line')
    output.extend(old[position:])
    return ''.join(output)


original = (WORKTREE / 'main.py').read_text()
sections = patch_sections((HERE / 'phase-timing-proposal.patch').read_text())
proposed = apply_in_memory(original, sections['main.py'])
original_phase_tests = apply_in_memory('', sections['tests/test_episode_phase_timing.py'])

new_method = '''    def _enable_render_phase_diagnostics(self):
        """Observe existing instances only when EDS diagnostics are enabled."""
        try:
            previous = getattr(self, "_render_phase_diagnostics", None)
            if previous is not None:
                previous.close()
            self._render_phase_diagnostics = None
            config = _config_section_to_dict(self.config.get("eds_eval"), "main.eds_eval")
            if not config.get("enabled", False):
                return
            from core.render_phase_diagnostics import RenderPhaseDiagnostics
            observer = RenderPhaseDiagnostics(
                Path(config.get("output_dir") or self.output_dir) / "render_phase_timing.jsonl")
            observer.install(self.adapter)
            self._render_phase_diagnostics = observer
        except Exception:
            log.warning("Render phase timing unavailable")

'''
anchor = '    def _append_phase_timing(self, *, episode, global_step, name, event, elapsed_s):\n'
assert proposed.count(anchor) == 1
proposed = proposed.replace(anchor, new_method + anchor)
anchor = '        """Best-effort scalar phase markers; never log operation inputs/errors."""\n'
proposed = proposed.replace(anchor, anchor + '''        observed_wall_s = float(elapsed_s)
        observer_overhead_s = 0.0
        observer = getattr(self, "_render_phase_diagnostics", None)
        if observer is not None:
            try:
                overhead = observer.set_phase(episode, global_step, name, event)
                if event == "exit":
                    observer_overhead_s = float(overhead)
                    elapsed_s = max(0.0, observed_wall_s - observer_overhead_s)
            except Exception:
                pass
''')
proposed = proposed.replace('"schema": "qd-ed-phase-timing-v1"', '"schema": "qd-ed-phase-timing-v2"')
proposed = proposed.replace('"elapsed_s": float(elapsed_s),\n',
    '"elapsed_s": float(elapsed_s), "observed_wall_s": observed_wall_s,\n'
    '                "nested_observer_s": observer_overhead_s,\n')
original_phase_tests = original_phase_tests.replace('"schema": "qd-ed-phase-timing-v1"',
    '"schema": "qd-ed-phase-timing-v2"').replace(
        '"elapsed_s": 0.0 if record["event"] == "enter" else 0.125}',
        '"elapsed_s": 0.0 if record["event"] == "enter" else 0.125,\n'
        '            "observed_wall_s": 0.0 if record["event"] == "enter" else 0.125, "nested_observer_s": 0.0}')
anchor = '        self._enable_phase_diagnostics()\n'
assert proposed.count(anchor) == 1
proposed = proposed.replace(anchor, anchor + '        self._enable_render_phase_diagnostics()\n')

extra_main_tests = '''

def test_parent_context_is_updated_even_after_main_writer_failure(tmp_path):
    runner, _, _, _ = timing_runner(tmp_path)
    calls = []
    runner._render_phase_diagnostics = SimpleNamespace(set_phase=lambda *args: calls.append(args))
    runner._phase_timing_write_failed = True
    runner._append_phase_timing(episode=1, global_step=4,
        name="adapter_step", event="exit", elapsed_s=0)
    assert calls == [(1, 4, "adapter_step", "exit")]


def test_cached_fresh_and_stage_instrumentation_remains_around_actual_calls(tmp_path):
    _, _, main, _ = timing_runner(tmp_path)
    episode = next(node for node in main.body if isinstance(node, ast.FunctionDef)
                   and node.name == "_run_episode")
    loop = next(node for node in episode.body if isinstance(node, ast.While))
    pos = next(i for i, node in enumerate(loop.body) if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "self.policy.select_action")
    assert ast.unparse(loop.body[pos - 2].value.func) == "self._append_phase_timing"
    assert ast.unparse(loop.body[pos + 2].value.func) == "self._append_phase_timing"
    for node in (loop.body[pos - 2], loop.body[pos + 2]):
        name = next(kw.value for kw in node.value.keywords if kw.arg == "name")
        assert isinstance(name, ast.IfExp)
        assert name.body.value == "select_action_fresh"
        assert name.orelse.value == "select_action_cached"
    markers = [node for node in ast.walk(episode) if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute) and node.func.attr == "_append_phase_timing"]
    stage = [node for node in markers if any(kw.arg == "name" and isinstance(kw.value, ast.Constant)
        and kw.value.value == "chunk_keypoints_stage" for kw in node.keywords)]
    assert [next(kw.value.value for kw in node.keywords if kw.arg == "event") for node in stage] == ["enter", "exit"]


def test_main_phase_separates_original_wall_and_nested_observer_estimate(tmp_path):
    captured = []
    runner, _, _, _ = timing_runner(tmp_path, append=lambda path, record: captured.append(record))
    runner._render_phase_diagnostics = SimpleNamespace(set_phase=lambda *args: 0.25)
    runner._append_phase_timing(episode=0, global_step=0,
        name="adapter_step", event="exit", elapsed_s=1.0)
    assert captured[0]["observed_wall_s"] == 1.0
    assert captured[0]["nested_observer_s"] == 0.25
    assert captured[0]["elapsed_s"] == 0.75
'''

helper = (HERE / 'render-phase-helper.proposed.py').read_text()
render_tests = (HERE / 'render-phase-tests.proposed.py').read_text()
files = {'main.py': proposed, 'core/render_phase_diagnostics.py': helper,
    'tests/test_episode_phase_timing.py': original_phase_tests + extra_main_tests,
    'tests/test_render_phase_diagnostics.py': render_tests}
for name, content in files.items():
    compile(content, name, 'exec')


class RemoveDiagnostics(ast.NodeTransformer):
    def visit_Import(self, node):
        node.names = [alias for alias in node.names if alias.name != 'faulthandler']
        return node if node.names else None
    def visit_FunctionDef(self, node):
        if node.name in {'_enable_phase_diagnostics', '_append_phase_timing', '_enable_render_phase_diagnostics'}:
            return None
        return self.generic_visit(node)
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute):
            if node.value.func.attr in {'_enable_phase_diagnostics', '_append_phase_timing', '_enable_render_phase_diagnostics'}:
                return None
        return self.generic_visit(node)
    def visit_Assign(self, node):
        if any(isinstance(target, ast.Name) and target.id == 'phase_started_s' for target in node.targets):
            return None
        return self.generic_visit(node)
    def visit_If(self, node):
        node = self.generic_visit(node)
        return node if node.body or node.orelse else None


old_ast = ast.dump(ast.parse(original), include_attributes=False)
stripped_ast = ast.dump(RemoveDiagnostics().visit(ast.parse(proposed)), include_attributes=False)
assert old_ast == stripped_ast, 'Original operation AST changed'

def phase_methods(text):
    return {node.name: ast.dump(node, include_attributes=False) for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.FunctionDef) and node.name in {'_enable_phase_diagnostics', '_append_phase_timing'}}

previous_main = apply_in_memory(original, sections['main.py'])
gpu6_methods = phase_methods((GPU6 / 'main.py').read_text())
assert phase_methods(previous_main)['_append_phase_timing'] == gpu6_methods['_append_phase_timing'], 'GPU6 phase writer differs'

bundle = ''.join(''.join(difflib.unified_diff(
    (original if name == 'main.py' else '').splitlines(keepends=True), content.splitlines(keepends=True),
    fromfile='a/' + name if name == 'main.py' else '/dev/null', tofile='b/' + name))
    for name, content in files.items())
patch_path = HERE / 'main-render-phase-timing-proposal.patch'
patch_path.write_text(bundle)
check = subprocess.run(['git', 'apply', '--check', str(patch_path)], cwd=WORKTREE,
    text=True, capture_output=True, check=True)
with tempfile.TemporaryDirectory(prefix='phase-cpu-', dir=HERE) as temporary:
    root = Path(temporary)
    for name, content in files.items():
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content)
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
        str(root / 'tests/test_episode_phase_timing.py'), str(root / 'tests/test_render_phase_diagnostics.py')],
        cwd=root, text=True, capture_output=True, timeout=60)
    (HERE / 'main-render-phase-timing-cpu-tests.txt').write_text(result.stdout + result.stderr)
    print(result.stdout + result.stderr)
    result.check_returncode()
report = {'base_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=WORKTREE, text=True).strip(),
    'base_main_sha256': hashlib.sha256(original.encode()).hexdigest(),
    'patch_sha256': hashlib.sha256(bundle.encode()).hexdigest(),
    'patch_path': str(patch_path), 'source_applied': False,
    'git_apply_check': 'passed', 'cpu_tests': result.stdout.strip(),
    'original_operations_ast_unchanged': old_ast == stripped_ast,
    'operation_ast_sha256': hashlib.sha256(old_ast.encode()).hexdigest(),
    'gpu6_phase_writer_matches_original_proposal': True,
    'gpu6_extra_global_diagnostic_install_not_copied': True,
    'files_in_patch': list(files)}
assert (WORKTREE / 'main.py').read_text() == original
(HERE / 'main-render-phase-timing-validation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
