import copy,json,os,subprocess
from pathlib import Path
from contextlib import nullcontext
from types import SimpleNamespace
import pytest
import torch
from scripts import qd_ed_n27_backend as b,qd_ed_n27_contract as c,qd_ed_n23_worker as w,qd_ed_final_runner as r
from scripts import qd_ed_n27_preflight as child,qd_ed_n27_bridge as bridge
from scripts.qd_ed_n27_reference import CASES,LAYOUTS
from scripts.qd_ed_audit_backend import create_backend
from test_n27_controller import write,rows,triplet,state

@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
@pytest.mark.parametrize('case',CASES)
@pytest.mark.parametrize('layout',LAYOUTS)
def test_actual_preflight_numerical_path_on_cpu(case,dtype,layout):
    result=child.check_case(case,dtype,layout,create_backend('cpu'))
    assert result['accepted'] and len(result['negative_controls_rejected'])==7
    assert not torch.cuda.is_initialized()

@pytest.fixture
def proof_fixture(tmp_path,monkeypatch):
    root=tmp_path;source={'commit':'final','files':[],'sha256':'source'};runtime=write(root/'runtime.json',{'gpu_mapping':{'physical_gpu':7}})
    for name,path in [('PLAN',root/'plan.json'),('AUTHORITY',root/'authority.json'),('REVIEW',root/'review.json')]:monkeypatch.setattr(b,name,path)
    monkeypatch.setattr(c,'RUN_DIR',root);monkeypatch.setattr(c,'BACKEND_PROOF',root/'proof.json');monkeypatch.setattr(c,'runtime_ref',lambda:runtime)
    monkeypatch.setattr(w,'verify_source',lambda *a:None);monkeypatch.setattr(b,'authority',lambda *a:write(root/'authority.json',{}))
    plan=b.build_plan(source,runtime,root,'CPU__n27_tensor_arithmetic_v1',authority_ref=b.authority());plan['frozen']=True;write(b.PLAN,plan)
    process={'pid':1,'proc_start_ticks':'100','boot_id':'boot','resource_id':plan['resource_id']};process_ref=write(root/'process.json',process)
    item={'accepted':True,'candidate_rows':16,'comparison':'native contiguous uint8; zero tolerance','custom_boundary_derivative_verified':True,
        'production_projection_calls':16,'production_origin_reads':16,'invalid_inputs_rejected':['nonfinite','wrong_horizon'],
        'feasible_ray_verified':True,'tail_mask_rng_verified':True,'rng_scope':'cpu_and_assigned_cuda','clean_object_selection_verified':True,'clean_input_binding_verified':True,'sample_only_negative_controls':[None,'epsilon','v_prediction'],
        'wrong_source_rejected':True,'signed_zero_rejected':True,'zero_gradient':False,'negative_controls_rejected':['input_xyz','projected_xyz','gradient_before','gradient_after','update_operand','model_output_before','model_output_after']}
    report={'schema':'n27-tensor-arithmetic-report-v1','accepted':True,'resource_id':plan['resource_id'],'source':source,'runtime':runtime,
        'plan':c.ref(b.PLAN),'process':{k:process[k] for k in ('pid','proc_start_ticks','boot_id')},'process_unchanged':True,'errors':[],
        'model_calls':0,'api_calls':0,'simulation_steps':0,'episodes':0,'worker_wall_seconds':2.,
        'cases':[{**item,'dtype':dtype,'case':case,'layout':layout,'input_stride':list(LAYOUTS[layout][0]),'synthetic_storage_offset':LAYOUTS[layout][1],'interior_original_parity':True if case=='strict_interior' else None}
                 for dtype in ('torch.float32','torch.bfloat16') for case in CASES for layout in LAYOUTS],
        'backend':{'kind':'cuda','logical_device':'cuda:0','physical_gpu':7,'physical_uuid':c.GPU7_UUID,'actual_uuid':c.GPU7_UUID[4:],
          'actual_uuid_type':'torch._C._CUuuid','actual_uuid_bytes_hex':c.GPU7_UUID[4:].replace('-',''),
          'identity_diagnostic':{'status':'matched','visible_device_count':1,'current_device':0,'cuda_visible_devices':'7'},
          'dtype_coverage':['torch.float32','torch.bfloat16']}}
    report_ref=write(root/'report.json',report)
    base={'resource_id':plan['resource_id'],'kind':b.KIND,'plan':c.ref(b.PLAN),'physical_gpu':7}
    terminal={**base,'event':'completed','cleanup_complete':True,'cost_measurement_complete':True,'report':report_ref,'process':process_ref,'gpu_process_wall_seconds':3.}
    resources=[{**base,'event':'reserved'},{**base,'event':'dispatched'},terminal]
    proof={'schema':'n27-metered-tensor-proof-v1','accepted':True,'source':source,'runtime':runtime,'plan':c.ref(b.PLAN),
        'report':report_ref,'process':process_ref,'terminal':write(root/'terminal.json',terminal)}
    write(c.BACKEND_PROOF,proof)
    return root,source,runtime,plan,process,report,resources,proof

