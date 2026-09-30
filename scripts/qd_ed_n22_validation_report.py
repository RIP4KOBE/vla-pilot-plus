#!/usr/bin/env python3
"""Persist protected detailed evidence; expose only a separate aggregate gate."""
import argparse
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts import qd_ed_final_runner as runner
from scripts import qd_ed_n22_validation_contract as contract

COST_FIELDS=('gpu_process_wall_seconds','guided_chunks','unguided_chunks','candidate_evaluations','score_batches',
 'model_forward_calls','model_batch_rows','reward_calls','reward_evaluations','reward_scoring_batches',
 'provider_logical_call_attempts','stage_codex_logical_call_attempts','provider_input_tokens',
 'provider_output_tokens','provider_cached_input_tokens','provider_failed_calls')


def summarize(plan,events,load=contract.read):
    local=[e for e in events if e.get('identity',{}).get('iteration')==contract.COHORT]
    rows=plan['episodes'];cells=[];known=set();complete=True;invalid=False;active=0
    totals={a:{k:0 for k in COST_FIELDS} for a in contract.ARMS};missing=[]
    for row in rows:
        subset=[e for e in local if e.get('episode_key')==row['episode_key']]
        ids={e['attempt_id'] for e in subset};known|=ids
        require=contract.require;require(len(ids)<=1,'validation duplicate attempt for protected cell')
        final=[e for e in subset if e['event'] in runner.TERMINAL]
        require(len(final)<=1,'validation duplicate terminal')
        status='not_run';success=None;checkpoint=None;terminal=final[0] if final else None
        if terminal:
            for k in COST_FIELDS:
                value=terminal.get(k)
                if type(value) in (int,float) and math.isfinite(value) and value>=0:totals[row['profile']][k]+=value
                else:missing.append({'episode_key':row['episode_key'],'field':k})
            status='invalid'
            if terminal['event']=='valid' and terminal.get('outcome_valid') is True:
                try:checkpoint=load(Path(terminal['output_dir'])/'eds_eval/n22-validation-cell-audit.json')
                except (FileNotFoundError,ValueError,KeyError):checkpoint=None
                if checkpoint and checkpoint.get('accepted') is True:
                    contract.verify_checkpoint(checkpoint,terminal,row,plan,vars(runner))
                    status='valid_native_audited';success=terminal['success']
                    if row['profile']=='N22':active+=checkpoint['guided_chunks']
            invalid|=status=='invalid'
        complete &= status=='valid_native_audited'
        cells.append({**{k:row[k] for k in ('task_id','seed_block','env_seed','policy_seed','profile','episode_key')},
            'status':status,'success':success,'terminal':terminal,'checkpoint':checkpoint})
    contract.require({e['attempt_id'] for e in local}==known,'out-of-matrix validation attempt')
    counts={a:sum(c['success'] is True for c in cells if c['profile']==a) for a in contract.ARMS}
    denominators={a:sum(c['status']=='valid_native_audited' for c in cells if c['profile']==a) for a in contract.ARMS}
    full=complete and len(rows)==60 and not missing
    promoted=full and active>0 and counts['N22']>=10 and counts['N22']>=max(counts['C0'],counts['Q0'])
    paired={}
    for arm in ('C0','Q0'):
        a={(c['seed_block'],c['task_id']):c['success'] for c in cells if c['profile']==arm and c['status']=='valid_native_audited'}
        n={(c['seed_block'],c['task_id']):c['success'] for c in cells if c['profile']=='N22' and c['status']=='valid_native_audited'}
        keys=set(a)&set(n);paired[arm]={'denominator':len(keys),'gains':sum(n[k] and not a[k] for k in keys),
            'losses':sum(not n[k] and a[k] for k in keys)}
    detailed={'schema':'n22-protected-validation-detail-v1','cohort_id':contract.COHORT,'seed_cohort':plan['n22_validation']['seed_cohort'],
        'source_commit':plan['source_commit'],'accepted_cells':sum(denominators.values()),'expected_cells':60,
        'success_counts':counts,'denominators':denominators,'paired':paired,'costs':totals,'missing_costs':missing,
        'cells':cells,'decision':'PROMOTE' if promoted else 'REJECT' if full else 'INVALID' if invalid or missing else 'INCOMPLETE',
        'claim':'same-layout seed robustness; not new-layout generalization','formal_authorized':False}
    aggregate={'schema':'n22-validation-aggregate-disposition-v1','cohort_id':contract.DEV_COHORT,
        'aggregate_only':True,'terminal':bool(full or invalid or missing),'gate_passed':bool(promoted),
        'outcome_valid':bool(full),'dev_promoted':True}
    return detailed,aggregate


def write_reports(plan,events,directory):
    directory=runner.owned(directory,plan['artifact_root']);directory.mkdir(parents=True,exist_ok=True)
    # Preserve the complete protected evidence even if an identity/hash check rejects adjudication.
    try:detail,aggregate=summarize(plan,events)
    except (ValueError,KeyError,TypeError,FileNotFoundError) as exc:
        runner.durable_json(directory/'protected-unadjudicated-evidence.json',{'schema':'n22-validation-invalid-evidence-v1',
            'failure_class':type(exc).__name__,'planned_rows':plan['episodes'],
            'events':[e for e in events if e.get('identity',{}).get('iteration')==contract.COHORT]})
        raise
    runner.durable_json(directory/'protected-detail.json',detail)
    runner.durable_json(directory/'aggregate-disposition.json',aggregate)
    return aggregate


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args();plan,_,_=runner.validate_plan(args.plan,root=ROOT)
    aggregate=write_reports(plan,runner.read_events(ROOT/'data/attempt-ledger.jsonl'),args.output_dir)
    print(json.dumps(aggregate))  # Never emit per-task or per-arm protected outcomes.


if __name__=='__main__':main()
