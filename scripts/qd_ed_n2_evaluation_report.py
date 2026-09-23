#!/usr/bin/env python3
"""SHA-bound protected-phase report. Partial evidence is Unknown, never promotion."""
import argparse
from collections import Counter,defaultdict
import copy
import json
import os
from pathlib import Path

import qd_ed_n2_evaluation as e


def terminal_check(t,plan,plan_sha,r):
    row=next((x for x in plan['episodes'] if x['episode_key']==t.get('episode_key')),None)
    r.require(row is not None and t.get('identity')==r.episode_identity(row),'evaluation terminal cell differs')
    r.require(t.get('event') in r.TERMINAL and t.get('plan_sha256')==plan_sha and t.get('physical_gpu')==3
        and t.get('source_commit')==plan['source_commit'] and t.get('profile_manifest_sha256')==plan['profiles_sha256']
        and t.get('runtime_manifest_sha256')==plan['runtime_manifest_sha256']
        and t.get('runtime_inventory_sha256')==plan['runtime_inventory_sha256']
        and t.get('init_row_sha256')==row['init_row_sha256'] and t.get('retry_of')==row.get('retry_of')
        and t.get('n2_cohort_id')==plan['n2_evaluation']['cohort_id'] and t.get('n2_frozen_identity')==e.binding(plan),
        'evaluation terminal frozen identity differs')
    r.require(type(t.get('success')) is bool and type(t.get('outcome_valid')) is bool
        and type(t.get('gpu_process_wall_seconds')) in (int,float) and t['gpu_process_wall_seconds']>=0,
        'evaluation terminal outcome/cost missing')
    return row


