"""A Stage-stream-invalid C1 cell gets one typed recovery, never a legal retry."""
import copy
from pathlib import Path

import pytest

from scripts import qd_ed_final_runner as runner
from scripts import qd_ed_n7_validation_continuation as recovery


def test_exact_pending_matrix_and_one_typed_recovery():
    original=runner.read_json(recovery.ORIGINAL)
    rows=recovery.expected_rows(original)
    assert len(rows)==54
    assert [r['episode_key'] for r in rows]==[r['episode_key'] for r in original['episodes'][6:]]
    assert rows[0]['retry_of']==recovery.OLD_ATTEMPT
    assert rows[0]['budget_bucket']=='recovery'
    assert all(r.get('retry_of') is None and r['budget_bucket']=='validation' for r in rows[1:])
    assert all(r['profile']==original['episodes'][6+i]['profile'] for i,r in enumerate(rows))


def test_real_stream_failure_is_only_retry_exception():
    original=runner.read_json(recovery.ORIGINAL)
    # Reconstruct the immutable pre-recovery ledger view; this also works in
    # a separate source worktree whose private journal is intentionally empty.
    owner=Path(original['worktree'])
    events=[e for e in runner.read_events(owner/'data/attempt-ledger.jsonl')
            if e.get('retry_of')!=recovery.OLD_ATTEMPT]
    row=recovery.expected_rows(original)[0]
    runner.check_retry(events,row)
    ordinary=copy.deepcopy(row)
    ordinary.pop('n7_validation_recovery_contract')
    with pytest.raises(runner.GateError,match='legal completed outcome'):
        runner.check_retry(events,ordinary)
    consumed=events+[{'attempt_id':'synthetic-recovery-reservation',
                      'identity':runner.episode_identity(row),'event':'reserved',
                      'retry_of':recovery.OLD_ATTEMPT}]
    with pytest.raises(runner.GateError,match='already consumed'):
        runner.check_retry(consumed,row)


def test_scope_rejects_wrong_cell():
    plan={'source_commit':'frozen','n7_validation_continuation':{}}
    support=runner.n7_dispatch_support(plan)
    with support.supervised_scope(plan,runner.ROOT,'cell_a'):
        support.require_scope(plan,runner.ROOT,runner.__dict__,{'episode_key':'cell_a'})
        with pytest.raises(runner.GateError,match='one-cell supervisor'):
            support.require_scope(plan,runner.ROOT,runner.__dict__,{'episode_key':'cell_b'})
