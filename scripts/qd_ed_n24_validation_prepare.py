#!/usr/bin/env python3
"""Illustrative CPU draft or exact root-authorized fresh N24 validation freeze."""
import argparse
import copy
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts import qd_ed_final_runner as r
from scripts import qd_ed_n24_validation_contract as c
from scripts import qd_ed_n24_validation_identity as identity
from scripts import qd_ed_n23_worker as w


def build_plan(parent,seeds,cohort,*,source,source_bridge,dev_review=None,source_review=None,authorization=None,selection=None):
    plan=copy.deepcopy(parent)
    plan.update(frozen=False,worktree=str(ROOT),source_commit=source['commit'],code_files=source['files'],
        candidate_profiles={'N24':{'path':str(ROOT/'configs/qd_ed_final/candidate_n24.json'),
            'sha256':parent['candidate_profiles']['N24']['sha256']}},episodes=identity.rows_for(seeds,cohort),
        phase_authorization={'dev':False,'validation':True,'formal':False},n24_cohort=c.WORKER_MARKER)
    plan['n24_validation']={'schema':'n24-protected-validation-v1','cohort_id':c.COHORT,'seed_cohort':cohort,
        'limits':c.LIMITS,'protocol':c.ref(c.PROTOCOL),'dev_review':dev_review,'source_review':source_review,
        'authority':authorization,'source_bridge':source_bridge,'metadata_selection':selection}
    return plan


def freeze(path):
    c.require(Path(path).resolve()==c.VALIDATION_PLAN.resolve(),'N24 validation frozen plan path differs')
    with r.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True),r.locked(ROOT/'data/qd-ed-state.lock'):
        parent=c.original_plan();source,source_bridge=c.source_record(ROOT,parent)
        dev_review=c.dev_promotion(ROOT,vars(r));review=c.review_source(source,source_bridge,parent)
        seed,hist,registry,ledger,snapshot=identity.metadata(ROOT,parent);cohort=identity.first_unused(seed,hist,registry,ledger)
        authorization=c.authority(source,source_bridge,parent)
        c.require(w.read_ref(authorization)['seed_cohort']==cohort,'N24 validation reviewed cohort is no longer first unused')
        plan=build_plan(parent,seed,cohort,source=source,source_bridge=source_bridge,dev_review=dev_review,source_review=review,
            authorization=authorization,selection=snapshot)
        events=r.read_events(ROOT/'data/attempt-ledger.jsonl');state=r.read_state(ROOT/'research-state.yaml')
        resources=r.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl')
        c.protected_budget(state,events,resources,plan['episodes'][0],1800,vars(r),plan=plan)
        r.check_budget(state,events,plan['episodes'][0],resources,r.read_events(ROOT/'data/gpu-hour-reservation-ledger.jsonl'),physical_gpu=7)
        plan['frozen']=True;w.atomic_json(path,plan);r.validate_plan(path,root=ROOT)
        return plan


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--freeze',action='store_true')
    p.add_argument('--preview-cohort',choices=['c1','c2','c3','c4']);args=p.parse_args()
    if args.freeze:
        c.require(args.preview_cohort is None,'N24 fresh release cannot use preview identity');plan=freeze(args.output)
    else:
        c.require(args.preview_cohort is not None,'N24 CPU preview requires an illustrative cohort')
        parent=c.original_plan();source,source_bridge=c.source_record(ROOT,parent)
        plan=build_plan(parent,c.read(parent['seed_plan_path']),args.preview_cohort,source=source,source_bridge=source_bridge,
            selection={'preview_only':True,'release_authorized':False});w.atomic_json(args.output,plan)
    print(json.dumps({'path':str(args.output.resolve()),'sha256':c.sha(args.output),'frozen':plan['frozen'],'dispatched':False}))


if __name__=='__main__':main()
