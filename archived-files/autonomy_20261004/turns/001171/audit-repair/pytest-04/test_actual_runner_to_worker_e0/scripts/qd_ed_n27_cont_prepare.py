#!/usr/bin/env python3
"""Non-executable pure draft; root seal/review/adoption precede one immutable freeze."""
import argparse
import copy
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n27_cont_contract as c

def build_plan(seal,source,*,meta=None):
    plan=copy.deepcopy(seal['original_plan_content'])
    plan.update(frozen=False,source_commit=source['commit'],code_files=source['files'],episodes=c.rows(seal),
        derived_from=seal['original_plan'],n27_cohort={'schema':'n27-hydra-audit-family-v1','worker_audit':c.WORKER_CONTRACT},
        n27_hydra_continuation=meta or {'schema':'n27-hydra-continuation-v1','executable':False,'authority':None,'seal':None,'final_review':None})
    return plan

def freeze(path,root=ROOT):
    w.require(Path(path).resolve()==c.PLAN.resolve() and not Path(path).exists() and not Path(path).is_symlink(),'one immutable exact plan freeze')
    with r.locked(Path(root)/'data/qd-ed-runner.lock',nonblocking=True):
        seal=c.history();source=w.source_record(root,c.source_paths(vars(r)))
        c.final_review(source,seal['runtime'],root);c.authority(source,seal['runtime'],root)
        with r.locked(Path(root)/'data/qd-ed-state.lock'):
            events=r.read_events(Path(root)/'data/attempt-ledger.jsonl');w.require(not c.local_events(events),'any reservation consumes continuation')
            c.full_capacity(r.read_state(Path(root)/'research-state.yaml'),events,r.read_events(Path(root)/'data/gpu-healthcheck-ledger.jsonl'),vars(r))
        plan=build_plan(seal,source,meta=c.metadata(source,seal['runtime'],root));plan['frozen']=True
        w.atomic_json(path,plan);r.validate_plan(path,root=root);return plan

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--freeze',action='store_true',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();freeze(args.output)
if __name__=='__main__':main()
