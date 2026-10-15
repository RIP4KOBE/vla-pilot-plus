#!/usr/bin/env python3
"""Exact C1 continuation after one independently audited Stage stream failure."""
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

ROOT = Path(__file__).resolve().parents[1]
COHORT = 'N7_VALIDATION_C1_20260925'
ORIGINAL = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260925/n7-validation-c1-v1/plan.frozen.v3.json')
ORIGINAL_SHA = 'f2f0242d11711163603e62fc66ad63967bbfeda1884bb948356f805c7b130f9c'
ELIGIBILITY = ORIGINAL.parent.parent / 'n7-validation-c1-recovery-v1/eligibility-audit-v1.json'
ELIGIBILITY_SHA = '0e7f4f0964749e8931b96616f5b1404609f2e14abab3d5bdebab68d734cd8e34'
OLD_ATTEMPT = 'rdt-qd-ed-final-20260921T093925Z__n7v_b1_t02_c0_20260925__e5df6c421513'
PROTOCOL = 'experiments/iteration_007_direction_height/validation-continuation-protocol.md'
NEW_FILES = {PROTOCOL, 'scripts/qd_ed_n7_validation_continuation.py',
             'scripts/qd_ed_n7_validation_continuation_supervise.py',
             'scripts/qd_ed_n7_validation_continuation_report.py',
             'tests/test_qd_ed_n7_validation_continuation.py'}
_SCOPE = None


def api(value):
    return SimpleNamespace(**value) if isinstance(value, dict) else value


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def old_accepted(events, original, runner):
    r = api(runner)
    accepted = []
    for row in original['episodes'][:6]:
        finals = [e for e in events if e.get('episode_key') == row['episode_key']
                  and e.get('event') in r.TERMINAL]
        r.require(len(finals) == 1 and finals[0]['event'] == 'valid'
                  and finals[0]['outcome_valid'] is True
                  and finals[0]['plan_sha256'] == ORIGINAL_SHA
                  and finals[0]['source_commit'] == original['source_commit'],
                  'old six C1 cells are not exactly accepted')
        checkpoint_path = Path(finals[0]['output_dir']) / 'eds_eval/n7-validation-cell-audit.json'
        r.require(checkpoint_path.is_file(), 'old C1 cell native audit missing')
        checkpoint = r.read_json(checkpoint_path)
        r.require(checkpoint.get('accepted') is True
                  and checkpoint.get('attempt_id') == finals[0]['attempt_id']
                  and checkpoint.get('episode_key') == row['episode_key']
                  and checkpoint.get('plan_sha256') == ORIGINAL_SHA
                  and checkpoint.get('source_commit') == original['source_commit'],
                  'old C1 cell native audit differs')
        accepted.append(finals[0])
    return accepted


def eligibility(events, original, runner):
    r = api(runner)
    r.require(sha(ORIGINAL) == ORIGINAL_SHA and sha(ELIGIBILITY) == ELIGIBILITY_SHA,
              'original plan or typed eligibility audit changed')
    audit = r.read_json(ELIGIBILITY)
    r.require(audit['attempt_id'] == OLD_ATTEMPT and all(audit['checks'].values()),
              'typed Stage-stream eligibility audit rejected')
    old = [e for e in events if e.get('attempt_id') == OLD_ATTEMPT]
    r.require([e['event'] for e in old] == ['reserved', 'dispatched', 'valid'],
              'named old attempt not fully preserved')
    terminal = old[-1]
    row = original['episodes'][6]
    r.require(terminal['identity'] == r.episode_identity(row)
              and terminal['episode_key'] == row['episode_key']
              and terminal['plan_sha256'] == ORIGINAL_SHA
              and terminal['outcome_valid'] is False
              and terminal['reason'] == 'Codex Stage call failure invalidates the frozen transport condition'
              and terminal['stage_failed_queries'] == 1
              and terminal['stage_successful_queries'] == 25
              and terminal['compute_outcome'] == 'completed',
              'named old attempt lacks exact Stage-stream invalidity')
    evidence = audit['evidence']
    r.require(sha(evidence['terminal_result_path']) == evidence['terminal_result_sha256']
              and sha(evidence['stage_events_path']) == evidence['stage_events_sha256'],
              'typed Stage-stream evidence bytes changed')
    stages = r.read_events(evidence['stage_events_path'])
    failures = [s for s in stages if s.get('query_ok') is not True]
    r.require(len(failures) == 1 and failures[0]['global_step'] == 24
              and failures[0]['error'] == 'codex_unexpected_event'
              and any(e.get('kind') == 'error' and e.get('error_category') == 'stream_error'
                      for e in failures[0]['transport']['lifecycle']['events']),
              'typed Stage stream-error witness differs')
    r.require(not any(e.get('retry_of') == OLD_ATTEMPT for e in events),
              'typed Stage-stream recovery already consumed')
    return terminal


