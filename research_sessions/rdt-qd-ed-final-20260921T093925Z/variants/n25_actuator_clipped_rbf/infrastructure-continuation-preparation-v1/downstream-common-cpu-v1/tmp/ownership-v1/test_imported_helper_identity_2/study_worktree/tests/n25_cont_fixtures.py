"""Only synthetic JSON/source/process fixtures; never opens real research artifacts."""
import copy
import json
from pathlib import Path
from scripts import qd_ed_n25_cont_evidence as e,qd_ed_n25_cont_contract as c


def put(p,o):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(o,sort_keys=True,indent=2)+'\n');return e.ref(p)

def plan_rows():
    return [dict(split='dev',seed_block='dev',iteration=e.OLD,profile=a,task_id=t,env_seed=100+t,policy_seed=200+t,init_index=0,
        init_row_sha256='row'+str(t),init_file_sha256='init'+str(t),bddl_sha256='bddl'+str(t),timeout_seconds=1800,
        budget_bucket='baseline' if a=='C0' else 'development',episode_key=f'n25_dev_t{t:02d}_{a.lower()}_20260930') for t in range(10) for a in e.ARMS]

def public_calls():
    failsteps=[96,120,128,136,168,176];out=[]
    for i in range(43):
        fail=i<6;events=[{'kind':'thread.started'},{'kind':'turn.started'},{'kind':'error','error_category':'stream_error'},
            {'kind':'item.completed','item_kind':'error','error_category':'item_error'}]
        for position,event in enumerate(events):event['observed_at']=2.+position
        life={'request_started_at':0.,'spawn_started_at':.1,'spawn_returned_at':.2,'communicate_started_at':1.,
            'cleanup_started_at':181.1,'cleanup_returned_at':181.2,'process_exit_observed_at':181.3,'observer_finished_at':181.4,'schema':'codex-stage-lifecycle-v1','observation_complete':True,'observer_error_category':None,
            'timeout_observed_at':181.,'first_completed_observed_at':None,'first_complete_usage_observed_at':None,
            'complete_usage_observed':False,'events':events}
        out.append({'event_position':i,'global_step':failsteps[i] if fail else 200+i*8,'chunk_id':i,'episode_id':0,
            'query_ok':not fail,'query_status':'error' if fail else 'ok','error':'codex_timeout' if fail else None,
            'codex_logical_call_attempts':1,'codex_completed_turns':int(not fail),'codex_failed_calls':int(fail),
            'codex_usage_complete_calls':int(not fail),'codex_reasoning_output_tokens':None,'codex_call_latency_s':181.4,
            'transport':{'backend':'codex_cli','auth_mode':'chatgpt','model':'gpt-6-astra','reasoning_effort':'low','timeout_seconds':180.,'event_types':[v['kind'] for v in events],'item_types':['error'],'lifecycle':life}})
    return out

