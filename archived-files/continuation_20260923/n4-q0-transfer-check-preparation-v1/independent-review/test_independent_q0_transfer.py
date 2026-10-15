"""Focused synthetic source review only; never invoke the actual reader."""
import copy
import importlib.util
from pathlib import Path

import pytest
import torch

E = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-decision-evidence-20260923/docs/03_evidence/qd_ed_final/continuation_20260923/n4-q0-transfer-check-preparation')
spec = importlib.util.spec_from_file_location('independent_n4_fixture', E/'test_q0_transfer.py')
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
m = f.m


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', '')
    assert not torch.cuda.is_initialized()
    result = m.dependencies(f.DEFINITION)
    yield result
    assert not torch.cuda.is_initialized()


def test_terminal_pre_reset_ack_keeps_actual_m(modules):
    rows = f.fixture_rows(modules, actual_m=3)
    returned = next(r for r in reversed(rows) if r['event'] == 'step_returned')
    outcome = next(r for r in reversed(rows) if r['event'] == 'pre_reset_outcome')
    boundary = copy.deepcopy(outcome)
    boundary.update(event='automatic_reset_boundary', values={'reset_will_follow': True, 'reset_completed': None})
    rows.insert(rows.index(returned), boundary)
    for i, row in enumerate(rows): row['sequence'] = i+1
    # Original canonical score references precede this last-window insertion.
    returned['reset_sequence'] = 1
    returned['values']['terminated'] = True
    got = m.inspect_decision(rows, modules)
    assert got['status'] == 'known_guided_comparison'
    assert got['comparison']['actual_prefix_length'] == 3
    assert len(got['comparison']['actual_dispatched_commands_FP32']['values']) == 3


def test_stored_bfloat16_ties_choose_first_index(modules):
    got = m.check_guided(f.fixture_rows(modules), modules)
    assert got['minimum_cost_tie_indices'] == [0, 1, 2]
    assert got['alternative_first_index'] == 0
    assert got['canonical_batches'][-1]['stored_cost']['dtype'] == 'torch.bfloat16'


def test_member_tie_action_change_is_not_conjunction(modules):
    x = f.last_template()
    costs = torch.arange(1000, 1016).to(torch.bfloat16)
    x[0, :, 39], x[1, :, 39] = 1, 2
    costs[0] = costs[1] = 0
    got = m.check_guided(f.fixture_rows(modules, last_actions=x, last_costs=costs, select_last=1), modules)
    assert got['last_canonical_membership_indices'] == [1]
    assert got['alternative_first_index'] == 0
    assert got['different_actual_m'] and not got['nonmember_and_actual_m_difference']


@pytest.mark.parametrize('kind', ['inactive_dimension', 'suffix_after_actual_m', 'signed_zero'])
def test_nonmember_without_actual_command_effect_does_not_pass(modules, kind):
    x = f.last_template()
    x[0] = 0
    x[0, :, 10] = -1
    if kind == 'inactive_dimension': x[0, :, 2] = 9
    elif kind == 'suffix_after_actual_m': x[0, 3:, 39] = 1
    else: x[0, :, 39] = -0.0
    got = m.check_guided(f.fixture_rows(modules, last_actions=x, actual_m=3), modules)
    assert got['nonmember'] and got['alternative_native_identity_differs']
    assert not got['different_actual_m'] and not got['nonmember_and_actual_m_difference']
    assert got['difference_only_after_m'] == (kind == 'suffix_after_actual_m')


def test_numeric_equal_parent_dtype_alias_fails_native_binding(modules):
    rows = f.fixture_rows(modules)
    parent = next(r for r in rows if r['event'] == 'parent_allocation')
    parent['values']['source_population'] = parent['values']['source_population'].float()
    got = m.inspect_decision(rows, modules)
    assert got['status'] == 'Unknown_required_association'
    assert got['reason'] == 'Q0_sparse_identity_parent_contract'


def test_equal_numbers_in_wrong_native_cost_shape_are_unknown(modules):
    rows = f.fixture_rows(modules)
    effect = next(r for r in reversed(rows) if r['event'] == 'effective_quality')
    effect['values']['costs'] = effect['values']['costs'].reshape(1, 16)
    got = m.inspect_decision(rows, modules)
    assert got['status'] == 'Unknown_required_association'
    assert got['reason'] == 'native_shape_or_type'
