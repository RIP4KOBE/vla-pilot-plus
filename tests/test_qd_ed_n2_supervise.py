"""CPU-only supervision tests; all files synthetic, no GPU/kernel/provider call."""
import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_qd_ed_n2_plan import r,n,load,fixture,ROOT,events

s=load('n2_test_supervisor',ROOT/n.SUPERVISOR)


def test_audit_occurs_after_original_terminal_and_never_rewrites_it(tmp_path):
    output=tmp_path/'attempt';(output/'eds_eval').mkdir(parents=True)
    outcome={'event':'valid','outcome_valid':True,'success':False,'output_dir':str(output)}
    saved=copy.deepcopy(outcome);calls=[]
    def original(*args,**kwargs):calls.append('terminal_accounted');return [outcome]
    fake=SimpleNamespace(run_plan=original,require=r.require,durable_json=r.durable_json)
    def audit(*args):
        assert calls==['terminal_accounted'];calls.append('audit')
        return {'accepted':True,'evidence_complete':True}
    with s.audited_calls(fake,audit):assert fake.run_plan('plan',episode_keys=['one'])==[saved]
    assert fake.run_plan is original and outcome==saved and calls==['terminal_accounted','audit']
    record=r.read_json(output/'eds_eval/decision-evidence-audit.json')
    assert record['wrapper_observation']['audit_wall_seconds']>=0
    assert record['wrapper_observation']['parent_ru_maxrss_after_kib']>=0


@pytest.mark.parametrize('report',[{'accepted':False,'evidence_complete':False},
                                    {'accepted':True,'evidence_complete':False},None])
def test_incomplete_or_broken_audit_stops_after_accounting_without_retry(tmp_path,report):
    output=tmp_path/'attempt';(output/'eds_eval').mkdir(parents=True)
    terminal={'event':'valid','outcome_valid':True,'success':False,'output_dir':str(output)}
    calls=[]
    def original(*args,**kwargs):calls.append('dispatch_once');return [terminal]
    fake=SimpleNamespace(run_plan=original,require=r.require,durable_json=r.durable_json)
    def audit(*args):
        if report is None:raise OSError('diagnostic failure')
        return dict(report)
    with pytest.raises(r.GateError,match='original terminal preserved'):
        with s.audited_calls(fake,audit):fake.run_plan('plan',episode_keys=['one'])
    assert calls==['dispatch_once'] and terminal['outcome_valid'] is True and fake.run_plan is original
    assert (output/'eds_eval/decision-evidence-audit.json').exists()


def test_invalid_original_terminal_does_not_run_audit_or_create_retry():
    calls=[]
    def original(*args,**kwargs):calls.append('terminal_invalid_accounted');raise r.GateError('original invalid gate')
    fake=SimpleNamespace(run_plan=original,require=r.require,durable_json=r.durable_json)
    with pytest.raises(r.GateError,match='original invalid'):
        with s.audited_calls(fake,lambda *_:calls.append('unexpected_audit')):
            fake.run_plan('plan',episode_keys=['one'])
    assert calls==['terminal_invalid_accounted'] and fake.run_plan is original


