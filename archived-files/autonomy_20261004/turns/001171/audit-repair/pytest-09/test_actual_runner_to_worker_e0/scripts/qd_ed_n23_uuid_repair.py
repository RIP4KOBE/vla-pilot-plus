#!/usr/bin/env python3
"""Single prospective named UUID engineering repair; no general retry authority."""
from __future__ import annotations
import copy
from pathlib import Path
import subprocess
from scripts import qd_ed_n23_v2_contract as c
from scripts import qd_ed_n23_worker as w
from scripts.qd_ed_audit_backend import canonical_cuda_uuid

EXCEPTION=c.RUN_DIR/'uuid-repair-engineering-exception-v1.md'
EXCEPTION_SHA='d5c80006512203343d89dc24ab4de53356c045bc0f755800bf0e8337524d5f20'
FAILURE_REVIEW=c.RUN_DIR/'backend-failure-review-v1.json'
FAILURE_SHA='95353cd515ca1e759e781d63108ecf03fcdea62372c7d1578159fe79a225c661'
AUTHORITY=c.RUN_DIR/'uuid-repair-adoption-v1/authority.json'
FINAL_REVIEW=c.RUN_DIR/'final-source-runtime-review.uuid-repair.v1.json'
FAILED_ATTEMPT='rdt-qd-ed-final-20260921T093925Z__n23_backend_preflight_v2__7ca117f9b7fb'
ORIGINAL_SOURCE='77302aab40d6b059e85c8d1d8011ea36cb3d3856'
ORIGINAL_PLAN_SHA='44147944afdc773938d2a97ce564dc2fc9e184ac2cac2957df006d70489213d1'
ERROR='RuntimeError:audit physical CUDA UUID differs or unavailable'
ORIGINAL_SECONDS=6.538148973020725
LIMITS={'additional_backend_attempts':1,'timeout_seconds':120,'cleanup_seconds':40,'physical_gpu':7,'budget_bucket':'recovery'}
CAPS={'attempts':478,'gpu_hours':100,'buckets':{'baseline':51,'development':187,'validation':180,'formal':40,'recovery':20}}
EXTRA_SOURCE={'scripts/qd_ed_n23_uuid_repair.py','tests/test_qd_ed_n23_uuid_repair.py',
    'experiments/iteration_023_actuator_clipped_quality/uuid-repair-engineering-exception-v1.md'}
ALLOWED_DELTA=EXTRA_SOURCE|{'scripts/qd_ed_audit_backend.py','scripts/qd_ed_n23_worker.py','tests/test_qd_ed_n23_backend.py',
    'scripts/qd_ed_n23_v2_contract.py','scripts/qd_ed_n23_v2_backend.py','scripts/qd_ed_n23_v2_preflight_admit.py',
    'scripts/qd_ed_n23_v2_prepare.py'}


def binding():
    w.require(c.sha(EXCEPTION)==EXCEPTION_SHA and c.sha(FAILURE_REVIEW)==FAILURE_SHA,'UUID repair immutable scope changed')
    return {'schema':'n23-uuid-repair-binding-v1','exception':c.ref(EXCEPTION),'failed_review':c.ref(FAILURE_REVIEW),
        'authority':c.ref(AUTHORITY),'retry_of':FAILED_ATTEMPT}


def source_delta(root):
    changed=set(subprocess.check_output(['git','diff','--name-only',ORIGINAL_SOURCE,'HEAD'],cwd=root,text=True).splitlines())
    w.require(changed<=ALLOWED_DELTA,'UUID repair changed scientific or unrelated source bytes')
    tracked=Path(root)/'experiments/iteration_023_actuator_clipped_quality/uuid-repair-engineering-exception-v1.md'
    w.require(c.sha(tracked)==EXCEPTION_SHA,'UUID repair tracked exception differs')
    return sorted(changed)


def final_review(source,runtime):
    w.require(c.sha(c.PROTOCOL)==c.PROTOCOL_SHA and c.sha(c.BACKEND_PROTOCOL)==c.BACKEND_PROTOCOL_SHA
        and c.sha(c.BUDGET_AMENDMENT)==c.AMENDMENT_SHA and c.sha(c.OBSERVABILITY)==c.OBSERVABILITY_SHA
        and c.sha(EXCEPTION)==EXCEPTION_SHA and c.sha(FAILURE_REVIEW)==FAILURE_SHA,
        'UUID repair immutable protocol/amendment/exception/failure bytes differ')
    reference=c.ref(FINAL_REVIEW);record=w.read_ref(reference)
    w.require(record=={'schema':'n23-final-source-runtime-review-uuid-repair-v1','disposition':'accepted',
        'source':source,'runtime':runtime,'dev_protocol':c.ref(c.PROTOCOL),'backend_protocol':c.ref(c.BACKEND_PROTOCOL),
        'amendment':c.ref(c.BUDGET_AMENDMENT),'timeout_observability':c.ref(c.OBSERVABILITY),
        'exception':c.ref(EXCEPTION),'failed_review':c.ref(FAILURE_REVIEW),'no_gpu_release':True},
        'UUID repair final source/runtime review missing or differs')
    return reference


