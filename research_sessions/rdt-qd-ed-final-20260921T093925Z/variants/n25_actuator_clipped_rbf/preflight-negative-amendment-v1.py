from pathlib import Path
p=Path('scripts/qd_ed_n25_preflight.py');s=p.read_text();s=s.replace("adapter=SimpleNamespace(get_ee_pose_world=lambda:SimpleNamespace(position=origin.numpy()),_decision_evidence=None)","origin_calls=[]\n    def pose():\n        origin_calls.append(1);return SimpleNamespace(position=origin.numpy())\n    adapter=SimpleNamespace(get_ee_pose_world=pose,_decision_evidence=None)")
s=s.replace("    return steer\n","    steer.origin_calls=origin_calls\n    return steer\n",1)
s=s.replace('from scripts.qd_ed_n25_reference import fixed_case,audit_witness,exact','from scripts.qd_ed_n25_reference import fixed_case,audit_witness,exact,reconstruct')
s=s.replace("    operand=-1.*20.*gradient", "    w.require(len(steer.origin_calls)==16,'N25 production projection/origin count changed')\n    operand=-1.*20.*gradient",1)
s=s.replace("    w.require(len(rejected)==5,'N25 negative control accepted')", """    w.require(len(rejected)==5,'N25 negative control accepted')
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
    w.require(wrong_bounds,'N25 wrong clipped geometry accepted')""")
s=s.replace("'custom_boundary_derivative_verified':True,'zero_gradient'", "'custom_boundary_derivative_verified':True,'production_projection_calls':16,'production_origin_reads':16,\n        'invalid_inputs_rejected':input_rejected,'wrong_bounds_rejected':wrong_bounds,'zero_gradient'")
p.write_text(s)
p=Path('scripts/qd_ed_n25_backend.py');s=p.read_text().replace("and row.get('custom_boundary_derivative_verified') is True and type", "and row.get('custom_boundary_derivative_verified') is True\n            and row.get('production_projection_calls')==16 and row.get('production_origin_reads')==16\n            and row.get('invalid_inputs_rejected')==['nonfinite','wrong_horizon'] and row.get('wrong_bounds_rejected') is True and type");p.write_text(s)
p=Path('tests/test_qd_ed_n25_backend.py');s=p.read_text().replace("'zero_gradient':False,'negative_controls_rejected'", "'production_projection_calls':16,'production_origin_reads':16,'invalid_inputs_rejected':['nonfinite','wrong_horizon'],\n        'wrong_bounds_rejected':True,'zero_gradient':False,'negative_controls_rejected'");p.write_text(s)
