#!/usr/bin/env python3
"""One released tensor-only child; no model, simulator, provider or episode."""
import argparse,ast,copy,json,logging,os,sys,time
from pathlib import Path
from types import SimpleNamespace,MethodType
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts import qd_ed_n23_worker as w


def pure_projection(root,origin):
    """Compile exact frozen numerical methods, not their environment/model modules."""
    import __future__
    import numpy as np
    import torch
    scope={'torch':torch,'np':np,'log':logging.getLogger(__name__),
           'RDT_GUIDED_ACTION_INDICES':(39,40,41,42,43,44,10)}
    origin_calls=[]
    def pose():
        origin_calls.append(1);return SimpleNamespace(position=origin.numpy())
    adapter=SimpleNamespace(get_ee_pose_world=pose,_decision_evidence=None)
    steer=SimpleNamespace(_adapter=adapter,_action_chunk_horizon=8,_increment_compute=lambda *a:None)
    for file,cls,names,obj in (
      ('core/env_adapters/libero_adapter.py','LiberoAdapter',('delta_actions_to_ee_trajectory',),adapter),
      ('core/rdt_policy_steer.py','RDTSteerPolicy',('_decode_rdt_actions_for_guidance','_rdt_sample_to_trajectory_3d','_compute_diversity_gradient'),steer)):
        tree=ast.parse((Path(root)/file).read_text())
        classes=[n for n in tree.body if isinstance(n,ast.ClassDef)]
        # The exact named methods uniquely select the frozen policy class.
        matched=[n for n in classes if all(any(isinstance(m,ast.FunctionDef) and m.name==name for m in n.body) for name in names)]
        w.require(len(matched)==1,'N27 numerical method source ambiguous')
        for name in names:
            method=next(n for n in matched[0].body if isinstance(n,ast.FunctionDef) and n.name==name)
            exec(compile(ast.Module(body=[method],type_ignores=[]),file,'exec',flags=__future__.annotations.compiler_flag),scope)
            setattr(obj,name,MethodType(scope[name],obj))
    steer.origin_calls=origin_calls
    return steer


def check_case(case,dtype,layout,backend,root=ROOT):
    import torch
    from core.qd_actuator_clipped_rbf import clipped_rbf_gradient,applied_evidence
    from core.qd_clean_output_rbf import geometry_input,bind_input_evidence,CLEAN_SOURCE
    from core.qd_feasible_ray_rbf import step,observe
    from scripts.qd_ed_n27_reference import fixed_case,audit_witness,exact,reconstruct,with_layout,LAYOUTS
    values,origins=fixed_case(case,dtype,'contiguous')
    # Construct AFTER transfer: .to() need not preserve a non-dense sliced backing.
    clean=with_layout(backend.native(values),layout)
    noisy=torch.full_like(clean,-.375);steer=pure_projection(root,origins[0])
    profile=w.read_ref({'path':str(Path(root)/'configs/qd_ed_final/candidate_n27.json'),
                       'sha256':w.sha(Path(root)/'configs/qd_ed_final/candidate_n27.json')})['profile']
    cfg=SimpleNamespace(**{**profile,'use_initial_cache':False,'save_initial_cache':False,
         'save_ed_cache':False,'initial_population_cache':None,'ed_population_cache':None})
    scheduler=SimpleNamespace(config={'prediction_type':'sample'})
    argument=geometry_input(noisy,clean,cfg,scheduler)
    w.require(argument is clean and argument.stride()==LAYOUTS[layout][0]
        and argument.storage_offset()==LAYOUTS[layout][1] and not exact(noisy,clean),'N27 clean object/layout selection failed')
    capture={};before=clean[:,:8,(39,40,41)].clone()
    gradient,row=clipped_rbf_gradient(argument,project=steer._rdt_sample_to_trajectory_3d,horizon=8,capture_out=capture)
    w.require(len(steer.origin_calls)==16,'N27 production projection/origin count changed')
    bind_input_evidence(row,cfg,scheduler)
    operand=-1.*20.*gradient[:,:,(39,40,41)]
    original_bytes=clean.clone();rng=torch.random.get_rng_state().clone()
    cuda_rng=torch.cuda.get_rng_state(clean.device).clone() if clean.is_cuda else None
    feasible,started=step(before,operand[:,:8,:],cfg,scheduler)
    clean[:,:8,(39,40,41)]=feasible.prefix
    mask=torch.ones_like(clean,dtype=torch.bool);mask[:,:8,(39,40,41)]=False
    w.require(exact(clean[mask],original_bytes[mask]) and torch.equal(rng,torch.random.get_rng_state())
        and (cuda_rng is None or torch.equal(cuda_rng,torch.cuda.get_rng_state(clean.device))),'N27 tail/mask/RNG changed')
    after=clean[:,:8,(39,40,41)].clone()
    capture.update(update_operand=operand[:,:8,:].clone(),model_output_before=before,model_output_after=after)
    applied_evidence(row,masked=gradient,update=operand,phase='initial',iteration=-1,step=0,timestep=4)
    observe(row,before,after,operand[:,:8,:],feasible.alpha,started)
    metadata={'call':row};result=audit_witness(capture,metadata,backend)
    # Restore only the fixed synthetic fixture; no second live origin acquisition for the candidate witness.
    original=with_layout(backend.native(values),layout)
    if case=='strict_interior':
        independent=reconstruct(before,backend.native(origins),input_stride=list(original.stride()),clipped=False)
        w.require(exact(capture['gradient_after'],independent['gradient_after']),
                  'N27 strict interior independent absolute-RBF parity failed')
    boundary=(before<=-1)|(before>=1)
    w.require(torch.count_nonzero(capture['gradient_before'][boundary])==0,'N27 custom boundary derivative differs')
    rejected=[]
    for name in ('input_xyz','projected_xyz','gradient_before','gradient_after','update_operand','model_output_before','model_output_after'):
        bad={k:v.clone() for k,v in capture.items()};value=bad[name]
        value[0,0,0]=torch.nextafter(value[0,0,0],torch.tensor(float('inf'),dtype=value.dtype,device=value.device))
        try:audit_witness(bad,metadata,backend)
        except ValueError:rejected.append(name)
    w.require(len(rejected)==7,'N27 finite-element corruption accepted')
    signed={k:v.clone() for k,v in capture.items()}
    signed['input_xyz'][0,0,0]=0.;signed['model_output_before'][0,0,0]=-0.
    signed_rejected=False
    try:audit_witness(signed,metadata,backend)
    except ValueError:signed_rejected=True
    w.require(signed_rejected,'N27 signed-zero source corruption accepted')
    source_rejected=[]
    for prediction in (None,'epsilon','v_prediction'):
        try:geometry_input(noisy,original,cfg,SimpleNamespace(config={'prediction_type':prediction}))
        except ValueError:source_rejected.append(prediction)
    w.require(source_rejected==[None,'epsilon','v_prediction'],'N27 sample-only gate differs')
    wrong=dict(row);wrong['input_source']='noisy_sample';wrong_source=False
    try:audit_witness(capture,{'call':wrong},backend)
    except ValueError:wrong_source=True
    w.require(wrong_source,'N27 wrong source tag accepted')
    input_rejected=[];previous_calls=len(steer.origin_calls)
    for name in ('nonfinite','wrong_horizon'):
        bad=original.clone()
        if name=='nonfinite':bad[0,0,39]=float('nan')
        try:clipped_rbf_gradient(bad,project=steer._rdt_sample_to_trajectory_3d,horizon=7 if name=='wrong_horizon' else 8)
        except ValueError:input_rejected.append(name)
    w.require(input_rejected==['nonfinite','wrong_horizon'] and len(steer.origin_calls)==previous_calls,
              'N27 invalid input not rejected before projection')
    backend.synchronize()
    return {'case':case,'dtype':str(dtype),'layout':layout,'input_stride':list(original.stride()),
        'synthetic_storage_offset':original.storage_offset(),'accepted':True,'candidate_rows':16,
        'comparison':'native contiguous uint8; zero tolerance','interior_original_parity':True if case=='strict_interior' else None,
        'feasible_ray_verified':True,'tail_mask_rng_verified':True,'rng_scope':'cpu_and_assigned_cuda' if clean.is_cuda else 'cpu_only','clean_object_selection_verified':True,'clean_input_binding_verified':True,
        'custom_boundary_derivative_verified':True,'production_projection_calls':16,'production_origin_reads':16,
        'invalid_inputs_rejected':input_rejected,'sample_only_negative_controls':source_rejected,
        'wrong_source_rejected':wrong_source,'signed_zero_rejected':signed_rejected,
        'zero_gradient':result['zero_gradient'],'negative_controls_rejected':rejected}