def fixture(tmp,monkeypatch):
    root=tmp/'old_source';root.mkdir();files=[]
    for n in range(257):
        p=root/f'source_{n}.py';p.write_text(f'number={n}\n');files.append({'path':p.name,'sha256':e.sha(p)})
    source={'commit':e.BASE,'files':files,'sha256':e.canonical(files)};src=put(tmp/'source.json',source)
    runtime={'worktree':str(root),'gpu_mapping':{'physical_gpu':7,'uuid':'GPU-48473162-9548-1a19-04aa-ea86c5349187'}};rt=put(tmp/'runtime.json',runtime)
    dummy=put(tmp/'proof-extra.json',{'completed':True})
    proof=put(tmp/'proof.json',{'schema':'n25-metered-tensor-proof-v1','accepted':True,'source':source,'runtime':rt,**{k:dummy for k in ('plan','report','process','terminal')}})
    budget=put(tmp/'budget.json',{'caps':c.CAPS,'amendment':'synthetic'})
    auth=put(tmp/'old-authority.json',{'source':source,'runtime':rt,'local_gpu_hours':22.,'budget_authority':budget})
    freview=put(tmp/'old-final-review.json',{'source':source,'runtime':rt,'disposition':'accepted','backend_proof':proof})
    rows=plan_rows();plan={'source_commit':e.BASE,'code_files':files,'worktree':str(root),'frozen':True,'episodes':rows,
        'runtime_manifest_path':rt['path'],'runtime_manifest_sha256':rt['sha256'],'profiles_sha256':'profiles','runtime_inventory_sha256':'inventory',
        'n25_cohort':{'final_review':freview,'authority':auth},'derived_from':dummy,'artifact_root':str(tmp/'attempts'),
        'phase_authorization':{'dev':True,'validation':False,'formal':False}}
    planref=put(tmp/'plan.json',plan);attempts=[];accepted=[];ledger=[];natives={a:{} for a in e.ARMS};aux={a:{} for a in e.ARMS}
    walls=[0.]*17+[e.OLD_SECONDS-e.FAILED_SECONDS,e.FAILED_SECONDS]
    assert sum(walls)==e.OLD_SECONDS
    for n,row in enumerate(rows[:19]):
        aid=e.FAILED if n==18 else 'synthetic-'+str(n);out=tmp/'attempts'/aid;out.mkdir(parents=True)
        pid=900000+n;process={'pid':pid,'proc_start_ticks':str(100+n),'boot_id':'old-boot','attempt_id':aid};proc={k:process[k] for k in ('pid','proc_start_ticks','boot_id')}
        put(out/'process.json',process)
        context={'source':source,'plan':planref,'runtime':rt,'attempt_id':aid,'episode_key':row['episode_key'],'profile':row['profile'],
            'output_dir':str(out),'main_argv':[str(root/'main.py')],'worktree':str(root),'schema':'n23-metered-worker-context-v1'}
        cr=put(out/'n23-worker-context.json',context)
        put(out/'eds_eval/in-worker-audit-start.json',{'schema':'n23-worker-start-v1','process':proc,'context':cr})
        native={'guided_decisions':1,'parent_rounds_verified':10};backend={'kind':'cuda' if row['profile'] in {'N23','N25'} else 'cpu'}
        if n<18:
            ar=put(out/'eds_eval/decision-evidence-audit.json',{'accepted':True,'evidence_complete':True,'n23_arithmetic_backend':backend})
            evidence=[{'path':f'd{j}.pt','sha256':'a'*64} for j in range(2100)]
            receipt={'accepted':True,'main_exit_code':0,'process_unchanged':True,'context':cr,'audit_report':ar,'source':source,'plan':planref,'runtime':rt,
                'attempt_id':aid,'profile':row['profile'],'episode_key':row['episode_key'],'main_argv_sha256':e.canonical(context['main_argv']),
                'process':proc,'evidence':{'files':evidence,'sha256':e.canonical(evidence)},'audit_backend':backend,
                'worker_cuda':{'physical_gpu':7,'physical_uuid':'GPU-48473162-9548-1a19-04aa-ea86c5349187'},'audit_seconds':0.,'worker_wall_seconds':0.,
                'n25_native_counts':native,'n25_auxiliary':{}}
            rr=put(out/'eds_eval/in-worker-audit-receipt.json',receipt)
            for k,v in native.items():natives[row['profile']][k]=natives[row['profile']].get(k,0)+v
        final={'attempt_id':aid,'episode_key':row['episode_key'],'identity':e.identity(row),'event':'valid','outcome_valid':n<18,
            'source_commit':e.BASE,'plan_sha256':planref['sha256'],'runtime_manifest_sha256':rt['sha256'],'profile_manifest_sha256':'profiles',
            'runtime_inventory_sha256':'inventory','init_row_sha256':row['init_row_sha256'],'physical_gpu':7,'output_dir':str(out),'budget_bucket':row['budget_bucket'],
            'retry_of':None,'gpu_process_wall_seconds':walls[n],'success':n==15,'required_cost_telemetry_complete':n<18,
            'provider_logical_call_attempts':43 if n==18 else 1,'provider_completed_turns':37 if n==18 else 1,
            'provider_failed_calls':6 if n==18 else 0,'provider_usage_complete_calls':37 if n==18 else 1,'provider_token_usage_complete':n<18}
        if n==18:final.update(reason='TimeoutExpired',compute_outcome='completed')
        else:final['n23_worker_receipt']=rr
        tr=put(out/'attempt-result.json',final)
        if n<18:accepted.append({'attempt_id':aid,'episode_key':row['episode_key'],'task_id':row['task_id'],'profile':row['profile'],'success':final['success'],
            'audit':ar,'worker_context':cr,'worker_receipt':rr,'attempt_result':tr})
        attempts.append({'attempt_id':aid,'episode_key':row['episode_key'],'profile':row['profile'],'terminal':final})
        ledger.extend([{**final,'event':'reserved'},{**final,'event':'dispatched'},final])
    out=Path(attempts[-1]['terminal']['output_dir']);(out/'results.txt').write_text('present, not accepted')
    put(out/'eds_eval/episode_compute.jsonl',{'compute_outcome':'completed'})
    lr=put(tmp/'ledger.json',ledger);status={'status':'failed','completed_keys':[q['episode_key'] for q in rows[:18]]};sr=put(tmp/'status.json',status)
    result={'schema':'n25-dev-cohort-result-v1','decision':'INVALID_OR_INTERRUPTED','cohort_id':e.OLD,'source_commit':e.BASE,'audited_cells':18,
        'planned':40,'dispatched':19,'counts':e.EXPECTED_COUNTS,'dev_gate_promoted':False,'controller_evidence':{'consistent':True},'plan':planref,
        'ledger_snapshot':lr,'terminal_status':{**sr,'content':status},'accepted_cells':accepted,'attempts':attempts,'native':natives,'auxiliary':aux}
    res=put(tmp/'result.json',result)
    review={'schema':'n25-root-terminal-review-v1','decision':'ACCEPT_TERMINAL_RECONSTRUCTION','cohort_disposition':'INVALID_OR_INTERRUPTED',
        'source_files_verified':257,'accepted_cells':18,'counts':e.EXPECTED_COUNTS,'all_attempts':19,'all_attempt_gpu_process_seconds':e.OLD_SECONDS,
        'result':res,'plan':planref,'source':src,'ledger':lr}
    rev=put(tmp/'review.json',review)
    ctl=put(tmp/'controller.json',{'schema':'n25-root-controller-process-v1','plan':planref,'controller_pid':999999,'controller_start_ticks':'88','boot_id':'old-boot'})
    public={'schema':'n25-public-stage-metadata-v1','attempt_id':e.FAILED,'response_payloads_included':False,
        'source_stage_events':{'path':str(tmp/'NEVER_READ.jsonl'),'sha256':'f'*64},'calls':public_calls()}
    public['attestation']={'root_terminal_review':rev,'source_stage_events':public['source_stage_events'],'public_fields_only':True,'all_logical_calls_included':True,'reader':dummy}
    st=put(tmp/'public-stage.json',public)
    refs={'review':rev,'result':res,'source':src,'plan':planref,'controller':ctl,'stage_public':st}
    monkeypatch.setattr(e,'FROZEN',{k:refs[k]['sha256'] for k in ('review','result','source','plan')})
    files=[e.ref(p) for p in tmp.rglob('*') if p.is_file() and p.suffix in {'.json','.jsonl','.txt'}]
    data={'schema':'n25-continuation-sealing-input-v1','root_authorized':True,'files':files,'references':refs}
    return data,root,plan


