#!/usr/bin/env python3
"""Independent metadata review of existing immutable successor result; optional repair writer."""
import argparse
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n25_cont_contract as c,qd_ed_n25_cont_report as report
from scripts import qd_ed_n25_cont_evidence as e


def review_existing(result,plan,seal,current,reader,source,*,cleanup=e.process_cleanup):
    """Does not call report.analyze or a native auditor; independently derives gates/costs."""
    e.require(result['schema']=='n25-infrastructure-continuation-result-v1' and result['cohort_id']==c.COHORT
        and result['original_disposition']=='INVALID_OR_INTERRUPTED' and result['original_result']==seal['original_result']
        and result['historical_unknowns']==e.UNKNOWN,'result history/Unknown altered')
    e.require(plan['source_commit']==source['commit'] and plan['code_files']==source['files'] and plan['episodes']==c.rows(seal),'new plan/source closure')
    e.require(reader.json(result['plan'])==plan and reader.json(result['ledger_snapshot'])==current,'current journal/snapshot differs')
    gg=e.groups(current);finals=[]
    for aid,g in gg.items():
        e.require(g[0]['event']=='reserved' and g[-1]['event'] in {'valid','aborted'} and sum(x['event']=='dispatched' for x in g)<=1,'unsettled new group')
        finals.append(g[-1])
    e.require({x['attempt_id']:x['terminal'] for x in result['attempts']}=={x['attempt_id']:x for x in [q['terminal'] for q in seal['all_old_attempts']]+finals},'all old/new terminal costs must be retained')
    imported=[{**x['cell'],'logical_index':x['logical_index'],'origin':'imported_original'} for x in seal['accepted_prefix']]
    e.require(result['accepted_cells'][:18]==imported,'imported prefix changed')
    new=result['accepted_cells'][18:];keys=[x['episode_key'] for x in plan['episodes']]
    e.require([x['episode_key'] for x in new]==keys[:len(new)] and len(new)<=22,'new accepted prefix differs')
    wins={a:seal['counts'][a]['success'] for a in c.ARMS};denom={a:seal['counts'][a]['audited'] for a in c.ARMS}
    native={a:dict(seal['native'][a]) for a in c.ARMS};aux={a:dict(seal['auxiliary'][a]) for a in c.ARMS};processes=[]
    for offset,cell in enumerate(new):
        row=plan['episodes'][offset];own=[x for x in finals if x['episode_key']==row['episode_key']]
        e.require(len(own)==1 and cell['logical_index']==18+offset and cell['origin']=='new_successor','new accepted mapping')
        final=own[0];rec=e.accepted_metadata(cell,final,row,plan,result['plan'],source,seal['runtime'],reader,historical=False)
        receipt=reader.json(cell['worker_receipt']);audit=reader.json(cell['audit']);counts,cost=e.measured_native_metadata(final,receipt,audit)
        processes.append(rec['process']);wins[row['profile']]+=int(final['success'] is True);denom[row['profile']]+=1
        for dest,data in ((native,counts),(aux,cost)):
            for k,v in data.items():dest[row['profile']][k]=dest[row['profile']].get(k,0)+v
    # Every later attempt must be the one next unaccepted cell, never a skipped suffix.
    allowed=set(keys[:len(new)])|({keys[len(new)]} if len(new)<22 else set())
    e.require(all(f['episode_key'] in allowed for f in finals),'journal contains skipped/later cell')
    unexpected_valid=[f for f in finals if f['episode_key'] not in keys[:len(new)] and f.get('outcome_valid') is True]
    e.require(not unexpected_valid,'valid journal outcome omitted from immutable result')
    expected_counts={a:{'audited':denom[a],'success':wins[a]} for a in c.ARMS}
    e.require(result['counts']==expected_counts and result['native']==native and result['auxiliary']==aux
        and result['audited_cells']==18+len(new),'independent result counts/native differ')
    n=18+len(new);promoted=n==40 and wins['N25']>=5 and wins['N25']>=max(wins[a] for a in c.ARMS[:-1]) and native['N25'].get('guided_decisions',0)>0 and native['N25'].get('parent_rounds_verified',0)>0
    invalid=any(f.get('outcome_valid') is not True for f in finals)
    expected='ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION' if promoted else 'REJECT' if n==40 else 'REJECT_NUMERIC_FUTILITY' if n%4==0 and wins['N25']+10-n//4<5 and not invalid else 'INVALID_OR_INTERRUPTED'
    statusref={k:result['terminal_status'][k] for k in ('path','sha256')}
    status=reader.json(statusref) if statusref['sha256'] is not None else result['terminal_status']['content']
    e.require(status==result['terminal_status']['content'],'status bytes/content mismatch')
    phase=status.get('status');prefix=[x['episode_key'] for x in new]
    consistent=status.get('completed_keys')==prefix and status.get('dev_gate_promoted')==promoted
    consistent=consistent and ((phase=='rejected_numeric_futility' and expected=='REJECT_NUMERIC_FUTILITY') or
        (phase=='completed_all_forty_audited' and n==40) or (phase in {'failed','interrupted'} and expected=='INVALID_OR_INTERRUPTED'))
    e.require(result['controller_evidence']=={'consistent':consistent,'completed_keys':status.get('completed_keys'),'journal_accepted_keys':prefix,'status_phase':phase},'controller consistency claim differs')
    if not consistent:
        e.require(result['journal_reconstructed_disposition']==expected,'unrecorded controller discrepancy');expected='INVALID_OR_INTERRUPTED';promoted=False
    e.require(result['decision']==expected and result['dev_gate_promoted'] is promoted and result['validation_authorized'] is False
        and result['formal_authorized'] is False,'independent disposition differs')
    # Recompute each cost with the same chronological sum domain; no imputed fields.
    costs={a:{k:{'observed_total':0,'observed_attempts':0,'missing_attempts':[]} for k in report.old_report.COST_FIELDS} for a in c.ARMS}
    unknown=[];unmeasured=[]
    for item in result['attempts']:
        f=item['terminal'];logical=f.get('provider_logical_call_attempts');usage=f.get('provider_usage_complete_calls')
        if type(logical) is int and type(usage) is int and 0<=usage<=logical:unknown.append(logical-usage)
        else:unmeasured.append(f['attempt_id'])
        for k,slot in costs[item['profile']].items():
            v=f.get(k)
            if type(v) in (int,float) and math.isfinite(v) and v>=0:slot['observed_total']+=v;slot['observed_attempts']+=1
            else:slot['missing_attempts'].append(f['attempt_id'])
    e.require(result['all_attempt_costs']==costs and result['known_unknown_token_calls']==sum(unknown)
        and result['unknown_token_calls']==(None if unmeasured else sum(unknown)) and result['unmeasured_token_call_attempts']==unmeasured
        and result['all_attempt_token_usage_complete'] is False,'partial cost/usage differs')
    e.require(result['dispatched']==19+sum(x['event']=='dispatched' for x in current),'combined dispatch denominator differs')
    cleanup(processes)
    return {'schema':'n25-continuation-root-terminal-review-v1','decision':'ACCEPT_TERMINAL_RECONSTRUCTION',
        'cohort_disposition':expected,'accepted_cells':n,'counts':expected_counts,'all_attempts':len(result['attempts']),
        'historical_unknowns':e.UNKNOWN,'metadata_only':True,'tensor_reads':0,'next_gpu_execution_authorized':False,
        'downstream_adapter_required':True,'reader':e.ref(__file__)}


