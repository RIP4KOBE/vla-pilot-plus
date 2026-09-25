#!/usr/bin/env python3
"""Run exact N7/C0/Q0/N6 fixed-set formal cells sequentially on GPU3."""
from __future__ import annotations

import argparse
from pathlib import Path
import signal

import audit_decision_evidence as audit
import qd_ed_final_runner as runner
import qd_ed_n7_formal_plan as contract
import qd_ed_n7_validation_supervise as gpu_wait

ROOT=Path(__file__).resolve().parents[1]


def release_check(path,plan_path,plan):
    expected={'schema':'qd-ed-n7-formal-execution-release-v1',
        'plan_path':str(plan_path.resolve()),'plan_sha256':runner.digest(plan_path),
        'source_commit':plan['source_commit'],'cohort_id':contract.COHORT,
        'episode_keys':[x['episode_key'] for x in plan['episodes']],
        'validation_report_sha256':plan['n7_formal']['validation_report']['sha256'],
        'physical_gpu':3,'formal_authorized':True}
    runner.require(runner.read_json(path)==expected,'N7 formal exact release differs')


def audit_result(summary,row,status,completed):
    output=Path(summary['output_dir'])
    report=audit.audit_episode(output/'eds_eval/decision_evidence/episode_000',
                               output/'eds_eval/episode_compute.jsonl')
    runner.durable_json(output/'eds_eval/decision-evidence-audit.json',report)
    runner.require(report.get('accepted') is True and report.get('evidence_complete') is True,
                   'N7 formal native evidence audit rejected')
    metrics=runner.read_events(output/'eds_eval/eds_metrics.jsonl')
    runner.require(len(metrics)==summary.get('guided_chunks')
                   and summary.get('stage_failed_queries')==0
                   and summary.get('outcome_valid') is True,
                   'N7 formal metric/Stage/terminal accounting differs')
    native=report.get('n7_direction_height_audit' if row['profile']=='N7' else
                      'n6_height_audit' if row['profile']=='N6' else 'absent')
    if row['profile'] in {'N6','N7'}:
        schema=('n7-native-direction-height-descriptor-audit-v1' if row['profile']=='N7'
                else 'n6-native-height-descriptor-audit-v1')
        runner.require((not metrics and native is None)
                       or (isinstance(native,dict) and native.get('schema')==schema
                           and native.get('checked_decisions')==len(metrics)
                           and native.get('assignments_verified')==len(metrics)*11
                           and native.get('candidates_verified')==len(metrics)*176),
                       'N6/N7 formal native descriptor audit differs')
    descriptor={'N6':'target_horizontal_radius_signed_height_v1',
                'N7':'target_xy_quadrant_signed_height_v1'}
    for metric in metrics:
        if row['profile'] in {'Q0','N6','N7'}:
            runner.require(metric.get('score_call_count')==11
                           and metric.get('search_evaluation_count')==176,
                           'N7 formal full 176/11 search accounting differs')
        if row['profile'] in descriptor:
            runner.require(metric.get('qd_descriptor')==descriptor[row['profile']]
                           and metric.get('qd_final_selection_mode')=='terminal_grasp_proximity_v1'
                           and runner.n5_support().provider_metric(metric),
                           'N6/N7 formal descriptor/provider/selector differs')
        if row['profile']=='C0':
            runner.require(metric.get('qd_archive_enabled') is False,
                           'C0 formal P2 control unexpectedly uses QD')
    checkpoint={'schema':'qd-ed-n7-formal-cell-audit-v1',
        'episode_key':row['episode_key'],'attempt_id':summary['attempt_id'],
        'accepted':True,'profile':row['profile'],'task_id':row['task_id'],
        'env_seed':row['env_seed'],'init_row_sha256':row['init_row_sha256'],
        'success':summary['success'],'guided_chunks':len(metrics),
        'qd_activity_observed':summary.get('qd_activity_observed') is True,
        'native_descriptor_assignments':native['assignments_verified'] if isinstance(native,dict) else None,
        'source_commit':summary['source_commit'],'plan_sha256':summary['plan_sha256']}
    dest=output/'eds_eval/n7-formal-cell-audit.json'
    runner.durable_json(dest,checkpoint)
    runner.durable_json(status,{'status':'cell_audited','completed_count':len(completed)+1,
                                'latest_checkpoint':str(dest),'selected_physical_gpu':3})
    return checkpoint


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--release',type=Path,required=True)
    parser.add_argument('--status',type=Path,required=True)
    args=parser.parse_args()
    runner.require(Path(runner.read_state(ROOT/'research-state.yaml')['worktree']).resolve()==ROOT,
                   'N7 formal supervisor must run from owning study')
    plan,_,_=runner.validate_plan(args.plan,root=ROOT)
    runner.require(len(plan['episodes'])==40,'N7 formal exact 40 cells required')
    release_check(args.release,args.plan,plan)
    status=runner.owned(args.status,plan['artifact_root'])
    runner.require(not status.exists(),'N7 formal status already exists')
    completed=[]
    runner.durable_json(status,{'status':'started','completed_count':0,'selected_physical_gpu':3})
    try:
        for row in plan['episodes']:
            gpu_wait.wait_gpu3(status,completed)
            runner.durable_json(status,{'status':'dispatching','completed_count':len(completed),
                'current_key':row['episode_key'],'selected_physical_gpu':3})
            with runner.n7_formal_support().supervised_scope(plan,ROOT,row['episode_key']):
                summaries=runner.run_plan(args.plan,split='formal',iteration=contract.COHORT,
                                          episode_keys=[row['episode_key']],root=ROOT)
            runner.require(len(summaries)==1 and summaries[0]['event']=='valid'
                           and summaries[0]['outcome_valid'] is True,
                           'N7 formal cell invalid; preserve terminal and stop')
            audit_result(summaries[0],row,status,completed)
            completed.append(row['episode_key'])
        runner.durable_json(status,{'status':'completed_all_40_audited',
            'completed_count':40,'selected_physical_gpu':3})
    except BaseException as exc:
        runner.durable_json(status,{'status':'interrupted' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'failed',
            'completed_count':len(completed),
            'reason':str(exc) if isinstance(exc,runner.GateError) else type(exc).__name__,
            'selected_physical_gpu':3})
        raise


if __name__=='__main__':
    signal.signal(signal.SIGTERM,lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    main()