def fake_cleanup(ps):return {'boot_id':'new','checked_processes':ps,'no_owned_processes':True}


def new_events(plan,n=22,*,fail=None,wins=5):
    events=[]
    for i,row in enumerate(plan['episodes'][:n]):
        final={'attempt_id':'new-'+str(i),'episode_key':row['episode_key'],'identity':e.identity(row),'retry_of':row.get('retry_of'),
            'budget_bucket':row['budget_bucket'],'event':'valid','outcome_valid':i!=fail,'required_cost_telemetry_complete':i!=fail,
            'success':row['profile']=='N25' and row['task_id']<4+wins,'gpu_process_wall_seconds':100.,
            'provider_logical_call_attempts':1,'provider_usage_complete_calls':1,'provider_token_usage_complete':True}
        events.extend([{**final,'event':'reserved'},{**final,'event':'dispatched'},final])
    return events


def materialize_new(tmp,plan,seal,events):
    pref=put(tmp/'new-plan.json',plan);source={'commit':plan['source_commit'],'files':plan['code_files'],'sha256':e.canonical(plan['code_files'])}
    cells={};groups=e.groups(events)
    for i,(aid,group) in enumerate(groups.items()):
        row=plan['episodes'][i];out=tmp/'new-native'/aid;out.mkdir(parents=True);final=group[-1]
        final.update(source_commit=source['commit'],plan_sha256=pref['sha256'],runtime_manifest_sha256=plan['runtime_manifest_sha256'],
            profile_manifest_sha256=plan['profiles_sha256'],runtime_inventory_sha256=plan['runtime_inventory_sha256'],init_row_sha256=row['init_row_sha256'],
            physical_gpu=7,output_dir=str(out),rbf_gradient_calls=154,guidance_api_request_attempts=0,grounding_api_request_attempts=0,
            stage_transport={'backend':'codex_cli','auth_mode':'chatgpt','model':'gpt-6-astra','reasoning_effort':'low','timeout_seconds':180.})
        for q in group[:-1]:q.update(final)
        group[0]['event']='reserved';group[1]['event']='dispatched'
        proc={'pid':800000+i,'proc_start_ticks':'1','boot_id':'test'};put(out/'process.json',{**proc,'attempt_id':aid})
        ctx={'source':source,'plan':pref,'runtime':seal['runtime'],'attempt_id':aid,'episode_key':row['episode_key'],'profile':row['profile'],
            'output_dir':str(out),'main_argv':[str(tmp/'main.py')]};cr=put(out/'n23-worker-context.json',ctx)
        put(out/'eds_eval/in-worker-audit-start.json',{'schema':'n23-worker-start-v1','process':proc,'context':cr})
        backend={'kind':'cuda' if row['profile'] in {'N23','N25'} else 'cpu'};counts={'guided_decisions':1,'parent_rounds_verified':10 if row['profile'] in {'N23','N25'} else 0}
        if row['profile'] in {'N23','N25'}:counts.update(score_batches_verified=11,candidate_scores_verified=176)
        audit={'accepted':True,'evidence_complete':True,'errors':[],'n23_arithmetic_backend':backend}
        if row['profile']=='N25':
            counts.update(all_call_summaries_verified=154,witness_calls_verified=0,zero_gradient_calls=0,clipped_components=10)
            audit['n25_actuator_clipped_rbf_audit']={'schema':'n25-native-rbf-audit-v1','accepted':True,**counts,'witness_numeric_bytes':0,'witness_checks':[]}
        ar=put(out/'eds_eval/decision-evidence-audit.json',audit)
        receipt={'accepted':True,'main_exit_code':0,'process_unchanged':True,'context':cr,'audit_report':ar,'source':source,'plan':pref,'runtime':seal['runtime'],
            'attempt_id':aid,'profile':row['profile'],'episode_key':row['episode_key'],'main_argv_sha256':e.canonical(ctx['main_argv']),'process':proc,
            'evidence':{'files':[],'sha256':e.canonical([])},'audit_backend':backend,'worker_cuda':{'physical_gpu':7,'physical_uuid':'GPU-48473162-9548-1a19-04aa-ea86c5349187'},
            'audit_seconds':0.,'worker_wall_seconds':0.,'n25_native_counts':counts,'n25_auxiliary':{}}
        rr=put(out/'eds_eval/in-worker-audit-receipt.json',receipt);final['n23_worker_receipt']=rr
        tr=put(out/'attempt-result.json',final)
        cells[row['episode_key']]=({'episode_key':row['episode_key'],'task_id':row['task_id'],'profile':row['profile'],'attempt_id':aid,'success':final['success'],
            'audit':ar,'worker_context':cr,'worker_receipt':rr,'attempt_result':tr},counts,{})
    return pref,source,cells