@pytest.mark.parametrize('fault',['none','cpu','wrong_uuid','raw_missing','native_bytes','count','mask','dtype','fp32','missing_case','negative','process','time','source','zero_valid'])
def test_fixed_native_proof_gates(proof_fixture,fault):
    root,source,runtime,plan,process,report,resources,proof=proof_fixture
    if fault=='cpu':report['backend']['kind']='cpu'
    if fault=='wrong_uuid':report['backend']['physical_uuid']='GPU-other'
    if fault=='raw_missing':report['backend'].pop('actual_uuid')
    if fault=='native_bytes':report['backend']['actual_uuid_bytes_hex']='00'*16
    if fault=='count':report['backend']['identity_diagnostic']['visible_device_count']=2
    if fault=='mask':report['backend']['identity_diagnostic']['cuda_visible_devices']='3'
    if fault=='dtype':report['backend']['dtype_coverage']=['torch.bfloat16']
    if fault=='fp32':report['cases'][0]['accepted']=False
    if fault=='missing_case':report['cases'].pop()
    if fault=='negative':report['cases'][0]['negative_controls_rejected']=[]
    if fault=='process':report['process']['pid']=999
    if fault=='time':report['worker_wall_seconds']=121
    if fault=='source':report['source']={'commit':'wrong'}
    if fault=='zero_valid':
        for row in report['cases']:row['zero_gradient']=True
    if fault in {'none','zero_valid'}:b.validate_report(report,plan,process)
    else:
        with pytest.raises(ValueError):b.validate_report(report,plan,process)

@pytest.mark.parametrize('fault',['none','missing','duplicate','aborted','unsettled','cost','future_source'])
def test_settled_once_proof_and_same_dev_source(proof_fixture,fault):
    root,source,runtime,plan,process,report,resources,proof=proof_fixture
    if fault=='missing':resources=[]
    if fault=='duplicate':resources.insert(0,{**resources[0],'resource_id':'other'})
    if fault=='aborted':resources[-1]['event']='aborted'
    if fault=='unsettled':resources.pop()
    if fault=='cost':resources[-1]['gpu_process_wall_seconds']=161
    if fault=='future_source':source={**source,'commit':'changed'}
    if fault=='none':
        assert b.settled_proof(proof,resources,vars(r))==proof
        assert b.verify_proof(c.ref(c.BACKEND_PROOF),source,runtime,root)==proof
    elif fault=='future_source':
        with pytest.raises(ValueError):b.verify_proof(c.ref(c.BACKEND_PROOF),source,runtime,root)
    else:
        with pytest.raises(ValueError):b.settled_proof(proof,resources,vars(r))

