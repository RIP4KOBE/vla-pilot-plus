#!/usr/bin/env python3
"""Serial N23 v2: first valid cell, two exact infra recoveries, full cost retention."""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import signal
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
if str(ROOT/'scripts') not in sys.path:sys.path.insert(0,str(ROOT/'scripts'))
from scripts import qd_ed_final_runner as runner
from scripts import qd_ed_n23_v2_contract as c
from scripts import qd_ed_n23_v2_recovery as recovery
from scripts import qd_ed_n23_worker as worker
import qd_ed_available_gpu_queue as queue

COST_FIELDS=('gpu_process_wall_seconds','guided_chunks','unguided_chunks','candidate_evaluations','score_batches',
 'model_forward_calls','model_batch_rows','reward_calls','reward_evaluations','reward_scoring_batches',
 'provider_logical_call_attempts','stage_codex_logical_call_attempts','provider_input_tokens',
 'provider_output_tokens','provider_cached_input_tokens','provider_failed_calls')
NATIVE_FIELDS=('score_batches_verified','candidate_scores_verified','clipped_prefix_candidates','rank_changed_batches')
AUX_FIELDS=('qd_actuator_overhead_seconds','qd_actuator_quality_batches','qd_actuator_quality_candidates','qd_actuator_clipped_prefix_candidates')


def summarize(outcomes,attempts):
    by_arm={a:{v['task_id']:v['success'] for v in outcomes if v['profile']==a} for a in c.ARMS}
    pairs={a:{'denominator':len(set(by_arm['N23'])&set(by_arm[a])),
        'gains':sum(by_arm['N23'][t] and not by_arm[a][t] for t in set(by_arm['N23'])&set(by_arm[a])),
        'losses':sum(not by_arm['N23'][t] and by_arm[a][t] for t in set(by_arm['N23'])&set(by_arm[a]))} for a in c.ARMS[:-1]}
    costs={a:{k:{'observed_total':0,'observed_attempts':0,'missing_attempts':[]} for k in COST_FIELDS} for a in c.ARMS}
    for attempt in attempts:
        for k in COST_FIELDS:
            v=attempt['terminal'].get(k);slot=costs[attempt['profile']][k]
            if type(v) in (int,float) and math.isfinite(v) and v>=0:slot['observed_total']+=v;slot['observed_attempts']+=1
            else:slot['missing_attempts'].append(attempt['attempt_id'])
    unknown_values=[v['unknown_token_calls'] for v in attempts]
    unmeasured=[v['attempt_id'] for v in attempts if v['unknown_token_calls'] is None]
    known_unknown=sum(v for v in unknown_values if v is not None)
    unknown=None if unmeasured else known_unknown
    return {'accepted_cell_denominators':{a:len(v) for a,v in by_arm.items()},'matched_comparisons':pairs,
        'primary_attempt_denominators':{a:sum(v['profile']==a and not v['terminal'].get('retry_of') for v in attempts) for a in c.ARMS},
        'all_attempt_denominators':{a:sum(v['profile']==a for v in attempts) for a in c.ARMS},
        'all_attempt_costs':costs,'unknown_token_calls':unknown,'known_unknown_token_calls':known_unknown,
        'unmeasured_token_call_attempts':unmeasured,
        'all_attempt_token_usage_complete':bool(attempts) and unknown==0 and all(v['terminal'].get('provider_token_usage_complete') is True for v in attempts),
        'token_cost_interpretation':'observed token totals are partial lower bounds when any timeout usage is unknown',
        'dependent_exposed_dev_reuse':True}


def attempt_record(final,row):
    logical=final.get('provider_logical_call_attempts');complete=final.get('provider_usage_complete_calls')
    unknown=(logical-complete if type(logical) is int and type(complete) is int and 0<=complete<=logical else None)
    return {'attempt_id':final['attempt_id'],'episode_key':row['episode_key'],'profile':row['profile'],
        'terminal':final,'unknown_token_calls':unknown}


