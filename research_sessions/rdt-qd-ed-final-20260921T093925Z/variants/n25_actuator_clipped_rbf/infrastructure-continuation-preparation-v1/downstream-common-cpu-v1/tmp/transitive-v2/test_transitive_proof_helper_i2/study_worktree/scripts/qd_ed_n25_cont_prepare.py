#!/usr/bin/env python3
"""Pure successor draft; --freeze requires complete root-owned review/adoption."""
import argparse
import copy
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n25_cont_contract as c


def build_plan(prior,seal,source,*,meta=None):
    plan=copy.deepcopy(prior)
    plan.update(frozen=False,source_commit=source['commit'],code_files=source['files'],episodes=c.rows(seal),
        derived_from=seal['original_plan'],n25_cohort={'schema':'n25-continuation-audit-family-v1','worker_audit':c.WORKER_CONTRACT},
        n25_infrastructure_continuation=meta or {'schema':'n25-infrastructure-continuation-v1','executable':False,
            'protocol_sha256':c.PROTOCOL_SHA,'seal':None,'authority':None,'final_review':None})
    return plan


def freeze(path,root=ROOT):
    w.require(Path(path).resolve()==c.PLAN.resolve(),'exact successor plan path required')
    w.require(not Path(path).exists() and not Path(path).is_symlink(),'immutable successor plan already exists')
    with r.locked(Path(root)/'data/qd-ed-runner.lock',nonblocking=True):
        seal=c.history(cleanup=True);source=w.source_record(root,c.source_paths(vars(r)))
        c.final_review(source,seal['runtime'],root);c.authority(source,seal['runtime'],root)
        with r.locked(Path(root)/'data/qd-ed-state.lock'):
            events=r.read_events(Path(root)/'data/attempt-ledger.jsonl')
            w.require(not c.local_events(events),'any reservation consumes successor launch')
            c.full_capacity(r.read_state(Path(root)/'research-state.yaml'),events,r.read_events(Path(root)/'data/gpu-healthcheck-ledger.jsonl'),vars(r))
        plan=build_plan(w.read_ref(seal['original_plan']),seal,source,meta=c.metadata(source,seal['runtime'],root));plan['frozen']=True
        w.atomic_json(path,plan);r.validate_plan(path,root=root);return plan


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--freeze',action='store_true',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();freeze(a.output)
if __name__=='__main__':main()
