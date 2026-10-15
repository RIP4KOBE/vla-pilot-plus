#!/usr/bin/env python3
"""Build closed N23 drafts; freeze only after reviewed, ledger-bound backend proof."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from scripts import qd_ed_final_runner as runner
from scripts import qd_ed_n23_dev_contract as contract
from scripts import qd_ed_n23_worker as worker


def build_plan(*, predecessor=None, review=None, proof=None):
    parent = runner.read_json(contract.SOURCE_PLAN)
    runner.require(parent.get('n22_cohort', {}).get('cohort_id') == 'N22_HOLD_LIFT_DEV_20260930', 'N23 predecessor identity differs')
    source = worker.source_record(ROOT, contract.source_paths(vars(runner)))
    plan = copy.deepcopy(parent)
    for key in list(plan):
        if key.startswith(('n7_', 'n9_', 'n11_', 'n17_', 'n18_', 'n19_', 'n20_', 'n21_', 'n22_', 'n23_')):
            plan.pop(key)
    plan.update(frozen=False, worktree=str(ROOT), source_commit=source['commit'], code_files=source['files'],
        candidate_profiles={arm: contract.ref(ROOT / f'configs/qd_ed_final/candidate_{arm.lower()}.json') for arm in ('N7','N23')},
        episodes=contract.expected_rows(), phase_authorization={'dev': True, 'validation': False, 'formal': False},
        derived_from=contract.ref(contract.SOURCE_PLAN), runtime_manifest_path=str(contract.GPU7_RUNTIME),
        runtime_manifest_sha256=contract.sha(contract.GPU7_RUNTIME))
    plan['scientific_config_files'] = sorted(set(plan['scientific_config_files']) |
        {'configs/qd_ed_final/candidate_n7.json', 'configs/qd_ed_final/candidate_n23.json'})
    plan['n23_cohort'] = {'schema': 'n23-clipped-quality-dev-v1', 'cohort_id': contract.COHORT,
        'limits': contract.LIMITS, 'n7_role': 'ablation_control_only_no_promotion',
        'predecessor_review': predecessor, 'budget_amendment': contract.ref(contract.BUDGET_AMENDMENT),
        'protocol': contract.ref(contract.PROTOCOL), 'source_plan': contract.ref(contract.SOURCE_PLAN),
        'final_review': review, 'worker_audit': worker.WORKER_CONTRACT, 'backend_proof': proof,
        'early_stop': 'numeric_futility_after_complete_task_quadruple'}
    return plan


def freeze(path, proof):
    with runner.locked(ROOT / 'data/qd-ed-runner.lock', nonblocking=True):
        source = worker.source_record(ROOT, contract.source_paths(vars(runner)))
        predecessor = contract.predecessor_review()
        review = contract.final_review(source, contract.ref(contract.GPU7_RUNTIME))
        contract.backend_proof(proof, source, ROOT, vars(runner))
        with runner.locked(ROOT / 'data/qd-ed-state.lock'):
            state = runner.read_state(ROOT / 'research-state.yaml')
            events = runner.read_events(ROOT / 'data/attempt-ledger.jsonl')
            contract.full_capacity(state, events, runner.read_events(ROOT / 'data/gpu-healthcheck-ledger.jsonl'), vars(runner))
            runner.require(not any(e.get('identity', {}).get('iteration') == contract.COHORT for e in events), 'N23 cohort already reserved')
        plan = build_plan(predecessor=predecessor, review=review, proof=proof); plan['frozen'] = True
        worker.atomic_json(path, plan)
        runner.validate_plan(path, root=ROOT)
        return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--freeze', action='store_true')
    parser.add_argument('--backend-proof', type=Path)
    args = parser.parse_args()
    if args.freeze:
        runner.require(args.backend_proof is not None, 'N23 freeze requires actual backend proof reference')
        plan = freeze(args.output, runner.read_json(args.backend_proof))
    else:
        plan = build_plan(); worker.atomic_json(args.output, plan)
    print(json.dumps({'path': str(args.output.resolve()), 'sha256': worker.sha(args.output),
                     'frozen': plan['frozen'], 'gpu_dispatched': False}))


if __name__ == '__main__': main()
