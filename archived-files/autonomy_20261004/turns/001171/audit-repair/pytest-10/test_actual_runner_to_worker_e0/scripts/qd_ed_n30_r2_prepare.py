#!/usr/bin/env python3
"""Prepare the ten-row N30 repair; only explicit root artifacts permit freeze."""
import argparse,copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts import qd_ed_final_runner as r
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n30_r2_contract as c


def build_plan(*,source=None,root=ROOT,enabled=False):
    h=c.history();source=source or w.source_record(root,c.source_paths(vars(r)));plan=copy.deepcopy(h['plan'])
    plan.pop('n30_cohort');plan.update(frozen=bool(enabled),worktree=str(Path(root).resolve()),source_commit=source['commit'],code_files=source['files'],
        episodes=c.expected_rows(h),derived_from=h['review']['plan'],artifact_root=str(c.ARTIFACT_DIR.resolve()),
        candidate_profiles={'N30':c.ref(Path(root)/'configs/qd_ed_final/candidate_n30.json')})
    if enabled:plan['n30_r2_cohort']=c.metadata(source,root,h)
    else:plan['n30_r2_cohort']={'schema':'n30-r2-cohort-v1','cohort_id':c.COHORT,'limits':c.LIMITS,
        'worker_audit':c.WORKER_CONTRACT,'authority':None,'final_review':None,'source_bridge':None,'executable':False}
    return plan


def freeze(path,*,root=ROOT):
    w.require(Path(path).resolve()==c.PLAN.resolve() and not Path(path).exists(),'r2 one immutable plan/path')
    with r.locked(Path(root)/'data/qd-ed-runner.lock',nonblocking=True):
        with r.locked(Path(root)/'data/qd-ed-state.lock'):
            events=r.read_events(Path(root)/'data/attempt-ledger.jsonl')
            w.require(not any(e.get('identity',{}).get('iteration')==c.COHORT for e in events),'r2 no prior reservation')
            c.full_capacity(r.read_state(Path(root)/'research-state.yaml'),events,r.read_events(Path(root)/'data/gpu-healthcheck-ledger.jsonl'),vars(r))
        plan=build_plan(root=root,enabled=True);w.atomic_json(path,plan);r.validate_plan(path,root=root);return plan


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--freeze',action='store_true');args=p.parse_args()
    if args.freeze:plan=freeze(args.output)
    else:plan=build_plan();w.atomic_json(args.output,plan)
    print(json.dumps({'path':str(args.output.resolve()),'sha256':w.sha(args.output),'frozen':plan['frozen'],'gpu_dispatched':False}))
if __name__=='__main__':main()