def test_native_and_current_boot_gpu_identity_prerequisites(fixture):
    root,plan,_,runtime,_,_,_=fixture
    artifact=Path(plan['artifact_root'])
    current={'physical_gpu':3,'uuid':'GPU-frozen','pci_bus_id':'00000000:61:00.0',
             'driver_version':'580.65.06','egl_device_index':0}
    runtime['gpu_mapping']=current
    native=artifact/'native.so';native.write_bytes(b'native bytes')
    dependencies=[{'path':str(native),'sha256':r.digest(native)}]
    r.durable_json(root/n.DEPENDENCIES,{'files':dependencies})
    def ref(name,value):
        path=artifact/(name+'.json');r.durable_json(path,value)
        return {'path':str(path),'sha256':r.digest(path)}
    prior=ref('runtime',{'gpu_mapping':current})
    contract={'boot_id':n.BOOT,'physical_gpu':3,'resource_id':'freshboot-proof',
        'runtime_manifest_path':prior['path'],'runtime_manifest_sha256':prior['sha256'],
        'runtime_inventory_sha256':plan['runtime_inventory_sha256'],'seed_plan_sha256':plan['seed_plan_sha256'],
        'dependency_sources':dependencies,'source_commit':'prior-engineering-source-not-N2'}
    cref=ref('health_contract',contract)
    health={'event':'completed','faults':[],'boot_id':n.BOOT,'physical_gpu':3,
        'resource_id':'freshboot-proof','contract_sha256':cref['sha256']}
    identity={'attempt_id':'prior-c0','pid':123,'proc_start_ticks':789,'boot_id':n.BOOT}
    refs={'health_contract':cref,'health_result':ref('health_result',health),
        'common_result':ref('common_result',{'event':'valid','outcome_valid':True,'success':False,
            'physical_gpu':3,'episode_key':'freshboot_c0_t00_20260923','attempt_id':'prior-c0'}),
        'common_process':ref('common_process',identity),
        'common_kernel':ref('common_kernel',{**identity,'physical_gpu':3,'kind':'episode','faults':[]})}
    plan['n2_cohort']['runtime_prerequisites']['references']=refs
    plan['n2_cohort']['health_resources'].append({'resource_id':'freshboot-proof','scope':'reused_prior'})
    plan['code_files']=[{'path':x['path'],'sha256':r.digest(root/x['path'])} for x in plan['code_files']]
    metadata='GPU-frozen, 00000000:61:00.0, 580.65.06'
    s.prerequisite(r,n,plan,runtime,root,boot=n.BOOT,gpu_metadata=metadata)
    with pytest.raises(r.GateError,match='boot changed'):
        s.prerequisite(r,n,plan,runtime,root,boot='rebooted',gpu_metadata=metadata)
    with pytest.raises(r.GateError,match='UUID/PCI/driver'):
        s.prerequisite(r,n,plan,runtime,root,boot=n.BOOT,gpu_metadata=metadata.replace('580.65.06','changed'))
    drift=copy.deepcopy(runtime);drift['gpu_mapping']['uuid']='another'
    with pytest.raises(r.GateError,match='current/prior GPU'):
        s.prerequisite(r,n,plan,drift,root,boot=n.BOOT,gpu_metadata=metadata)
    native.write_bytes(b'drifted dependency')
    with pytest.raises(r.GateError,match='frozen file changed'):
        s.prerequisite(r,n,plan,runtime,root,boot=n.BOOT,gpu_metadata=metadata)


def test_prior_audit_gate_cannot_be_bypassed_by_direct_runner(fixture):
    root,plan,_,runtime,_,resources,_=fixture
    first=plan['episodes'][0];journal=events(plan,runtime,first)
    audit=Path(journal[-1]['output_dir'])/'eds_eval/decision-evidence-audit.json'
    r.durable_json(audit,{'accepted':True,'evidence_complete':False})
    with pytest.raises(r.GateError,match='audit rejected'):
        n.admission(plan,runtime,plan['episodes'][1],journal,resources,root,r)


def test_frozen_hardware_reuses_exact_proof_without_probe_or_runtime_revision(tmp_path):
    from contextlib import nullcontext
    calls=[];proof={'resource_id':'same-proof'}
    mapping={'physical_gpu':3,'uuid':'same-GPU'}
    runtime={'gpu_mapping':mapping,'cuda_egl_probe':proof,'cuda_egl_verified':True}
    def unexpected(*args,**kwargs):raise AssertionError('no original hardware mutation/probe')
    fake=SimpleNamespace(locked=lambda *a,**kw:nullcontext(),validate_plan=lambda *a,**kw:None,
        require=r.require,read_events=lambda *a:[],gpu_admission=lambda **kw:calls.append('admission'))
    q=SimpleNamespace(bind_plan=unexpected,pending_gate=lambda *a:None,current_metadata=lambda *a,**kw:mapping,
        same_mapping=lambda a,b:a==b,find_probe=lambda *a,**kw:proof,
        reservation_admission=lambda *a:calls.append('reservation'))
    with s.frozen_hardware(fake,q):
        result=q.bind_plan('plan',{},runtime,mapping,{},'events',root=tmp_path)
        assert result==(Path('plan'),{},runtime) and calls==['reservation','admission']
        q.find_probe=lambda *a,**kw:None
        with pytest.raises(r.GateError,match='no automatic probe'):
            q.bind_plan('plan',{},runtime,mapping,{},'events',root=tmp_path)
    assert q.bind_plan is unexpected
