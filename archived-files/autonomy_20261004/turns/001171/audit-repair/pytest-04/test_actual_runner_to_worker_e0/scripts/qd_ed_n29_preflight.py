#!/usr/bin/env python3
"""Released N29 24-case tensor-only proof; no model/provider/environment imports."""
import argparse,copy,json,os,sys,time
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts import qd_ed_n23_worker as w
from scripts.qd_ed_n27_preflight import pure_projection


def check_case(case,dtype,layout,backend,root=ROOT):
    import torch
    from core.qd_actuator_clipped_rbf import clipped_rbf_gradient
    from core.qd_population_relative_rbf import mutate,TrustWitness as ParentWitness
    from scripts.qd_ed_n29_reference import fixed_case,audit_witness,exact,reconstruct,with_layout,LAYOUTS
    values,origins=fixed_case(case,dtype,'contiguous');parent=with_layout(backend.native(values),layout)
    steer=pure_projection(root,origins[0]);profile=json.loads((Path(root)/'configs/qd_ed_final/candidate_n29.json').read_text())['profile']
    cfg=SimpleNamespace(**{**profile,'use_initial_cache':False,'save_initial_cache':False,'save_ed_cache':False,
         'initial_population_cache':None,'ed_population_cache':None})
    scheduler=SimpleNamespace(config={'prediction_type':'sample'});saved=[]
    class Recorder:
        def record(self,event,**kw):saved.append((event,kw));return len(saved)
    witness=ParentWitness();witness.begin(Recorder())
    def gradient(x,descriptor_mode,descriptor_cfg,**kw):
        w.require(x is parent,'N29 parent object replaced before geometry')
        return clipped_rbf_gradient(x,project=steer._rdt_sample_to_trajectory_3d,horizon=8,**kw)
    before=parent.clone();rng=torch.random.get_rng_state().clone()
    cuda_rng=torch.cuda.get_rng_state(parent.device).clone() if parent.is_cuda else None
    row=mutate(parent,cfg=cfg,scheduler=scheduler,compute_gradient=gradient,mask_gradient=lambda g:g,
        witness=witness,iteration=0,parent_allocation_sequence=1)
    witness.observe_renoise_input(parent,3)
    mask=torch.ones_like(parent,dtype=torch.bool);mask[:,:8,(39,40,41)]=False
    w.require(exact(parent[mask],before[mask]) and torch.equal(rng,torch.random.get_rng_state())
        and (cuda_rng is None or torch.equal(cuda_rng,torch.cuda.get_rng_state(parent.device))),'N29 tail/mask/RNG changed')
    capture=saved[0][1]['tensors'];metadata=saved[0][1]['metadata'];boundary=saved[1][1]
    w.require(saved[0][0]=='n29_rbf_witness' and saved[1][0]=='n29_parent_renoise_input'
        and exact(boundary['prefix'],capture['parent_offspring_after']) and boundary['metadata']['same_tensor_object_verified'] is True,
        'N29 synthetic boundary observer binding differs')
    w.require(len(steer.origin_calls)==16 and parent.stride()==LAYOUTS[layout][0]
        and parent.storage_offset()==LAYOUTS[layout][1],'N29 projector/layout changed')
    result=audit_witness(capture,metadata,backend)
    if case=='strict_interior':
        raw=reconstruct(capture['input_xyz'],backend.native(origins),input_stride=list(parent.stride()),clipped=False)
        w.require(exact(capture['gradient_after'],raw['gradient_after']),'N29 interior geometry differs')
    unsupported=(capture['input_xyz']<=-1)|(capture['input_xyz']>=1)
    w.require(torch.count_nonzero(capture['gradient_before'][unsupported])==0,'N29 custom derivative support differs')
    rejected=[]
    for name in ('input_xyz','projected_xyz','gradient_before','gradient_after','update_operand','parent_offspring_before','parent_offspring_after','scaled_operand','beta','radius','operand_norms'):
        bad={k:v.clone() for k,v in capture.items()};v=bad[name]
        flat=v.reshape(-1);flat[0]=torch.nextafter(flat[0],torch.tensor(float('inf'),dtype=v.dtype,device=v.device))
        try:audit_witness(bad,metadata,backend)
        except ValueError:rejected.append(name)
    w.require(len(rejected)==11,'N29 finite corruption accepted')
    bad={k:v.clone() for k,v in capture.items()};bad['input_xyz'][0,0,0]=0.;bad['parent_offspring_before'][0,0,0]=-0.
    signed=False
    try:audit_witness(bad,metadata,backend)
    except ValueError:signed=True
    w.require(signed,'N29 signed-zero corruption accepted')
    wrong=False
    try:audit_witness(capture,{'call':{**row,'input_source':'model_output_sample_v1'}},backend)
    except ValueError:wrong=True
    w.require(wrong,'N29 wrong-source corruption accepted')
    rejected_predictions=[]
    for prediction in (None,'epsilon','v_prediction'):
        try:mutate(parent,cfg=cfg,scheduler=SimpleNamespace(config={'prediction_type':prediction}),
            compute_gradient=lambda *a,**k:None,mask_gradient=None,witness=ParentWitness(),iteration=0,parent_allocation_sequence=1)
        except ValueError:rejected_predictions.append(prediction)
    w.require(rejected_predictions==[None,'epsilon','v_prediction'],'N29 sample-only gate differs')
    invalid=[];prior_calls=len(steer.origin_calls)
    for name in ('nonfinite','wrong_horizon'):
        bad=parent.clone()
        if name=='nonfinite':bad[0,0,39]=float('nan')
        try:clipped_rbf_gradient(bad,project=steer._rdt_sample_to_trajectory_3d,horizon=7 if name=='wrong_horizon' else 8)
        except ValueError:invalid.append(name)
    w.require(invalid==['nonfinite','wrong_horizon'] and len(steer.origin_calls)==prior_calls,'N29 invalid-input projection')
    # Fixed helper-domain cases complement wrapper RBF, whose identical rows
    # naturally produce zero raw gradient. No RNG/model/projector added.
    from core.qd_population_relative_trust import population_relative_trust_update
    from scripts.qd_ed_n29_reference import reconstruct_trust,bytes_equal
    hb=before[:,:8,[39,40,41]].clone();hp=torch.zeros_like(hb)
    hp[(hb>-1)&(hb<1)]=.5
    if case=='zero_operand':hp.zero_()
    elif case=='active_box':hp[(hb>-1)&(hb<1)]=2.
    actual=population_relative_trust_update(hb,hp);independent=reconstruct_trust(hb,hp)
    w.require(all(bytes_equal(getattr(actual,k),val) for k,val in independent.items()),'N29 independent helper semantic case differs')
    backend.synchronize()
    return {'case':case,'dtype':str(dtype),'layout':layout,'input_stride':list(parent.stride()),
        'synthetic_storage_offset':parent.storage_offset(),'accepted':True,'candidate_rows':16,
        'comparison':'native contiguous uint8; zero tolerance','interior_original_parity':True if case=='strict_interior' else None,
        'population_trust_verified':True,'helper_semantic_case_verified':True,'feasible_ray_verified':True,'tail_mask_rng_verified':True,'rng_scope':'cpu_and_assigned_cuda' if parent.is_cuda else 'cpu_only',
        'parent_object_selection_verified':True,'parent_input_binding_verified':True,'boundary_observer_binding_verified':True,
        'custom_boundary_derivative_verified':True,'production_projection_calls':16,'production_origin_reads':16,
        'invalid_inputs_rejected':invalid,'sample_only_negative_controls':rejected_predictions,'wrong_source_rejected':wrong,
        'signed_zero_rejected':signed,'zero_gradient':result['zero_gradient'],'negative_controls_rejected':rejected}


