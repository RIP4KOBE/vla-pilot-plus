"""Ordered real-recorder terminal traces; no simulator or GPU execution."""
import copy
import pytest
import torch
from test_n35_closure_intent_integration import (
    episode, expected, _patch_core_imports, stub_adapter, mock_batch,
)
from scripts import qd_ed_n35_native as audit


@pytest.mark.parametrize('terminal_kind', ['terminated', 'truncated'])
@pytest.mark.parametrize('prefix', [1, 4, 8])
def test_terminal_prefix_and_reset_evidence(tmp_path, monkeypatch, stub_adapter, mock_batch,
                                          terminal_kind, prefix):
    m, original, c, generic = episode(tmp_path, monkeypatch, stub_adapter, mock_batch,
        target=0., terminal_kind=terminal_kind, terminal_prefix=prefix)
    trust = expected(original)
    result = generic()
    assert result['accepted'], result['errors']
    result = audit.audit_events('N35', m, original, c, expected_runtime=trust)
    assert result['executed_actions_verified'] == prefix
    assert result['lifecycle']['acknowledgements'] == prefix
    assert result['lifecycle']['resets'] == ['terminal']
    assert result['lifecycle']['created_tokens'] == 0
    kinds = ('pre_reset_outcome', 'automatic_reset_boundary', 'step_returned',
             'n35_step_acknowledged', 'n35_memory_reset')
    terminal = [e for e in original if e['global_step'] == prefix-1 and e['event'] in kinds]
    assert [e['event'] for e in terminal] == [k for k in kinds
        if k != 'automatic_reset_boundary' or terminal_kind == 'terminated']
    assert [e['reset_sequence'] for e in terminal] == (
        [0, 0, 1, 1, 1] if terminal_kind == 'terminated' else [0, 0, 0, 0])
    assert not torch.cuda.is_initialized()

    # Reuse the expensive native policy trace; independently corrupt each
    # mandatory association, preserving ordering numbers for moved records.
    faults = ['missing_reset', 'duplicate_reset', 'reset_before_ack', 'reset_before_return',
              'reset_after_boundary', 'reset_wrong_reason', 'reset_episode', 'reset_decision',
              'reset_step', 'reset_epoch', 'ack_epoch', 'return_epoch', 'outcome_epoch',
              'early_n35_epoch', 'ack_step', 'duplicate_ack', 'missing_ack',
              'reset_sequence', 'return_termination', 'reset_without_terminal',
              'ack_before_return', 'ack_after_boundary']
    if terminal_kind == 'terminated':
        faults += ['missing_auto', 'duplicate_auto', 'auto_after_return', 'auto_epoch',
                   'auto_episode', 'auto_decision', 'auto_step', 'auto_terminal_episode']
    else:
        faults += ['spurious_auto']
    for fault in faults:
        events = copy.deepcopy(original)
        def last(kind):
            return next(e for e in reversed(events) if e['event'] == kind)
        reset = last('n35_memory_reset')
        ack = last('n35_step_acknowledged')
        returned = last('step_returned')
        outcome = last('pre_reset_outcome')
        if fault == 'missing_reset': events.remove(reset)
        elif fault == 'duplicate_reset': events.append(copy.deepcopy(reset))
        elif fault in ('reset_before_ack', 'reset_before_return'):
            events.remove(reset)
            events.insert(events.index(ack if fault == 'reset_before_ack' else returned), reset)
        elif fault == 'reset_after_boundary':
            boundary = copy.deepcopy(reset);boundary['event'] = 'decision_context'
            boundary['values'] = copy.deepcopy(events[0]['values'])
            events.insert(events.index(reset), boundary)
        elif fault == 'ack_before_return':
            events.remove(ack);events.insert(events.index(returned), ack)
        elif fault == 'ack_after_boundary':
            boundary = copy.deepcopy(ack);boundary['event'] = 'decision_context'
            boundary['values'] = copy.deepcopy(events[0]['values'])
            events.insert(events.index(ack), boundary)
        elif fault == 'reset_wrong_reason': reset['values']['reason'] = 'episode_reset'
        elif fault == 'reset_sequence': reset['sequence'] = ack['sequence']
        elif fault.startswith('reset_') and fault.split('_')[1] in ('episode','decision','step','epoch'):
            key = {'episode':'episode','decision':'decision_id','step':'global_step','epoch':'reset_sequence'}[fault.split('_')[1]]
            reset[key] = 'wrong' if key == 'decision_id' else reset[key]+1
        elif fault in ('ack_epoch','return_epoch','outcome_epoch'):
            {'ack_epoch':ack,'return_epoch':returned,'outcome_epoch':outcome}[fault]['reset_sequence'] += 1
        elif fault == 'early_n35_epoch':
            next(e for e in events if e['event']=='n35_boundary_entry')['reset_sequence'] += 1
        elif fault == 'ack_step': ack['global_step'] += 1
        elif fault == 'duplicate_ack': events.insert(events.index(reset), copy.deepcopy(ack))
        elif fault == 'missing_ack': events.remove(ack)
        elif fault == 'return_termination': returned['values']['terminated'] = not returned['values']['terminated']
        elif fault == 'reset_without_terminal':
            # A consistent nonterminal return cannot authorize a terminal reset.
            outcome['values'].update(terminated=False,success=False)
            returned['values'].update(terminated=False,truncated=False,success=False)
            ack['values']['ended'] = False
            events = [e for e in events if e['event'] != 'automatic_reset_boundary']
            for e in events: e['reset_sequence'] = 0
        elif fault == 'spurious_auto':
            auto = copy.deepcopy(outcome);auto['event'] = 'automatic_reset_boundary'
            auto['values'] = {'terminal_episode':0,'reset_will_follow':True,'reset_completed':None}
            events.insert(events.index(returned), auto)
        else:
            auto = last('automatic_reset_boundary')
            if fault == 'missing_auto': events.remove(auto)
            elif fault == 'duplicate_auto': events.insert(events.index(auto), copy.deepcopy(auto))
            elif fault == 'auto_after_return':
                events.remove(auto);events.insert(events.index(returned)+1, auto)
            elif fault == 'auto_terminal_episode': auto['values']['terminal_episode'] += 1
            else:
                key = {'auto_epoch':'reset_sequence','auto_episode':'episode',
                       'auto_decision':'decision_id','auto_step':'global_step'}[fault]
                auto[key] = 'wrong' if key == 'decision_id' else auto[key]+1
        if fault != 'reset_sequence':
            for sequence, e in enumerate(events, 1): e['sequence'] = sequence
        with pytest.raises(ValueError):
            audit.audit_events('N35', m, events, c, expected_runtime=trust)
        print('REJECTED', terminal_kind, prefix, fault)
