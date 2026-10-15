#!/usr/bin/env python3
"""One separately authorized arithmetic audit repair; no fifth opportunity."""
from __future__ import annotations
from collections import Counter
import copy
import math
from pathlib import Path
import subprocess
from scripts import qd_ed_n23_v2_contract as c
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n23_uuid_repair as first
from scripts import qd_ed_n23_uuid_native_repair as prior

EXCEPTION=c.RUN_DIR/'arithmetic-repair-engineering-exception-v3.md'
EXCEPTION_SHA='bf3f28caf3967c4d3cf4cc6674bdaafd2d54abbdd22f5e9bc676853a12424727'
FAILURE_REVIEW=c.RUN_DIR/'native-backend-arithmetic-failure-review-v1.json'
FAILURE_SHA='6d9381fe1c0b8631df00a7eebb8f89d3b04869991e7e79fe7e8742f3accf1ada'
AUTHORITY=c.RUN_DIR/'arithmetic-repair-adoption-v3/authority.json'
FINAL_REVIEW=c.RUN_DIR/'final-source-runtime-review.arithmetic-repair.v3.json'
FAILED_ATTEMPT='rdt-qd-ed-final-20260921T093925Z__n23_backend_uuid_native_repair__839018c768de'
FAILED_SOURCE='fbe5ac996467e00fcbc7a1d7e5f24659725f6b3d'
FAILED_PLAN_SHA='a12364193309ba5a3fd12130e1a978319e89b8155ffa2629fc4b550c06dfcaa0'
FAILED_SECONDS=16.66395034897141
PRIOR_ATTEMPTS=[first.FAILED_ATTEMPT,prior.FAILED_ATTEMPT]
LIMITS={**first.LIMITS,'max_total_backend_attempts':4}
CAPS=first.CAPS
CORRECTION={'scripts/audit_decision_evidence.py':'8c47a4d90fbec4e22329bdab7d53fddc2d01e88c742352e4f9e01a65d1dc8182',
    'scripts/qd_ed_n23_backend_preflight.py':'fbdd30ac1864ea9d282ce849f45faddda4738c6a5f092351e08bd0d2d13795be'}
EXTRA_SOURCE={'scripts/qd_ed_n23_arithmetic_repair.py','tests/test_qd_ed_n23_arithmetic_repair.py',
    'experiments/iteration_023_actuator_clipped_quality/arithmetic-repair-engineering-exception-v3.md'}
ALLOWED_DELTA=EXTRA_SOURCE|set(CORRECTION)|{'tests/test_qd_ed_n23_backend.py','scripts/qd_ed_n23_v2_contract.py',
    'scripts/qd_ed_n23_v2_backend.py','scripts/qd_ed_n23_v2_preflight_admit.py','scripts/qd_ed_n23_v2_prepare.py'}
verify_identity=prior.verify_identity


def binding():
    w.require(c.sha(EXCEPTION)==EXCEPTION_SHA and c.sha(FAILURE_REVIEW)==FAILURE_SHA
        and c.sha(prior.FAILURE_REVIEW)==prior.FAILURE_SHA,'arithmetic repair immutable scope changed')
    return {'schema':'n23-arithmetic-repair-binding-v3','exception':c.ref(EXCEPTION),'failed_review':c.ref(FAILURE_REVIEW),
        'prior_failure':c.ref(prior.FAILURE_REVIEW),'authority':c.ref(AUTHORITY),'retry_of':FAILED_ATTEMPT,
        'prior_attempts':PRIOR_ATTEMPTS}


def source_delta(root):
    changed=set(subprocess.check_output(['git','diff','--name-only',FAILED_SOURCE,'HEAD'],cwd=root,text=True).splitlines())
    w.require(changed<=ALLOWED_DELTA,'arithmetic repair changed scientific or unrelated source bytes')
    w.require(all(c.sha(Path(root)/p)==h for p,h in CORRECTION.items()),'arithmetic repair exact three normalization corrections differ')
    w.require(c.sha(Path(root)/'experiments/iteration_023_actuator_clipped_quality'/EXCEPTION.name)==EXCEPTION_SHA,
        'arithmetic repair tracked exception differs')
    return sorted(changed)


