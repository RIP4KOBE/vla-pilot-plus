#!/usr/bin/env python3
"""Prepare non-executable preview or root-authorized fresh N23 validation plan."""
import argparse
import copy
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts import qd_ed_final_runner as runner
from scripts import qd_ed_n23_validation_contract as contract
from scripts import qd_ed_n23_validation_identity as identity
from scripts import qd_ed_n23_worker as worker


def build_plan(parent,seeds,cohort,*,source,source_bridge,dev_review=None,source_review=None,selection=None):
    plan=copy.deepcopy(parent);plan.pop('n23_cohort',None);plan.pop('n21_cohort',None)
    plan.update(frozen=False,worktree=str(ROOT),source_commit=source['commit'],code_files=source['files'],
        candidate_profiles={'N23':{'path':str(ROOT/'configs/qd_ed_final/candidate_n23.json'),
                                  'sha256':parent['candidate_profiles']['N23']['sha256']}},
        episodes=identity.rows_for(seeds,cohort),phase_authorization={'dev':False,'validation':True,'formal':False})
    plan['n23_validation']={'schema':'n23-protected-validation-v1','cohort_id':contract.COHORT,
        'seed_cohort':cohort,'limits':contract.LIMITS,'protocol':contract.ref(contract.PROTOCOL),
        'dev_review':dev_review,'source_review':source_review,'metadata_selection':selection,
        'source_bridge':source_bridge,'backend_proof':parent['n23_cohort']['backend_proof'],'worker_audit':worker.WORKER_CONTRACT}
    return plan


def save_new(path,value):
    path=Path(path);runner.require(not path.exists(),'validation output already exists')
    path.parent.mkdir(parents=True,exist_ok=True);runner.durable_json(path,value)


def freeze(path):
    contract.require(Path(path).resolve()==contract.VALIDATION_PLAN.resolve(),'validation frozen plan path differs')
    with runner.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True),runner.locked(ROOT/'data/qd-ed-state.lock'):
        parent=contract.read(contract.DEV_PLAN);source,source_bridge=contract.source_record(ROOT,parent)
        dev=contract.dev_promotion(ROOT,vars(runner));review=contract.review_source(source,source_bridge,parent)
        seeds,hist,registry,ledger,snapshot=identity.metadata(ROOT,parent)
        cohort=identity.first_unused(seeds,hist,registry,ledger)
        plan=build_plan(parent,seeds,cohort,source=source,source_bridge=source_bridge,dev_review=dev,source_review=review,selection=snapshot)
        state=runner.read_state(ROOT/'research-state.yaml');events=runner.read_events(ROOT/'data/attempt-ledger.jsonl')
        resources=runner.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl')
        contract.protected_budget(state,events,resources,plan['episodes'][0],1800,vars(runner),plan=plan)
        runner.check_budget(state,events,plan['episodes'][0],resources,
            runner.read_events(ROOT/'data/gpu-hour-reservation-ledger.jsonl'),physical_gpu=7)
        plan['frozen']=True;save_new(path,plan)
        runner.validate_plan(path,root=ROOT)
    return plan


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--freeze',action='store_true');p.add_argument('--preview-cohort',choices=['c1','c2','c3','c4'])
    args=p.parse_args()
    if args.freeze:
        runner.require(args.preview_cohort is None,'fresh release cannot use a snapshot-selected cohort')
        plan=freeze(args.output)
    else:
        runner.require(args.preview_cohort is not None,'CPU preview requires an explicitly illustrative cohort')
        parent=contract.read(contract.DEV_PLAN)
        source,source_bridge=contract.source_record(ROOT,parent)
        plan=build_plan(parent,contract.read(parent['seed_plan_path']),args.preview_cohort,
            source=source,source_bridge=source_bridge,selection={'preview_only':True,'release_authorized':False})
        save_new(args.output,plan)
    print(json.dumps({'plan':str(args.output.resolve()),'sha256':contract.sha(args.output),'frozen':plan['frozen'],
                      'separate_root_release_required':True,'dispatched':False}))


if __name__=='__main__':main()