def metadata_inventory(result):
    refs=[result['plan'],result['ledger_snapshot']]
    if result['terminal_status']['sha256'] is not None:refs.append({k:result['terminal_status'][k] for k in ('path','sha256')})
    for cell in result['accepted_cells'][18:]:
        refs.extend(cell[k] for k in ('audit','worker_context','worker_receipt','attempt_result'))
        out=Path(cell['attempt_result']['path']).parent
        refs.extend(e.ref(out/n) for n in ('process.json','eds_eval/in-worker-audit-start.json'))
    return list({str(Path(q['path']).resolve()):q for q in refs}.values())


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--status',type=Path,required=True)
    p.add_argument('--repair-missing-result',action='store_true');a=p.parse_args()
    with r.locked(c.RUN_DIR/'execution/supervisor.lock',nonblocking=True):
        with r.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True):
            plan,_,_=r.validate_plan(a.plan,root=ROOT);controller=w.read_ref(c.ref(c.RUN_DIR/'execution/controller-process-v1.json'))
            e.require(controller['schema']=='n25-continuation-controller-process-v1' and controller['plan']==c.ref(a.plan),'controller record differs')
            e.process_cleanup([controller['process']]);resultpath=c.RUN_DIR/'result-v1.json'
            if a.repair_missing_result:
                w.require(not resultpath.exists(),'terminal result already immutable');report.write_terminal(a.plan,plan,a.status,ROOT,vars(r));return
            result=w.read_ref(c.ref(resultpath));seal=c.history();source=w.source_record(ROOT,c.source_paths(vars(r)))
            current=c.local_events(r.read_events(ROOT/'data/attempt-ledger.jsonl'))
            review=review_existing(result,plan,seal,current,e.Reader(metadata_inventory(result)),source)
            review.update(result=c.ref(resultpath),plan=c.ref(a.plan),source=source,seal=c.ref(c.SEAL),ledger=result['ledger_snapshot'],controller=c.ref(c.RUN_DIR/'execution/controller-process-v1.json'))
            w.atomic_json(c.RUN_DIR/'root-terminal-review-v1.json',review)
if __name__=='__main__':main()
