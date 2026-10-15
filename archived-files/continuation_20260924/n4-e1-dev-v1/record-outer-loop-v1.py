#!/usr/bin/env python3
"""Record bounded N4 outer-loop evidence without releasing a GPU experiment."""
import datetime
import os
from pathlib import Path
import sys
import tempfile

import yaml

W = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
B = Path(__file__).resolve().parent
sys.path.insert(0, str(W / 'scripts'))
import qd_ed_final_runner as r

review = B / 'outer-loop-v1.md'
exposure = B / 'dev-exposure-reconcile-v1/reconciliation.json'
assert review.is_file() and exposure.is_file()
assert r.read_json(exposure)['decision'] == 'ALL_TEN_FROZEN_DEV_TASK_SEED_INIT_IDENTITIES_EXPOSED'
with r.locked(W / 'data/qd-ed-runner.lock', nonblocking=True):
    with r.locked(W / 'data/qd-ed-state.lock'):
        path = W / 'research-state.yaml'
        state = r.read_state(path)
        snapshot = r.budget_snapshot(r.read_events(W / 'data/attempt-ledger.jsonl'),
                                     r.read_events(W / 'data/gpu-healthcheck-ledger.jsonl'))
        assert snapshot['running'] == 0 and snapshot['dispatched'] == 92
        assert snapshot['by_bucket'] == {'baseline': 20, 'development': 66,
                                         'validation': 0, 'formal': 0, 'recovery': 6}
        assert state['candidate']['status'] == 'N4E1_DEV_REJECT_NUMERIC'
        assert state['candidate']['online_dispatch_authorized'] is False
        assert state['study']['status'] == 'ACTIVE_OUTER_REVIEW_AFTER_N4E1_DEV'
        assert state['current_owned_workers'] == []
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        reference = {'path': str(review), 'sha256': r.digest(review)}
        state['study']['status'] = 'ACTIVE_TARGETED_EVIDENCE_PREPARATION'
        state['continuation']['owned_worker_phase'] = 'N4E1_COMPLETE_NO_OWNED_GPU_WORKER'
        state['continuation']['post_n4_outer_loop'] = reference
        state['continuation']['dev_exposure_reconciliation'] = {
            'path': str(exposure), 'sha256': r.digest(exposure)}
        state['next_action'] = ('Prepare a bounded same-state proposal-versus-selection diagnostic protocol '
                                'and verify complete state restoration; extra branch-simulation scope '
                                'requires separate approval before any GPU dispatch. No N5 or protected release yet.')
        state['updated_at'] = now
        descriptor, temporary = tempfile.mkstemp(prefix='.research-state.outer-', suffix='.yaml', dir=W)
        try:
            with os.fdopen(descriptor, 'w') as stream:
                yaml.safe_dump(state, stream, sort_keys=False, allow_unicode=True)
                stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, path)
            directory = os.open(W, os.O_RDONLY)
            try: os.fsync(directory)
            finally: os.close(directory)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)
        ledger = W / 'docs/03_evidence/qd_ed_final/iteration-ledger.md'
        with ledger.open('a') as stream:
            stream.write(f'\n\n### {now} — Post-N4 bounded outer loop\n\n')
            stream.write('N4-E1 rejected at1/4 versus C0/Q0 0/4. Existing metrics/videos were '
                         'reviewed; active terminal selection and large endpoint overflow do not '
                         'establish a task-beneficial alternative. Historical H1 overflow repair '
                         'failed validation, and N2/N3 geometric feedback failed Dev. '
                         'Decision COLLECT_TARGETED_EVIDENCE; no N5, new GPU work, validation, '
                         'or formal release. Ten Dev exposure identities reconciled. '
                         f'Outer review {review} SHA{r.digest(review)}; '
                         f'exposure reconciliation {exposure} SHA{r.digest(exposure)}. '
                         'Same-state branch simulation requires proven restoration and separately '
                         'approved capped scope; current study remains active.\n')
            stream.flush(); os.fsync(stream.fileno())
print({'study_status': state['study']['status'], 'review': reference,
       'gpu_workers': state['current_owned_workers']})