@pytest.mark.parametrize('fault',['none','prior_reserved','prior_aborted','dev_reserved','inflight','hours','bucket','protected_attempts','state_cost','state_adoption'])
def test_resource_admission_no_retry_and_capacity(tmp_path,monkeypatch,fault):
    st=state();st['budget'].update(dispatched=0,gpu_hours_consumed=40.)
    snap=r.budget_snapshot([]);snap['gpu_hours_consumed']=40.;events=[];resources=[]
    monkeypatch.setattr(c,'require_budget_state',lambda *a:None);monkeypatch.setattr(c,'validate_runtime',lambda *a:None)
    monkeypatch.setattr(c,'BRIDGE',tmp_path/'bridge.json');write(c.BRIDGE,{})
    monkeypatch.setattr(c,'budget_authority',lambda:{'caps':c.BASE_CAPS});rt=write(tmp_path/'runtime.json',{})
    def auth(*a):
        if fault=='state_adoption':raise ValueError('not adopted')
    monkeypatch.setattr(b,'authority',auth)
    if fault=='prior_reserved':resources=[{'kind':b.KIND,'event':'reserved'}]
    if fault=='prior_aborted':resources=[{'kind':b.KIND,'event':'aborted'}]
    if fault=='dev_reserved':events=triplet(rows()[0],'a')[:1]
    if fault=='inflight':snap['gpu_healthcheck_inflight']=1
    if fault=='hours':snap['gpu_hours_consumed']=56.;st['budget']['gpu_hours_consumed']=56.
    if fault=='bucket':snap['by_bucket']['development']=c.BASE_CAPS['buckets']['development']-11
    if fault=='protected_attempts':snap['dispatched']=c.BASE_CAPS['attempts']-18-220+1;st['budget']['dispatched']=snap['dispatched']
    if fault=='state_cost':st['budget']['gpu_hours_consumed']=1.
    env={**vars(r),'budget_snapshot':lambda *a:snap}
    if fault=='none':b.admission(st,events,resources,env,{},rt,tmp_path,reservation_events=[{'event':'gpu_hour_reservations_changed','gpu_hour_reservations':c.BASE_CAPS['protected_gpu_hours']}])
    else:
        with pytest.raises(ValueError):b.admission(st,events,resources,env,{},rt,tmp_path,reservation_events=[{'event':'gpu_hour_reservations_changed','gpu_hour_reservations':c.BASE_CAPS['protected_gpu_hours']}])

@pytest.mark.parametrize('fault',['none','timeout','launch_error','bad_report','cleanup_error'])
def test_actual_resource_runner_charges_before_launch_cleanup_terminal(tmp_path,monkeypatch,fault):
    root=tmp_path;monkeypatch.setattr(c,'RUN_DIR',root);monkeypatch.setattr(c,'BACKEND_PROOF',root/'proof.json')
    monkeypatch.setattr(b,'PLAN',root/'plan.json');monkeypatch.setattr(b,'AUTHORITY',root/'auth.json');write(b.AUTHORITY,{})
    monkeypatch.setattr(b,'RELEASE',root/'release.json')
    source={'commit':'frozen','files':[],'sha256':'s'};rt=write(root/'runtime.json',{'gpu_mapping':{'physical_gpu':7}})
    monkeypatch.setattr(c,'runtime_ref',lambda:rt);monkeypatch.setattr(c,'source_paths',lambda *a:set())
    monkeypatch.setattr(w,'source_record',lambda *a:source);monkeypatch.setattr(b,'validate_plan',lambda *a,**k:None)
    monkeypatch.setattr(b,'admission',lambda *a,**k:None);monkeypatch.setattr(r,'locked',lambda *a,**k:nullcontext())
    monkeypatch.setattr(r,'read_state',lambda *a:{'run_name':'CPU'});events=[]
    monkeypatch.setattr(r,'read_events',lambda *a:copy.deepcopy(events));monkeypatch.setattr(r,'append_healthcheck_event',lambda root,e:events.append(e))
    monkeypatch.setattr(r,'gpu_admission',lambda **k:{});monkeypatch.setattr(r,'child_environment',lambda *a:{})
    monkeypatch.setattr(b,'settled_proof',lambda *a:None)
    write(b.RELEASE,{'schema':'n27-tensor-resource-release-v1','source':source,'runtime':rt,'authority':c.ref(b.AUTHORITY),'limits':b.LIMITS,'one_shot':True})
    cleaned=[];launched=[]
    def popen(argv,**kw):
        assert events[-1]['event']=='dispatched';launched.append(argv)
        if fault=='launch_error':raise OSError('synthetic launch')
        write(root/'arithmetic-preflight/worker/report.json',{'accepted':fault!='bad_report'})
        return SimpleNamespace(pid=os.getpid())
    monkeypatch.setattr(b.subprocess,'Popen',popen)
    def wait(*a,**k):
        if fault=='timeout':raise TimeoutError('bounded worker')
        return 0
    monkeypatch.setattr(r,'wait_exclusively',wait)
    def cleanup(p):
        cleaned.append(p)
        if fault=='cleanup_error':raise RuntimeError('synthetic cleanup')
    monkeypatch.setattr(r,'terminate_owned',cleanup)
    def verify(rep,*a):
        if not rep['accepted']:raise ValueError('native failure')
    monkeypatch.setattr(b,'validate_report',verify)
    if fault=='none':assert b.run(root=root)['accepted']
    else:
        with pytest.raises(ValueError,match='no retry'):b.run(root=root)
    assert len(launched)==len(cleaned)==1
    assert [e['event'] for e in events]==['reserved','dispatched','completed' if fault=='none' else 'aborted']
    assert events[-1]['gpu_process_wall_seconds']>=0 and events[-1]['episode_attempts']==0
    snap=r.budget_snapshot([],events)
    assert snap['dispatched']==0 and snap['by_bucket']['recovery']==0
    assert snap['gpu_hours_consumed']==snap['gpu_healthcheck_hours']==events[-1]['gpu_process_wall_seconds']/3600


