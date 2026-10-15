#!/usr/bin/env python3
"""Second explicit UUID exception: preserve two named failures, allow no fourth."""
from __future__ import annotations
import copy
from pathlib import Path
import subprocess
from scripts import qd_ed_n23_v2_contract as c
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n23_uuid_repair as prior
from scripts.qd_ed_audit_backend import canonical_cuda_uuid

EXCEPTION=c.RUN_DIR/'uuid-native-repair-engineering-exception-v2.md'
EXCEPTION_SHA='b75b60a13a2e1d0ff90433d9161f32b1bec4c056807d9f46598c10bdfe4d4071'
FAILURE_REVIEW=c.RUN_DIR/'uuid-repair-native-type-failure-review-v1.json'
FAILURE_SHA='b6bed05adae2e1895a17bb331bfa91f6176eb37591bad02ff807958245bd72a7'
AUTHORITY=c.RUN_DIR/'uuid-native-repair-adoption-v2/authority.json'
FINAL_REVIEW=c.RUN_DIR/'final-source-runtime-review.uuid-native-repair.v2.json'
FAILED_ATTEMPT='rdt-qd-ed-final-20260921T093925Z__n23_backend_uuid_repair__41eab61a8079'
FAILED_SOURCE='675c2f4d07e787a7e160a2a26312c8ab2e4a19f6'
FAILED_SECONDS=6.601666689035483
FAILED_WORKER_SECONDS=5.115942551055923
LIMITS={**prior.LIMITS,'max_total_backend_attempts':3}
CAPS=prior.CAPS
EXTRA_SOURCE={'scripts/qd_ed_n23_uuid_native_repair.py','tests/test_qd_ed_n23_uuid_native_repair.py',
    'experiments/iteration_023_actuator_clipped_quality/uuid-native-repair-engineering-exception-v2.md'}
ALLOWED_DELTA=prior.ALLOWED_DELTA|EXTRA_SOURCE


def binding():
    w.require(c.sha(EXCEPTION)==EXCEPTION_SHA and c.sha(FAILURE_REVIEW)==FAILURE_SHA
        and c.sha(prior.FAILURE_REVIEW)==prior.FAILURE_SHA,'native UUID repair immutable scope changed')
    return {'schema':'n23-uuid-native-repair-binding-v2','exception':c.ref(EXCEPTION),
        'failed_review':c.ref(FAILURE_REVIEW),'prior_failure':c.ref(prior.FAILURE_REVIEW),
        'authority':c.ref(AUTHORITY),'retry_of':FAILED_ATTEMPT,'prior_attempt':prior.FAILED_ATTEMPT}


def source_delta(root):
    changed=set(subprocess.check_output(['git','diff','--name-only',prior.ORIGINAL_SOURCE,'HEAD'],cwd=root,text=True).splitlines())
    w.require(changed<=ALLOWED_DELTA,'native UUID repair changed scientific or unrelated source bytes')
    for filename,expected in ((EXCEPTION.name,EXCEPTION_SHA),(prior.EXCEPTION.name,prior.EXCEPTION_SHA)):
        w.require(c.sha(Path(root)/'experiments/iteration_023_actuator_clipped_quality'/filename)==expected,
            'native UUID repair tracked exception differs')
    return sorted(changed)


def final_review(source,runtime):
    w.require(c.sha(c.PROTOCOL)==c.PROTOCOL_SHA and c.sha(c.BACKEND_PROTOCOL)==c.BACKEND_PROTOCOL_SHA
        and c.sha(c.BUDGET_AMENDMENT)==c.AMENDMENT_SHA and c.sha(c.OBSERVABILITY)==c.OBSERVABILITY_SHA
        and c.sha(EXCEPTION)==EXCEPTION_SHA and c.sha(FAILURE_REVIEW)==FAILURE_SHA
        and c.sha(prior.EXCEPTION)==prior.EXCEPTION_SHA and c.sha(prior.FAILURE_REVIEW)==prior.FAILURE_SHA,
        'native UUID repair immutable protocol/amendment/exception/failure bytes differ')
    reference=c.ref(FINAL_REVIEW);record=w.read_ref(reference)
    w.require(record=={'schema':'n23-final-source-runtime-review-uuid-native-repair-v2','disposition':'accepted',
        'source':source,'runtime':runtime,'dev_protocol':c.ref(c.PROTOCOL),'backend_protocol':c.ref(c.BACKEND_PROTOCOL),
        'amendment':c.ref(c.BUDGET_AMENDMENT),'timeout_observability':c.ref(c.OBSERVABILITY),
        'exception':c.ref(EXCEPTION),'failed_review':c.ref(FAILURE_REVIEW),'prior_failure':c.ref(prior.FAILURE_REVIEW),
        'no_gpu_release':True},'native UUID repair final source/runtime review missing or differs')
    return reference