def release_check(path,plan_path,plan):
    worker.require(worker.read_ref(c.ref(path))=={'schema':'n23-dev-execution-release-v2','plan':c.ref(plan_path),
        'source_commit':plan['source_commit'],'cohort_id':c.COHORT,'episode_keys':[v['episode_key'] for v in plan['episodes']],
        'physical_gpu':7,'limits':c.LIMITS,'timeout_observability':c.ref(c.OBSERVABILITY),
        'validation_authorized':False,'formal_authorized':False},'N23 v2 exact external release differs')


def one_attempt(plan_path,plan,row,*,eligibility=None):
    before=runner.read_events(ROOT/'data/attempt-ledger.jsonl');seen={e['attempt_id'] for e in before}
    with c.supervised_scope(plan,ROOT,row['episode_key'],eligibility=eligibility):
        try:
            values=runner.run_plan(plan_path,split='dev',iteration=c.COHORT,episode_keys=[row['episode_key']],root=ROOT)
            worker.require(len(values)==1,'N23 v2 one worker result missing');return values[0]
        except runner.GateError:
            # run_plan journals invalid completed attempts before raising. Preserve that real terminal.
            after=runner.read_events(ROOT/'data/attempt-ledger.jsonl')
            finals=[e for e in after if e['attempt_id'] not in seen and e['event'] in runner.TERMINAL
                and e.get('identity',{}).get('iteration')==c.COHORT and e.get('episode_key')==row['episode_key']]
            if len(finals)!=1:raise
            return finals[0]


