#!/usr/bin/env python3
"""CPU-reviewable N27 draft; exact root authority is required for immutable freeze."""
import argparse
import copy
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts import qd_ed_final_runner as r
from scripts import qd_ed_n27_contract as c
from scripts import qd_ed_n23_worker as w


def build_plan(*,source=None,root=ROOT,review=None,authority=None,predecessor_ref=None):
    source=source or w.source_record(root,c.source_paths(vars(r)))
    plan=copy.deepcopy(c.original_plan())
    for key in list(plan):
        if key.startswith(('n7_','n9_','n11_','n17_','n18_','n19_','n20_','n21_','n22_','n23_','n24_','n25_','n26_')):plan.pop(key)
    runtime=c.runtime_ref()
    plan.update(frozen=False,worktree=str(Path(root).resolve()),source_commit=source['commit'],code_files=source['files'],
        candidate_profiles={a:c.ref(Path(root)/f'configs/qd_ed_final/candidate_{a.lower()}.json') for a in ('N26','N27')},
        episodes=c.expected_rows(),phase_authorization={'dev':True,'validation':False,'formal':False},
        derived_from=c.ref(c.SOURCE_PLAN),runtime_manifest_path=runtime['path'],runtime_manifest_sha256=runtime['sha256'])
    plan['scientific_config_files']=sorted(set(plan['scientific_config_files'])|{'configs/qd_ed_final/candidate_n26.json','configs/qd_ed_final/candidate_n27.json'})
    plan['n27_cohort']={'schema':'n27-feasible-ray-screen-v1','cohort_id':c.COHORT,'limits':c.LIMITS,
        'protocol':c.ref(c.PROTOCOL),'source_plan':c.ref(c.SOURCE_PLAN),'timeout_observability':c.ref(c.OBSERVABILITY),
        'final_review':review,'authority':authority,'predecessor':predecessor_ref,
        'budget_reuse':None if review is None else c.ref(c.BUDGET_REUSE),'worker_audit':c.WORKER_CONTRACT,
        'n26_role':'control_only_no_promotion','early_stop':'none_full_sixteen_required'}
    return plan


def freeze(path,*,root=ROOT):
    w.require(Path(path).resolve()==(c.RUN_DIR/'plan.frozen.v1.gpu7.json').resolve(),'N27 frozen plan path differs')
    with r.locked(Path(root)/'data/qd-ed-runner.lock',nonblocking=True):
        source=w.source_record(root,c.source_paths(vars(r)))
        review=c.final_review(source,c.runtime_ref(),root)
        authority=c.authority(source,c.runtime_ref(),root)
        with r.locked(Path(root)/'data/qd-ed-state.lock'):
            events=r.read_events(Path(root)/'data/attempt-ledger.jsonl')
            c.full_capacity(r.read_state(Path(root)/'research-state.yaml'),events,r.read_events(Path(root)/'data/gpu-healthcheck-ledger.jsonl'),vars(r))
            w.require(not any(e.get('identity',{}).get('iteration') in {c.COHORT,c.PREFLIGHT} for e in events),'N27 already reserved')
        plan=build_plan(source=source,root=root,review=review,authority=authority,predecessor_ref=c.predecessor());plan['frozen']=True
        w.atomic_json(path,plan)
        r.validate_plan(path,root=root)
        return plan


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--freeze',action='store_true')
    args=p.parse_args()
    if args.freeze:plan=freeze(args.output)
    else:plan=build_plan();w.atomic_json(args.output,plan)
    print(json.dumps({'path':str(args.output.resolve()),'sha256':w.sha(args.output),'frozen':plan['frozen'],'gpu_dispatched':False}))


if __name__=='__main__':main()
