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

def historical_fixture(tmp,monkeypatch):
    root=tmp/'study_worktree';root.mkdir();files,objects,new,reverse=source_fixture(root)
    source={'commit':e.BASE,'files':files,'sha256':e.canonical(files)};src=put(tmp/'source.json',source)
    runtime={'worktree':str(root),'gpu_mapping':{'physical_gpu':7,'uuid':'GPU-48473162-9548-1a19-04aa-ea86c5349187'}};rt=put(tmp/'runtime.json',runtime)
    dummy=put(tmp/'proof-extra.json',{'completed':True})
    proof=make_proof(tmp,source,rt,monkeypatch)
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
    return data,root,plan,objects,new,reverse


from scripts import qd_ed_n25_cont_downstream as d,qd_ed_n25_cont_bridge as bridge
from scripts import qd_ed_n25_cont_seal as sealer,qd_ed_n25_cont_report as reporting,qd_ed_n25_cont_terminal as terminal
from scripts import qd_ed_n25_backend as backend,qd_ed_n23_worker as w,qd_ed_audit_backend as audit_backend,qd_ed_n25_reference as reference
from n25_cont_fixtures import fake_cleanup,new_events,materialize_new
import ast,difflib
ACTUAL=Path(__file__).resolve().parents[1]

class Objects:
    def __init__(self,values):self.values=values;self.allowed={(d.HISTORICAL,bridge.DOC+'/original-source-v1.json')};self.reads=[]
    def authorize(self,values):self.allowed.update(values)
    def __call__(self,commit,path):
        assert (commit,path) in self.allowed
        self.reads.append((commit,path));return self.values[commit,path]


def source_fixture(root):
    worker=bridge.functions((ACTUAL/'scripts/qd_ed_n23_worker.py').read_text())
    wb='\n\n'.join(worker[k] for k in ('require','sha','canonical_sha','read_ref'))+'\n\ndef validate_context():\n    return "old"\n'
    rb='\n\n'.join(f'def {n}():\n    return "old"' for n in sorted(bridge.ROUTES['scripts/qd_ed_final_runner.py']))+'\n'
    old={'scripts/qd_ed_n23_worker.py':wb.encode(),'scripts/qd_ed_final_runner.py':rb.encode()}
    for name in ('qd_ed_n25_backend','qd_ed_n25_reference','qd_ed_audit_backend','qd_ed_n25_report','qd_ed_n25_contract'):old['scripts/'+name+'.py']=(ACTUAL/'scripts'/ (name+'.py')).read_bytes()
    for i in range(257-len(old)):old[f'fake_source_{i:03}.py']=f'n={i}\n'.encode()
    files=[{'path':p,'sha256':d.digest(b)} for p,b in sorted(old.items())]
    source={'commit':e.BASE,'files':files,'sha256':e.canonical(files)};new=dict(old)
    reverse={'schema':'synthetic-exact-reverse','base_commit':e.BASE,'files':[]}
    for path in bridge.ROUTES:
        new[path]=old[path].replace(b'return "old"',b'return "new"');a=old[path].decode().splitlines(keepends=True);z=new[path].decode().splitlines(keepends=True)
        edits=[{'new_start':j,'new_end':k,'new':''.join(z[j:k]),'old':''.join(a[i:l])} for tag,i,l,j,k in difflib.SequenceMatcher(a=a,b=z).get_opcodes() if tag!='equal']
        reverse['files'].append({'path':path,'old_sha256':d.digest(old[path]),'new_sha256':d.digest(new[path]),'edits':edits})
    for path in bridge.EXTRAS:new[path]=(ACTUAL/path).read_bytes()
    new[bridge.DOC+'/original-source-v1.json']=(json.dumps(source,sort_keys=True,indent=2)+'\n').encode()
    new[bridge.DOC+'/reverse-routes-v1.json']=(json.dumps(reverse,sort_keys=True,indent=2)+'\n').encode()
    nfiles=[{'path':p,'sha256':d.digest(b)} for p,b in sorted(new.items())]
    ns={'commit':d.HISTORICAL,'files':nfiles,'sha256':e.canonical(nfiles)}
    for path,b in old.items():p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    return files,Objects({**{(e.BASE,p):b for p,b in old.items()},**{(d.HISTORICAL,p):b for p,b in new.items()}}),ns,reverse