def final_review(source,runtime):
    w.require(c.sha(c.PROTOCOL)==c.PROTOCOL_SHA and c.sha(c.BACKEND_PROTOCOL)==c.BACKEND_PROTOCOL_SHA
        and c.sha(c.BUDGET_AMENDMENT)==c.AMENDMENT_SHA and c.sha(c.OBSERVABILITY)==c.OBSERVABILITY_SHA
        and all(c.sha(module.EXCEPTION)==module.EXCEPTION_SHA and c.sha(module.FAILURE_REVIEW)==module.FAILURE_SHA
            for module in (first,prior)) and c.sha(EXCEPTION)==EXCEPTION_SHA and c.sha(FAILURE_REVIEW)==FAILURE_SHA,
        'arithmetic repair immutable protocol/amendment/exception/failure bytes differ')
    reference=c.ref(FINAL_REVIEW);record=w.read_ref(reference)
    w.require(record=={'schema':'n23-final-source-runtime-review-arithmetic-repair-v3','disposition':'accepted',
        'source':source,'runtime':runtime,'dev_protocol':c.ref(c.PROTOCOL),'backend_protocol':c.ref(c.BACKEND_PROTOCOL),
        'amendment':c.ref(c.BUDGET_AMENDMENT),'timeout_observability':c.ref(c.OBSERVABILITY),
        'exception':c.ref(EXCEPTION),'failed_review':c.ref(FAILURE_REVIEW),'prior_failure':c.ref(prior.FAILURE_REVIEW),
        'audit_correction':CORRECTION,'no_gpu_release':True},'arithmetic repair final source/runtime review missing or differs')
    return reference


def authority(meta,source,runtime,state=None):
    w.require(meta==binding(),'arithmetic repair exact authority binding differs')
    record=w.read_ref(meta['authority'])
    keys={'schema','exception','failed_review','prior_failure','final_source_review','source','runtime',
        'authority_interpretation','recorded_at','user_message','cumulative_caps','limits','validation_authorized','formal_authorized'}
    w.require(set(record)==keys and record['schema']=='n23-arithmetic-repair-authority-v3'
        and record['exception']==c.ref(EXCEPTION) and record['failed_review']==c.ref(FAILURE_REVIEW)
        and record['prior_failure']==c.ref(prior.FAILURE_REVIEW)
        and record['final_source_review']==final_review(source,runtime) and record['source']==source and record['runtime']==runtime
        and all(isinstance(record[k],str) and record[k].strip() for k in ('authority_interpretation','recorded_at'))
        and record['user_message']==c.AUTONOMOUS_REPLY and record['cumulative_caps']==CAPS and record['limits']==LIMITS
        and record['validation_authorized'] is False and record['formal_authorized'] is False,'arithmetic repair finite authority differs')
    if state is not None:w.require(state.get('n23_arithmetic_repair_authority')==meta['authority'],
        'arithmetic repair not adopted in private state')
    return record


def numerical_failure(report,review,runtime):
    batches=report.get('batches',[]);synthetic=report.get('synthetic',[])
    w.require(len(batches)==176 and sum(v.get('candidates',0) for v in batches)==2816
        and all(v.get('candidates')==16 and v.get('dtype')=='torch.bfloat16' and v.get('production_helper_passed') is True for v in batches)
        and sum(v.get('accepted') is True for v in batches)==162 and report.get('errors')==[]
        and report.get('wrong_bounds_rejected') is True,'arithmetic repair original complete failed corpus differs')
    mismatch=Counter(v.get('check') for row in batches for v in row.get('mismatches',[]))
    expected={'clipped_quality_or_mask':7,'raw_score':8,'independent_arithmetic':7}
    w.require(mismatch==expected and review.get('mismatch_counts')==expected
        and review.get('rejected_batches')==[v for v in batches if v.get('accepted') is not True],
        'arithmetic repair exact failed batch evidence differs')
    for row in batches:
        kinds=[m['check'] for m in row['mismatches']]
        if row['accepted']:
            w.require(not kinds and row.get('independent_passed') is True and row.get('wrong_score_rejected') is True,
                'arithmetic repair previously accepted batch differs')
        elif kinds==['clipped_quality_or_mask']:
            w.require(row.get('independent_passed') is True and row.get('wrong_score_rejected') is True,
                'arithmetic repair clipped-only failure differs')
        else:
            w.require(Counter(kinds) in (Counter(raw_score=1,independent_arithmetic=1),Counter(raw_score=2,independent_arithmetic=1))
                and row.get('independent_passed') is False
                and all(m.get('error')=='AuditFailure:n23_seven_point_raw_provider' for m in row['mismatches'] if m['check']=='independent_arithmetic'),
                'arithmetic repair raw-only failure differs')
    w.require(len(synthetic)==2 and review.get('synthetic')==synthetic
        and [v.get('dtype') for v in synthetic]==['torch.float32','torch.bfloat16']
        and all(v.get('candidates')==4 and v.get('production_helper_passed') is True
            and v.get('independent_passed') is True and v.get('wrong_score_rejected') is True for v in synthetic)
        and synthetic[0].get('accepted') is False and synthetic[0].get('mismatches')==[{'check':'clipped_quality_or_mask'}]
        and synthetic[1].get('accepted') is True and synthetic[1].get('mismatches')==[],
        'arithmetic repair requires original FP32 rejection and BF16 synthetic pass')
    verify_identity(report.get('backend',{}),runtime)
    w.require(review.get('identity_diagnostic')==report['backend']['identity_diagnostic'],
        'arithmetic repair original native UUID identity differs')


