#!/usr/bin/env python3
"""One closed N22 protected cohort, aggregate-only progress, no auto retry."""
import argparse
import json
from pathlib import Path
import signal
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
if str(ROOT/'scripts') not in sys.path:sys.path.insert(0,str(ROOT/'scripts'))
from scripts import qd_ed_final_runner as runner
from scripts import qd_ed_n22_validation_contract as contract
from scripts import qd_ed_n22_validation_report as reporting
import audit_decision_evidence as audit
import qd_ed_available_gpu_queue as queue


def release_check(path,plan_path,plan):
    require=contract.require
    require(contract.read(path)=={'schema':'n22-validation-execution-release-v1',
        'plan':contract.ref(plan_path),'source_commit':plan['source_commit'],'cohort_id':contract.COHORT,
        'seed_cohort':plan['n22_validation']['seed_cohort'],'episode_keys':[v['episode_key'] for v in plan['episodes']],
        'dev_review':plan['n22_validation']['dev_review'],'source_review':plan['n22_validation']['source_review'],
        'physical_gpu':7,'uuid':contract.GPU7_UUID,'validation_authorized':True,'formal_authorized':False},
        'N22 validation exact root release differs')
    with runner.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True),runner.locked(ROOT/'data/qd-ed-state.lock'):
        m=contract.metadata(ROOT,contract.read(contract.DEV_PLAN))
        require(contract.first_unused(*m[:4])==plan['n22_validation']['seed_cohort'],'validation release freshness changed')
        events=runner.read_events(ROOT/'data/attempt-ledger.jsonl');resources=runner.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl')
        state=runner.read_state(ROOT/'research-state.yaml')
        contract.protected_budget(state,events,resources,plan['episodes'][0],1800,vars(runner),plan=plan)
        runner.check_budget(state,events,plan['episodes'][0],resources,runner.read_events(ROOT/'data/gpu-hour-reservation-ledger.jsonl'),physical_gpu=7)


def audit_result(result,row):
    require=contract.require;out=Path(result['output_dir'])
    require(result['event']=='valid' and result.get('outcome_valid') is True,'protected attempt invalid')
    report=audit.audit_episode(out/'eds_eval/decision_evidence/episode_000',out/'eds_eval/episode_compute.jsonl')
    runner.durable_json(out/'eds_eval/decision-evidence-audit.json',report)
    require(report.get('accepted') is True and report.get('evidence_complete') is True,'protected native audit failed')
    metrics=runner.read_events(out/'eds_eval/eds_metrics.jsonl');n=len(metrics)
    require(n==result['guided_chunks'] and result.get('required_cost_telemetry_complete') is True,'protected cost/guided telemetry incomplete')
    if row['profile']=='N22':
        gate=report.get('n22_hold_lift_quality_audit',{});selection=report.get('n5_grasp_timing_audit',{})
        require((n==0 and not gate and not selection) or (gate.get('score_batches_verified')==11*n
            and gate.get('candidate_scores_verified')==176*n and selection.get('checked_decisions')==n
            and selection.get('parent_rounds_verified')==10*n),'protected hold/parent native compute differs')
        require(all(m.get('qd_quality_mode')=='close_hold_then_lift_v1' and m.get('qd_archive_active_for_chunk') is True
            and m.get('score_call_count')==11 and m.get('search_evaluation_count')==176
            and all(m.get(k)==10 for k in ('resample_count','renoise_count','rollout_count')) for m in metrics),
            'protected substantive QD/ED differs')
    if row['profile']=='Q0':require(all(m.get('score_call_count')==11 and m.get('search_evaluation_count')==176 for m in metrics),'protected Q0 compute differs')
    if row['profile']=='C0':require(all(m.get('qd_archive_enabled') is False for m in metrics),'protected C0 archive active')
    checkpoint={'schema':'n22-validation-cell-audit-v1','accepted':True, 'attempt_id':result['attempt_id'],
        **{k:row[k] for k in ('episode_key','profile','seed_block',*contract.FIELDS)},
        'success':result['success'],'guided_chunks':n,'source_commit':result['source_commit'],
        'plan_sha256':result['plan_sha256'],'native_report':contract.ref(out/'eds_eval/decision-evidence-audit.json')}
    runner.durable_json(out/'eds_eval/n22-validation-cell-audit.json',checkpoint)
    return checkpoint


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--release',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args();plan,_,runtime=runner.validate_plan(args.plan,root=ROOT);release_check(args.release,args.plan,plan)
    output=runner.owned(args.output_dir,plan['artifact_root']);output.mkdir(parents=True,exist_ok=True)
    status=output/'aggregate-progress.json';contract.require(not status.exists(),'validation supervisor cannot resume')
    completed=0
    def progress(phase,**extra):runner.durable_json(status,{'phase':phase,'completed_count':completed,'expected_cells':60,'protected_outcomes_disclosed':False,**extra})
    progress('started')
    try:
        for row in plan['episodes']:
            devices=queue.inventory();contract.require(7 in devices and devices[7]['uuid']==contract.GPU7_UUID,'validation GPU7 differs')
            queue.reservation_admission(devices[7]);runner.gpu_admission(physical_gpu=7,expected_uuid=contract.GPU7_UUID)
            mapping=queue.current_metadata(7,root=ROOT)
            probe=queue.find_probe(runtime,mapping,runner.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl'),root=ROOT)
            contract.require(queue.same_mapping(runtime['gpu_mapping'],mapping) and isinstance(probe,dict)
                and probe.get('resource_id')==contract.GPU7_PROOF,'validation existing EGL/probe differs')
            with runner.n22_validation_support().supervised_scope(plan,ROOT,row['episode_key']):
                results=runner.run_plan(args.plan,split='validation',iteration=contract.COHORT,episode_keys=[row['episode_key']],root=ROOT)
            contract.require(len(results)==1,'validation one-cell result missing');audit_result(results[0],row)
            completed+=1;progress('cell_audited')
        aggregate=reporting.write_reports(plan,runner.read_events(ROOT/'data/attempt-ledger.jsonl'),output)
        progress('completed',gate_passed=aggregate['gate_passed'],outcome_valid=aggregate['outcome_valid'])
    except BaseException as exc:
        progress('invalid_or_interrupted',failure_class=type(exc).__name__)
        try:reporting.write_reports(plan,runner.read_events(ROOT/'data/attempt-ledger.jsonl'),output)
        finally:
            # Even a predispatch interruption is not a valid aggregate rejection.
            runner.durable_json(output/'aggregate-disposition.json',{'schema':'n22-validation-aggregate-disposition-v1',
                'cohort_id':contract.DEV_COHORT,'aggregate_only':True,'terminal':True,'gate_passed':False,
                'outcome_valid':False,'dev_promoted':True})
        raise


if __name__=='__main__':
    signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt()))
    main()
