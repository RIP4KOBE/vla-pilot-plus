#!/usr/bin/env python3
"""Exact independently reviewed predecessor transition; generic INVALID is closed."""
from __future__ import annotations
from pathlib import Path
from scripts import qd_ed_n23_v2_contract as c
from scripts import qd_ed_n23_worker as worker
from scripts import qd_ed_n23_backend_preflight as legacy

NAMED_ATTEMPT='rdt-qd-ed-final-20260921T093925Z__n22_dev_t04_c0_20260930__43653a91ead8'
N22_COHORT='N22_HOLD_LIFT_DEV_20260930'
N22_SOURCE='60425750c41c8a46e1102e02e2e4e4d2f97fb242'
N22_PLAN_SHA='30846268778c46f2d9ad25a92abe7869395d3ead218da1a97dbf24fae4d07218'


def same_ref(a,b):
    return (isinstance(a,dict) and isinstance(b,dict) and set(a)==set(b)=={'path','sha256'}
        and Path(a['path']).resolve()==Path(b['path']).resolve() and a['sha256']==b['sha256'])


def gate(reference):
    require=worker.require;review=worker.read_ref(reference)
    common={'schema','source_plan','route','allow_n23_v2','rationale','timeout_observability'}
    require(review.get('schema')=='n23-n22-prerequisite-v2' and review.get('allow_n23_v2') is True
        and isinstance(review.get('rationale'),str) and review['rationale'].strip()
        and c.sha(c.OBSERVABILITY)==c.OBSERVABILITY_SHA and review.get('timeout_observability')==c.ref(c.OBSERVABILITY)
        and same_ref(review.get('source_plan'),c.ref(c.SOURCE_PLAN)), 'N23 v2 root predecessor review missing')
    if review.get('route')=='valid_aggregate_rejection':
        require(set(review)==common|{'valid_rejection_review'},'N23 v2 valid-rejection review scope differs')
        prior=legacy.predecessor_gate(review['valid_rejection_review'])
        require(same_ref(prior['source_plan'],review['source_plan']),'N23 v2 valid rejection source differs')
        return review
    require(set(review)==common|{'named_failure_proof'} and review.get('route')=='named_n22_c0_task4_timeout',
        'N23 v2 generic invalid transition is forbidden')
    proof=worker.read_ref(review['named_failure_proof'])
    require(set(proof)=={'schema','disposition','allow_n23_v2','source_plan','source_commit','terminal_status',
        'terminal_result','named_attempt','named_terminal','native_audit','timeout_diagnostic','evidence_files',
        'ledger_closure','prior_cell_audits','native_evidence','owned_worker_absent','n22_promoted','timeout_observability'}
        and proof['schema']=='n23-named-n22-timeout-proof-v2' and proof['disposition']=='invalid_incomplete_not_scientific_rejection'
        and proof['allow_n23_v2'] is True and proof['named_attempt']==NAMED_ATTEMPT
        and proof['source_commit']==N22_SOURCE and same_ref(proof['source_plan'],review['source_plan'])
        and proof['source_plan']['sha256']==N22_PLAN_SHA and proof['owned_worker_absent'] is True
        and proof['n22_promoted'] is False and proof['timeout_observability']==c.ref(c.OBSERVABILITY),
        'N23 v2 named predecessor proof identity differs')
    plan=worker.read_ref(proof['source_plan']);status=worker.read_ref(proof['terminal_status'])
    result=worker.read_ref(proof['terminal_result']);terminal=worker.read_ref(proof['named_terminal'])
    audit=worker.read_ref(proof['native_audit']);diagnostic=worker.read_ref(proof['timeout_diagnostic'])
    closure=worker.read_ref(proof['ledger_closure'])
    require(plan.get('n22_cohort',{}).get('cohort_id')==N22_COHORT and plan['source_commit']==N22_SOURCE
        and len(plan['episodes'])==40 and plan['episodes'][16]['task_id']==4 and plan['episodes'][16]['profile']=='C0',
        'N23 v2 frozen N22 predecessor row differs')
    require(status.get('status')=='failed' and status.get('dev_gate_promoted') is False
        and status.get('completed_keys')==[r['episode_key'] for r in plan['episodes'][:16]],
        'N23 v2 predecessor must stop invalid after exactly16 audited cells')
    require(result.get('schema')=='n22-dev-cohort-result-v1' and result.get('cohort_id')==N22_COHORT
        and result.get('source_commit')==N22_SOURCE and same_ref(result.get('plan'),proof['source_plan'])
        and result.get('decision')=='INVALID_OR_INTERRUPTED' and result.get('dev_gate_promoted') is False
        and result.get('dispatched')==17 and result.get('audited_cells')==16 and result.get('planned')==40
        and len(result.get('rows',[]))==17,'N23 v2 predecessor result is not exact invalid/incomplete closure')
    rs=result.get('terminal_status',{})
    require(set(rs)=={'path','sha256','content'} and same_ref({k:rs[k] for k in ('path','sha256')},proof['terminal_status'])
        and rs['content']==status,'N23 v2 predecessor status/result association differs')
    require(terminal.get('attempt_id')==NAMED_ATTEMPT and terminal.get('episode_key')==plan['episodes'][16]['episode_key']
        and terminal.get('event')=='valid' and terminal.get('outcome_valid') is False and terminal.get('retry_of') is None
        and terminal.get('source_commit')==N22_SOURCE and terminal.get('plan_sha256')==N22_PLAN_SHA
        and terminal.get('compute_outcome')=='completed' and terminal.get('required_cost_telemetry_complete') is False
        and audit.get('accepted') is True and audit.get('evidence_complete') is True,
        'N23 v2 named native/terminal identity invalid')
    require(diagnostic.get('schema')=='n23-v2-timeout-diagnostic-v1'
        and diagnostic.get('eligible_infrastructure_only') is True and diagnostic.get('outcome_valid') is False
        and diagnostic.get('attempt_id')==NAMED_ATTEMPT and diagnostic.get('source_commit')==N22_SOURCE
        and diagnostic.get('plan_sha256')==N22_PLAN_SHA and diagnostic.get('evidence_files')==proof['evidence_files']
        and diagnostic.get('global_step')==112 and diagnostic.get('unknown_token_calls')==1
        and diagnostic.get('timeout_observability')==c.ref(c.OBSERVABILITY)
        and diagnostic.get('original_required_cost_telemetry_complete') is False
        and diagnostic.get('all_attempt_token_usage_complete') is False,
        'N23 v2 named timeout diagnostic absent')
    # Immutable root proof records the CPU diagnostic inputs; their byte binding is rechecked here.
    require(set(proof['evidence_files'])=={'stage_events','episode_compute','episode_metadata','safety_events','metrics','resolved_config','results'},
        'N23 v2 named sole-invalidity evidence list incomplete')
    from scripts.qd_ed_n23_v2_recovery import evidence_files
    require(proof['evidence_files']==evidence_files(terminal['output_dir'])
        and Path(audit['episode_dir']).resolve()==(Path(terminal['output_dir'])/'eds_eval/decision_evidence/episode_000').resolve()
        and Path(audit['episode_compute_file']).resolve()==(Path(terminal['output_dir'])/'eds_eval/episode_compute.jsonl').resolve()
        and proof['native_evidence']==worker.evidence_record(terminal['output_dir']),
        'N23 v2 named evidence belongs to another attempt')
    for reference in proof['evidence_files'].values():
        require(set(reference)=={'path','sha256'} and Path(reference['path']).is_absolute()
            and c.sha(reference['path'])==reference['sha256'],'N23 v2 named evidence changed')
    require(len(proof['prior_cell_audits'])==16,'N23 v2 prior audited prefix missing')
    for row,reference in zip(result['rows'][:16],proof['prior_cell_audits']):
        prior_audit=worker.read_ref(reference['report'])
        require(reference['attempt_id']==row['attempt_id'] and same_ref(reference['report'],row['audit'])
            and row.get('native_valid') is True and row.get('outcome_valid') is True
            and prior_audit.get('accepted') is True and prior_audit.get('evidence_complete') is True,
            'N23 v2 predecessor prefix not fully audited')
    require(result['rows'][-1]['attempt_id']==NAMED_ATTEMPT and result['rows'][-1]['outcome_valid'] is False
        and result['rows'][-1]['native_valid'] is False,'N23 v2 invalid primary was reclassified')
    require(set(closure)=={'schema','ledger','snapshot_bytes','snapshot_sha256','cohort_id','attempt_ids','all_terminal',
        'dispatched','unsettled','owned_worker_absent','source_commit'}
        and closure['schema']=='n22-terminal-ledger-closure-v1' and closure['cohort_id']==N22_COHORT
        and closure['source_commit']==N22_SOURCE and closure['dispatched']==17 and closure['unsettled']==0
        and closure['all_terminal'] is True and closure['owned_worker_absent'] is True
        and closure['attempt_ids']==[v['attempt_id'] for v in result['rows']], 'N23 v2 unsettled predecessor ledger')
    # The actual live journal can append later; the reviewed prefix must remain byte-identical.
    import hashlib
    ledger=Path(closure['ledger']).read_bytes();size=closure['snapshot_bytes']
    require(type(size) is int and 0<size<=len(ledger) and hashlib.sha256(ledger[:size]).hexdigest()==closure['snapshot_sha256'],
        'N23 v2 predecessor ledger prefix changed')
    import json
    from scripts import qd_ed_final_runner as runner
    require(Path(closure['ledger']).resolve()==(Path(plan['worktree'])/'data/attempt-ledger.jsonl').resolve(),
        'N23 v2 closure names another private journal')
    journal=[json.loads(line) for line in ledger[:size].splitlines()]
    local=[e for e in journal if e.get('identity',{}).get('iteration')==N22_COHORT]
    groups=runner.event_groups(local)
    require(len(groups)==17 and [e['attempt_id'] for e in local if e['event']=='dispatched']==closure['attempt_ids']
        and all(g[-1]['event'] in runner.TERMINAL for g in groups.values())
        and groups[NAMED_ATTEMPT][-1]==terminal,'N23 v2 predecessor actual journal closure differs')
    for index,aid in enumerate(closure['attempt_ids']):
        group=groups[aid];last=group[-1];row=plan['episodes'][index]
        require([e['event'] for e in group]==['reserved','dispatched','valid']
            and last.get('identity')==runner.episode_identity(row) and last.get('source_commit')==N22_SOURCE
            and last.get('plan_sha256')==N22_PLAN_SHA and last.get('retry_of') is None
            and last.get('outcome_valid') is (index<16),'N23 v2 prior terminal identity/invalidity differs')
    return review