def authority(meta,source,runtime,state=None):
    w.require(meta==binding(),'native UUID repair exact authority binding differs')
    record=w.read_ref(meta['authority'])
    keys={'schema','exception','failed_review','prior_failure','final_source_review','source','runtime',
        'authority_interpretation','recorded_at','user_message','cumulative_caps','limits','validation_authorized','formal_authorized'}
    w.require(set(record)==keys and record['schema']=='n23-uuid-native-repair-authority-v2'
        and record['exception']==c.ref(EXCEPTION) and record['failed_review']==c.ref(FAILURE_REVIEW)
        and record['prior_failure']==c.ref(prior.FAILURE_REVIEW)
        and record['final_source_review']==final_review(source,runtime) and record['source']==source and record['runtime']==runtime
        and all(isinstance(record[k],str) and record[k].strip() for k in ('authority_interpretation','recorded_at'))
        and record['user_message']==c.AUTONOMOUS_REPLY and record['cumulative_caps']==CAPS and record['limits']==LIMITS
        and record['validation_authorized'] is False and record['formal_authorized'] is False,'native UUID repair finite authority differs')
    if state is not None:w.require(state.get('n23_uuid_native_repair_authority')==meta['authority'],
        'native UUID repair not adopted in private state')
    return record


def named_failures(events,r):
    first,original,_=prior.named_failure(events,r)
    review=w.read_ref(c.ref(FAILURE_REVIEW))
    w.require(c.sha(FAILURE_REVIEW)==FAILURE_SHA and review.get('schema')=='n23-uuid-repair-native-type-failure-review-v1'
        and review.get('attempt_id')==FAILED_ATTEMPT and review.get('status')=='INVALID_INFRASTRUCTURE_BEFORE_ARITHMETIC'
        and review.get('task_outcome') is False and review.get('dev_dispatched') is False
        and review.get('gpu_process_wall_seconds')==FAILED_SECONDS
        and review.get('additional_gpu_recovery_under_v1_authorized') is False
        and review.get('current_failed_worker_raw_uuid')=='not recorded; neither failed worker exposed its live value'
        and review.get('prior_failure')==c.ref(prior.FAILURE_REVIEW) and review.get('authority')==c.ref(prior.AUTHORITY),
        'native UUID repair second named failure review differs')
    plan=w.read_ref(review['plan']);report=w.read_ref(review['report']);terminal=w.read_ref(review['attempt_result'])
    meta=plan.get('uuid_repair');prior.authority(meta,plan['source'],plan['runtime'])
    w.require(plan=={**original,'source':review['source'],'uuid_repair':meta} and plan['source']['commit']==FAILED_SOURCE
        and report.get('plan')==review['plan'] and report.get('source')==plan['source']
        and report.get('attempt_id')==FAILED_ATTEMPT and report.get('schema')=='n23-backend-preflight-proof-v2'
        and report.get('accepted') is False and report.get('task_outcome') is False
        and report.get('errors')==[prior.ERROR] and report.get('batches')==report.get('synthetic')==[]
        and report.get('runtime')==plan['runtime'] and report.get('uuid_repair')==meta
        and report.get('retry_of')==prior.FAILED_ATTEMPT and report.get('worker_wall_seconds')==FAILED_WORKER_SECONDS,
        'native UUID repair requires second zero-arithmetic UUID failure with unchanged corpus')
    w.require(terminal.get('attempt_id')==FAILED_ATTEMPT and terminal.get('event')=='aborted'
        and terminal.get('outcome_valid') is False and terminal.get('task_outcome') is False
        and terminal.get('source_commit')==FAILED_SOURCE and terminal.get('plan_sha256')==review['plan']['sha256']
        and terminal.get('budget_bucket')=='recovery' and terminal.get('retry_of')==prior.FAILED_ATTEMPT
        and terminal.get('gpu_process_wall_seconds')==FAILED_SECONDS and terminal.get('n23_preflight_dispatched') is True
        and terminal.get('process')==report.get('process') and terminal.get('n23_uuid_repair')==meta
        and terminal.get('n23_final_review')==prior.final_review(plan['source'],plan['runtime']),
        'native UUID repair second terminal/cost/source differs')
    groups=r['event_groups'](events);group=groups.get(FAILED_ATTEMPT,[])
    w.require([e['event'] for e in group]==['reserved','dispatched','aborted'] and group[-1]==terminal
        and all(e.get('identity',{}).get('iteration')==c.PREFLIGHT and e.get('retry_of')==prior.FAILED_ATTEMPT
            and e.get('source_commit')==FAILED_SOURCE and e.get('plan_sha256')==review['plan']['sha256']
            and e.get('n23_uuid_repair')==meta and e.get('n23_backend_preflight') is True
            and e.get('budget_bucket')=='recovery' and e.get('physical_gpu')==7 for e in group),
        'native UUID repair second charged ledger group differs')
    first_end=next(i for i,e in enumerate(events) if e is groups[prior.FAILED_ATTEMPT][-1])
    second_start=next(i for i,e in enumerate(events) if e is group[0])
    w.require(first_end<second_start,'native UUID repair failed predecessors out of order')
    return review,original,terminal