def authority(meta,source,runtime,state=None):
    w.require(meta==binding(),'UUID repair exact authority binding differs')
    record=w.read_ref(meta['authority'])
    keys={'schema','exception','failed_review','final_source_review','source','runtime','authority_interpretation',
        'recorded_at','user_message','cumulative_caps','limits','validation_authorized','formal_authorized'}
    w.require(set(record)==keys and record['schema']=='n23-uuid-repair-authority-v1'
        and record['exception']==c.ref(EXCEPTION) and record['failed_review']==c.ref(FAILURE_REVIEW)
        and record['final_source_review']==final_review(source,runtime) and record['source']==source and record['runtime']==runtime
        and all(isinstance(record[k],str) and record[k].strip() for k in ('authority_interpretation','recorded_at'))
        and record['user_message']==c.AUTONOMOUS_REPLY and record['cumulative_caps']==CAPS and record['limits']==LIMITS
        and record['validation_authorized'] is False and record['formal_authorized'] is False,'UUID repair finite authority differs')
    if state is not None:w.require(state.get('n23_uuid_repair_authority')==meta['authority'],'UUID repair not adopted in private state')
    return record


def named_failure(events,r):
    review=w.read_ref(c.ref(FAILURE_REVIEW))
    w.require(c.sha(FAILURE_REVIEW)==FAILURE_SHA and review.get('schema')=='n23-preflight-uuid-fault-review-v1'
        and review.get('attempt_id')==FAILED_ATTEMPT and review.get('status')=='INVALID_INFRASTRUCTURE_BEFORE_ARITHMETIC'
        and review.get('task_outcome') is False and review.get('dev_dispatched') is False
        and review.get('arithmetic_batches')==review.get('synthetic_batches')==0
        and review.get('original_opportunity_consumed') is True and review.get('original_v1_v2_retry_authorized') is False
        and review.get('gpu_process_wall_seconds')==ORIGINAL_SECONDS
        and review.get('current_failed_worker_raw_uuid')=='not recorded; exact live value unavailable',
        'UUID repair named failure review differs')
    plan=w.read_ref(review['plan']);report=w.read_ref(review['report']);terminal=w.read_ref(review['attempt_result'])
    w.require(review['plan']['sha256']==ORIGINAL_PLAN_SHA and plan['source']==review['original_source']
        and plan['source']['commit']==ORIGINAL_SOURCE and report.get('plan')==review['plan']
        and report.get('source')==plan['source'] and report.get('attempt_id')==FAILED_ATTEMPT
        and report.get('schema')=='n23-backend-preflight-proof-v2' and report.get('accepted') is False
        and report.get('task_outcome') is False and report.get('errors')==[ERROR]
        and report.get('batches')==report.get('synthetic')==[] and report.get('runtime')==plan['runtime'],
        'UUID repair is restricted to zero-arithmetic UUID compatibility failure')
    w.require(terminal.get('attempt_id')==FAILED_ATTEMPT and terminal.get('event')=='aborted'
        and terminal.get('outcome_valid') is False and terminal.get('task_outcome') is False
        and terminal.get('source_commit')==ORIGINAL_SOURCE and terminal.get('plan_sha256')==ORIGINAL_PLAN_SHA
        and terminal.get('budget_bucket')=='recovery' and terminal.get('retry_of') is None
        and terminal.get('gpu_process_wall_seconds')==ORIGINAL_SECONDS and terminal.get('n23_preflight_dispatched') is True
        and terminal.get('process')==report.get('process'), 'UUID repair original terminal/cost differs')
    historical=w.read_ref(review['historical_accounted_probe'])
    evidence=review['historical_uuid_evidence']
    w.require(evidence.get('physical_gpu')==7 and canonical_cuda_uuid(evidence.get('torch_uuid'))==c.GPU7_UUID
        and canonical_cuda_uuid(evidence.get('nvidia_uuid'))==c.GPU7_UUID,'UUID repair historical evidence indicates another device')
    # The historical full probe ref is immutable; it is supporting evidence,
    # never an assertion that this failed worker captured its raw UUID.
    w.require(historical.get('schema')=='qd-ed-gpu-context-probe-v2'
        and historical.get('resource_id')==c.GPU7_PROOF and historical.get('physical_gpu')==7
        and historical.get('torch_logical_device')==0 and historical.get('torch_visible_device_count')==1
        and historical.get('nvidia_physical_gpu')==7 and historical.get('validation_status')=='passed'
        and historical.get('simulation_steps')==0 and historical.get('cuda_visible_devices')=='7'
        and historical.get('display_egl_device_index')==4
        and all(historical.get(k)==evidence.get(k) for k in ('torch_uuid','nvidia_uuid','torch_version','physical_gpu')),
        'UUID repair supporting accounted probe identity differs')
    groups=r['event_groups'](events);group=groups.get(FAILED_ATTEMPT,[])
    w.require([e['event'] for e in group]==['reserved','dispatched','aborted'] and group[-1]==terminal
        and all(e.get('identity',{}).get('iteration')==c.PREFLIGHT and e.get('retry_of') is None
            and e.get('source_commit')==ORIGINAL_SOURCE and e.get('plan_sha256')==ORIGINAL_PLAN_SHA for e in group),
        'UUID repair original charged ledger group differs')
    return review,plan,terminal


