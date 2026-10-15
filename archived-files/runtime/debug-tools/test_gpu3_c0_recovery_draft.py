"""Artifact-only CPU tests; no plans written, models imported or GPU queries."""
import copy
import importlib.util
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('c0_draft_builder', HERE / 'build-gpu3-c0-recovery-draft.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
r = builder.load_runner(builder.WORKTREE)


def original():
    return r.read_json(builder.SOURCE_PLAN)


def events_for(row):
    identity = r.episode_identity(row)
    return [{'attempt_id': builder.ORIGINAL_ATTEMPT_ID, 'event': event, 'identity': identity,
             **({'retryable_infrastructure': True} if event == 'aborted' else {})}
            for event in ('reserved', 'dispatched', 'aborted')]


def draft_row(source=None):
    source = source or original()
    return builder.recovery_row(source, r, events=events_for(source['episodes'][0]),
        retry_of=builder.ORIGINAL_ATTEMPT_ID, episode_key='gpu3_native_c0_t00_r1')


def test_exact_scientific_identity_and_only_three_recovery_row_changes():
    source = original()
    row = draft_row(source)
    old = source['episodes'][0]
    assert r.episode_identity(row) == r.episode_identity(old)
    assert {k for k in set(row) | set(old) if row.get(k) != old.get(k)} == {'episode_key', 'retry_of', 'budget_bucket'}
    assert row['timeout_seconds'] == 1800 and row['iteration'] == 'GPU6_NATIVE_C0'
    r.check_retry(events_for(row), row)


def test_consumed_retry_fails_before_any_draft_or_launch(tmp_path, monkeypatch, capsys):
    row = draft_row()
    events = events_for(row)
    events += [{'attempt_id': 'other_worktree_recovery', 'event': 'reserved',
                'identity': r.episode_identity(row), 'retry_of': builder.ORIGINAL_ATTEMPT_ID}]
    monkeypatch.setattr(builder, 'load_runner', lambda root: r)
    monkeypatch.setattr(r, 'read_events', lambda path: events)
    monkeypatch.setattr(builder.subprocess, 'check_output',
        lambda *args, **kwargs: pytest.fail('Consumed retry must fail before external command'))
    result = builder.main(['--source-head', 'not-read', '--runtime', '/not-read',
        '--retry-of', builder.ORIGINAL_ATTEMPT_ID, '--episode-key', 'gpu3_native_c0_t00_r1',
        '--protocol', 'not-read', '--output', str(tmp_path / 'not-created.json')])
    assert result == 2
    assert 'retry_of already consumed' in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_nonretryable_outcome_cannot_be_recovered():
    row = draft_row()
    events = events_for(row)
    events[-1]['retryable_infrastructure'] = False
    with pytest.raises(r.GateError, match='only infrastructure abort is retryable'):
        r.check_retry(events, row)


def test_single_c0_row_and_dev_only_remove_native_probe_contracts():
    base = r.read_json(builder.WORKTREE / 'data/qd-ed-native-gpu7-queue-v2-plan.json')
    row = draft_row()
    plan = builder.plan_skeleton(base, row)
    assert plan['episodes'] == [row]
    assert plan['phase_authorization'] == {'dev': True, 'validation': False, 'formal': False}
    assert not plan['frozen']
    assert not (builder.DROP_FIELDS & plan.keys())
    assert 'diagnostic_only' in base


def test_identity_drift_is_rejected_without_repair():
    source = original()
    for field, value in [('iteration', 'N1'), ('profile', 'Q0'), ('task_id', 1), ('timeout_seconds', 1801)]:
        changed = copy.deepcopy(source)
        changed['episodes'][0][field] = value
        with pytest.raises(r.GateError, match='original C0 scientific identity changed'):
            draft_row(changed)


def test_explicit_second_parent_is_allowed_without_inference_or_identity_change():
    source = original()
    row = source['episodes'][0]
    events = events_for(row)
    parent = 'rdt-qd-ed-final-20260921T093925Z__gpu6_native_c0_t00_r1__03c5d2b4a1df'
    events.extend({'attempt_id': parent, 'event': event, 'identity': r.episode_identity(row),
        'retry_of': builder.ORIGINAL_ATTEMPT_ID, 'episode_key': 'gpu6_native_c0_t00_r1',
        **({'retryable_infrastructure': True} if event == 'aborted' else {})}
        for event in ('reserved', 'dispatched', 'aborted'))
    recovered = builder.recovery_row(source, r, events=events, retry_of=parent,
        episode_key='gpu3_native_c0_t00_r2')
    assert recovered['retry_of'] == parent
    assert r.episode_identity(recovered) == r.episode_identity(row)
    with pytest.raises(r.GateError, match='retry_of already consumed'):
        builder.recovery_row(source, r, events=events, retry_of=builder.ORIGINAL_ATTEMPT_ID,
            episode_key='gpu3_native_c0_t00_r1')
    with pytest.raises(r.GateError, match='explicit retry parent is absent'):
        builder.recovery_row(source, r, events=events, retry_of='not-in-ledger',
            episode_key='gpu3_native_c0_t00_r3')