def expected_rows(original):
    rows = copy.deepcopy(original['episodes'][6:])
    assert len(rows) == 54 and rows[0]['episode_key'] == 'n7v_b1_t02_c0_20260925'
    rows[0]['retry_of'] = OLD_ATTEMPT
    rows[0]['budget_bucket'] = 'recovery'
    rows[0]['n7_validation_recovery_contract'] = ELIGIBILITY_SHA
    return rows


def validate_contract(plan, manifest, runtime, seeds, root, runner):
    r = api(runner)
    original = r.read_json(ORIGINAL)
    cohort = plan.get('n7_validation_continuation')
    r.require(isinstance(cohort, dict)
              and cohort.get('schema') == 'qd-ed-n7-validation-continuation-v1'
              and cohort.get('cohort_id') == COHORT
              and cohort.get('original_plan') == {'path': str(ORIGINAL), 'sha256': ORIGINAL_SHA}
              and cohort.get('eligibility_audit') == {'path': str(ELIGIBILITY), 'sha256': ELIGIBILITY_SHA}
              and cohort.get('protocol') == {'path': PROTOCOL, 'sha256': r.digest(Path(root)/PROTOCOL)}
              and cohort.get('limits') == {'old_accepted': 6, 'pending': 54,
                  'primary_dispatches': 60, 'typed_recoveries': 1,
                  'cohort_gpu_hours': 14.0, 'physical_gpu': 3},
              'N7 C1 continuation authority differs')
    r.require(plan.get('n7_validation') is None and plan.get('n7_cohort') is None
              and plan['episodes'] == expected_rows(original)
              and plan['phase_authorization'] == {'dev': False, 'validation': True, 'formal': False}
              and plan['candidate_profiles'] == original['candidate_profiles']
              and plan['profiles_sha256'] == original['profiles_sha256']
              and plan['runtime_manifest_sha256'] == original['runtime_manifest_sha256']
              and plan['runtime_inventory_sha256'] == original['runtime_inventory_sha256']
              and plan['seed_plan_sha256'] == original['seed_plan_sha256']
              and r.runtime_gpu(runtime) == 3,
              'N7 C1 exact remaining identities or scientific bindings differ')
    old_code = {x['path']: x['sha256'] for x in original['code_files']}
    now_code = {x['path']: x['sha256'] for x in plan['code_files']}
    r.require(all(now_code.get(k) == v for k,v in old_code.items()
                  if k != 'scripts/qd_ed_final_runner.py')
              and NEW_FILES <= set(now_code),
              'N7 C1 scientific code changed after original release')
    state = r.read_state(Path(root)/'research-state.yaml')
    r.require(state['budget']['max_episode_attempts'] == 240
              and state['budget']['max_gpu_hours'] == 48.0
              and state['budget']['reserved'] == r.BUCKETS
              and r.authorized_gpu(state) == 3
              and state['resource_isolation']['status'] == 'ACTIVE',
              'N7 C1 private budget/GPU3 authority differs')


def check_retry(events, row, runner):
    r = api(runner)
    original = r.read_json(ORIGINAL)
    r.require(row == expected_rows(original)[0]
              and row['n7_validation_recovery_contract'] == ELIGIBILITY_SHA,
              'N7 C1 recovery row differs')
    eligibility(events, original, runner)
    groups = r.event_groups(events)
    same = [g for g in groups.values() if g[0]['identity'] == r.episode_identity(row)
            and any(e['event'] == 'dispatched' for e in g)]
    r.require(len(same) == 1 and same[0][0]['attempt_id'] == OLD_ATTEMPT,
              'N7 C1 recovery has another prior dispatch')


@contextmanager
def supervised_scope(plan, root, episode_key):
    global _SCOPE
    if _SCOPE is not None:
        raise RuntimeError('nested N7 C1 continuation scope')
    _SCOPE = (str(Path(root).resolve()), plan['source_commit'], episode_key,
              os.getpid(), threading.get_ident())
    try:
        yield
    finally:
        _SCOPE = None