def validate_plan(plan):
    authority(plan['uuid_repair'],plan['source'],plan['runtime']);source_delta(plan['worktree'])
    original=w.read_ref(w.read_ref(c.ref(prior.FAILURE_REVIEW))['plan'])
    w.require(plan=={**original,'source':plan['source'],'uuid_repair':plan['uuid_repair']},
        'native UUID repair changed original corpus/arithmetic/runtime outside source and lineage')
    return plan


def admission(plan,state,events,resources,reservations,*,root,r):
    from scripts import qd_ed_n23_v2_backend as backend
    from scripts import qd_ed_n23_v2_preflight_admit as admit
    c.require_state(state,r);authority(plan['uuid_repair'],plan['source'],plan['runtime'],state)
    named_failures(events,r);prior.no_dev(events)
    w.require({e['attempt_id'] for e in prior.backend_events(events)}=={prior.FAILED_ATTEMPT,FAILED_ATTEMPT},
        'native UUID repair already reserved or another backend opportunity exists')
    w.require(plan['source']==w.source_record(root,c.source_paths(r)) and plan['runtime']==c.ref(c.GPU7_RUNTIME)
        and plan['predecessor_review']==c.predecessor_review(),'native UUID repair source/runtime/predecessor differs')
    runtime=backend.validate_plan(plan);c.validate_runtime(runtime,root,r)
    w.require(Path(plan['artifact_root']).resolve()==Path(state['artifacts']).resolve()
        and Path(state.get('worktree',root)).resolve()==Path(root).resolve(),'native UUID repair private owning roots differ')
    w.require(r['check_budget'](state,events,admit.diagnostic_row(plan),resources,reservations,physical_gpu=7)==120,
        'native UUID repair existing recovery capacity unavailable')
    c.full_capacity(state,events,resources,r,preflight=True)
    return runtime


def verify_lineage(plan,reference,events,source,r):
    authority(plan['uuid_repair'],source,plan['runtime']);named_failures(events,r)
    groups=r['event_groups'](prior.backend_events(events))
    w.require(set(groups)=={prior.FAILED_ATTEMPT,FAILED_ATTEMPT,reference['attempt_id']}
        and reference['attempt_id'] not in {prior.FAILED_ATTEMPT,FAILED_ATTEMPT},
        'native UUID repair proof must retain exactly three backend attempts')
    repaired=groups[reference['attempt_id']]
    w.require([e['event'] for e in repaired]==['reserved','dispatched','valid']
        and all(e.get('retry_of')==FAILED_ATTEMPT and e.get('n23_uuid_repair')==plan['uuid_repair']
            and e.get('identity',{}).get('iteration')==c.PREFLIGHT and e.get('n23_backend_preflight') is True
            and e.get('budget_bucket')=='recovery' and e.get('physical_gpu')==7
            and e.get('source_commit')==source['commit'] and e.get('plan_sha256')==reference['plan']['sha256'] for e in repaired)
        and repaired[-1].get('outcome_valid') is True and repaired[-1].get('n23_final_review')==final_review(source,plan['runtime']),
        'native UUID repair proof terminal lineage/review differs')
    second_end=next(i for i,e in enumerate(events) if e is groups[FAILED_ATTEMPT][-1])
    repaired_start=next(i for i,e in enumerate(events) if e is repaired[0])
    w.require(second_end<repaired_start,'native UUID repair precedes second failure closure')
    boundary=next(i for i,e in enumerate(events) if e is repaired[-1]);prior.no_dev(events[:boundary+1])
    return repaired[-1]


def verify_identity(backend,runtime):
    expected=canonical_cuda_uuid(runtime['gpu_mapping']['uuid'])
    raw=backend.get('actual_uuid');kind=backend.get('actual_uuid_type');native_hex=backend.get('actual_uuid_bytes_hex')
    w.require(canonical_cuda_uuid(raw)==expected and backend.get('physical_uuid')==expected
        and kind in {'builtins.str','torch._C._CUuuid'}
        and ((kind=='builtins.str' and native_hex is None)
            or (kind=='torch._C._CUuuid' and native_hex==expected[4:].replace('-','')))
        and backend.get('cuda_visible_devices')=='7','native UUID repair serialized raw/type/canonical evidence differs')
    diagnostic=backend.get('identity_diagnostic')
    w.require(isinstance(diagnostic,dict) and type(diagnostic.get('visible_device_count')) is int
        and type(diagnostic.get('current_device')) is int and diagnostic=={'schema':'n23-public-cuda-identity-diagnostic-v1',
        'expected_physical_gpu':7,'expected_uuid':expected,'cuda_visible_devices':'7','visible_device_count':1,
        'current_device':0,'uuid_public_type':kind,'serialized_raw_uuid':raw,'canonical_uuid':expected,'status':'matched'},
        'native UUID repair matched public device diagnostic missing or differs')


def build_plan(root,r):
    original=w.read_ref(w.read_ref(c.ref(prior.FAILURE_REVIEW))['plan'])
    source=w.source_record(root,c.source_paths(r));plan=copy.deepcopy(original)
    plan.update(source=source,uuid_repair=binding());validate_plan(plan)
    return plan
