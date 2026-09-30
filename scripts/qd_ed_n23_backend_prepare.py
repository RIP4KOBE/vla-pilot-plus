#!/usr/bin/env python3
"""Write an explicitly non-executable N23 backend preflight draft; no GPU/ledger use."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import qd_ed_n23_backend_preflight as preflight
from scripts import qd_ed_n23_worker as worker


def build_draft(source_plan_path, protocol, corpus_index, *, root=ROOT):
    """Uses source/runtime/input records only; does not inspect running outcomes."""
    source_plan_path = Path(source_plan_path).resolve()
    parent = json.loads(source_plan_path.read_text())
    from scripts import qd_ed_n23_dev_contract as contract
    from scripts import qd_ed_final_runner as runner
    worker.require(parent.get('n22_cohort', {}).get('cohort_id') == 'N22_HOLD_LIFT_DEV_20260930',
                   'preflight draft parent must be frozen N22 plan')
    return preflight.build_plan(root=root, protocol=protocol,
        runtime={'path': parent['runtime_manifest_path'], 'sha256': parent['runtime_manifest_sha256']},
        corpus_index={'path': str(Path(corpus_index).resolve()), 'sha256': worker.sha(corpus_index)},
        source_paths=contract.source_paths(vars(runner)), artifact_root=parent['artifact_root'],
        predecessor_review=None)


def freeze_plan(plan, output, *, root=ROOT):
    from scripts import qd_ed_final_runner as runner
    from scripts import qd_ed_n23_dev_contract as contract
    from scripts import qd_ed_n23_preflight_admit as admit
    with runner.locked(Path(root) / 'data/qd-ed-runner.lock', nonblocking=True):
        plan = dict(plan); plan['predecessor_review'] = contract.predecessor_review()
        with runner.locked(Path(root) / 'data/qd-ed-state.lock'):
            admit.admission(plan, runner.read_state(Path(root) / 'research-state.yaml'),
                runner.read_events(Path(root) / 'data/attempt-ledger.jsonl'),
                runner.read_events(Path(root) / 'data/gpu-healthcheck-ledger.jsonl'),
                runner.read_events(Path(root) / 'data/gpu-hour-reservation-ledger.jsonl'), root=root)
        worker.atomic_json(output, plan)
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-plan', type=Path, required=True)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--corpus-index', type=Path, required=True)
    parser.add_argument('--draft-output', type=Path, required=True)
    parser.add_argument('--freeze', action='store_true', help='Require root review, adopted budget and valid predecessor; never dispatch')
    args = parser.parse_args()
    plan=build_draft(args.source_plan,args.protocol,args.corpus_index)
    if args.freeze: plan=freeze_plan(plan,args.draft_output)
    else: worker.atomic_json(args.draft_output,plan)
    print(json.dumps({'draft':str(args.draft_output.resolve()),'sha256':worker.sha(args.draft_output),
                      'frozen':bool(args.freeze),'separate_admission_required':True,'gpu_dispatched':False,'source_commit':plan['source']['commit']}))


if __name__=='__main__':
    main()
