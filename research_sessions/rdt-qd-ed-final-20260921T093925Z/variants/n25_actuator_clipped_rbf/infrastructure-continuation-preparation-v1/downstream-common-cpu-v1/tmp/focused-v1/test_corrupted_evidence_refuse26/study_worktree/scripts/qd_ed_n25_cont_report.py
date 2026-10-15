"""Independent logical40 aggregation, immutable original INVALID and all costs retained."""
from pathlib import Path
from scripts import qd_ed_n23_worker as w,qd_ed_n25_report as old_report,qd_ed_n25_native as native
from scripts import qd_ed_n25_cont_contract as c,qd_ed_n25_cont_evidence as e


def analyze(plan,seal,events,acceptor):
    local=c.local_events(events);gg=e.groups(local);rows=plan['episodes'];keys=[x['episode_key'] for x in rows]
    w.require(len(rows)==22 and rows==c.rows(seal),'fixed22 reporting map differs')
    attempts=[]
    for aid,g in gg.items():
        w.require(g[0]['event']=='reserved' and g[-1]['event'] in {'valid','aborted'}
            and sum(x['event']=='dispatched' for x in g)<=1 and all(x['episode_key']==g[0]['episode_key'] for x in g),'new unsettled/malformed journal')
        w.require(g[0]['episode_key'] in keys,'unknown successor cell')
        row=rows[keys.index(g[0]['episode_key'])]
        attempts.append({'attempt_id':aid,'episode_key':row['episode_key'],'profile':row['profile'],'terminal':g[-1]})
    accepted=[{**q['cell'],'logical_index':q['logical_index'],'origin':'imported_original'} for q in seal['accepted_prefix']]
    native_counts={a:dict(seal['native'][a]) for a in c.ARMS};aux={a:dict(seal['auxiliary'][a]) for a in c.ARMS};failure=None
    for n,row in enumerate(rows,18):
        own=[g for g in gg.values() if g[0]['episode_key']==row['episode_key']]
        if not own:break
        try:
            cell,counts,cost=acceptor(row,local)
            w.require(len(own)==1 and cell['attempt_id']==own[0][-1]['attempt_id'],'new accepted lineage differs')
        except (ValueError,RuntimeError,OSError,KeyError,AssertionError) as exc:
            failure={'episode_key':row['episode_key'],'logical_index':n,'type':type(exc).__name__,'reason':str(exc)};break
        accepted.append({**cell,'logical_index':n,'origin':'new_successor'})
        for dest,data in ((native_counts,counts),(aux,cost)):
            for k,v in data.items():dest[row['profile']][k]=dest[row['profile']].get(k,0)+v
    added=len(accepted)-18;allowed=set(keys[:added])|({keys[added]} if added<22 else set())
    w.require(all(x['episode_key'] in allowed for x in local),'journal continued past invalid/missing cell')
    counts={a:{'audited':sum(x['profile']==a for x in accepted),'success':sum(x['profile']==a and x['success'] is True for x in accepted)} for a in c.ARMS}
    wins=counts['N25']['success'];substantive=native_counts['N25'].get('guided_decisions',0)>0 and native_counts['N25'].get('parent_rounds_verified',0)>0
    promoted=len(accepted)==40 and wins>=5 and wins>=max(counts[a]['success'] for a in c.ARMS[:-1]) and substantive
    futile=len(accepted)%4==0 and wins+10-len(accepted)//4<5
    decision='ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION' if promoted else 'REJECT' if len(accepted)==40 else 'REJECT_NUMERIC_FUTILITY' if futile and failure is None else 'INVALID_OR_INTERRUPTED'
    combined=seal['all_old_attempts']+attempts
    w.require(len({x['attempt_id'] for x in combined})==len(combined),'cost attempt duplicated')
    return {'schema':'n25-infrastructure-continuation-result-v1','cohort_id':c.COHORT,'source_commit':plan['source_commit'],
        'planned':40,'imported_cells':18,'new_accepted_cells':added,'audited_cells':len(accepted),'counts':counts,'accepted_cells':accepted,
        'original_disposition':'INVALID_OR_INTERRUPTED','original_result':seal['original_result'],'prefix_seal':c.ref(c.SEAL),
        'historical_unknowns':e.UNKNOWN,'new_attempts':attempts,'attempts':combined,
        'new_dispatched':sum(x['event']=='dispatched' for x in local),'dispatched':19+sum(x['event']=='dispatched' for x in local),
        'native':native_counts,'auxiliary':aux,'failure':failure,'decision':decision,'dev_gate_promoted':promoted,
        'old_costs':old_report.summary([],seal['all_old_attempts']),'new_costs':old_report.summary([],attempts),
        **old_report.summary(accepted,combined),'validation_authorized':False,'formal_authorized':False,'goal_status':'TARGET_NOT_MET',
        'downstream_adapter_required':True}