def make_proof(tmp,source,rt,monkeypatch):
    from scripts.qd_ed_n25_reference import CASES
    rid='synthetic__n25_tensor_arithmetic_v1';p=tmp/'old-proof-plan.json';monkeypatch.setattr(backend,'PLAN',p)
    pr=put(p,{'frozen':True,'resource_id':rid,'source':source,'runtime':rt})
    process={'pid':700000,'proc_start_ticks':'1','boot_id':'old','resource_id':rid};cr=put(tmp/'old-proof-process.json',process)
    uuid=c.old.GPU7_UUID
    report={'schema':'n25-tensor-arithmetic-report-v1','accepted':True,'resource_id':rid,'source':source,'runtime':rt,'plan':pr,
        'process':{k:process[k] for k in ('pid','proc_start_ticks','boot_id')},'process_unchanged':True,'errors':[],
        'model_calls':0,'api_calls':0,'simulation_steps':0,'episodes':0,'worker_wall_seconds':10.,'backend':{'kind':'cuda','logical_device':'cuda:0',
        'physical_gpu':7,'physical_uuid':uuid,'actual_uuid':uuid,'actual_uuid_type':'builtins.str','actual_uuid_bytes_hex':None,
        'identity_diagnostic':{'status':'matched','visible_device_count':1,'current_device':0,'cuda_visible_devices':'7'},'dtype_coverage':['torch.float32','torch.bfloat16']},'cases':[]}
    for dtype in ('torch.float32','torch.bfloat16'):
        for case in CASES:
            report['cases'].append({'dtype':dtype,'case':case,'accepted':True,'candidate_rows':16,'comparison':'native contiguous uint8; zero tolerance',
                'custom_boundary_derivative_verified':True,'production_projection_calls':16,'production_origin_reads':16,
                'invalid_inputs_rejected':['nonfinite','wrong_horizon'],'wrong_bounds_rejected':True,'zero_gradient':False,
                'interior_original_parity':True if case=='strict_interior' else None,
                'negative_controls_rejected':['projected_xyz','gradient_before','gradient_after','update_operand','model_output_after']})
    rr=put(tmp/'old-proof-report.json',report)
    final={'event':'completed','resource_id':rid,'kind':backend.KIND,'plan':pr,'report':rr,'process':cr,'cleanup_complete':True,'cost_measurement_complete':True,'gpu_process_wall_seconds':11.}
    tr=put(tmp/'old-proof-terminal.json',final)
    return put(tmp/'proof.json',{'schema':'n25-metered-tensor-proof-v1','accepted':True,'source':source,'runtime':rt,'plan':pr,'report':rr,'process':cr,'terminal':tr})