def backend_events(events):
    return [e for e in events if e.get('identity',{}).get('iteration') in c.ALL_PREFLIGHTS
        or e.get('n23_backend_preflight') is True
        or (str(e.get('identity',{}).get('iteration','')).startswith('N23_')
            and 'BACKEND' in str(e.get('identity',{}).get('iteration','')))]


def no_dev(events):
    w.require(not any(e.get('identity',{}).get('iteration') in c.ALL_COHORTS
        or e.get('n23_episode_dispatched') is True
        or (str(e.get('identity',{}).get('iteration','')).startswith('N23_')
            and ('DEV' in str(e.get('identity',{}).get('iteration','')) or e.get('identity',{}).get('split')=='dev')) for e in events),'UUID repair cannot follow any N23 Dev reservation')


def validate_plan(plan):
    authority(plan['uuid_repair'],plan['source'],plan['runtime'])
    source_delta(plan['worktree'])
    review=w.read_ref(c.ref(FAILURE_REVIEW));old=w.read_ref(review['plan'])
    expected={**old,'source':plan['source'],'uuid_repair':plan['uuid_repair']}
    w.require(plan==expected,'UUID repair changed corpus/arithmetic/runtime/plan outside final source and explicit lineage')
    return plan


def admission(plan,state,events,resources,reservations,*,root,r):
    from scripts import qd_ed_n23_v2_backend as backend
    from scripts import qd_ed_n23_v2_preflight_admit as admit
    c.require_state(state,r);authority(plan['uuid_repair'],plan['source'],plan['runtime'],state)
    review,old,terminal=named_failure(events,r);no_dev(events)
    w.require({e['attempt_id'] for e in backend_events(events)}=={FAILED_ATTEMPT},'UUID repair already reserved or another backend opportunity exists')
    w.require(plan['source']==w.source_record(root,c.source_paths(r)) and plan['runtime']==c.ref(c.GPU7_RUNTIME)
        and plan['predecessor_review']==c.predecessor_review(),'UUID repair source/runtime/predecessor differs')
    runtime=backend.validate_plan(plan);c.validate_runtime(runtime,root,r)
    w.require(Path(plan['artifact_root']).resolve()==Path(state['artifacts']).resolve()
        and Path(state.get('worktree',root)).resolve()==Path(root).resolve(),'UUID repair private owning roots differ')
    w.require(r['check_budget'](state,events,admit.diagnostic_row(plan),resources,reservations,physical_gpu=7)==120,
        'UUID repair existing recovery capacity unavailable')
    c.full_capacity(state,events,resources,r,preflight=True)
    return runtime


def verify_lineage(plan,reference,events,source,r):
    authority(plan['uuid_repair'],source,plan['runtime'])
    named_failure(events,r)
    local=backend_events(events);groups=r['event_groups'](local)
    w.require(set(groups)=={FAILED_ATTEMPT,reference['attempt_id']} and reference['attempt_id']!=FAILED_ATTEMPT,
        'UUID repair proof must retain exactly two backend attempts')
    repaired=groups[reference['attempt_id']]
    w.require([e['event'] for e in repaired]==['reserved','dispatched','valid']
        and all(e.get('retry_of')==FAILED_ATTEMPT and e.get('n23_uuid_repair')==plan['uuid_repair']
            and e.get('identity',{}).get('iteration')==c.PREFLIGHT and e.get('n23_backend_preflight') is True
            and e.get('budget_bucket')=='recovery' and e.get('physical_gpu')==7
            and e.get('source_commit')==source['commit'] and e.get('plan_sha256')==reference['plan']['sha256'] for e in repaired)
        and repaired[-1].get('outcome_valid') is True and repaired[-1].get('n23_final_review')==final_review(source,plan['runtime']),
        'UUID repair proof terminal lineage/review differs')
    # No task reservation may precede the completed repair; later original Dev is allowed.
    original_end=next(i for i,e in enumerate(events) if e is groups[FAILED_ATTEMPT][-1])
    repaired_start=next(i for i,e in enumerate(events) if e is repaired[0])
    w.require(original_end<repaired_start,'UUID repair precedes original terminal closure')
    boundary=next(i for i,e in enumerate(events) if e is repaired[-1])
    no_dev(events[:boundary+1])
    return repaired[-1]


def build_plan(root,r):
    review=w.read_ref(c.ref(FAILURE_REVIEW));old=w.read_ref(review['plan'])
    w.require(review['plan']['sha256']==ORIGINAL_PLAN_SHA,'UUID repair original plan changed')
    source=w.source_record(root,c.source_paths(r));plan=copy.deepcopy(old)
    plan.update(source=source,uuid_repair=binding())
    validate_plan(plan)
    return plan
