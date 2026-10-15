"""Separate successor outcome and logical sixteen; historical INVALID never changes."""
from pathlib import Path
from scripts import qd_ed_n23_worker as w,qd_ed_n27_report as old
from scripts import qd_ed_n27_cont_contract as c,qd_ed_n27_cont_history as h

def analyze(plan,seal,events,acceptor):
    local=c.local_events(events);gg=list(h.groups(local).values());rows=plan['episodes'];keys=[x['episode_key'] for x in rows]
    w.require(rows==c.rows(seal),'exact fixed reporting matrix')
    attempts=[]
    for i,g in enumerate(gg):
        w.require(i<len(rows) and g[0]['episode_key']==keys[i] and [x['event'] for x in g] in (
            ['reserved','dispatched','valid'],['reserved','dispatched','aborted'],['reserved','aborted'])
            and all(x['episode_key']==keys[i] and x['attempt_id']==g[0]['attempt_id'] for x in g),'ordered settled new attempt groups')
        w.require(g[-1]['identity']['iteration']==c.COHORT,'new cohort identity')
        attempts.append({'attempt_id':g[0]['attempt_id'],'episode_key':keys[i],'profile':rows[i]['profile'],'terminal':g[-1]})
    # Reject interleaved/reordered groups, not just dictionary ordering.
    w.require(local==[event for group in gg for event in group],'interleaved attempt history')
    accepted=[{**q['cell'],'logical_index':q['logical_index'],'origin':'imported_original','source_commit':h.BASE} for q in seal['accepted_prefix']]
    native={a:{} for a in c.ARMS};aux={a:{} for a in c.ARMS}
    for item in seal['accepted_prefix']:
        arm=item['cell']['profile'];native[arm]=dict(item['native']);aux[arm]=dict(item['auxiliary'])
    failure=None
    for i,row in enumerate(rows):
        if i>=len(gg):break
        try:
            cell,counts,cost=acceptor(row,local)
            w.require(cell['attempt_id']==gg[i][-1]['attempt_id'] and cell['episode_key']==row['episode_key']
                and cell['profile']==row['profile'] and cell['task_id']==row['task_id'] and type(cell['success']) is bool,'new cell identity')
        except (ValueError,RuntimeError,OSError,KeyError,AssertionError) as exc:
            failure={'episode_key':row['episode_key'],'failure_class':type(exc).__name__,'reason':str(exc)};break
        accepted.append({**cell,'logical_index':i+3,'origin':'new_continuation','source_commit':plan['source_commit']})
        for dest,data in ((native,counts),(aux,cost)):
            for k,v in data.items():dest[row['profile']][k]=dest[row['profile']].get(k,0)+v
    added=len(accepted)-3;w.require(len(gg)<=added+(1 if added<13 else 0),'continued after invalid/missing result')
    counts={a:{'audited':sum(x['profile']==a for x in accepted),'success':sum(x['profile']==a and x['success'] for x in accepted)} for a in c.ARMS}
    wins=counts['N27']['success'];complete=len(accepted)==16
    promoted=complete and wins>=2 and wins>=max(counts[a]['success'] for a in c.ARMS[:-1]) and wins>counts['N26']['success']
    promoted=promoted and native['N27'].get('guided_decisions',0)>0 and native['N27'].get('parent_rounds_verified',0)>0
    decision='ELIGIBLE_FOR_SEPARATELY_FROZEN_FULL_DEV' if promoted else 'REJECT_SCREEN' if complete else 'INVALID_OR_INTERRUPTED'
    combined=seal['all_old_attempts']+attempts;w.require(len({x['attempt_id'] for x in combined})==len(combined),'attempt charged twice')
    return {'schema':'n27-hydra-continuation-result-v1','cohort_id':c.COHORT,'source_commit':plan['source_commit'],
        'original_disposition':'INVALID_OR_INTERRUPTED','original_result':seal['original_result'],'prefix_seal':c.ref(c.SEAL),
        'planned':16,'imported_cells':3,'new_planned':13,'new_accepted_cells':added,'audited_cells':len(accepted),
        'continuation_disposition':'COMPLETE_THIRTEEN_VALID' if complete else 'INVALID_OR_INTERRUPTED','decision':decision,
        'dev_gate_promoted':promoted,'counts':counts,'accepted_cells':accepted,'native':native,'auxiliary':aux,'failure':failure,
        'new_attempts':attempts,'attempts':combined,'new_dispatched':sum(x['event']=='dispatched' for x in local),
        'dispatched':4+sum(x['event']=='dispatched' for x in local),'historical_unknowns':h.UNKNOWN,
        'old_costs':old.summary([],seal['all_old_attempts']),'new_costs':old.summary([],attempts),**old.summary(accepted,combined),
        'validation_authorized':False,'formal_authorized':False,'goal_status':'TARGET_NOT_MET','new_numerical_preflight':False}