def complete_fixture(tmp,monkeypatch,disposition='promotion'):
    data,root,parent,objects,source,reverse=historical_fixture(tmp,monkeypatch)
    monkeypatch.setattr(sealer.subprocess,'check_output',lambda *a,**k:e.BASE+'\n')
    seal=sealer.build(data,root,cleanup=fake_cleanup)
    for (commit,path),b in objects.values.items():
        if commit==d.HISTORICAL:p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    target=root/d.DOC/'protocol-v1.md';target.parent.mkdir(parents=True);target.write_bytes((ACTUAL/d.DOC/'protocol-v1.md').read_bytes())
    monkeypatch.setattr(d,'ROOT',root)
    for module in (c,c.old,e,terminal,bridge,terminal.w,terminal.report,terminal.report.old_report,backend,audit_backend,reference):monkeypatch.setattr(module,'__file__',str(root/'scripts'/Path(module.__file__).name))
    run=root.parent/'variants/n25_actuator_clipped_rbf/infrastructure-continuation-v1';monkeypatch.setattr(c,'RUN_DIR',run)
    for name,file in (('SEAL','seal.json'),('PLAN','plan.json'),('PROTOCOL','protocol.md')):monkeypatch.setattr(c,name,run/file)
    c.PROTOCOL.parent.mkdir(parents=True,exist_ok=True);c.PROTOCOL.write_bytes((ACTUAL/'experiments/qd_ed_n25_continuation/protocol-v1.md').read_bytes())
    sealref=put(c.SEAL,seal);src=put(tmp/'new-source.json',source)
    refs={'old_source':data['references']['source'],'source':src,'seal':sealref}
    refs['seal_review']=put(run/'seal-review.json',{'schema':'n25-continuation-root-seal-review-v1','accepted':True,'seal':sealref,'protocol':e.ref(c.PROTOCOL),
        'original_disposition':'INVALID_OR_INTERRUPTED','history_is_metadata_attestation':True,'historical_unknowns':e.UNKNOWN,'gpu_authorized':False})
    delta=d.historical_sources(seal['original_source'],source,objects)
    b={'schema':'n25-continuation-source-bridge-v1','old_source':seal['original_source'],'new_source':source,**delta,
        'historical_backend_proof':seal['historical_backend_proof'],'new_numerical_preflight':False,
        'interpretation':'Historical5a proof is not generated by new commit; unchanged science/native arithmetic plus reviewed administrative route bridge.'}
    refs['source_bridge']=put(run/'bridge.json',b)
    refs['source_review']=put(run/'source-review.json',{'schema':'n25-continuation-source-runtime-review-v1','accepted':True,'source':source,'runtime':seal['runtime'],
        'protocol':e.ref(c.PROTOCOL),'seal':sealref,'root_seal_review':refs['seal_review'],'source_bridge':refs['source_bridge'],
        'historical_backend_proof':seal['historical_backend_proof'],'no_new_preflight':True,'gpu_authorized':False})
    refs['authority']=put(run/'authority.json',{'schema':'n25-continuation-authority-v1','cohort_id':c.COHORT,'source':source,'runtime':seal['runtime'],'protocol':e.ref(c.PROTOCOL),
        'seal':sealref,'final_review':refs['source_review'],'existing_budget_authority':json.loads(Path(seal['old_authority']['path']).read_text())['budget_authority'],
        'caps':c.CAPS,'limits':c.LIMITS,'old_gpu_seconds':e.OLD_SECONDS,'original_local_gpu_hours':22.,'remaining_local_gpu_hours':19.,'recorded_at':'synthetic','authority_interpretation':'synthetic','validation_authorized':False,'formal_authorized':False})
    plan={**parent,'source_commit':d.HISTORICAL,'code_files':source['files'],'episodes':c.rows(seal),
        'derived_from':seal['original_plan'],'n25_cohort':{'schema':'n25-continuation-audit-family-v1','worker_audit':c.WORKER_CONTRACT},
        'n25_infrastructure_continuation':{'schema':'n25-infrastructure-continuation-v1','cohort_id':c.COHORT,'protocol':e.ref(c.PROTOCOL),
        'seal':sealref,'final_review':refs['source_review'],'authority':refs['authority'],'limits':c.LIMITS,'historical_unknowns':e.UNKNOWN,'imports':18,'dispatchable':22}}
    n=10 if disposition=='futility' else 22;events=new_events(plan,n,wins=5 if disposition=='promotion' else 0)
    # materialize_new chooses its own path; normal aliases remain exact via copy/ref.
    pref,_,cells=materialize_new(tmp,plan,seal,events);c.PLAN.write_bytes(Path(pref['path']).read_bytes());refs['plan']=e.ref(c.PLAN)
    # Rebind final source and plan references to immutable intended plan path.
    for g in e.groups(events).values():
        f=g[-1];out=Path(f['output_dir']);cr=cells[f['episode_key']][0]['worker_context'];ctx=json.loads(Path(cr['path']).read_text());ctx['plan']=refs['plan'];nr=put(cr['path'],ctx)
        put(out/'eds_eval/in-worker-audit-start.json',{'schema':'n23-worker-start-v1','process':{k:json.loads((out/'process.json').read_text())[k] for k in ('pid','proc_start_ticks','boot_id')},'context':nr})
        rr=cells[f['episode_key']][0]['worker_receipt'];rec=json.loads(Path(rr['path']).read_text());rec.update(context=nr,plan=refs['plan']);newrr=put(rr['path'],rec)
        f['n23_worker_receipt']=newrr;tr=put(out/'attempt-result.json',f);cells[f['episode_key']][0].update(worker_context=nr,worker_receipt=newrr,attempt_result=tr)
    result=reporting.analyze(plan,seal,events,lambda row,ev:cells[row['episode_key']])
    result.update(plan=refs['plan'],source_bridge=refs['source_bridge'],reader={'path':str(root/'scripts/qd_ed_n25_cont_report.py'),'sha256':e.sha(root/'scripts/qd_ed_n25_cont_report.py')},ledger_snapshot=put(run/'new-ledger.json',events))
    newkeys=[x['episode_key'] for x in result['accepted_cells'][18:]];phase='rejected_numeric_futility' if disposition=='futility' else 'completed_all_forty_audited'
    status={'schema':'n25-continuation-supervisor-status-v1','status':phase,'cohort_id':c.COHORT,'plan':refs['plan'],'source_commit':d.HISTORICAL,'prefix_seal':sealref,
        'completed_keys':newkeys,'attempts':[g[-1] for g in e.groups(events).values()],
        'outcomes':[{'episode_key':g[-1]['episode_key'],'attempt_id':g[-1]['attempt_id'],'success':g[-1]['success']} for g in e.groups(events).values()],'protected_authorized':False,'dev_gate_promoted':result['dev_gate_promoted'],'counts_success':{a:result['counts'][a]['success'] for a in c.ARMS}}
    refs['status']=put(run/'status.json',status);result['terminal_status']={**refs['status'],'content':status}
    result['controller_evidence']={'consistent':True,'completed_keys':newkeys,'journal_accepted_keys':newkeys,'status_phase':phase}
    refs['result']=put(run/'result.json',result)
    refs['release']=put(run/'release.json',{'schema':'n25-continuation-execution-release-v1','plan':refs['plan'],'source_commit':d.HISTORICAL,'cohort_id':c.COHORT,
        'authority':refs['authority'],'seal':sealref,'episode_keys':[x['episode_key'] for x in plan['episodes']], 'limits':c.LIMITS,'physical_gpu':7,'one_launch':True,'validation_authorized':False,'formal_authorized':False})
    refs['controller']=put(run/'controller.json',{'schema':'n25-continuation-controller-process-v1','plan':refs['plan'],'release':refs['release'],'source_commit':d.HISTORICAL,
        'process':{'pid':600000,'proc_start_ticks':'1','boot_id':'test'}})
    # Historical terminal reader's __file__ remains the actual immutable source.
    rr=terminal.review_existing(result,plan,seal,events,e.Reader(terminal.metadata_inventory(result,events)),source,cleanup=fake_cleanup)
    rr.update(result=refs['result'],plan=refs['plan'],source=source,seal=sealref,ledger=result['ledger_snapshot'],controller=refs['controller'])
    refs['root_review']=put(run/'root-review.json',rr)
    att={'root_terminal_review':refs['root_review'],'all_matching_events_included':True,'protected_events_included':False,'collected_at':'2026-10-01T00:00:00Z',
        'source_ledger':{'path':str(tmp/'NEVER_READ_FULL_LEDGER'),'sha256':'f'*64},'collector':{'path':str(tmp/'NEVER_READ_COLLECTOR'),'sha256':'c'*64}}
    old_events=json.loads(Path(seal['old_ledger']['path']).read_text())
    refs['journal_projection']=put(run/'journal-projection.json',{'schema':'n25-current-dev-journal-projection-v1',**att,'original_events':old_events,'continuation_events':events,
        'original_event_count':len(old_events),'continuation_event_count':len(events)})
    proof=json.loads(Path(seal['historical_backend_proof']['path']).read_text());final=json.loads(Path(proof['terminal']['path']).read_text());resource=[{**final,'event':v} for v in ('reserved','dispatched','completed')]
    refs['resource_projection']=put(run/'resource-projection.json',{'schema':'n25-current-resource-projection-v1',**att,'resource_id':final['resource_id'],'resource_kind':backend.KIND,'event_count':3,'events':resource})
    files=[e.ref(p) for p in tmp.rglob('*') if p.is_file() and p.suffix in {'.json','.jsonl','.txt'} and not p.is_relative_to(root)]
    return {'schema':'n25-logical-dev-evidence-input-v1','root_authorized':True,'owning_root':str(root),'references':refs,'files':files},objects