def write_terminal(plan_path,plan,status_path,root,r):
    w.require(Path(status_path).resolve()==(c.RUN_DIR/'execution/supervisor-status-v1.json').resolve(),'controller status exact split-root path')
    seal=c.history();events=r['read_events'](Path(root)/'data/attempt-ledger.jsonl');local=c.local_events(events)
    try:status=w.read_ref(c.ref(status_path));status_ref=c.ref(status_path)
    except (OSError,ValueError,KeyError) as exc:status={'status':'unavailable','type':type(exc).__name__};status_ref={'path':str(status_path),'sha256':None}
    def accept(row,ev):
        final=c.accepted_cell({**plan,'_path':str(plan_path)},row,ev,root,r);out=Path(final['output_dir'])
        report=c.old.read_worker_report(out,r);counts,aux=native.from_output(row['profile'],out,report,final.get('guided_chunks'))
        return {'episode_key':row['episode_key'],'task_id':row['task_id'],'profile':row['profile'],'attempt_id':final['attempt_id'],
            'success':final['success'],'audit':c.ref(out/'eds_eval/decision-evidence-audit.json'),
            'worker_context':c.ref(out/'n23-worker-context.json'),'worker_receipt':c.ref(out/'eds_eval/in-worker-audit-receipt.json'),
            'attempt_result':c.ref(out/'attempt-result.json')},counts,aux
    try:result=analyze(plan,seal,events,accept)
    except (ValueError,RuntimeError,OSError,KeyError,AssertionError) as exc:
        # Malformed/unsettled metadata cannot be silently converted into accepted cells.
        attempts=[]
        for g in e.groups(local).values():
            attempts.append({'attempt_id':g[0]['attempt_id'],'episode_key':g[0]['episode_key'],
                'profile':g[0]['identity']['profile'],'terminal':g[-1]})
        combined=seal['all_old_attempts']+attempts
        result={'schema':'n25-infrastructure-continuation-result-v1','cohort_id':c.COHORT,'decision':'INVALID_OR_INTERRUPTED',
            'dev_gate_promoted':False,'original_disposition':'INVALID_OR_INTERRUPTED','original_result':seal['original_result'],
            'accepted_cells':[dict(q['cell'],origin='imported_original',logical_index=q['logical_index']) for q in seal['accepted_prefix']],
            'audited_cells':18,'journal_reconstruction_error':{'type':type(exc).__name__,'reason':str(exc)},'attempts':combined,
            'unsettled_or_malformed_new_journal':local,'historical_unknowns':e.UNKNOWN,**old_report.summary([],combined)}
    prefix=[x['episode_key'] for x in result['accepted_cells'] if x['origin']=='new_successor']
    phase=status.get('status');consistent=status.get('completed_keys')==prefix and status.get('dev_gate_promoted')==result['dev_gate_promoted']
    consistent=consistent and ((phase=='rejected_numeric_futility' and result['decision']=='REJECT_NUMERIC_FUTILITY')
        or (phase=='completed_all_forty_audited' and result['audited_cells']==40)
        or (phase in {'failed','interrupted'} and result['decision']=='INVALID_OR_INTERRUPTED'))
    result['controller_evidence']={'consistent':consistent,'completed_keys':status.get('completed_keys'),'journal_accepted_keys':prefix,'status_phase':phase}
    if not consistent:
        result['journal_reconstructed_disposition']=result['decision'];result['decision']='INVALID_OR_INTERRUPTED';result['dev_gate_promoted']=False
    snapshot=c.RUN_DIR/'execution/terminal-ledger-v1.json';w.atomic_json(snapshot,local)
    result.update(plan=c.ref(plan_path),source_bridge=c.ref(c.BRIDGE),terminal_status={**status_ref,'content':status},ledger_snapshot=c.ref(snapshot),
        reader=c.ref(__file__),validation_authorized=False,formal_authorized=False)
    w.atomic_json(c.RUN_DIR/'result-v1.json',result);return result