def require_scope(plan, root, runner, row=None):
    r = api(runner)
    r.require(_SCOPE is not None and _SCOPE[0] == str(Path(root).resolve())
              and _SCOPE[1] == plan['source_commit']
              and _SCOPE[3:] == (os.getpid(), threading.get_ident())
              and (row is None or _SCOPE[2] == row['episode_key']),
              'N7 C1 continuation requires one-cell supervisor')


def protected_budget(state, events, resources, row, timeout, runner, *, plan):
    r = api(runner)
    r.require(row['iteration'] == COHORT and row['split'] == 'validation'
              and timeout == 1800 and state['budget']['reserved'] == r.BUCKETS,
              'N7 C1 continuation row or budget differs')
    original = r.read_json(ORIGINAL)
    r.require(row in expected_rows(original), 'N7 C1 continuation row not frozen')
    cohort = [e for e in events if e.get('identity',{}).get('iteration') == COHORT]
    primary = [e for e in cohort if e['event'] == 'dispatched' and e['budget_bucket'] == 'validation']
    recovery = [e for e in cohort if e['event'] == 'dispatched' and e['budget_bucket'] == 'recovery']
    r.require(len(primary) < 60 if row['budget_bucket'] == 'validation' else len(recovery) < 1,
              'N7 C1 primary/recovery dispatch cap exceeded')
    spent = sum(e.get('gpu_process_wall_seconds',0.) for e in cohort if e['event'] in r.TERMINAL)
    r.require(spent + timeout + 40 <= 14*3600,
              'N7 C1 cumulative GPU-hour cap exceeded')
    r.require(state['budget']['gpu_hours_consumed'] + (timeout+40)/3600
              + state['budget']['gpu_hour_reservations']['formal'] <= 48,
              'N7 C1 continuation cannot borrow formal reserve')


def admission(plan, runtime, row, events, resources, root, runner):
    return {'n7_validation_cohort_id': COHORT,
            'n7_validation_continuation': True,
            'n7_validation_original_plan_sha256': ORIGINAL_SHA,
            'n7_validation_recovery_of': OLD_ATTEMPT if row.get('retry_of') else None}


def build_plan(original, head, runner):
    r = api(runner)
    r.require(sha(ORIGINAL) == ORIGINAL_SHA and sha(ELIGIBILITY) == ELIGIBILITY_SHA,
              'N7 C1 original plan or eligibility audit changed')
    events = r.read_events(ROOT/'data/attempt-ledger.jsonl')
    old_accepted(events, original, runner)
    eligibility(events, original, runner)
    rows = expected_rows(original)
    paths = {x['path'] for x in original['code_files']} | NEW_FILES | {'scripts/qd_ed_final_runner.py'}
    files=[]
    for relative in sorted(paths):
        actual=(ROOT/relative).read_bytes()
        committed=subprocess.check_output(['git','show',head+':'+relative],cwd=ROOT)
        r.require(actual == committed, 'uncommitted N7 C1 continuation source: '+relative)
        files.append({'path':relative,'sha256':hashlib.sha256(actual).hexdigest()})
    plan=copy.deepcopy(original)
    plan.pop('n7_validation')
    plan.update(source_commit=head, episodes=rows, code_files=files,
                scientific_config_files=sorted(set(plan['scientific_config_files'])|{PROTOCOL}))
    plan['n7_validation_continuation']={
        'schema':'qd-ed-n7-validation-continuation-v1','cohort_id':COHORT,
        'original_plan':{'path':str(ORIGINAL),'sha256':ORIGINAL_SHA},
        'eligibility_audit':{'path':str(ELIGIBILITY),'sha256':ELIGIBILITY_SHA},
        'protocol':{'path':PROTOCOL,'sha256':r.digest(ROOT/PROTOCOL)},
        'limits':{'old_accepted':6,'pending':54,'primary_dispatches':60,
                  'typed_recoveries':1,'cohort_gpu_hours':14.0,'physical_gpu':3}}
    return plan


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-head',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    import qd_ed_final_runner as r
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    r.require(head==args.source_head and not args.output.exists(),
              'N7 C1 continuation source or output differs')
    with r.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True):
        plan=build_plan(r.read_json(ORIGINAL),head,r.__dict__)
        output=r.owned(args.output,plan['artifact_root'])
        output.parent.mkdir(parents=True,exist_ok=True)
        r.durable_json(output,plan)
        r.validate_plan(output,root=ROOT)
    print(json.dumps({'status':'frozen_no_dispatch','plan':str(output),
                      'sha256':sha(output),'pending_cells':54}))


if __name__=='__main__':
    main()