@pytest.mark.parametrize('arm',c.ARMS)
@pytest.mark.parametrize('fault',['none','audit_failure','main_exit','receipt_mode'])
def test_same_process_worker_n27_route_and_no_supervisor_cuda(tmp_path,monkeypatch,arm,fault):
    from scripts import qd_ed_n27_native as native
    from scripts.qd_ed_audit_backend import AuditBackend
    root=tmp_path/'worktree';root.mkdir();monkeypatch.setattr(w,'ROOT',root)
    output=tmp_path/'artifact/attempts/one';episode=output/'eds_eval/decision_evidence/episode_000';episode.mkdir(parents=True)
    main=root/'main.py';main.write_text('raise SystemExit(7)\n' if fault=='main_exit' else 'pass\n')
    (episode/'bundle.pt').write_bytes(b'synthetic no-payload audit placeholder')
    write(episode/'status.json',{});(episode/'events.jsonl').write_text(json.dumps({'bundle':'bundle.pt'})+'\n')
    (output/'eds_eval/episode_compute.jsonl').write_text('{}\n')
    rt=write(tmp_path/'runtime.json',{'gpu_mapping':{'physical_gpu':7,'uuid':c.GPU7_UUID}})
    source={'commit':'synthetic','files':[],'sha256':'source'};row={**rows()[0],'profile':arm}
    plan={'frozen':True,'worktree':str(root),'artifact_root':str(tmp_path/'artifact'),'episodes':[row],
        'source_commit':'synthetic','code_files':[],'candidate_profiles':{'N26':{},'N27':{}},'n27_cohort':{'worker_audit':c.WORKER_CONTRACT},
        'runtime_manifest_path':rt['path'],'runtime_manifest_sha256':rt['sha256']}
    pr=write(tmp_path/'plan.json',plan);argv=[str(main),'literal=space value']
    context={'schema':'n23-metered-worker-context-v1','attempt_id':'one','episode_key':row['episode_key'],'profile':arm,
        'output_dir':str(output),'worktree':str(root),'main_argv':argv,'plan':pr,'runtime':rt,'source':source}
    contextpath=tmp_path/'context.json';write(contextpath,context);monkeypatch.setattr(w,'verify_source',lambda *a:None)
    calls=[]
    identity={**w.cuda_binding(w.read_ref(rt)),'physical_uuid':c.GPU7_UUID,'actual_uuid':c.GPU7_UUID,
        'actual_uuid_type':'builtins.str','actual_uuid_bytes_hex':None,'torch_version':'FAKE-CPU','cuda_version':'FAKE'}
    monkeypatch.setattr(w,'assigned_cuda_identity',lambda binding:(calls.append('identity') or identity))
    def backend(kind,**kwargs):
        calls.append(kind)
        return AuditBackend(torch.device('cpu'),{'kind':kind,'logical_device':'cuda:0' if kind=='cuda' else 'cpu',
            'physical_uuid':c.GPU7_UUID if kind=='cuda' else None,'torch_version':'FAKE-CPU','cuda_version':'FAKE'})
    monkeypatch.setattr(w,'create_backend',backend)
    def baseaudit(*args,arithmetic_backend):
        calls.append('base');arithmetic_backend.native(torch.ones(1))
        return {'accepted':True,'evidence_complete':True,'n23_arithmetic_backend':arithmetic_backend.report(),
            'n23_actuator_clipped_quality_audit':{'candidate_scores_verified':1}}
    monkeypatch.setattr(w.audit,'audit_episode',baseaudit)
    def newaudit(profile,out,report,backend):
        assert profile==arm and out==output;calls.append('n27')
        if fault=='audit_failure':raise ValueError('missing profile gate')
        return report
    monkeypatch.setattr(native,'audit_output',newaudit);monkeypatch.setattr(native,'from_output',lambda *a:({'guided_decisions':1},{}))
    if fault=='main_exit':
        with pytest.raises(SystemExit) as e:w.run_worker(contextpath,argv)
        assert e.value.code==7 and calls==[]
        receipt=w.read_ref(c.ref(output/'eds_eval/in-worker-audit-receipt.json'));assert not receipt['accepted']
        return
    if fault=='audit_failure':
        with pytest.raises(ValueError):w.run_worker(contextpath,argv)
        assert not w.read_ref(c.ref(output/'eds_eval/in-worker-audit-receipt.json'))['accepted'];return
    assert w.run_worker(contextpath,argv)==0
    assert calls==['identity','cuda' if arm in {'N26','N27'} else 'cpu','base','n27']
    process={**w.process_identity(),'attempt_id':'one'}
    if fault=='receipt_mode':
        path=output/'eds_eval/in-worker-audit-receipt.json';value=json.loads(path.read_text());value['audit_backend']['kind']='wrong';write(path,value)
        with pytest.raises(ValueError):w.verify_receipt(contextpath,process)
    else:assert w.verify_receipt(contextpath,process)['accepted']
    assert calls==['identity','cuda' if arm in {'N26','N27'} else 'cpu','base','n27']
    assert not torch.cuda.is_initialized()