def summarize(plan,attempts,r,d,*,validated_rows=None):
    phase=plan['n2_evaluation']['phase'];limits=e.PHASES[phase]
    originals=[x for x in plan['episodes'] if not x.get('retry_of')]
    bykey={x['episode_key']:x for x in plan['episodes']};grouped=defaultdict(list)
    r.require(len(attempts)<=limits['originals']+limits['recoveries'] and
        len({a['terminal']['attempt_id'] for a in attempts})==len(attempts),'duplicate/excess evaluation attempts')
    if validated_rows is not None:
        r.require(set(validated_rows)=={a['terminal']['attempt_id'] for a in attempts},
                  'evaluation report validated row inventory differs')
    for attempt in attempts:
        terminal=attempt['terminal']
        row=(validated_rows[terminal['attempt_id']] if validated_rows is not None else bykey.get(terminal['episode_key']))
        r.require(row is not None and row['episode_key']==terminal['episode_key']
            and r.episode_identity(row)==terminal['identity'] and row.get('retry_of')==terminal.get('retry_of'),
            'evaluation report lacks exact validated terminal plan row')
        grouped[e.cell(row)].append(attempt)
    r.require(set(grouped)<={e.cell(x) for x in originals},'outside evaluation matrix')
    cells=[];recoveries=0
    for row in originals:
        group=sorted(grouped[e.cell(row)],key=lambda a:a['terminal']['time_unix'])
        r.require(len(group)<=2 and (not group or not group[0]['terminal'].get('retry_of')),'invalid evaluation recovery chain')
        if len(group)==2:
            recoveries+=1;first,second=(a['terminal'] for a in group)
            r.require(second.get('retry_of')==first['attempt_id'] and second.get('n2_frozen_identity')==e.binding(plan)
                and e.recoverable(first,e.binding(plan)),'ineligible evaluation recovery')
        valid=[x for x in group if x['status']=='complete_valid']
        r.require(len(valid)<=1 and (not valid or valid[0] is group[-1]),'cannot supersede valid evaluation outcome')
        chosen=valid[0] if valid else None
        cells.append({'identity':{k:row[k] for k in (*d.IDENTITY,'seed_block')},
            'status':'complete_valid' if chosen else group[-1]['status'] if group else 'pending',
            'valid_attempt_id':chosen['terminal']['attempt_id'] if chosen else None,
            'success':chosen['terminal']['success'] if chosen else None,'attempts':group,
            'metrics':chosen.get('metrics') if chosen else None})
    r.require(recoveries<=limits['recoveries'],'evaluation recovery ceiling exceeded')
    profiles={}
    for profile in ('C0','Q0','N2')+(('N2_QD_OFF',) if phase=='formal' else ()):
        selected=[x for x in cells if x['identity']['profile']==profile];valid=[x for x in selected if x['status']=='complete_valid']
        raw=[a['terminal'] for x in selected for a in x['attempts']]
        profiles[profile]={'expected':limits['per_arm'],'complete_valid':len(valid),
            'successes_observed':sum(x['success'] is True for x in valid),
            'failures_observed':sum(x['success'] is False for x in valid),
            'success_rate':sum(x['success'] is True for x in valid)/limits['per_arm'] if len(valid)==limits['per_arm'] else None,
            'all_attempt_gpu_seconds':d.observed([x.get('gpu_process_wall_seconds') for x in raw]),
            'all_attempt_costs':{key:d.observed([x.get(key) for x in raw]) for key in d.COSTS},
            'blocks':{block:{'expected':10,'complete_valid':sum(x['status']=='complete_valid' for x in selected if x['identity']['seed_block']==block),
                'successes_observed':sum(x['success'] is True for x in selected if x['identity']['seed_block']==block)}
                for block in dict.fromkeys(x['identity']['seed_block'] for x in selected)}}
    complete=all(x['status']=='complete_valid' for x in cells)
    comparisons={}
    for control in ('C0','Q0')+(('N2_QD_OFF',) if phase=='formal' else ()):
        left={e.sample(x['identity']):x for x in cells if x['identity']['profile']=='N2'}
        right={e.sample(x['identity']):x for x in cells if x['identity']['profile']==control}
        r.require(left.keys()==right.keys(),'unmatched protected evaluation arms')
        comparable=all(x['status']=='complete_valid' for x in (*left.values(),*right.values()))
        comparisons['N2_vs_'+control]={'matched_complete':comparable,
            'gained':[list(k) for k in left if left[k]['success'] and not right[k]['success']] if comparable else None,
            'lost':[list(k) for k in left if not left[k]['success'] and right[k]['success']] if comparable else None,
            'success_delta':profiles['N2']['successes_observed']-profiles[control]['successes_observed'] if comparable else None}
    numeric=(profiles['N2']['successes_observed']>=limits['threshold'] and
        all(profiles['N2']['successes_observed']>=profiles[x]['successes_observed'] for x in ('C0','Q0'))) if complete else None
    return {'schema':'qd-ed-n2-evaluation-report-v1','phase':phase,'cohort_id':plan['n2_evaluation']['cohort_id'],
        'candidate_fingerprint':plan['n2_evaluation']['candidate_fingerprint'],'complete':complete,'numeric_pass':numeric,
        'cells':cells,'profiles':profiles,'paired_comparisons':comparisons,'statuses':dict(Counter(x['status'] for x in cells)),
        'phase_authorized':False,'scientific_promotion':'Requires separately hash-bound correctness/activation review.',
        'ablation_scope':'Reported comparison only; no extra superiority threshold; ties do not establish causal contribution.',
        'unknown_scope':'Missing or invalid cells remain Unknown; full denominators fixed; no chunk-level independent samples.',
        'cost_scope':'All supplied original/recovery episode terminals. Global totals and healthcheck costs remain in authoritative journals; no prior proof is charged again.'}


