"""Source-only CPU parity; no adapter imports, provenance or runtime fixtures."""
import ast
import copy
import hashlib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / 'scripts/qd_ed_n36_engineering.py'
CHILD = ROOT / 'scripts/qd_ed_n36_engineering_r1.py'
PARENT_SHA256 = 'd93eed25e93fb4a211180cc9abdc76d767ca278a7663dbedd1f29aee53874af1'


def dump(node):
    return ast.dump(node, include_attributes=False)


def functions(text):
    nodes = [n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)]
    assert len(nodes) == len({n.name for n in nodes}), 'duplicate function'
    return {n.name: n for n in nodes}


def assert_parent_parity(parent_path=PARENT, child_path=CHILD, *, child_text=None):
    parent_bytes = Path(parent_path).read_bytes()
    assert hashlib.sha256(parent_bytes).hexdigest() == PARENT_SHA256
    old = functions(parent_bytes)
    new = functions(Path(child_path).read_text() if child_text is None else child_text)
    intentional = {'specification', 'validate_audit_view', 'validate_plan_shape', 'validate_authority',
                   '_journal_suffixes', 'reconcile', 'validate_readiness', 'child_environment'}
    assert set(old) == set(new) - {'terminal_parent_prefix', 'validate_runtime_binding', 'preparation_health_suffix',
        '_recovery_json', '_recovery_rows', '_recovery_read', '_recovery_contract',
        '_recovery_capture', '_recovery_partition', '_recovery_specification', '_recovery_predecessors',
        '_recovery_inventory', '_recovery_inventory_previous', 'validate_private_budget'}, 'helper inventory'

    helper = copy.deepcopy(new['validate_private_budget'])
    if (helper.body and isinstance(helper.body[0], ast.Expr)
            and isinstance(helper.body[0].value, ast.Constant)
            and isinstance(helper.body[0].value.value, str)):
        helper.body.pop(0)  # The only semantic-tree normalization permitted.
    expected = ast.parse('def validate_private_budget(authority, state):\n    pass').body[0]
    expected.body = copy.deepcopy(old['validate_state'].body[2:])
    assert dump(helper) == dump(expected), 'private budget helper differs from frozen parent'

    caller = copy.deepcopy(new['validate_state'])
    references = [n for n in ast.walk(caller)
                  if isinstance(n, ast.Name) and n.id == 'validate_private_budget']
    assert len(references) == 1, 'private budget helper call count'
    call = ast.parse('validate_private_budget(authority, state)').body[0]
    assert len(caller.body) == 3 and dump(caller.body[-1]) == dump(call), 'private budget call shape/order'
    caller.body[-1:] = copy.deepcopy(helper.body)
    new['validate_state'] = caller
    for name in old.keys() - intentional:
        assert dump(new[name]) == dump(old[name]), name


def test_parent_source_and_shared_safety_predicates_unchanged():
    assert_parent_parity()


# Every budget/cap/isolation clause is independently attacked in memory.
@pytest.mark.parametrize('before,after', [
    ('full.validate_caps(caps)', 'pass'),
    ('r.authorized_gpu(state) == 7', 'r.authorized_gpu(state) == 6'),
    ("budget['max_episode_attempts'] == caps['attempts']", 'True'),
    ("budget['max_gpu_hours'] == caps['gpu_hours']", 'True'),
    ("budget['reserved'] == caps['buckets']", 'True'),
    ("budget['gpu_hour_reservations'] == caps['protected_gpu_hours']", 'True'),
    ("budget['amendment'] == authority['amendment']", 'True'),
    ("isolation.get('status') == 'ACTIVE'", 'True'),
    ("isolation.get('validation_status') == 'PASS'", 'True'),
    ("isolation.get('private_budget') is True", "isolation.get('private_budget') == True"),
    ("not state.get('external_resource_hold', {}).get('do_not_auto_resume', False)", 'True'),
    ('and', 'or'),
])
def test_private_budget_predicate_mutations_rejected(before, after):
    tree = ast.parse(CHILD.read_text())
    helper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'validate_private_budget')
    source = ast.unparse(helper)
    assert before in source
    mutated = ast.parse(source.replace(before, after, 1)).body[0]
    tree.body[tree.body.index(helper)] = mutated
    with pytest.raises(AssertionError, match='private budget helper differs'):
        assert_parent_parity(child_text=ast.unparse(tree))


@pytest.mark.parametrize('mutation', [
    'missing_call', 'duplicate_call', 'wrong_arguments', 'keyword_call', 'conditional_call',
    'reordered_call', 'missing_owner', 'missing_adoption', 'helper_default', 'helper_extra_arg',
    'helper_decorator', 'helper_return', 'helper_extra_string', 'extra_helper', 'duplicate_helper',
    'other_shared_predicate',
])
def test_extraction_structure_mutations_rejected(mutation):
    tree = ast.parse(CHILD.read_text())
    nodes = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    caller, helper = nodes['validate_state'], nodes['validate_private_budget']
    if mutation == 'missing_call': caller.body.pop()
    elif mutation == 'duplicate_call': caller.body.append(copy.deepcopy(caller.body[-1]))
    elif mutation == 'wrong_arguments': caller.body[-1].value.args.reverse()
    elif mutation == 'keyword_call':
        caller.body[-1] = ast.parse('validate_private_budget(authority=authority, state=state)').body[0]
    elif mutation == 'conditional_call':
        caller.body[-1] = ast.If(test=ast.Constant(True), body=[caller.body[-1]], orelse=[])
    elif mutation == 'reordered_call': caller.body.insert(0, caller.body.pop())
    elif mutation == 'missing_owner': caller.body[0] = ast.Pass()
    elif mutation == 'missing_adoption': caller.body[1] = ast.Pass()
    elif mutation == 'helper_default': helper.args.defaults.append(ast.Constant(None))
    elif mutation == 'helper_extra_arg': helper.args.args.append(ast.arg(arg='plan'))
    elif mutation == 'helper_decorator': helper.decorator_list.append(ast.Name(id='decorator', ctx=ast.Load()))
    elif mutation == 'helper_return': helper.body.append(ast.Return(value=ast.Constant(True)))
    elif mutation == 'helper_extra_string': helper.body.append(ast.Expr(value=ast.Constant('not a docstring')))
    elif mutation == 'extra_helper': tree.body.append(ast.parse('def unexpected():\n    pass').body[0])
    elif mutation == 'duplicate_helper': tree.body.append(copy.deepcopy(helper))
    elif mutation == 'other_shared_predicate': nodes['headroom'].body.append(ast.Pass())
    with pytest.raises(AssertionError):
        assert_parent_parity(child_text=ast.unparse(ast.fix_missing_locations(tree)))


def test_only_helper_docstring_is_ignored():
    tree = ast.parse(CHILD.read_text())
    helper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'validate_private_budget')
    helper.body[0].value.value = 'Different explanatory docstring.'
    assert_parent_parity(child_text=ast.unparse(tree))
    helper.body.pop(0)
    assert_parent_parity(child_text=ast.unparse(tree))