def verify_arithmetic_success(report):
    batches=report.get('batches',[]);synthetic=report.get('synthetic',[])
    w.require(len(batches)==176 and len(synthetic)==2 and report.get('errors')==[]
        and all(v.get('candidates')==16 and v.get('dtype')=='torch.bfloat16' for v in batches)
        and [v.get('dtype') for v in synthetic]==['torch.float32','torch.bfloat16']
        and all(v.get('candidates')==4 for v in synthetic)
        and all(v.get('accepted') is True and v.get('mismatches')==[] and v.get('production_helper_passed') is True
            and v.get('independent_passed') is True and v.get('wrong_score_rejected') is True for v in batches+synthetic)
        and report.get('wrong_bounds_rejected') is True,
        'arithmetic repair actual full dtype/candidate/negative-control proof differs')


def named_failures(events,r):
    _,original,_=prior.named_failures(events,r)
    review=w.read_ref(c.ref(FAILURE_REVIEW))
    w.require(c.sha(FAILURE_REVIEW)==FAILURE_SHA and review.get('schema')=='n23-native-backend-arithmetic-failure-review-v1'
        and review.get('attempt_id')==FAILED_ATTEMPT and review.get('status')=='INVALID_BACKEND_ARITHMETIC'
        and review.get('task_outcome') is False and review.get('dev_dispatched') is False
        and review.get('gpu_process_wall_seconds')==FAILED_SECONDS and review.get('backend_opportunities_consumed')==3
        and review.get('additional_gpu_under_v2_authorized') is False and review.get('stage_provider_calls')==0
        and review.get('authority')==c.ref(prior.AUTHORITY) and review.get('batch_count')==176
        and review.get('candidate_count')==2816 and review.get('accepted_batches')==162,
        'arithmetic repair third named failure review differs')
    plan=w.read_ref(review['plan']);report=w.read_ref(review['report']);terminal=w.read_ref(review['attempt_result'])
    meta=plan.get('uuid_repair');prior.authority(meta,plan['source'],plan['runtime'])
    w.require(review['plan']['sha256']==FAILED_PLAN_SHA and plan=={**original,'source':review['source'],'uuid_repair':meta}
        and plan['source']['commit']==FAILED_SOURCE and report.get('plan')==review['plan'] and report.get('source')==plan['source']
        and report.get('attempt_id')==FAILED_ATTEMPT and report.get('schema')=='n23-backend-preflight-proof-v2'
        and report.get('accepted') is False and report.get('task_outcome') is False and report.get('runtime')==plan['runtime']
        and report.get('uuid_repair')==meta and report.get('retry_of')==prior.FAILED_ATTEMPT
        and type(report.get('worker_wall_seconds')) in (int,float) and math.isfinite(report['worker_wall_seconds'])
        and 0<=report['worker_wall_seconds']<=FAILED_SECONDS,'arithmetic repair original plan/source/report differs')
    numerical_failure(report,review,w.read_ref(plan['runtime']))
    w.require(terminal.get('attempt_id')==FAILED_ATTEMPT and terminal.get('event')=='aborted'
        and terminal.get('outcome_valid') is False and terminal.get('task_outcome') is False
        and terminal.get('source_commit')==FAILED_SOURCE and terminal.get('plan_sha256')==FAILED_PLAN_SHA
        and terminal.get('budget_bucket')=='recovery' and terminal.get('retry_of')==prior.FAILED_ATTEMPT
        and terminal.get('gpu_process_wall_seconds')==FAILED_SECONDS and terminal.get('n23_preflight_dispatched') is True
        and terminal.get('process')==report.get('process') and terminal.get('n23_uuid_repair')==meta
        and terminal.get('n23_final_review')==prior.final_review(plan['source'],plan['runtime']),
        'arithmetic repair original terminal/cost/source differs')
    groups=r['event_groups'](events);group=groups.get(FAILED_ATTEMPT,[])
    w.require([e['event'] for e in group]==['reserved','dispatched','aborted'] and group[-1]==terminal
        and all(e.get('identity',{}).get('iteration')==c.PREFLIGHT and e.get('retry_of')==prior.FAILED_ATTEMPT
            and e.get('source_commit')==FAILED_SOURCE and e.get('plan_sha256')==FAILED_PLAN_SHA
            and e.get('n23_uuid_repair')==meta and e.get('n23_backend_preflight') is True
            and e.get('budget_bucket')=='recovery' and e.get('physical_gpu')==7 for e in group),
        'arithmetic repair third charged ledger group differs')
    previous_end=next(i for i,e in enumerate(events) if e is groups[prior.FAILED_ATTEMPT][-1])
    third_start=next(i for i,e in enumerate(events) if e is group[0])
    w.require(previous_end<third_start,'arithmetic repair failed predecessors out of order')
    return review,original,terminal