def native_counts(final,row,report):
    metrics=runner.read_events(Path(final['output_dir'])/'eds_eval/eds_metrics.jsonl');n=len(metrics)
    worker.require(final.get('guided_chunks')==n,'N23 v2 native/compute guided count differs')
    counts={'guided_decisions':0,'parent_rounds_verified':0};aux={k:0 for k in AUX_FIELDS}
    if row['profile'] not in {'N7','N23'}:return counts,aux
    gate=report.get('n23_actuator_clipped_quality_audit',{}) if row['profile']=='N23' else {}
    selection=report.get('n5_grasp_timing_audit',{})
    if n==0:worker.require(not gate and not selection,'N23 v2 unguided audit differs');return counts,aux
    worker.require(selection.get('checked_decisions')==n and selection.get('parent_rounds_verified')==10*n,
        'N23 v2 native parent compute differs')
    mode='actuator_clipped_provider_v1' if row['profile']=='N23' else 'provider'
    worker.require(all(m.get('qd_archive_active_for_chunk') is True and m.get('qd_quality_mode')==mode
        and m.get('score_call_count')==11 and m.get('search_evaluation_count')==176
        and all(m.get(k)==10 for k in ('resample_count','renoise_count','rollout_count')) for m in metrics),
        'N23 v2 substantive fixed QD/ED differs')
    counts.update(guided_decisions=n,parent_rounds_verified=10*n)
    if row['profile']=='N23':
        worker.require(gate.get('score_batches_verified')==11*n and gate.get('candidate_scores_verified')==176*n,
            'N23 v2 independent quality compute differs')
        for k in NATIVE_FIELDS:
            worker.require(type(gate.get(k)) is int and gate[k]>=0,'N23 v2 descriptive native counter missing');counts[k]=gate[k]
        for k in AUX_FIELDS:
            values=[m.get(k) for m in metrics]
            worker.require(all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in values),'N23 v2 auxiliary telemetry missing')
            aux[k]=sum(values)
    return counts,aux


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--release',type=Path,required=True);p.add_argument('--status',type=Path,required=True)
    args=p.parse_args();plan,manifest,runtime=runner.validate_plan(args.plan,root=ROOT);release_check(args.release,args.plan,plan)
    status=runner.owned(args.status,plan['artifact_root']);worker.require(not status.exists(),'N23 v2 cannot resume existing status')
    status.parent.mkdir(parents=True,exist_ok=True)
    attempts=[];outcomes=[];completed=[];successes={a:0 for a in c.ARMS}
    native={'N7':{'guided_decisions':0,'parent_rounds_verified':0},
        'N23':{'guided_decisions':0,'parent_rounds_verified':0,**{k:0 for k in NATIVE_FIELDS}}}
    auxiliary={k:0 for k in AUX_FIELDS}
    def write(phase,**extra):
        runner.durable_json(status,{'schema':'n23-dev-supervisor-status-v2','status':phase,'cohort_id':c.COHORT,
            'completed_keys':completed,'attempts':attempts,'outcomes':outcomes,'successes':successes,'native':native,
            'auxiliary':auxiliary,**summarize(outcomes,attempts),'dev_gate_promoted':False,
            'timeout_observability':c.ref(c.OBSERVABILITY),'protected_authorized':False,**extra})
    def record(final,row):
        item=attempt_record(final,row)
        attempts.append(item);write('attempt_journaled')
        return item
    write('started')
    try:
        for row in plan['episodes']:
            devices=queue.inventory();worker.require(7 in devices and devices[7]['uuid']==c.GPU7_UUID,'N23 v2 GPU7 differs')
            queue.reservation_admission(devices[7]);runner.gpu_admission(physical_gpu=7,expected_uuid=c.GPU7_UUID)
            result=one_attempt(args.plan,plan,row);item=record(result,row)
            if result.get('outcome_valid') is not True:
                events=runner.read_events(ROOT/'data/attempt-ledger.jsonl')
                eligibility=recovery.create_eligibility(args.plan,plan,row,result,manifest['profiles'][row['profile']],runtime,events,ROOT,vars(runner))
                worker.require(item['unknown_token_calls']==1,'typed eligibility unknown-call count differs')
                item.update(timeout_diagnostic=eligibility['diagnostic'])
                path=c.RUN_DIR/'eligibility-v2'/f"{result['attempt_id']}.json"
                worker.atomic_json(path,eligibility);item['typed_eligibility']=c.ref(path);write('primary_invalid_typed_recovery_eligible')
                result=one_attempt(args.plan,plan,row,eligibility=c.ref(path));record(result,row)
            events=runner.read_events(ROOT/'data/attempt-ledger.jsonl')
            accepted=c.accepted_cell(plan,row,events,ROOT,vars(runner))
            worker.require(accepted['attempt_id']==result['attempt_id'],'N23 v2 accepted selection differs from first valid attempt')
            report=c.read_worker_report(result['output_dir'],vars(runner));counts,aux=native_counts(result,row,report)
            if row['profile'] in native:
                for k,v in counts.items():native[row['profile']][k]+=v
            for k,v in aux.items():auxiliary[k]+=v
            outcomes.append({'task_id':row['task_id'],'profile':row['profile'],'success':result['success'],
                'attempt_id':result['attempt_id'],'recovered':result.get('retry_of') is not None})
            successes[row['profile']]+=int(result['success'] is True);completed.append(row['episode_key']);write('cell_audited')
            if row['profile']=='N23':
                remaining=10-len(completed)//4
                if successes['N23']+remaining<5:
                    write('rejected_numeric_futility',remaining_tasks=remaining,maximum_possible_candidate_successes=successes['N23']+remaining);return
        promoted=(len(completed)==40 and successes['N23']>=5 and successes['N23']>=max(successes[a] for a in c.ARMS[:-1])
            and native['N23']['guided_decisions']>0 and native['N23']['parent_rounds_verified']>0)
        write('completed_all_forty_audited',dev_gate_promoted=promoted,
            mechanism_caveat='Clipping counts are descriptive; zero clipping is not an additional promotion veto.')
    except BaseException as exc:
        write('interrupted' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'failed',failure_class=type(exc).__name__)
        raise


if __name__=='__main__':
    signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt()))
    main()
