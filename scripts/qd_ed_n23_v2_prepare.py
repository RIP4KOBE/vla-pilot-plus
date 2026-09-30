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
from scripts import qd_ed_n23_v2_contract as contract
from scripts import qd_ed_n23_worker as worker


def build_plan(*, predecessor=None, review=None, proof=None,uuid_repair=None):
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
    plan['n23_cohort'] = {'schema': 'n23-clipped-quality-dev-v2', 'cohort_id': contract.COHORT,
        'limits': contract.LIMITS, 'n7_role': 'ablation_control_only_no_promotion',
        'predecessor_review': predecessor, 'budget_amendment': contract.ref(contract.BUDGET_AMENDMENT),
        'protocol': contract.ref(contract.PROTOCOL), 'source_plan': contract.ref(contract.SOURCE_PLAN),
        'final_review': review, 'timeout_observability':contract.ref(contract.OBSERVABILITY), 'worker_audit': worker.WORKER_CONTRACT, 'backend_proof': proof,
        'early_stop': 'numeric_futility_after_complete_task_quadruple'}
    if uuid_repair is not None:plan['n23_cohort']['uuid_repair']=uuid_repair
    return plan


def freeze(path, proof):
    runner.require(Path(path).resolve()==(contract.RUN_DIR/'plan.frozen.v2.gpu7.json').resolve(),'N23 v2 frozen Dev plan path differs')
    with runner.locked(ROOT / 'data/qd-ed-runner.lock', nonblocking=True):
        source = worker.source_record(ROOT, contract.source_paths(vars(runner)))
        predecessor = contract.predecessor_review()
        repair=worker.read_ref(proof['plan']).get('uuid_repair')
        review = contract.final_review(source, contract.ref(contract.GPU7_RUNTIME),repair=repair)
        contract.backend_proof(proof, source, ROOT, vars(runner))
        with runner.locked(ROOT / 'data/qd-ed-state.lock'):
            state = runner.read_state(ROOT / 'research-state.yaml')
            events = runner.read_events(ROOT / 'data/attempt-ledger.jsonl')
            contract.full_capacity(state, events, runner.read_events(ROOT / 'data/gpu-healthcheck-ledger.jsonl'), vars(runner))
            runner.require(not any(e.get('identity', {}).get('iteration') == contract.COHORT for e in events), 'N23 cohort already reserved')
        plan = build_plan(predecessor=predecessor, review=review, proof=proof,uuid_repair=repair); plan['frozen'] = True
        worker.atomic_json(path, plan)
        runner.validate_plan(path, root=ROOT)
        return plan



def backend_draft(corpus_index=None):
    from scripts import qd_ed_n23_v2_backend as backend
    parent=runner.read_json(contract.SOURCE_PLAN)
    if corpus_index is not None:
        return backend.build_plan(root=ROOT,protocol=contract.BACKEND_PROTOCOL,
            runtime=contract.ref(contract.GPU7_RUNTIME),corpus_index=contract.ref(corpus_index),
            source_paths=contract.source_paths(vars(runner)),artifact_root=parent['artifact_root'])
    # Scope-limited CPU review does not read the historical corpus index or tensor data.
    return {'schema':'n23-backend-preflight-plan-v2','worktree':str(ROOT.resolve()),'limits':backend.LIMITS,
        'artifact_root':str(Path(parent['artifact_root']).resolve()),'protocol':contract.ref(contract.BACKEND_PROTOCOL),
        'runtime':contract.ref(contract.GPU7_RUNTIME),'source':worker.source_record(ROOT,contract.source_paths(vars(runner))),
        'corpus':None,'predecessor_review':None,'timeout_observability':contract.ref(contract.OBSERVABILITY),
        'synthetic_cases':'fp32_bf16_native_seven_point_v1','task_outcome':False,'requires_separate_release':True}


def freeze_backend(plan,path):
    from scripts import qd_ed_n23_v2_preflight_admit as admit
    name='backend-preflight-plan.uuid-repair.frozen.v1.json' if plan.get('uuid_repair') is not None else 'backend-preflight-plan.frozen.v2.json'
    if plan.get('uuid_repair',{}).get('schema')=='n23-uuid-native-repair-binding-v2':name='backend-preflight-plan.uuid-native-repair.frozen.v2.json'
    runner.require(Path(path).resolve()==(contract.RUN_DIR/name).resolve(),
        'N23 v2 preflight plan path differs')
    with runner.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True):
        plan=dict(plan);plan['predecessor_review']=contract.predecessor_review()
        with runner.locked(ROOT/'data/qd-ed-state.lock'):
            admit.admission(plan,runner.read_state(ROOT/'research-state.yaml'),runner.read_events(ROOT/'data/attempt-ledger.jsonl'),
                runner.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl'),runner.read_events(ROOT/'data/gpu-hour-reservation-ledger.jsonl'),root=ROOT)
        worker.atomic_json(path,plan)
    return plan


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kind',choices=['dev','backend','uuid-repair','uuid-native-repair'],required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--freeze',action='store_true');p.add_argument('--corpus-index',type=Path);p.add_argument('--backend-proof',type=Path)
    args=p.parse_args()
    if args.kind in {'uuid-repair','uuid-native-repair'}:
        if args.kind=='uuid-native-repair':from scripts import qd_ed_n23_uuid_native_repair as repair
        else:from scripts import qd_ed_n23_uuid_repair as repair
        plan=repair.build_plan(ROOT,vars(runner))
        if args.freeze:plan=freeze_backend(plan,args.output)
        else:worker.atomic_json(args.output,plan)
    elif args.kind=='backend':
        plan=backend_draft(args.corpus_index)
        if args.freeze:runner.require(args.corpus_index is not None,'N23 v2 preflight corpus not reviewed');plan=freeze_backend(plan,args.output)
        else:worker.atomic_json(args.output,plan)
    elif args.freeze:
        runner.require(args.backend_proof is not None,'N23 v2 Dev requires actual one-time backend proof')
        plan=freeze(args.output,runner.read_json(args.backend_proof))
    else:plan=build_plan();worker.atomic_json(args.output,plan)
    print(json.dumps({'path':str(args.output.resolve()),'sha256':worker.sha(args.output),
        'frozen':bool(args.freeze),'gpu_dispatched':False,'source_commit':plan.get('source_commit',plan.get('source',{}).get('commit'))}))


if __name__=='__main__':main()