def recompute(manifest,root,r):
    r.require(manifest.get('schema')=='qd-ed-n2-evaluation-report-input-v1' and manifest.get('script_sha256')==r.digest(Path(root)/e.REPORT)
        and manifest.get('protocol_sha256')==e.PROTOCOL_SHA,'evaluation report source contract differs')
    d=e.frozen_report(r)
    base=d.read_ref(manifest['base_plan']);plans={manifest['base_plan']['sha256']:base}
    seeds=r.read_json(base['seed_plan_path']);phase=base['n2_evaluation']['phase']
    r.require([x for x in base['episodes'] if not x.get('retry_of')]==e.rows(seeds,phase),'evaluation report original matrix differs')
    for ref in manifest.get('plan_revisions',[]):
        p=d.read_ref(ref)
        r.require(e.binding(p)==e.binding(base) and e.source_identity(p,r)==e.source_identity(base,r)
            and e.source_identity(e.read_ref(p['n2_evaluation']['dev_plan'],p,r),r)
                ==e.source_identity(e.read_ref(base['n2_evaluation']['dev_plan'],base,r),r)
            and [x for x in p['episodes'] if not x.get('retry_of')]==e.rows(seeds,phase),
            'evaluation report revision differs')
        plans[ref['sha256']]=p
    for p in plans.values():
        r.require(p.get('frozen') is True and p['phase_authorization'].get(phase) is True,
                  'evaluation report refers to an unreleased plan')
        profiles=r.read_json(p['profiles_path'])
        profiles['profiles']['N2']=r.expand_candidate('N2',r.read_json(Path(root)/e.dev.PROFILE),profiles['profiles']['Q0'])
        e.validate_contract(p,profiles,r.read_json(p['runtime_manifest_path']),seeds,root,r)
    original_metrics=d.summarize_metrics
    def metrics(records,terminal,audit,compute):
        if terminal['identity']['profile']=='N2_QD_OFF':
            r.require(all(x.get('qd_archive_active_for_chunk') is False for x in records),'QD ablation unexpectedly active')
            terminal=copy.deepcopy(terminal);terminal['identity']['profile']='N2'
        return original_metrics(records,terminal,audit,compute)
    validated_rows={}
    def validate_terminal(terminal,plan,sha):
        row=terminal_check(terminal,plan,sha,r)
        r.require(terminal['attempt_id'] not in validated_rows,'duplicate validated terminal attempt')
        validated_rows[terminal['attempt_id']]=row
        return row
    d.validate_terminal=validate_terminal
    d.summarize_metrics=metrics
    attempts=[]
    for spec in manifest['attempts']:
        attempt=d.load_attempt(spec,plans)
        terminal=d.read_ref(spec['terminal'])
        for key in ('failure_detail','gpu_monitor_timeout'):
            if key in terminal:attempt['terminal'][key]=terminal[key]
        attempts.append(attempt)
    by_id={a['terminal']['attempt_id']:a for a in attempts}
    for a in attempts:
        terminal=a['terminal']
        if terminal.get('retry_of'):
            r.require(terminal['retry_of'] in by_id,'recovery original missing from report')
            current_plan=plans[d.read_ref(a['references']['terminal'])['plan_sha256']]
            row=next(x for x in current_plan['episodes'] if x['episode_key']==terminal['episode_key'])
            original=d.read_ref(by_id[terminal['retry_of']]['references']['terminal'])
            e.recovery_release(current_plan,row,original,r)
    return summarize(base,attempts,r,d,validated_rows=validated_rows),attempts,base


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--execute-reviewed',action='store_true');args=p.parse_args()
    import qd_ed_final_runner as r
    r.require(args.execute_reviewed and os.environ.get('CUDA_VISIBLE_DEVICES')=='','explicit CPU-only reviewed report required')
    manifest=r.read_json(args.manifest);report,_,plan=recompute(manifest,e.ROOT,r)
    report.update(input_manifest=manifest,input_manifest_sha256=r.digest(args.manifest))
    output=r.owned(args.output,Path(plan['artifact_root'])/'continuation_20260923')
    r.require(not output.exists(),'preserve original report');output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as f:json.dump(report,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
    print(json.dumps({'complete':report['complete'],'numeric_pass':report['numeric_pass'],'output':str(output)}))


if __name__=='__main__':main()
