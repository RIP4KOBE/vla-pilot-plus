#!/usr/bin/env python3
"""Conditionally freeze N7, C0, Q0 and N6 on the historical fixed set."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
import subprocess
import threading
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
COHORT='N7_FORMAL_FIXED_20260925'
TASKS=tuple(range(10))
ARMS=('C0','Q0','N6','N7')
FIELDS=('env_seed','policy_seed','init_index','init_row_sha256','init_file_sha256','bddl_sha256')
PROTOCOL='experiments/iteration_007_direction_height/formal-protocol.md'
VALIDATION_PLAN=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260925/n7-validation-c1-recovery-v1/plan.frozen.v1.json')
VALIDATION_PLAN_SHA='9fd4ace8f49b3e676d3a00b4aa8b2ca03fc3d2a26bfaffeff0c28cc6ba85f77b'
VALIDATION_REPORT=VALIDATION_PLAN.with_name('full-validation-report-v1.json')
N6_PROFILE='configs/qd_ed_final/candidate_n6.json'
N6_SHA='fa76d2e8819de23796193175626308f6728d45bab3b16543470e9c1769fec40f'
NEW_FILES={PROTOCOL,N6_PROFILE,'scripts/qd_ed_n7_formal_plan.py',
           'scripts/qd_ed_n7_formal_supervise.py','scripts/qd_ed_n7_formal_report.py',
           'tests/test_qd_ed_n7_formal_plan.py'}
LIMITS={'original_cells':40,'dispatches':40,'gpu_hours':10.0,
        'episode_timeout_seconds':1800,'cleanup_seconds':40,'physical_gpu':3}
_SCOPE=None


def api(value):
    return SimpleNamespace(**value) if isinstance(value,dict) else value


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows_from_parent(parent,seeds):
    template=copy.deepcopy(parent['episodes'][0])
    template.pop('n7_validation_recovery_contract',None)
    rows=[]
    mapping={x['task_id']:x for x in seeds['blocks']['formal']}
    if set(mapping)!=set(TASKS):
        raise ValueError('formal seed block does not cover exact backend tasks')
    for task in TASKS:
        source=mapping[task]
        for arm in ARMS:
            row=copy.deepcopy(template)
            row.update({field:source[field] for field in FIELDS})
            row.update(split='formal',seed_block='formal',task_id=task,
                       iteration=COHORT,profile=arm,budget_bucket='formal',
                       episode_key=f'n7f_t{task:02d}_{arm.lower()}_20260925',
                       timeout_seconds=1800,retry_of=None)
            rows.append(row)
    return rows


def eligibility(report,r):
    r.require(sha(VALIDATION_PLAN)==VALIDATION_PLAN_SHA
              and report.get('schema')=='qd-ed-n7-validation-c1-continuation-report-v1'
              and report.get('decision')=='ELIGIBLE_FOR_SEPARATELY_FROZEN_FORMAL'
              and report.get('accepted_cells')==report.get('expected_cells')==60
              and report.get('terminal_attempts')==61
              and report.get('candidate_numeric_gate') is True
              and report.get('success_counts',{}).get('N7',0)>=10
              and report['success_counts']['N7']>=report['success_counts']['C0']
              and report['success_counts']['N7']>=report['success_counts']['Q0']
              and report.get('formal_authorized') is False
              and report.get('continuation_plan')==
                  {'path':str(VALIDATION_PLAN),'sha256':VALIDATION_PLAN_SHA},
              'N7 C1 full validation did not authorize formal eligibility')


def validate_contract(plan,manifest,runtime,seeds,root,runner):
    r=api(runner)
    parent=r.read_json(VALIDATION_PLAN)
    cohort=plan.get('n7_formal')
    r.require(isinstance(cohort,dict)
              and cohort.get('schema')=='qd-ed-n7-formal-fixed-v1'
              and cohort.get('cohort_id')==COHORT
              and cohort.get('limits')==LIMITS
              and cohort.get('protocol')=={'path':PROTOCOL,'sha256':r.digest(Path(root)/PROTOCOL)}
              and cohort.get('validation_plan')=={'path':str(VALIDATION_PLAN),'sha256':VALIDATION_PLAN_SHA}
              and cohort.get('validation_report',{}).get('path')==str(VALIDATION_REPORT)
              and sha(VALIDATION_REPORT)==cohort['validation_report']['sha256'],
              'N7 fixed formal identity/report differs')
    eligibility(r.read_json(VALIDATION_REPORT),r)
    r.require(plan.get('n7_validation') is None
              and plan.get('n7_validation_continuation') is None
              and plan.get('n7_cohort') is None
              and plan['episodes']==rows_from_parent(parent,seeds)
              and plan['phase_authorization']=={'dev':False,'validation':False,'formal':True}
              and set(plan['candidate_profiles'])=={'N6','N7'}
              and plan['candidate_profiles']['N7']==parent['candidate_profiles']['N7']
              and plan['candidate_profiles']['N6']==
                  {'path':str(Path(root)/N6_PROFILE),'sha256':N6_SHA}
              and plan['profiles_sha256']==parent['profiles_sha256']
              and plan['runtime_manifest_sha256']==parent['runtime_manifest_sha256']
              and plan['runtime_inventory_sha256']==parent['runtime_inventory_sha256']
              and plan['seed_plan_sha256']==parent['seed_plan_sha256']
              and r.runtime_gpu(runtime)==3,
              'N7 fixed formal rows, controls or runtime differ')
    prior_code={x['path']:x['sha256'] for x in parent['code_files']}
    now_code={x['path']:x['sha256'] for x in plan['code_files']}
    non_scientific_edits={'scripts/qd_ed_final_runner.py',
                          'tests/test_qd_ed_n7_validation_continuation.py'}
    r.require(all(now_code.get(k)==v for k,v in prior_code.items()
                  if k not in non_scientific_edits)
              and NEW_FILES<=set(now_code)
              and plan['candidate_profiles']['N6']['sha256']==sha(Path(root)/N6_PROFILE),
              'N7 fixed formal scientific source changed')
    r.require(manifest['profiles']['N6']['resolved_eds_config']['qd_descriptor']=='target_horizontal_radius_signed_height_v1'
              and manifest['profiles']['N7']['resolved_eds_config']['qd_descriptor']=='target_xy_quadrant_signed_height_v1',
              'N6/N7 formal descriptor identity differs')
    state=r.read_state(Path(root)/'research-state.yaml')
    r.require(state['budget']['max_episode_attempts']==240
              and state['budget']['max_gpu_hours']==48.0
              and state['budget']['reserved']==r.BUCKETS
              and r.authorized_gpu(state)==3
              and state['resource_isolation']['status']=='ACTIVE',
              'N7 formal GPU3/private budget authority differs')


@contextmanager
def supervised_scope(plan,root,episode_key):
    global _SCOPE
    if _SCOPE is not None:
        raise RuntimeError('nested N7 formal scope')
    _SCOPE=(str(Path(root).resolve()),plan['source_commit'],episode_key,
            os.getpid(),threading.get_ident())
    try:
        yield
    finally:
        _SCOPE=None


def require_scope(plan,root,runner,row=None):
    r=api(runner)
    r.require(_SCOPE is not None and _SCOPE[0]==str(Path(root).resolve())
              and _SCOPE[1]==plan['source_commit']
              and _SCOPE[3:]==(os.getpid(),threading.get_ident())
              and (row is None or row['episode_key']==_SCOPE[2]),
              'N7 formal requires its one-cell audited supervisor')


def protected_budget(state,events,resources,row,timeout,runner,*,plan):
    r=api(runner)
    r.require(row in rows_from_parent(r.read_json(VALIDATION_PLAN),
              r.read_json(plan['seed_plan_path']))
              and row['split']==row['budget_bucket']=='formal'
              and row['iteration']==COHORT and timeout==1800
              and state['budget']['reserved']==r.BUCKETS,
              'N7 formal cell/timeout/bucket differs')
    cohort=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    dispatched=[e for e in cohort if e['event']=='dispatched']
    settled=[e for e in cohort if e['event'] in r.TERMINAL]
    spent=sum(e.get('gpu_process_wall_seconds',0.) for e in settled)
    r.require(len(dispatched)<40 and spent+timeout+40<=10*3600,
              'N7 formal dispatch/GPU-hour cap exceeded')
    r.require(state['budget']['gpu_hours_consumed']+(timeout+40)/3600<=48,
              'N7 formal total GPU-hour cap exceeded')


def admission(plan,runtime,row,events,resources,root,runner):
    return {'n7_formal_cohort_id':COHORT,
            'n7_formal_validation_report_sha256':plan['n7_formal']['validation_report']['sha256'],
            'n7_formal_historical_fixed_set':True}


def build_plan(parent,report_path,head,runner):
    r=api(runner)
    r.require(report_path.resolve()==VALIDATION_REPORT and sha(VALIDATION_PLAN)==VALIDATION_PLAN_SHA,
              'N7 formal validation parent/report path differs')
    report=r.read_json(report_path)
    eligibility(report,r)
    r.require(sha(ROOT/N6_PROFILE)==N6_SHA,'N6 ablation profile changed')
    seeds=r.read_json(parent['seed_plan_path'])
    paths={x['path'] for x in parent['code_files']}|NEW_FILES|{'scripts/qd_ed_final_runner.py'}
    code_files=[]
    for relative in sorted(paths):
        actual=(ROOT/relative).read_bytes()
        committed=subprocess.check_output(['git','show',head+':'+relative],cwd=ROOT)
        r.require(actual==committed,'uncommitted N7 formal source: '+relative)
        code_files.append({'path':relative,'sha256':hashlib.sha256(actual).hexdigest()})
    plan=copy.deepcopy(parent)
    plan.pop('n7_validation_continuation')
    plan.update(source_commit=head,episodes=rows_from_parent(parent,seeds),code_files=code_files,
                phase_authorization={'dev':False,'validation':False,'formal':True},
                scientific_config_files=sorted(set(plan['scientific_config_files'])|{PROTOCOL,N6_PROFILE}))
    plan['candidate_profiles']['N6']={'path':str(ROOT/N6_PROFILE),'sha256':N6_SHA}
    plan['n7_formal']={'schema':'qd-ed-n7-formal-fixed-v1','cohort_id':COHORT,
        'protocol':{'path':PROTOCOL,'sha256':r.digest(ROOT/PROTOCOL)},
        'validation_plan':{'path':str(VALIDATION_PLAN),'sha256':VALIDATION_PLAN_SHA},
        'validation_report':{'path':str(report_path),'sha256':sha(report_path)},
        'limits':copy.deepcopy(LIMITS)}
    return plan


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validation-report',type=Path,required=True)
    parser.add_argument('--source-head',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    import qd_ed_final_runner as r
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    r.require(head==args.source_head and not args.output.exists(),
              'N7 formal source or output differs')
    with r.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True):
        plan=build_plan(r.read_json(VALIDATION_PLAN),args.validation_report,head,r.__dict__)
        output=r.owned(args.output,plan['artifact_root'])
        output.parent.mkdir(parents=True,exist_ok=True)
        r.durable_json(output,plan)
        r.validate_plan(output,root=ROOT)
    print(json.dumps({'status':'frozen_formal_no_release','plan':str(output),
                      'sha256':sha(output),'cells':40,'arms':ARMS}))


if __name__=='__main__':
    main()