def child(plan_path):
    started=time.perf_counter()
    from scripts import qd_ed_n29_backend as b
    plan=w.read_ref({'path':str(Path(plan_path).resolve()),'sha256':w.sha(plan_path)})
    w.require(os.environ.get('N29_PREFLIGHT_PARENT_PID')==str(os.getppid())
        and os.environ.get('N29_PREFLIGHT_RESOURCE_ID')==plan['resource_id'],'N29 no metered parent')
    w.verify_source(ROOT,plan['source']);runtime=w.read_ref(plan['runtime']);b.validate_plan(plan,ROOT,check_authority=True)
    identity=w.process_identity();report={'schema':'n29-tensor-arithmetic-report-v1','resource_id':plan['resource_id'],
        'plan':{'path':str(Path(plan_path).resolve()),'sha256':w.sha(plan_path)},'source':plan['source'],'runtime':plan['runtime'],
        'process':identity,'accepted':False,'cases':[],'errors':[],'model_calls':0,'api_calls':0,'simulation_steps':0,'episodes':0}
    try:
        from scripts.qd_ed_audit_backend import create_backend
        from scripts.qd_ed_n29_reference import CASES,DTYPES,LAYOUTS
        backend=create_backend('cuda',binding=w.cuda_binding(runtime))
        for dtype in DTYPES:
            for case in CASES:
                for layout in LAYOUTS:report['cases'].append(check_case(case,dtype,layout,backend))
        backend.synchronize();report['backend']=backend.report();w.verify_source(ROOT,plan['source']);w.read_ref(plan['runtime']);report['accepted']=True
    except BaseException as exc:
        report['errors'].append({'type':type(exc).__name__,'message':str(exc)})
        if hasattr(exc,'identity_diagnostic'):report['identity_diagnostic']=exc.identity_diagnostic
    finally:
        report['worker_wall_seconds']=time.perf_counter()-started;report['process_unchanged']=w.process_identity()==identity
        w.atomic_json(Path(plan['output_dir'])/'report.json',report)
    return 0 if report['accepted'] and report['process_unchanged'] else 2


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',type=Path,required=True)
    raise SystemExit(child(parser.parse_args().plan))