def child(plan_path):
    started=time.perf_counter()
    from scripts import qd_ed_n27_backend as b
    plan=w.read_ref({'path':str(Path(plan_path).resolve()),'sha256':w.sha(plan_path)})
    w.require(os.environ.get('N27_PREFLIGHT_PARENT_PID')==str(os.getppid())
        and os.environ.get('N27_PREFLIGHT_RESOURCE_ID')==plan['resource_id'],'N27 preflight child lacks metered parent')
    w.verify_source(ROOT,plan['source']);runtime=w.read_ref(plan['runtime'])
    b.validate_plan(plan,ROOT,check_authority=True)
    identity=w.process_identity()
    report={'schema':'n27-tensor-arithmetic-report-v1','resource_id':plan['resource_id'],
        'plan':{'path':str(Path(plan_path).resolve()),'sha256':w.sha(plan_path)},'source':plan['source'],'runtime':plan['runtime'],
        'process':identity,'accepted':False,'cases':[],'errors':[],'model_calls':0,'api_calls':0,'simulation_steps':0,'episodes':0}
    try:
        from scripts.qd_ed_audit_backend import create_backend
        from scripts.qd_ed_n27_reference import CASES,DTYPES,LAYOUTS
        backend=create_backend('cuda',binding=w.cuda_binding(runtime))
        for dtype in DTYPES:
            for case in CASES:
                for layout in LAYOUTS:report['cases'].append(check_case(case,dtype,layout,backend))
        backend.synchronize();report['backend']=backend.report()
        w.verify_source(ROOT,plan['source']);w.read_ref(plan['runtime'])
        report['accepted']=True
    except BaseException as exc:
        report['errors'].append({'type':type(exc).__name__,'message':str(exc)})
        if hasattr(exc,'identity_diagnostic'):report['identity_diagnostic']=exc.identity_diagnostic
    finally:
        report['worker_wall_seconds']=time.perf_counter()-started
        report['process_unchanged']=w.process_identity()==identity
        w.atomic_json(Path(plan['output_dir'])/'report.json',report)
    return 0 if report['accepted'] and report['process_unchanged'] else 2


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',type=Path,required=True)
    raise SystemExit(child(parser.parse_args().plan))
