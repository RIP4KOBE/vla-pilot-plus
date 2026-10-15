"""Independent wrapper-only synthetic checks; no cohort/episode input is read."""
import copy
import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-decision-evidence-20260923/docs/03_evidence/qd_ed_final/continuation_20260923/n3-post-dev-diagnostic-preparation/read_full_dev.py')
spec = importlib.util.spec_from_file_location('independent_n3_complete_adapter', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def never_called(*args):
    raise AssertionError('inactive/control path invoked native consumer')


def metric(active=False, applicable=True):
    return {'qd_quality_applicable': applicable, 'qd_feedback_active': active,
            'qd_feedback_context': {'stage': 1, 'target_valid': False, 'target_status': 'current_pose_fallback'} if applicable else {},
            'qd_feedback_previous': {}, 'qd_feedback_selected': {},
            'qd_quality_reason': 'synthetic_recognized' if applicable else 'unsupported',
            'qd_feedback_reason': 'synthetic_inactive'}


def selection(value):
    return [{'event': 'execution_feedback_selection', 'sequence': 7,
             'values': {key: value['qd_feedback_'+key] for key in ('active', 'context', 'previous', 'selected')}}]


def test_optional_stage_absent_empty_are_distinct_and_absence_rechecked(tmp_path):
    path = tmp_path/'stage_events.jsonl'; inputs = m.Inputs(tmp_path)
    assert m.optional_stage({'status': 'not_recorded', 'path': str(path)}, path, {}, inputs) is None
    path.write_bytes(b'')
    with pytest.raises(ValueError, match='absent_source_appeared'): inputs.finish()
    present = m.Inputs(tmp_path)
    ref = {'path': str(path), 'sha256': hashlib.sha256(b'').hexdigest()}
    assert m.optional_stage({'status': 'present', 'reference': ref}, path, {}, present) == []


def test_control_and_off_do_not_claim_runtime_tracking_failure_or_invoke_consumer():
    consumer = SimpleNamespace(analyze_active=never_called)
    control = m.runtime_record('Q0', {'use_guidance': True}, [], None, 3, consumer)
    off = m.runtime_record('N3', {'use_guidance': False}, [], None, 3, consumer)
    assert control['status'] == 'not_applicable_control' and control['active'] is None
    assert off['status'] == 'unguided' and off['active'] is False
    assert control['executed_actions'] == off['executed_actions'] == 3


def test_unsupported_and_runtime_inactive_keep_disposition_and_actual_m():
    consumer = SimpleNamespace(analyze_active=never_called)
    unsupported = m.runtime_record('N3', {'use_guidance': True}, [], metric(applicable=False), 3, consumer)
    value = metric(); before = copy.deepcopy(value)
    inactive = m.runtime_record('N3', {'use_guidance': True}, selection(value), value, 3, consumer)
    assert unsupported['status'] == 'unsupported' and inactive['status'] == 'recognized_inactive'
    assert inactive['active'] is False and inactive['executed_actions'] == 3
    assert inactive['runtime_context']['target_valid'] is False
    assert inactive['feedback_selection_event_sequence'] == 7
    assert inactive['previous_recorded_provenance'] == value['qd_feedback_previous']
    assert inactive['selected_recorded_provenance'] == value['qd_feedback_selected']
    assert value == before  # No retrospective pair result is substituted into runtime metadata.


def test_active_start_with_partial_execution_keeps_actual_prefix_count():
    value = metric(active=True); value['qd_feedback_context']['target_valid'] = True
    calls = []
    def consumer(rows, received):
        calls.append((rows, received)); return {'synthetic_consumer_marker': True}
    rows = selection(value)
    result = m.runtime_record('N3', {'use_guidance': True}, rows, value, 3, SimpleNamespace(analyze_active=consumer))
    assert result['active'] is True and result['executed_actions'] == 3
    assert result['consumer'] == {'synthetic_consumer_marker': True} and calls == [(rows, value)]


def test_runtime_event_metric_mismatch_rejects_before_consumer():
    value = metric(active=True); rows = selection(value); rows[0]['values']['active'] = False
    with pytest.raises(ValueError, match='native_metric_feedback_link_differs'):
        m.runtime_record('N3', {'use_guidance': True}, rows, value, 8, SimpleNamespace(analyze_active=never_called))