@pytest.mark.parametrize('hours,protected_used,okay',[(46.75,0.,True),(46.750001,0.,False),(50.,3.25,True),(50.000001,3.25,False)])
def test_full_9_25_hours_plus_remaining_protected_boundary(tmp_path,monkeypatch,hours,protected_used,okay):
    st=state();st['budget'].update(dispatched=0,gpu_hours_consumed=hours)
    snap=r.budget_snapshot([]);snap['gpu_hours_consumed']=hours;snap['gpu_hours_by_bucket']['validation']=protected_used
    monkeypatch.setattr(c,'require_budget_state',lambda *a:None);monkeypatch.setattr(c,'validate_runtime',lambda *a:None)
    monkeypatch.setattr(c,'budget_authority',lambda:{'caps':c.BASE_CAPS});monkeypatch.setattr(b,'authority',lambda *a:None)
    rt=write(tmp_path/'runtime.json',{})
    args=(st,[],[],{**vars(r),'budget_snapshot':lambda *a:snap},{},rt,tmp_path)
    kw={'reservation_events':[{'event':'gpu_hour_reservations_changed','gpu_hour_reservations':c.BASE_CAPS['protected_gpu_hours']}]}
    if okay:b.admission(*args,**kw)
    else:
        with pytest.raises(ValueError):b.admission(*args,**kw)
