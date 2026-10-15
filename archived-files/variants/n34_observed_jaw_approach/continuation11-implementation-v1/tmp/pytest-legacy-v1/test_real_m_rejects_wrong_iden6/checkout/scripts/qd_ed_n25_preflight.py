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
        w.require(len(matched)==1,'N25 numerical method source ambiguous')
        for name in names:
            method=next(n for n in matched[0].body if isinstance(n,ast.FunctionDef) and n.name==name)
            exec(compile(ast.Module(body=[method],type_ignores=[]),file,'exec',flags=__future__.annotations.compiler_flag),scope)
            setattr(obj,name,MethodType(scope[name],obj))
    steer.origin_calls=origin_calls
    return steer


def check_case(case,dtype,backend,root=ROOT):
    import torch
    from core.qd_actuator_clipped_rbf import clipped_rbf_gradient,applied_evidence
    from scripts.qd_ed_n25_reference import fixed_case,audit_witness,exact,reconstruct
    x,origins,before=fixed_case(case,dtype);steer=pure_projection(root,origins[0])
    x=backend.native(x);before=backend.native(before);capture={}
    gradient,row=clipped_rbf_gradient(x,project=steer._rdt_sample_to_trajectory_3d,horizon=8,capture_out=capture)
    w.require(len(steer.origin_calls)==16,'N25 production projection/origin count changed')
    operand=-1.*20.*gradient[:,:8,(39,40,41)];after=before.clone();after+=operand
    capture.update(update_operand=operand,model_output_before=before,model_output_after=after)
    applied_evidence(row,masked=gradient,update=operand,phase='initial',iteration=-1,step=0,timestep=4)
    metadata={'call':row};result=audit_witness(capture,metadata,backend)
    if case=='strict_interior':w.require(exact(gradient,steer._compute_diversity_gradient(x)),'N25 interior original byte parity failed')
    values=x[:,:8,39:42];boundary=(values<=-1)|(values>=1)
    w.require(torch.count_nonzero(capture['gradient_before'][boundary])==0,'N25 custom boundary derivative differs')
    rejected=[]
    for name in ('projected_xyz','gradient_before','gradient_after','update_operand','model_output_after'):
        bad={k:v.clone() for k,v in capture.items()};value=bad[name]
        value[0,0,0]=torch.nextafter(value[0,0,0],torch.tensor(float('inf'),dtype=value.dtype,device=value.device))
        try:audit_witness(bad,metadata,backend)
        except ValueError:rejected.append(name)
    w.require(len(rejected)==5,'N25 negative control accepted')
    input_rejected=[];previous_calls=len(steer.origin_calls)
    for name in ('nonfinite','wrong_horizon'):
        bad=x.clone()
        if name=='nonfinite':bad[0,0,39]=float('nan')
        try:clipped_rbf_gradient(bad,project=steer._rdt_sample_to_trajectory_3d,horizon=7 if name=='wrong_horizon' else 8)
        except ValueError:input_rejected.append(name)
    w.require(input_rejected==['nonfinite','wrong_horizon'] and len(steer.origin_calls)==previous_calls,
        'N25 invalid input not rejected before projection')
    wrong={k:v.clone() for k,v in capture.items()}
    wrong['projected_xyz']=reconstruct(backend.native(capture['input_xyz']).clamp(-.125,.125),
                                       backend.native(capture['source_origins']))['projected_xyz']
    wrong_bounds=False
    try:audit_witness(wrong,metadata,backend)
    except ValueError:wrong_bounds=True
    w.require(wrong_bounds,'N25 wrong clipped geometry accepted')
    backend.synchronize()
    return {'case':case,'dtype':str(dtype),'accepted':True,'candidate_rows':16,
        'comparison':'native contiguous uint8; zero tolerance','interior_original_parity':True if case=='strict_interior' else None,
        'custom_boundary_derivative_verified':True,'production_projection_calls':16,'production_origin_reads':16,
        'invalid_inputs_rejected':input_rejected,'wrong_bounds_rejected':wrong_bounds,'zero_gradient':result['zero_gradient'],'negative_controls_rejected':rejected}


def child(plan_path):
    started=time.perf_counter()
    from scripts import qd_ed_n25_backend as b
    plan=w.read_ref({'path':str(Path(plan_path).resolve()),'sha256':w.sha(plan_path)})
    w.require(os.environ.get('N25_PREFLIGHT_PARENT_PID')==str(os.getppid())
        and os.environ.get('N25_PREFLIGHT_RESOURCE_ID')==plan['resource_id'],'N25 preflight child lacks metered parent')
    w.verify_source(ROOT,plan['source']);runtime=w.read_ref(plan['runtime'])
    b.validate_plan(plan,ROOT,check_authority=True)
    identity=w.process_identity()
    report={'schema':'n25-tensor-arithmetic-report-v1','resource_id':plan['resource_id'],
        'plan':{'path':str(Path(plan_path).resolve()),'sha256':w.sha(plan_path)},'source':plan['source'],'runtime':plan['runtime'],
        'process':identity,'accepted':False,'cases':[],'errors':[],'model_calls':0,'api_calls':0,'simulation_steps':0,'episodes':0}
    try:
        from scripts.qd_ed_audit_backend import create_backend
        from scripts.qd_ed_n25_reference import CASES,DTYPES
        backend=create_backend('cuda',binding=w.cuda_binding(runtime))
        for dtype in DTYPES:
            for case in CASES:report['cases'].append(check_case(case,dtype,backend))
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
