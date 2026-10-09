"""Pinned 52a87af CPU parity: controls and old proposals do not allocate N35 memory."""
import ast
import subprocess
import textwrap
from types import MethodType
import pytest
import torch
from test_n31_capture_dwell_integration import make,packet,runtime_cfg,_patch_core_imports,stub_adapter,mock_batch
from scripts.qd_ed_n31_reference import same

BASE='52a87af0bf11f95b21ce17aba456dc98944d9774'

@pytest.mark.parametrize('arm',['C0','Q0','N34'])
@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_pinned_source_parity(monkeypatch,stub_adapter,mock_batch,arm,dtype):
    import core.rdt_policy_steer as module
    source=subprocess.check_output(['git','show',BASE+':core/rdt_policy_steer.py'],text=True)
    cls=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='RDTSteer')
    outputs=[]
    for old in (True,False):
        p,provider,conf,rec,counts,_=make('on' if arm=='N31' else 'off',stub_adapter,monkeypatch,dtype)
        if arm=='C0':conf.update(qd_archive_mode='none',qd_parent_sampling='uniform_cells')
        if arm=='N32':conf.update(archive_eligible_capture_mode='archive_eligible_capture_v1',
            n32_runtime_binding={'task_id':0,'source_commit':BASE,'run_id':'CPU-parity'})
        if arm=='N34':conf.update(observed_jaw_approach_mode='observed_jaw_approach_v1',
            n34_runtime_binding={'task_id':0,'source_commit':BASE,'run_id':'CPU-parity'})
        if old:
            for name in ('select_action','_eds_guided_denoise_loop','_resolve_eds_config_with_reference_defaults'):
                node=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==name)
                ns=dict(vars(module));exec(compile(textwrap.dedent(ast.get_source_segment(source,node)),'<pinned52a8>', 'exec'),ns)
                monkeypatch.setattr(p,name,MethodType(ns[name],p))
        ctx=packet(.01);ctx['task_id']=0
        torch.manual_seed(310)
        actions=p.select_action(mock_batch,generate_new_chunk=True,use_guidance=True,keypoints=ctx['keypoints'].numpy(),
            guidance_fns=[provider],guidance_type='eds',eds_config=runtime_cfg(conf),global_step=0,current_stage=1,capture_dwell_context=ctx)
        assert not hasattr(p,'_closure_intent') and not hasattr(p,'_nonprogress_tangent')
        assert not any(e['event'].startswith(('n35_','n36_')) for e in rec.events)
        canonical=[e['candidates'] for e in rec.events if e['event']=='canonical_candidate_batch']
        outputs.append((actions,torch.random.get_rng_state(),p.get_episode_compute_counters(),canonical,counts['origins']))
    a,b=outputs
    assert same(a[0],b[0]) and torch.equal(a[1],b[1]) and a[2]==b[2] and a[4]==b[4]
    assert len(a[3])==len(b[3])==11 and all(same(x,y) for x,y in zip(a[3],b[3]))