def validate_plan(plan):
    authority(plan['uuid_repair'],plan['source'],plan['runtime']);source_delta(plan['worktree'])
    original=w.read_ref(w.read_ref(c.ref(first.FAILURE_REVIEW))['plan'])
    w.require(plan=={**original,'source':plan['source'],'uuid_repair':plan['uuid_repair']},
        'arithmetic repair changed original corpus/runtime/plan outside source and lineage')
    return plan


def admission(plan,state,events,resources,reservations,*,root,r):
    from scripts import qd_ed_n23_v2_backend as backend
    from scripts import qd_ed_n23_v2_preflight_admit as admit
    c.require_state(state,r);authority(plan['uuid_repair'],plan['source'],plan['runtime'],state)
    named_failures(events,r);first.no_dev(events)
    w.require({e['attempt_id'] for e in first.backend_events(events)}==set(PRIOR_ATTEMPTS+[FAILED_ATTEMPT]),
        'arithmetic repair already reserved or another backend opportunity exists')
    w.require(plan['source']==w.source_record(root,c.source_paths(r)) and plan['runtime']==c.ref(c.GPU7_RUNTIME)
        and plan['predecessor_review']==c.predecessor_review(),'arithmetic repair source/runtime/predecessor differs')
    runtime=backend.validate_plan(plan);c.validate_runtime(runtime,root,r)
    w.require(Path(plan['artifact_root']).resolve()==Path(state['artifacts']).resolve()
        and Path(state.get('worktree',root)).resolve()==Path(root).resolve(),'arithmetic repair private owning roots differ')
    w.require(r['check_budget'](state,events,admit.diagnostic_row(plan),resources,reservations,physical_gpu=7)==120,
        'arithmetic repair existing recovery capacity unavailable')
    c.full_capacity(state,events,resources,r,preflight=True)
    return runtime


def verify_lineage(plan,reference,events,source,r):
    authority(plan['uuid_repair'],source,plan['runtime']);named_failures(events,r)
    groups=r['event_groups'](first.backend_events(events));previous=set(PRIOR_ATTEMPTS+[FAILED_ATTEMPT])
    w.require(set(groups)==previous|{reference['attempt_id']} and reference['attempt_id'] not in previous,
        'arithmetic repair proof must retain exactly four backend attempts')
    repaired=groups[reference['attempt_id']]
    w.require([e['event'] for e in repaired]==['reserved','dispatched','valid']
        and all(e.get('retry_of')==FAILED_ATTEMPT and e.get('n23_uuid_repair')==plan['uuid_repair']
            and e.get('identity',{}).get('iteration')==c.PREFLIGHT and e.get('n23_backend_preflight') is True
            and e.get('budget_bucket')=='recovery' and e.get('physical_gpu')==7
            and e.get('source_commit')==source['commit'] and e.get('plan_sha256')==reference['plan']['sha256'] for e in repaired)
        and repaired[-1].get('outcome_valid') is True and repaired[-1].get('n23_final_review')==final_review(source,plan['runtime']),
        'arithmetic repair proof terminal lineage/review differs')
    old_end=next(i for i,e in enumerate(events) if e is groups[FAILED_ATTEMPT][-1])
    start=next(i for i,e in enumerate(events) if e is repaired[0])
    w.require(old_end<start,'arithmetic repair precedes original failure closure')
    boundary=next(i for i,e in enumerate(events) if e is repaired[-1]);first.no_dev(events[:boundary+1])
    return repaired[-1]


def build_plan(root,r):
    original=w.read_ref(w.read_ref(c.ref(first.FAILURE_REVIEW))['plan'])
    source=w.source_record(root,c.source_paths(r));plan=copy.deepcopy(original)
    plan.update(source=source,uuid_repair=binding());validate_plan(plan)
    return plan