def write_terminal(path,plan,status_path,root,r):
    w.require(Path(status_path).resolve()==(c.RUN_DIR/'execution/supervisor-status-v1.json').resolve(),'status split-root path')
    seal=c.history();local=c.local_events(r['read_events'](Path(root)/'data/attempt-ledger.jsonl'))
    try:status=h.read(c.ref(status_path));status_ref=c.ref(status_path)
    except (OSError,ValueError,KeyError):status={'status':'unavailable'};status_ref={'path':str(status_path),'sha256':None}
    def accept(row,events):
        final=c.accepted_cell(plan,row,events,root,r);out=Path(final['output_dir']);report=c.read_worker_report(out,r)
        counts,aux=c.native.from_output(row['profile'],out,report,final.get('guided_chunks'))
        return {'episode_key':row['episode_key'],'task_id':row['task_id'],'profile':row['profile'],'attempt_id':final['attempt_id'],'success':final['success'],
            'audit':c.ref(out/'eds_eval/decision-evidence-audit.json'),'worker_context':c.ref(out/'n23-worker-context.json'),
            'worker_receipt':c.ref(out/'eds_eval/in-worker-audit-receipt.json'),'attempt_result':c.ref(out/'attempt-result.json')},counts,aux
    try:result=analyze(plan,seal,local,accept)
    except (ValueError,RuntimeError,OSError,KeyError,AssertionError) as exc:
        attempts=[{'attempt_id':g[0]['attempt_id'],'episode_key':g[0]['episode_key'],'profile':g[0]['identity']['profile'],'terminal':g[-1]} for g in h.groups(local).values()]
        all_attempts=seal['all_old_attempts']+attempts
        result={'schema':'n27-hydra-continuation-result-v1','cohort_id':c.COHORT,'source_commit':plan['source_commit'],
            'decision':'INVALID_OR_INTERRUPTED','dev_gate_promoted':False,'continuation_disposition':'INVALID_OR_INTERRUPTED',
            'original_disposition':'INVALID_OR_INTERRUPTED','original_result':seal['original_result'],'audited_cells':3,
            'accepted_cells':[{**q['cell'],'origin':'imported_original','source_commit':h.BASE,'logical_index':q['logical_index']} for q in seal['accepted_prefix']],
            'journal_reconstruction_error':{'type':type(exc).__name__,'reason':str(exc)},'unsettled_or_malformed_new_journal':local,
            'attempts':all_attempts,'new_attempts':attempts,'historical_unknowns':h.UNKNOWN,**old.summary([],all_attempts)}
    prefix=[x['episode_key'] for x in result['accepted_cells'] if x['origin']=='new_continuation'];phase=status.get('status')
    consistent=status.get('completed_keys')==prefix and status.get('dev_gate_promoted')==result['dev_gate_promoted']
    consistent=consistent and ((phase=='completed_all_sixteen_audited' and result['audited_cells']==16)
        or (phase in {'failed','interrupted'} and result['decision']=='INVALID_OR_INTERRUPTED'))
    result['controller_evidence']={'consistent':consistent,'completed_keys':status.get('completed_keys'),'journal_accepted_keys':prefix,'status_phase':phase}
    if not consistent:
        result['journal_reconstructed_disposition']=result['decision'];result['decision']='INVALID_OR_INTERRUPTED'
        result['dev_gate_promoted']=False;result['continuation_disposition']='INVALID_OR_INTERRUPTED'
    ledger=c.RUN_DIR/'execution/terminal-ledger-v1.json';w.atomic_json(ledger,local)
    result.update(plan=c.ref(path),source_bridge=c.ref(c.BRIDGE),terminal_status={**status_ref,'content':status},ledger_snapshot=c.ref(ledger),
        reader=c.ref(__file__),validation_authorized=False,formal_authorized=False)
    w.atomic_json(c.RUN_DIR/'result-v1.json',result);return result
