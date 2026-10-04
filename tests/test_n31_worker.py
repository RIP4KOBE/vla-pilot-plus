"""Exact generic worker dispatch and one real on-disk synthetic evidence episode."""
import json,copy
from pathlib import Path
import pytest,torch
from scripts import qd_ed_n31_contract as c,qd_ed_n23_worker as w,qd_ed_final_runner as r
from test_n31_controller import write
from test_n31_admission import frozen
from test_n31_native import episode,_patch_core_imports,stub_adapter,mock_batch


def context_fixture(frozen,monkeypatch,arm):
    path,plan,rt,st,calls=frozen;root=Path(plan['worktree'])
    _,manifest,_=r.validate_plan(path,root=root)
    row=next(row for row in plan['episodes'] if row['profile']==arm)
    command,output=r.build_command(plan,manifest,rt,row,'synthetic-'+arm)
    context={'schema':'n23-metered-worker-context-v1','attempt_id':output.name,'episode_key':row['episode_key'],'profile':arm,
        'output_dir':str(output),'worktree':str(root),'main_argv':command[1:],'plan':c.ref(path),
        'runtime':{'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']},
        'source':{'commit':plan['source_commit'],'files':plan['code_files'],'sha256':'synthetic'}}
    monkeypatch.setattr(w,'ROOT',root);monkeypatch.setattr(w,'verify_source',lambda *a:None)
    monkeypatch.setattr(r,'__file__',str(root/'scripts/qd_ed_final_runner.py'))
    return context,output


@pytest.mark.parametrize('arm',['C0','Q0','N31'])
def test_actual_worker_route_exact_profile_even_zero_guided(frozen,monkeypatch,arm):
    context,output=context_fixture(frozen,monkeypatch,arm)
    assert w.validate_context(context,context['main_argv'])[1]==output
    bad=copy.deepcopy(context)
    bad['main_argv']=[arg for arg in bad['main_argv'] if not arg.startswith('main.eds_config.qd_archive_mode=')]
    bad['main_argv'].append('main.eds_config.qd_archive_mode='+('grid_archive' if arm=='C0' else 'none'))
    with pytest.raises(ValueError,match='exact arm command'):w.validate_context(bad,bad['main_argv'])


def test_disk_recorder_generic_native_same_worker_receipt(frozen,tmp_path,monkeypatch,stub_adapter,mock_batch):
    from scripts.qd_ed_audit_backend import AuditBackend
    context,output=context_fixture(frozen,monkeypatch,'N31');ctx=tmp_path/'worker-context.json';write(ctx,context)
    identity={'pid':1234,'proc_start_ticks':567,'boot_id':'synthetic-boot'}
    monkeypatch.setattr(w,'process_identity',lambda:identity)
    binding=w.cuda_binding(w.read_ref(context['runtime']))
    cuda={**binding,'physical_uuid':c.GPU7_UUID,'actual_uuid':c.GPU7_UUID,'actual_uuid_type':'builtins.str',
        'actual_uuid_bytes_hex':None,'torch_version':'FAKE-CPU','cuda_version':'FAKE'}
    monkeypatch.setattr(w,'assigned_cuda_identity',lambda _:cuda)
    def backend(kind,**kw):
        assert kind=='cpu'
        return AuditBackend(torch.device('cpu'),{'kind':'cpu','logical_device':'cpu','physical_uuid':None,'torch_version':'FAKE-CPU','cuda_version':'FAKE'})
    monkeypatch.setattr(w,'create_backend',backend)
    def main_stub(*args,**kwargs):
        output.mkdir(parents=True,exist_ok=True)
        episode(output,monkeypatch,stub_adapter,mock_batch,disk=True)
    monkeypatch.setattr(w.runpy,'run_path',main_stub)
    assert w.run_worker(ctx,context['main_argv'])==0
    result=w.verify_receipt(ctx,{**identity,'attempt_id':context['attempt_id']})
    assert result['accepted'] and result['n31_capture_dwell_audit']['opportunities_verified']==10
    receipt=json.loads((output/'eds_eval/in-worker-audit-receipt.json').read_text())
    assert receipt['n31_native_counts']['other15_commitments_verified']==10 and receipt['audit_backend']['kind']=='cpu'
    assert not torch.cuda.is_initialized()
    # Receipt gate/scalar checks reconsume JSON, not arithmetic or tensor replay.
    receipt['n31_native_counts']['guided_decisions']=0;write(output/'eds_eval/in-worker-audit-receipt.json',receipt)
    with pytest.raises(ValueError):w.verify_receipt(ctx,{**identity,'attempt_id':context['attempt_id']})
