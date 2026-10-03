import json
from pathlib import Path
import pytest,torch
from scripts import qd_ed_n30_r1_contract as c,qd_ed_n23_worker as w
from n30_r1_synthetic import rows,write

@pytest.mark.parametrize('arm,fault',[(a,'none') for a in c.ARMS]+[('N30',f) for f in ('audit_failure','main_exit','receipt_mode')])
def test_same_process_worker_n30_route_and_no_supervisor_cuda(tmp_path,monkeypatch,arm,fault):
    from scripts import qd_ed_n30_native as native
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
        'source_commit':'synthetic','code_files':[],'candidate_profiles':{'N30':{}},'n30_r1_cohort':{'worker_audit':c.WORKER_CONTRACT},
        'runtime_manifest_path':rt['path'],'runtime_manifest_sha256':rt['sha256']}
    pr=write(tmp_path/'plan.json',plan);argv=[str(main),'literal=space value']
    context={'schema':'n23-metered-worker-context-v1','attempt_id':'one','episode_key':row['episode_key'],'profile':arm,
        'output_dir':str(output),'worktree':str(root),'main_argv':argv,'plan':pr,'runtime':rt,'source':source}
    contextpath=tmp_path/'context.json';write(contextpath,context);monkeypatch.setattr(w,'verify_source',lambda *a:None)
    calls=[]
    monkeypatch.setattr(w,'process_identity',lambda:{'pid':1234,'proc_start_ticks':567,'boot_id':'synthetic-boot'})
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
        assert profile==arm and out==output;calls.append('n30')
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
    assert calls==['identity','cpu','base','n30']
    process={**w.process_identity(),'attempt_id':'one'}
    if fault=='receipt_mode':
        path=output/'eds_eval/in-worker-audit-receipt.json';value=json.loads(path.read_text());value['audit_backend']['kind']='wrong';write(path,value)
        with pytest.raises(ValueError):w.verify_receipt(contextpath,process)
    else:assert w.verify_receipt(contextpath,process)['accepted']
    assert calls==['identity','cpu','base','n30']
    assert not torch.cuda.is_initialized()

