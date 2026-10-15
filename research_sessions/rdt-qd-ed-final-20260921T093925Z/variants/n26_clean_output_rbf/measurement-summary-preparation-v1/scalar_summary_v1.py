#!/usr/bin/env python3
"""N26 closed-prefix scalar description, never a scientific/dispatch gate."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics
import signal
import sys
import types

HERE=Path(__file__).resolve().parent
DEPENDENCIES={
 'bounded_metadata_v1':'296e87667196fdd9edb3347fa69c8fea8457e8d1ec61eb967a786078f8026ec0',
 'metadata_semantics_v1':'3a4cb74a1d45f41910ff48b0f1af00a1b7a2be5b645f95e1b82f8557c06ab2ae'}
for name,expected in DEPENDENCIES.items():
    path=HERE.parent/'terminal-review-preparation-v1'/(name+'.py')
    blob=path.read_bytes()
    if hashlib.sha256(blob).hexdigest()!=expected:raise RuntimeError('reviewed scalar dependency drift')
    if name in sys.modules:
        if Path(sys.modules[name].__file__).resolve()!=path.resolve():raise RuntimeError('shadowed scalar dependency')
    else:
        # Execute exactly the hash-checked pure source; no pyc cache discovery.
        module=types.ModuleType(name);module.__file__=str(path)
        sys.modules[name]=module;exec(compile(blob,str(path),'exec'),module.__dict__)
from bounded_metadata_v1 import MetadataError,need,decode,load_bound,digest,same_ref,is_ref,ref
from metadata_semantics_v1 import calls,COMMIT,COHORT,source_record,integer

REVIEW_READER_SHA='29fb5e36e2ef0dac6a2522ec68d8e9a2dc69eb622049efa927418ef0c74f6051'
ARMS=('N25','N26');PHASES=('initial','rollout')
NORMS=('gradient_before_normalization','gradient_after_normalization','masked_gradient','update_operand')
COMPONENTS=('clipped_components','boundary_components','interior_components')
CONTROL=('terminal_review','result','plan','source','terminal_input')
LIMITATIONS=[
 'Observed scalar metadata only; no native numerical replay or tensor witness reread.',
 'update_operand is not measured BF16 output delta, post-scheduler action delta, actuator displacement or counterfactual progress.',
 'Arm states, Stage durations and call counts differ; paired task/phase summaries are not same-state causal comparisons.',
 'Zero gradients may be legal. Mechanism activity is not task efficacy or a promotion gate.',
 'All accepted N25/N26 first-valid cells are included without outcome-based selection; an INVALID cohort remains INVALID.',
 'Original terminal review/native audit and its metadata scope are trusted attestations; no Stage/tensor/proof revalidation is performed.']

class BoundedReader:
    def __init__(self,records):
        need(isinstance(records,list) and len(records)<=32,'summary metadata count')
        self.rows={};self.cache={};self.bytes_read=0;total=0;types=Counter()
        for r in records:
            need(set(r)=={'role','path','present','sha256','bytes'} and r['role'] in (*CONTROL,'metrics'),'summary role')
            p=Path(r['path']);resolved=p.resolve()
            need(p.is_absolute() and p.suffix in {'.json','.jsonl'} and not p.is_symlink()
                 and not any(x in p.parts for x in ('decision_evidence','protected'))
                 and p.name not in {'stage_events.jsonl','events.jsonl','attempt-ledger.jsonl','gpu-healthcheck-ledger.jsonl'},'summary forbidden path')
            need(str(resolved) not in self.rows,'duplicate/aliased input')
            need(type(r['present']) is bool and type(r['bytes']) is int and 0<=r['bytes']<=16*1024*1024,'summary size/presence')
            if r['present']:need(is_ref({'path':r['path'],'sha256':r['sha256']}),'summary hash')
            else:need(r['role']=='metrics' and r['sha256'] is None and r['bytes']==0,'only attested metrics absence allowed')
            total+=r['bytes'];types[r['role']]+=1;self.rows[str(resolved)]=r
        need(total<=128*1024*1024 and types['metrics']<=20 and all(types[k]==1 for k in CONTROL),'summary finite role coverage')
    def get(self,reference,role):
        need(isinstance(reference,dict) and set(reference)=={'path','sha256'},'summary reference')
        key=str(Path(reference['path']).resolve());need(key in self.rows,'undeclared summary input')
        r=self.rows[key];need(r['role']==role and r['sha256']==reference['sha256'],'summary role/hash scope')
        if not r['present']:
            need(not Path(r['path']).exists() and not Path(r['path']).is_symlink(),'attested metrics absence changed');return None
        if key not in self.cache:
            b=load_bound(r['path']);need(len(b)==r['bytes'] and digest(b)==r['sha256'],'summary input drift')
            self.bytes_read+=len(b);need(self.bytes_read<=128*1024*1024,'summary byte limit')
            self.cache[key]=[decode(line) for line in b.splitlines() if line.strip()] if Path(r['path']).suffix=='.jsonl' else decode(b)
        return self.cache[key]

def ratio(n,d):return n/d if d else None
def distribution(values):
    return {'count':len(values),'min':min(values) if values else None,'median':statistics.median(values) if values else None,
            'mean':math.fsum(values)/len(values) if values else None,'max':max(values) if values else None}
def aggregate(rows,decisions):
    components=384*len(rows)
    return {'guided_decisions':decisions,'rbf_calls':len(rows),'input_components':components,
        **{k:sum(x[k] for x in rows) for k in COMPONENTS},
        **{k+'_ratio':ratio(sum(x[k] for x in rows),components) for k in COMPONENTS},
        'zero_gradient_calls':sum(x['zero_gradient'] for x in rows),
        'zero_gradient_ratio':ratio(sum(x['zero_gradient'] for x in rows),len(rows)),
        'input_dtype_counts':dict(sorted(Counter(x['input_dtype'] for x in rows).items())),
        'input_stride_counts':dict(sorted(Counter(','.join(map(str,x['input_stride'])) for x in rows).items())),
        'norms':{k:distribution([x[k]['norm'] for x in rows]) for k in NORMS}}
def summarize(cells):
    """Pure aggregation over already bound cells; no I/O, outcome selection or gates."""
    totals={a:{p:[] for p in PHASES} for a in ARMS};guidance={a:0 for a in ARMS};tasks=[];decision_rows=[]
    for cell in cells:
        a=cell['arm'];buckets={p:[] for p in PHASES};n=len(cell['metrics']);guidance[a]+=n
        for m in cell['metrics']:
            rows=calls(m,a)
            for row in rows:
                need(isinstance(row.get('input_stride'),list) and len(row['input_stride'])==3
                     and all(type(v) is int and v>0 for v in row['input_stride']),'recorded stride missing/malformed')
            decision={'arm':a,'task_id':cell['task_id'],'attempt_id':cell['attempt_id'],'global_step':m['global_step'],'phases':{}}
            for p in PHASES:
                q=[x for x in rows if x['phase']==p];buckets[p].extend(q)
                decision['phases'][p]={'rbf_calls':len(q),'input_components':384*len(q),
                    'zero_gradient_ratio':ratio(sum(x['zero_gradient'] for x in q),len(q)),
                    'clipped_component_ratio':ratio(sum(x['clipped_components'] for x in q),384*len(q))}
            decision_rows.append(decision)
        stats={p:aggregate(buckets[p],n) for p in PHASES}
        tasks.append({'arm':a,'task_id':cell['task_id'],'attempt_id':cell['attempt_id'],'guided_decisions':n,
                      'metrics_present':cell['metrics_present'],'phases':stats})
        for p in PHASES:totals[a][p].extend(buckets[p])
    arm_summary={a:{'accepted_cells':sum(x['arm']==a for x in cells),'guided_decisions':guidance[a],
                      'phases':{p:aggregate(totals[a][p],guidance[a]) for p in PHASES}} for a in ARMS}
    pairs=[]
    task_ids={a:{x['task_id'] for x in tasks if x['arm']==a} for a in ARMS}
    for task in sorted(task_ids['N25']&task_ids['N26']):
        left=next(x for x in tasks if x['arm']=='N25' and x['task_id']==task)
        right=next(x for x in tasks if x['arm']=='N26' and x['task_id']==task)
        for p in PHASES:
            x,y=left['phases'][p],right['phases'][p];present=bool(x['rbf_calls'] and y['rbf_calls'])
            delta={k:y[k]-x[k] if present else None for k in ('zero_gradient_ratio',*(c+'_ratio' for c in COMPONENTS))}
            pairs.append({'task_id':task,'phase':p,'both_phases_observed':present,
                'call_denominators':{'N25':x['rbf_calls'],'N26':y['rbf_calls']},
                'component_denominators':{'N25':x['input_components'],'N26':y['input_components']},
                'N26_minus_N25':{**delta,'norm_mean_differences':{k:y['norms'][k]['mean']-x['norms'][k]['mean'] if present else None for k in NORMS}}})
    return {'arms':arm_summary,'tasks':tasks,'decisions':decision_rows,'paired_task_phases':pairs,
        'pair_coverage':{'accepted_matched_tasks':sorted(task_ids['N25']&task_ids['N26']),
           'unmatched_tasks':{a:sorted(task_ids[a]-task_ids[ARMS[1-i]]) for i,a in enumerate(ARMS)},
           'matched_tasks_with_both_phase_observed':{p:sum(x['phase']==p and x['both_phases_observed'] for x in pairs) for p in PHASES}}}

def build(data,reader):
    need(data.get('schema')=='n26-scalar-summary-input-v1' and data.get('root_authorized') is True and data.get('executable') is True,'summary disabled input')
    refs=data['refs'];need(set(refs)==set(CONTROL),'summary control scope')
    review=reader.get(refs['terminal_review'],'terminal_review');result=reader.get(refs['result'],'result')
    plan=reader.get(refs['plan'],'plan');source=reader.get(refs['source'],'source');inventory=reader.get(refs['terminal_input'],'terminal_input')
    source_record(source)
    need(review.get('schema')=='n26-root-terminal-review-v1' and review.get('decision')=='ACCEPT_TERMINAL_RECONSTRUCTION'
         and review.get('discrepancies')==[] and review.get('unsettled_attempts')==[]
         and review.get('cohort_disposition')==result.get('decision')
         and is_ref(review.get('reader')) and review['reader']['sha256']==REVIEW_READER_SHA
         and all(same_ref(review.get(k),refs[k]) for k in ('result','plan','source'))
         and same_ref(review.get('input_manifest'),refs['terminal_input']),'independent terminal review binding')
    need(result.get('schema')=='n26-dev-cohort-result-v1' and result.get('cohort_id')==COHORT and result.get('source_commit')==COMMIT
         and same_ref(result.get('plan'),refs['plan']) and result.get('planned')==40
         and plan.get('source_commit')==COMMIT and plan.get('code_files')==source['files'],'source/plan/result identity')
    need(inventory.get('schema')=='n26-terminal-metadata-input-v1' and inventory.get('root_authorized') is True
         and inventory.get('executable') is True and all(same_ref(inventory.get('refs',{}).get(k),refs[k]) for k in ('result','plan','source')),
         'accepted terminal input scope')
    ordered=plan['episodes'];need(len(ordered)==40 and [(x['task_id'],x['profile']) for x in ordered]==[(t,a) for t in range(10) for a in ('C0','Q0','N25','N26')],'frozen ordered matrix')
    accepted=result['accepted_cells'];need(len(accepted)<=40 and [x['episode_key'] for x in accepted]==[x['episode_key'] for x in ordered[:len(accepted)]]
        and len({x['attempt_id'] for x in accepted})==len(accepted)
        and review.get('accepted_cells')==result.get('audited_cells')==len(accepted),'accepted prefix')
    counts={a:{'audited':sum(x['profile']==a for x in accepted),'success':sum(x['profile']==a and x['success'] for x in accepted)} for a in ('C0','Q0','N25','N26')}
    need(counts==result.get('counts')==review.get('counts') and result.get('native')==review.get('native'),'review accepted coverage')
    targets=[x for x in accepted if x['profile'] in ARMS]
    bindings=data['metrics'];need(len(bindings)<=20 and [x.get('attempt_id') for x in bindings]==[x['attempt_id'] for x in targets],'all accepted arm cells required')
    original=inventory['attempts'];need(len({x['attempt_id'] for x in original})==len(original),'duplicate terminal attempt')
    original_files=inventory['files'];attempts=result['attempts'];need(len({x['attempt_id'] for x in attempts})==len(attempts),'duplicate result attempt')
    loaded=[]
    for cell,b in zip(targets,bindings):
        row=ordered[[x['episode_key'] for x in ordered].index(cell['episode_key'])]
        need(cell['task_id']==row['task_id'] and cell['profile']==row['profile'],'accepted task/profile')
        match=[x for x in original if x['attempt_id']==cell['attempt_id']];need(len(match)==1,'missing terminal attempt scope');old=match[0]['refs']
        need(all(same_ref(cell.get(k),old[v]) for k,v in (('audit','audit'),('worker_context','context'),('worker_receipt','receipt'),('attempt_result','terminal'))),'accepted receipt scope')
        metric=b['ref'];need(metric==old['metrics'],'metric not from accepted inventory')
        record=[x for x in original_files if Path(x['path']).resolve()==Path(metric['path']).resolve()];need(len(record)==1 and record[0]['role']=='metrics','original metric declaration')
        declared=reader.rows[str(Path(metric['path']).resolve())];need(record[0]==declared,'original metric presence/hash/size scope')
        finals=[x['terminal'] for x in attempts if x['attempt_id']==cell['attempt_id']];need(len(finals)==1,'accepted terminal absent');final=finals[0]
        need(final.get('outcome_valid') is True and final.get('episode_key')==cell['episode_key'] and integer(final.get('guided_chunks')),'accepted measured cell')
        metrics=reader.get(metric,'metrics')
        if metrics is None:need(final['guided_chunks']==0,'missing positive-guided metric');metrics=[]
        need(isinstance(metrics,list) and len(metrics)==final['guided_chunks'] and all(type(m.get('global_step')) is int for m in metrics)
             and [m['global_step'] for m in metrics]==sorted({m['global_step'] for m in metrics}),'guided decision coverage/order')
        rows=[x for m in metrics for x in calls(m,cell['profile'])]
        need(final.get('rbf_gradient_calls')==len(rows) and final.get('rbf_gradient_batch_rows')==16*len(rows),'call cost denominator')
        loaded.append({'arm':cell['profile'],'task_id':cell['task_id'],'attempt_id':cell['attempt_id'],'metrics':metrics,'metrics_present':declared['present']})
    need(Counter(x['role'] for x in reader.rows.values())['metrics']==len(loaded),'extra metric file')
    output=summarize(loaded)
    for a in ARMS:
        total=output['arms'][a];native=result['native'][a]
        need(native.get('guided_decisions',0)==total['guided_decisions']
             and native.get('all_call_summaries_verified',0)==sum(total['phases'][p]['rbf_calls'] for p in PHASES)
             and native.get('zero_gradient_calls',0)==sum(total['phases'][p]['zero_gradient_calls'] for p in PHASES)
             and native.get('clipped_components',0)==sum(total['phases'][p]['clipped_components'] for p in PHASES),'terminal scalar totals')
    return {'schema':'n26-existing-scalar-summary-v1','cohort_id':COHORT,'source_commit':COMMIT,
       'cohort_disposition':result['decision'],'original_accepted_prefix_cells':len(accepted),'planned_cells':40,
       'all_accepted_N25_N26_cells_included':True,'describes_partial_prefix_only':len(accepted)<40 or result['decision']=='INVALID_OR_INTERRUPTED',
       'source_refs':refs,'metric_refs':bindings,'limitations':LIMITATIONS,**output,
       'files_read':len(reader.cache),'distinct_bytes_read':reader.bytes_read,
       'next_gpu_execution_authorized':False,'validation_authorized':False,'formal_authorized':False}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    signal.alarm(60)
    need(args.output.resolve().parent==HERE and not args.output.exists(),'owned immutable summary output')
    blob=load_bound(args.input);data=decode(blob);reader=BoundedReader(data['files'])
    need(len(blob)+sum(x['bytes'] for x in reader.rows.values())<=128*1024*1024,'summary manifest plus metadata byte limit')
    result=build(data,reader)
    result.update(input_manifest=ref(args.input),reader=ref(__file__),dependency_hashes=DEPENDENCIES)
    with args.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'schema':result['schema'],'cohort_disposition':result['cohort_disposition'],
       'described_cells':sum(v['accepted_cells'] for v in result['arms'].values()),'next_gpu_execution_authorized':False}))
if __name__=='__main__':main()
