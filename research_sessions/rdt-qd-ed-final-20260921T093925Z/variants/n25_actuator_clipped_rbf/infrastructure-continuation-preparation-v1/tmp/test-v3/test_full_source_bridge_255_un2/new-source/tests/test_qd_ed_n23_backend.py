"""N23 backend plumbing CPU tests: no CUDA, model, provider or simulator calls."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
import torch

from scripts import qd_ed_audit_backend as backends
from scripts import qd_ed_n23_worker as worker
from scripts import qd_ed_n23_backend_preflight as preflight
from scripts import audit_decision_evidence as audit


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return {'path': str(path.resolve()), 'sha256': worker.sha(path)}


def commit(root):
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    subprocess.run(['git', 'add', '.'], cwd=root, check=True)
    subprocess.run(['git', '-c', 'user.name=CPU Fixture', '-c', 'user.email=fixture@example.invalid',
                    'commit', '-qm', 'synthetic worker fixture'], cwd=root, check=True)


@pytest.fixture
def owned_job(tmp_path, monkeypatch):
    root = tmp_path / 'worktree'; root.mkdir()
    output = tmp_path / 'artifacts/attempts/n23-synthetic-attempt'
    paths = worker.REQUIRED_SOURCE | preflight.EXTRA_SOURCE
    for name in paths:
        p = root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text('# synthetic CPU source\n')
    (root/'main.py').write_text('import sys, json\nfrom pathlib import Path\nPath(' + repr(str(tmp_path/'observed-argv.json')) + ').write_text(json.dumps(sys.argv))\n')
    commit(root)
    monkeypatch.setattr(worker, 'ROOT', root)
    monkeypatch.setattr(preflight, 'ROOT', root)
    runtime = write_json(tmp_path/'runtime.json', {'gpu_mapping': {'physical_gpu': 7, 'uuid': 'GPU-48473162-9548-1a19-04aa-ea86c5349187'}})
    source = worker.source_record(root, paths)
    row = {'profile': 'N23', 'episode_key': 't00_N23', 'split': 'dev', 'timeout_seconds': 1800}
    plan = {'worktree': str(root), 'artifact_root': str(tmp_path/'artifacts'), 'episodes': [row],
            'n23_cohort': {'worker_audit': worker.WORKER_CONTRACT}, 'code_files': source['files'],
            'source_commit': source['commit'], 'runtime_manifest_path': runtime['path'], 'runtime_manifest_sha256': runtime['sha256']}
    plan_ref = write_json(tmp_path/'plan.json', plan)
    command = [sys.executable, str(root/'main.py'), 'alpha=1', 'quoted=value with spaces']
    context = worker.build_context(plan_ref['path'], runtime['path'], row, output.name, output, command)
    context_path = tmp_path/'context.json'; write_json(context_path, context)
    episode = output/'eds_eval/decision_evidence/episode_000'; episode.mkdir(parents=True)
    (episode/'bundle_000001.pt').write_bytes(b'CPU-only fake audit input')
    write_json(episode/'status.json', {'bundles': 1})
    (episode/'events.jsonl').write_text(json.dumps({'bundle': 'bundle_000001.pt'})+'\n')
    (output/'eds_eval/episode_compute.jsonl').write_text('{}\n')
    calls = []
    def gpu_identity(binding):
        calls.append('identity')
        return {**binding, 'actual_uuid': binding['uuid'], 'physical_uuid': binding['uuid'], 'actual_uuid_type':'builtins.str','actual_uuid_bytes_hex':None,'device_name': 'synthetic',
                'cuda_visible_devices': '7', 'torch_version': 'cpu-fixture', 'cuda_version': 'synthetic'}
    def backend(kind, *, binding=None):
        calls.append(kind)
        # Explicit fake metadata for wrapper tests; all arithmetic stays CPU.
        meta = {'kind': kind, 'logical_device': 'cuda:0' if kind == 'cuda' else 'cpu',
                'physical_uuid': 'GPU-48473162-9548-1a19-04aa-ea86c5349187' if kind == 'cuda' else None,
                'torch_version': 'cpu-fixture', 'cuda_version': 'synthetic'}
        return backends.AuditBackend(torch.device('cpu'), meta)
    def fake_audit(episode, compute, *, arithmetic_backend):
        calls.append('audit'); arithmetic_backend.native(torch.zeros(1, dtype=torch.bfloat16))
        return {'accepted': True, 'evidence_complete': True,
                'n23_arithmetic_backend': arithmetic_backend.report(),
                'n23_actuator_clipped_quality_audit': {'candidate_scores_verified': 1}}
    monkeypatch.setattr(worker, 'assigned_cuda_identity', gpu_identity)
    monkeypatch.setattr(worker, 'create_backend', backend)
    monkeypatch.setattr(worker.audit, 'audit_episode', fake_audit)
    return SimpleNamespace(root=root, output=output, context=context, context_path=context_path,
                           plan=plan, plan_ref=plan_ref, row=row, runtime=runtime, command=command, calls=calls,
                           process={**worker.process_identity(), 'attempt_id': output.name})


def refresh_job(job, *, profile=None, main_text=None):
    if profile:
        job.context['profile'] = profile; job.plan['episodes'][0]['profile'] = profile
    if main_text is not None:
        (job.root/'main.py').write_text(main_text)
        commit(job.root)
    source=worker.source_record(job.root, [r['path'] for r in job.context['source']['files']])
    job.plan['code_files']=source['files']; job.plan['source_commit']=source['commit']
    job.context['source']=source; job.context['plan']=write_json(Path(job.plan_ref['path']),job.plan)
    write_json(job.context_path,job.context)


@pytest.mark.parametrize('profile', ['C0', 'Q0', 'N7', 'N23'])
def test_same_process_main_arguments_exit_and_bound_receipt(owned_job, profile):
    job=owned_job; refresh_job(job, profile=profile)
    original_argv=list(sys.argv); original_cwd=Path.cwd()
    wrapped=worker.wrapped_command(job.command,job.context_path)
    assert str(job.root/'main.py') in wrapped and wrapped[wrapped.index('--')+1:] == job.command[2:]
    assert worker.run_worker(job.context_path,job.command[1:]) == 0
    assert sys.argv == original_argv and Path.cwd() == original_cwd
    assert json.loads((job.root.parent/'observed-argv.json').read_text()) == job.command[1:]
    assert job.calls == ['identity', 'cuda' if profile == 'N23' else 'cpu', 'audit']
    report=worker.verify_receipt(job.context_path,job.process)
    assert report['accepted'] and not torch.cuda.is_initialized()


@pytest.mark.parametrize('failure', ['exit7', 'exit_string', 'exception', 'keyboard'])
def test_main_failure_preserved_and_never_followed_by_audit(owned_job, failure):
    job=owned_job
    texts={'exit7':'raise SystemExit(7)\n','exit_string':"raise SystemExit('original-main-message')\n",
           'exception':"raise RuntimeError('original')\n",'keyboard':'raise KeyboardInterrupt()\n'}
    refresh_job(job,main_text=texts[failure])
    error={'exit7':SystemExit,'exit_string':SystemExit,'exception':RuntimeError,'keyboard':KeyboardInterrupt}[failure]
    with pytest.raises(error) as caught: worker.run_worker(job.context_path,job.command[1:])
    if failure=='exit7': assert caught.value.code==7
    if failure=='exit_string': assert caught.value.code=='original-main-message'
    assert job.calls==[]
    receipt=json.loads((job.output/'eds_eval/in-worker-audit-receipt.json').read_text())
    assert not receipt['accepted'] and receipt['audit_report'] is None


def test_receipt_write_failure_cannot_hide_original_main_exit(owned_job,monkeypatch):
    job=owned_job;refresh_job(job,main_text='raise SystemExit(9)\n')
    original_write=worker.atomic_json
    def write_or_fail(path,value):
        if Path(path).name=='in-worker-audit-receipt.json':raise OSError('full')
        return original_write(path,value)
    monkeypatch.setattr(worker,'atomic_json',write_or_fail)
    with pytest.raises(SystemExit) as caught:worker.run_worker(job.context_path,job.command[1:])
    assert caught.value.code==9 and job.calls==[]


@pytest.mark.parametrize('fault',['rejected_audit','audit_exception','evidence_mutation'])
def test_audit_failure_is_failed_worker_with_retained_inputs(owned_job,monkeypatch,fault):
    job=owned_job;original=worker.audit.audit_episode
    def failed(*args,**kwargs):
        if fault=='audit_exception':raise RuntimeError('audit failure')
        report=original(*args,**kwargs)
        if fault=='rejected_audit':report['accepted']=False
        else:(job.output/'eds_eval/episode_compute.jsonl').write_text('mutated\n')
        return report
    monkeypatch.setattr(worker.audit,'audit_episode',failed)
    if fault=='rejected_audit':assert worker.run_worker(job.context_path,job.command[1:])==2
    else:
        with pytest.raises((RuntimeError,ValueError)):worker.run_worker(job.context_path,job.command[1:])
    assert (job.output/'eds_eval/decision_evidence/episode_000/bundle_000001.pt').exists()
    assert not json.loads((job.output/'eds_eval/in-worker-audit-receipt.json').read_text())['accepted']


@pytest.mark.parametrize('fault',['process','attempt','runtime','source','evidence','cpu_proof','report','context'])
def test_supervisor_rejects_stale_or_misbound_receipt_without_cuda(owned_job,fault):
    job=owned_job;worker.run_worker(job.context_path,job.command[1:])
    path=job.output/'eds_eval/in-worker-audit-receipt.json';receipt=json.loads(path.read_text())
    if fault=='process':receipt['process']['proc_start_ticks']='wrong'
    if fault=='attempt':receipt['attempt_id']='other'
    if fault=='runtime':receipt['worker_cuda']['actual_uuid']='GPU-other'
    if fault=='source':receipt['source']['sha256']='0'*64
    if fault=='evidence':(job.output/'eds_eval/episode_compute.jsonl').write_text('changed')
    if fault=='cpu_proof':receipt['audit_backend']['kind']='cpu'
    if fault=='report':Path(receipt['audit_report']['path']).write_text('{}')
    if fault=='context':receipt['context']['sha256']='0'*64
    write_json(path,receipt)
    job.calls.clear()
    with pytest.raises(ValueError):worker.verify_receipt(job.context_path,job.process)
    assert job.calls==[] and not torch.cuda.is_initialized()


@pytest.mark.parametrize('fault',['argv','uncommitted_source','committed_new_source','runtime','profile'])
def test_worker_invalid_context_fails_before_main(owned_job,fault):
    job=owned_job;argv=list(job.command[1:])
    if fault=='argv':argv.append('new=1')
    if fault in {'uncommitted_source','committed_new_source'}:
        (job.root/'main.py').write_text('# changed')
        if fault=='committed_new_source':commit(job.root)
    if fault=='runtime':Path(job.runtime['path']).write_text('{}')
    if fault=='profile':job.context['profile']='N22';write_json(job.context_path,job.context)
    with pytest.raises(ValueError):worker.run_worker(job.context_path,argv)
    assert job.calls==[] and not (job.root.parent/'observed-argv.json').exists()


def test_explicit_cpu_backend_transfers_exact_native_values_without_cuda():
    backend=backends.create_backend('cpu')
    value=torch.tensor([-.0,.25],dtype=torch.bfloat16)
    assert torch.equal(value.view(torch.uint8),backend.native(value).view(torch.uint8))
    assert backend.report()['dtype_coverage']==['torch.bfloat16']
    with pytest.raises(ValueError):backends.create_backend('auto')
    with pytest.raises(ValueError):backends.create_backend('cpu',binding={})
    assert not torch.cuda.is_initialized()


@pytest.mark.parametrize('fault',['visible','count','current','uuid','missing_uuid'])
def test_assigned_cuda_binding_rejects_mismatch_using_cpu_stubs(monkeypatch,fault):
    binding={'physical_gpu':7,'uuid':'GPU-48473162-9548-1a19-04aa-ea86c5349187','logical_device':'cuda:0'}
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES','5' if fault=='visible' else '7')
    monkeypatch.setattr(torch.cuda,'is_available',lambda:True)
    monkeypatch.setattr(torch.cuda,'device_count',lambda:2 if fault=='count' else 1)
    monkeypatch.setattr(torch.cuda,'current_device',lambda:1 if fault=='current' else 0)
    props=SimpleNamespace(name='fake',uuid='GPU-00000000-0000-0000-0000-000000000001' if fault=='uuid' else 'GPU-48473162-9548-1a19-04aa-ea86c5349187')
    if fault=='missing_uuid':del props.uuid
    monkeypatch.setattr(torch.cuda,'get_device_properties',lambda i:props)
    with pytest.raises(RuntimeError):backends.assigned_cuda_identity(binding)
    assert not torch.cuda.is_initialized()


def test_preflight_synthetic_native_cpu_and_deliberate_corruptions():
    backend=backends.create_backend('cpu')
    rows=[]
    for batch in preflight.synthetic_batches(backend):
        row=preflight.check_batch(batch,backend);rows.append(row)
        assert row['accepted'] and row['wrong_score_rejected'] and row['clipped_candidates']==1
        bad=copy.deepcopy(batch);bad['raw'][0]=torch.nextafter(bad['raw'][0],torch.tensor(float('inf'),dtype=bad['raw'].dtype))
        rejected=preflight.check_batch(bad,backend)
        assert not rejected['accepted'] and any(m['check']=='raw_score' for m in rejected['mismatches'])
    assert len(rows)==2 and preflight.wrong_bounds_rejected()
    assert not torch.cuda.is_initialized()


@pytest.mark.parametrize('phase,status,allowed',[('dev','rejected_numeric_futility',True),
 ('dev','completed_all_forty_audited',True),('dev','cell_audited',False),('dev','failed',False),
 ('dev','interrupted',False),('validation','rejected',True),('validation','invalid',False),('validation','wrong_cohort',False)])
def test_preflight_predecessor_requires_valid_aggregate_rejection(tmp_path,phase,status,allowed):
    plan=write_json(tmp_path/'n22.json',{'n22_cohort':{'cohort_id':'N22_HOLD_LIFT_DEV_20260930'}})
    body=({'status':status,'dev_gate_promoted':False} if phase=='dev' else
          {'schema':'n22-validation-aggregate-disposition-v1','cohort_id':('OTHER' if status=='wrong_cohort' else 'N22_HOLD_LIFT_DEV_20260930'),'aggregate_only':True,
           'terminal':True,'gate_passed':False,'outcome_valid':status!='invalid','dev_promoted':True})
    status_ref=write_json(tmp_path/'status.json',body)
    review=write_json(tmp_path/'review.json',{'schema':'n23-n22-prerequisite-v1','source_plan':plan,'source_status':status_ref,
        'phase':phase,'disposition':'rejected','allow_n23':True,'rationale':'CPU fixture'})
    if allowed:assert preflight.predecessor_gate(review)['allow_n23']
    else:
        with pytest.raises(ValueError):preflight.predecessor_gate(review)
    assert not torch.cuda.is_initialized()


def preflight_fixture(job, tmp_path, monkeypatch):
    protocol=job.root/'experiments/iteration_023_actuator_clipped_quality/backend-arithmetic-protocol-v1.md'
    monkeypatch.setattr(preflight,'PROTOCOL_SHA',worker.sha(protocol))
    index=write_json(tmp_path/'bounded-index.json',{'paths':[{'label':'n21_task0',
        'attempt_id':'rdt-qd-ed-final-20260921T093925Z__n21_dev_t00_n21_20260930__a4957aa45fc2',
        'source_success':False,'native_audit_sha256':'a'*64,
        'verified_bundles':[{'path':str(tmp_path/f'bundle_{n}.pt'),'sha256':'b'*64} for n in range(2250)]}]})
    paths=[r['path'] for r in job.context['source']['files']]
    plan=preflight.build_plan(root=job.root,protocol=protocol,runtime=job.runtime,corpus_index=index,
        source_paths=paths,artifact_root=tmp_path/'preflight-artifacts')
    prior=write_json(tmp_path/'prior-n22.json',{'n22_cohort':{'cohort_id':'N22_HOLD_LIFT_DEV_20260930'}})
    status=write_json(tmp_path/'prior-status.json',{'status':'rejected_numeric_futility','dev_gate_promoted':False})
    review=write_json(tmp_path/'prerequisite.json',{'schema':'n23-n22-prerequisite-v1','source_plan':prior,
        'source_status':status,'phase':'dev','disposition':'rejected','allow_n23':True,'rationale':'CPU fixture'})
    return plan,review


def test_draft_without_terminal_review_cannot_execute_and_binds_commit(owned_job,tmp_path,monkeypatch):
    job=owned_job;plan,review=preflight_fixture(job,tmp_path,monkeypatch)
    assert plan['predecessor_review'] is None and plan['requires_separate_release']
    assert plan['source']['commit']==job.plan['source_commit']
    with pytest.raises((TypeError,ValueError)):preflight.validate_plan(plan)
    plan['predecessor_review']=review
    assert preflight.validate_plan(plan)['gpu_mapping']['physical_gpu']==7
    path=tmp_path/'preflight-plan.json';write_json(path,plan)
    cmd=preflight.command(sys.executable,path,tmp_path/'release.json',tmp_path/'attempt-context.json',root=job.root)
    assert str(job.root/'main.py') in cmd and '--ownership-main' in cmd
    assert not torch.cuda.is_initialized()


@pytest.mark.parametrize('fault',['limits','corpus','runtime','source','protocol','invalid_transition','promoted_dev'])
def test_preflight_frozen_scope_rejects_mutation(owned_job,tmp_path,monkeypatch,fault):
    job=owned_job;plan,review=preflight_fixture(job,tmp_path,monkeypatch);plan['predecessor_review']=review
    if fault=='limits':plan['limits']={**plan['limits'],'attempts':2}
    if fault=='corpus':plan['corpus']['expected_batches']=175
    if fault=='runtime':Path(job.runtime['path']).write_text('{}')
    if fault=='source':plan['source']['sha256']='0'*64
    if fault=='protocol':plan['protocol']['sha256']='0'*64
    if fault in {'invalid_transition','promoted_dev'}:
        r=json.loads(Path(review['path']).read_text())
        if fault=='invalid_transition':r['disposition']='invalid_resolved'
        else:
            stat=json.loads(Path(r['source_status']['path']).read_text());stat['dev_gate_promoted']=True
            r['source_status']=write_json(Path(r['source_status']['path']),stat)
        plan['predecessor_review']=write_json(Path(review['path']),r)
    with pytest.raises((ValueError,KeyError)):preflight.validate_plan(plan)
    assert not torch.cuda.is_initialized()


def executed_preflight_fixture(job,tmp_path,monkeypatch):
    plan,review=preflight_fixture(job,tmp_path,monkeypatch);plan['predecessor_review']=review
    planref=write_json(tmp_path/'frozen-preflight.json',plan)
    attempt='n23-one-recovery-fixture';output=Path(plan['artifact_root'])/'attempts'/attempt
    context={'schema':'n23-recovery-attempt-context-v1','attempt_id':attempt,'output_dir':str(output),
             'budget_bucket':'recovery','plan':planref,'timeout_seconds':120,'cleanup_seconds':40}
    ctxref=write_json(tmp_path/'attempt-context.json',context)
    release={'schema':'n23-backend-preflight-release-v1','plan':planref,'source':plan['source'],
             'runtime':plan['runtime'],'limits':preflight.LIMITS,'attempt_id':attempt,'predecessor_review':review}
    relref=write_json(tmp_path/'preflight-release.json',release)
    # CPU-only fake work for ownership/receipt gates. Numeric work has separate
    # real CPU tests above; this fixture is never a backend-readiness proof.
    backend=backends.AuditBackend(torch.device('cpu'),{'kind':'cuda','logical_device':'cuda:0',
        'physical_uuid':'GPU-48473162-9548-1a19-04aa-ea86c5349187','torch_version':'cpu-fixture','cuda_version':'synthetic'})
    backend.dtypes.update(['torch.float32','torch.bfloat16'])
    monkeypatch.setattr(preflight,'create_backend',lambda *a,**kw:backend)
    monkeypatch.setattr(preflight,'verify_corpus_files',lambda corpus:None)
    monkeypatch.setattr(preflight,'iter_batches',lambda corpus:iter([{'decision_id':'fixture','score_sequence':i} for i in range(176)]))
    monkeypatch.setattr(preflight,'synthetic_batches',lambda b:iter([{'decision_id':'synthetic','score_sequence':-1}]*2))
    monkeypatch.setattr(preflight,'check_batch',lambda batch,b:{**batch,'accepted':True,'candidates':16,
                                                            'mismatches':[],'wrong_score_rejected':True})
    assert preflight.run_preflight(planref['path'],relref['path'],ctxref['path'])==0
    proofpath=output/'n23-backend-preflight-report.json';proof=json.loads(proofpath.read_text())
    terminal={'budget_bucket':'recovery','event':'valid','outcome_valid':True,'attempt_id':attempt,
              'gpu_process_wall_seconds':proof['worker_wall_seconds']+.01,'process':proof['process'],
              'backend_preflight_report':{'path':str(proofpath),'sha256':worker.sha(proofpath)}}
    return planref,relref,ctxref,plan,proofpath,terminal


def test_preflight_same_source_metered_proof_and_no_retry(owned_job,tmp_path,monkeypatch):
    planref,release,context,plan,path,terminal=executed_preflight_fixture(owned_job,tmp_path,monkeypatch)
    assert preflight.verify_preflight_proof(planref['path'],path,terminal,plan['source'])['sha256']==worker.sha(path)
    with pytest.raises(ValueError):preflight.run_preflight(planref['path'],release['path'],context['path'])
    assert not torch.cuda.is_initialized()


@pytest.mark.parametrize('fault',['future_source','unmetered','cpu','process','report_sha','wrong_bucket','missing_batch','reported_mismatch','release_hash'])
def test_preflight_proof_cannot_authorize_different_or_unmetered_runtime(owned_job,tmp_path,monkeypatch,fault):
    planref,release,context,plan,path,terminal=executed_preflight_fixture(owned_job,tmp_path,monkeypatch)
    source=copy.deepcopy(plan['source']);proof=json.loads(path.read_text())
    if fault=='future_source':source['commit']='0'*40
    if fault=='unmetered':terminal['gpu_process_wall_seconds']=0
    if fault=='cpu':proof['backend']['kind']='cpu'
    if fault=='process':terminal['process']={**terminal['process'],'pid':1}
    if fault=='report_sha':terminal['backend_preflight_report']['sha256']='0'*64
    if fault=='wrong_bucket':terminal['budget_bucket']='development'
    if fault=='missing_batch':proof['batches'].pop()
    if fault=='reported_mismatch':proof['batches'][0]['mismatches']=['mismatch']
    if fault=='release_hash':Path(release['path']).write_text('{}')
    if fault in {'cpu','missing_batch','reported_mismatch'}:
        write_json(path,proof);terminal['backend_preflight_report']['sha256']=worker.sha(path)
    with pytest.raises(ValueError):preflight.verify_preflight_proof(planref['path'],path,terminal,source)
    assert not torch.cuda.is_initialized()


def test_main_system_exit_zero_still_runs_in_worker_audit(owned_job):
    job=owned_job;refresh_job(job,main_text='raise SystemExit(0)\n')
    assert worker.run_worker(job.context_path,job.command[1:])==0
    assert worker.verify_receipt(job.context_path,job.process)['accepted']


def test_no_guided_search_gets_no_artificial_per_episode_activity_veto(owned_job,monkeypatch):
    job=owned_job
    def no_guidance(*args,arithmetic_backend):
        return {'accepted':True,'evidence_complete':True,'observed_counts':{'canonical_candidate_batch':0},
                'n23_arithmetic_backend':arithmetic_backend.report()}
    monkeypatch.setattr(worker.audit,'audit_episode',no_guidance)
    assert worker.run_worker(job.context_path,job.command[1:])==0
    assert worker.verify_receipt(job.context_path,job.process)['accepted']
    assert not torch.cuda.is_initialized()


def test_previous_started_attempt_cannot_be_reused_even_without_final_receipt(owned_job):
    job=owned_job
    write_json(job.output/'eds_eval/in-worker-audit-start.json',{'interrupted':True})
    with pytest.raises(ValueError):worker.run_worker(job.context_path,job.command[1:])
    assert job.calls==[] and not (job.root.parent/'observed-argv.json').exists()


def test_preflight_corpus_proof_rechecks_each_input_byte_without_cuda(tmp_path):
    path=tmp_path/'input.pt';path.write_bytes(b'native fixture bytes')
    corpus={'bundles':[{'path':str(path),'sha256':worker.sha(path)}]}
    preflight.verify_corpus_files(corpus)
    path.write_bytes(b'mutated')
    with pytest.raises(ValueError):preflight.verify_corpus_files(corpus)
    assert not torch.cuda.is_initialized()


CANONICAL_GPU7_UUID='GPU-48473162-9548-1a19-04aa-ea86c5349187'

@pytest.mark.parametrize('value',[CANONICAL_GPU7_UUID,CANONICAL_GPU7_UUID[4:],CANONICAL_GPU7_UUID.upper(),
    CANONICAL_GPU7_UUID.lower(),CANONICAL_GPU7_UUID[4:].upper()])
def test_canonical_uuid_accepts_only_proper_prefixed_or_bare_spelling(value):
    assert backends.canonical_cuda_uuid(value)==CANONICAL_GPU7_UUID
    assert not torch.cuda.is_initialized()


@pytest.mark.parametrize('value',[None,'',17,b'48473162-9548-1a19-04aa-ea86c5349187','GPU-expected',
    '4847316295481a1904aaea86c5349187','GPU-GPU-48473162-9548-1a19-04aa-ea86c5349187',
    ' 48473162-9548-1a19-04aa-ea86c5349187','48473162-9548-1a19-04aa-ea86c5349187\n',
    'GPU-48473162-9548-1a19-04aa-ea86c534918z','MIG-48473162-9548-1a19-04aa-ea86c5349187'])
def test_canonical_uuid_rejects_absent_malformed_or_ambiguous_identity(value):
    with pytest.raises(ValueError):backends.canonical_cuda_uuid(value)
    assert not torch.cuda.is_initialized()


@pytest.mark.parametrize('observed',[CANONICAL_GPU7_UUID,CANONICAL_GPU7_UUID[4:],CANONICAL_GPU7_UUID.upper(),
    CANONICAL_GPU7_UUID[4:].upper()])
@pytest.mark.parametrize('visible',['7',CANONICAL_GPU7_UUID,CANONICAL_GPU7_UUID.upper()])
def test_assigned_cuda_raw_observation_and_canonical_metadata_without_cuda(monkeypatch,observed,visible):
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES',visible)
    monkeypatch.setattr(torch.cuda,'is_available',lambda:True)
    monkeypatch.setattr(torch.cuda,'device_count',lambda:1)
    monkeypatch.setattr(torch.cuda,'current_device',lambda:0)
    monkeypatch.setattr(torch.cuda,'get_device_properties',lambda _:SimpleNamespace(name='fixture',uuid=observed))
    binding={'physical_gpu':7,'uuid':CANONICAL_GPU7_UUID,'logical_device':'cuda:0'}
    identity=backends.assigned_cuda_identity(binding)
    assert identity['actual_uuid']==observed and identity['physical_uuid']==CANONICAL_GPU7_UUID
    assert identity['uuid']==binding['uuid'] and identity['cuda_visible_devices']==visible
    result=backends.create_backend('cuda',binding=binding)
    assert result.report()['actual_uuid']==observed and result.report()['physical_uuid']==CANONICAL_GPU7_UUID
    assert not torch.cuda.is_initialized()


@pytest.mark.parametrize('fault',['missing_env','other_index','multiple_visible','wrong_visible_uuid','malformed_visible',
    'unavailable','count','current','missing','malformed','wrong'])
def test_uuid_normalization_preserves_device_environment_and_identity_gates(monkeypatch,fault):
    binding={'physical_gpu':7,'uuid':CANONICAL_GPU7_UUID,'logical_device':'cuda:0'}
    visible={'other_index':'3','multiple_visible':'7,6','wrong_visible_uuid':'GPU-00000000-0000-0000-0000-000000000001',
        'malformed_visible':'GPU-expected'}.get(fault,'7')
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES',visible)
    if fault=='missing_env':monkeypatch.delenv('CUDA_VISIBLE_DEVICES')
    monkeypatch.setattr(torch.cuda,'is_available',lambda:fault!='unavailable')
    monkeypatch.setattr(torch.cuda,'device_count',lambda:2 if fault=='count' else 1)
    monkeypatch.setattr(torch.cuda,'current_device',lambda:1 if fault=='current' else 0)
    props=SimpleNamespace(name='fixture',uuid='bad' if fault=='malformed' else
        '00000000-0000-0000-0000-000000000001' if fault=='wrong' else CANONICAL_GPU7_UUID[4:])
    if fault=='missing':del props.uuid
    monkeypatch.setattr(torch.cuda,'get_device_properties',lambda _:props)
    with pytest.raises(RuntimeError):backends.assigned_cuda_identity(binding)
    assert not torch.cuda.is_initialized()


@pytest.mark.parametrize('profile',['C0','N23'])
@pytest.mark.parametrize('observed',[CANONICAL_GPU7_UUID[4:],CANONICAL_GPU7_UUID.upper()])
def test_worker_receipt_reconciles_raw_uuid_with_canonical_physical_identity(owned_job,monkeypatch,profile,observed):
    job=owned_job;refresh_job(job,profile=profile)
    original=worker.assigned_cuda_identity
    monkeypatch.setattr(worker,'assigned_cuda_identity',lambda binding:{**original(binding),'actual_uuid':observed})
    assert worker.run_worker(job.context_path,job.command[1:])==0
    assert worker.verify_receipt(job.context_path,job.process)['accepted']
    receipt=json.loads((job.output/'eds_eval/in-worker-audit-receipt.json').read_text())
    assert receipt['worker_cuda']['actual_uuid']==observed
    assert receipt['worker_cuda']['physical_uuid']==CANONICAL_GPU7_UUID
    assert not torch.cuda.is_initialized()


@pytest.mark.parametrize('fault',['raw_missing','raw_malformed','raw_wrong','canonical_missing','canonical_bare','canonical_wrong'])
def test_worker_receipt_rejects_inconsistent_raw_or_canonical_uuid(owned_job,fault):
    job=owned_job;assert worker.run_worker(job.context_path,job.command[1:])==0
    path=job.output/'eds_eval/in-worker-audit-receipt.json';receipt=json.loads(path.read_text());actual=receipt['worker_cuda']
    if fault=='raw_missing':actual.pop('actual_uuid')
    if fault=='raw_malformed':actual['actual_uuid']='bad'
    if fault=='raw_wrong':actual['actual_uuid']='00000000-0000-0000-0000-000000000001'
    if fault=='canonical_missing':actual.pop('physical_uuid')
    if fault=='canonical_bare':actual['physical_uuid']=CANONICAL_GPU7_UUID[4:]
    if fault=='canonical_wrong':actual['physical_uuid']='GPU-00000000-0000-0000-0000-000000000001'
    write_json(path,receipt)
    with pytest.raises(ValueError):worker.verify_receipt(job.context_path,job.process)
    assert not torch.cuda.is_initialized()


@pytest.fixture
def native_uuid_class(monkeypatch):
    # PyTorch's registered CUuuid has no public constructor. Its documented
    # surface is readonly vector<uint8_t>[16] bytes plus hyphenated __str__.
    class NativeUuid:
        def __init__(self,raw=CANONICAL_GPU7_UUID[4:],data=None):
            self.raw=raw;self.data=list(bytes.fromhex(CANONICAL_GPU7_UUID[4:].replace('-',''))) if data is None else data
        @property
        def bytes(self):return self.data
        def __str__(self):return self.raw
    monkeypatch.setattr(torch._C,'_CUuuid',NativeUuid)
    return NativeUuid


@pytest.mark.parametrize('raw',[CANONICAL_GPU7_UUID[4:],CANONICAL_GPU7_UUID,CANONICAL_GPU7_UUID.upper()])
def test_installed_native_uuid_surface_serializes_string_type_bytes_and_canonical(native_uuid_class,raw):
    observed=native_uuid_class(raw)
    assert not isinstance(observed,str)
    result=backends.serialize_cuda_uuid(observed)
    assert result=={'actual_uuid':raw,'actual_uuid_type':'torch._C._CUuuid',
        'actual_uuid_bytes_hex':CANONICAL_GPU7_UUID[4:].replace('-',''),'physical_uuid':CANONICAL_GPU7_UUID}
    assert json.loads(json.dumps(result))==result and not torch.cuda.is_initialized()


@pytest.mark.parametrize('fault',['wrong_bytes','short_bytes','bool_byte','overflow_byte','malformed_string','generic_object','fake_named_class'])
def test_native_uuid_requires_actual_type_and_matching_public_bytes(native_uuid_class,fault):
    observed=native_uuid_class()
    if fault=='wrong_bytes':observed.data[0]=0
    if fault=='short_bytes':observed.data.pop()
    if fault=='bool_byte':observed.data[0]=True
    if fault=='overflow_byte':observed.data[0]=256
    if fault=='malformed_string':observed.raw='malformed'
    if fault=='generic_object':
        class Generic:
            def __str__(self):raise AssertionError('generic object must never be stringified')
        observed=Generic()
    if fault=='fake_named_class':
        Forged=type('_CUuuid',(),{'__module__':'torch._C','__str__':lambda _:CANONICAL_GPU7_UUID[4:]})
        observed=Forged()
    with pytest.raises(ValueError):backends.serialize_cuda_uuid(observed)
    assert not torch.cuda.is_initialized()


def cpu_identity_properties(monkeypatch,observed):
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES','7')
    monkeypatch.setattr(torch.cuda,'is_available',lambda:True)
    monkeypatch.setattr(torch.cuda,'device_count',lambda:1)
    monkeypatch.setattr(torch.cuda,'current_device',lambda:0)
    monkeypatch.setattr(torch.cuda,'get_device_properties',lambda _:SimpleNamespace(name='fixture',uuid=observed))


def test_native_identity_metadata_is_json_serializable_and_matches_backend(native_uuid_class,monkeypatch):
    cpu_identity_properties(monkeypatch,native_uuid_class())
    binding={'physical_gpu':7,'uuid':CANONICAL_GPU7_UUID,'logical_device':'cuda:0'}
    identity=backends.assigned_cuda_identity(binding);result=backends.create_backend('cuda',binding=binding).report()
    assert identity['actual_uuid_type']=='torch._C._CUuuid' and identity['actual_uuid']==CANONICAL_GPU7_UUID[4:]
    assert identity['physical_uuid']==result['physical_uuid']==CANONICAL_GPU7_UUID
    assert json.loads(json.dumps(identity))==identity and json.loads(json.dumps(result))==result
    assert identity['identity_diagnostic']['status']=='matched' and not torch.cuda.is_initialized()


@pytest.mark.parametrize('kind',['missing','malformed','generic','native_bytes_mismatch','wrong_uuid','wrong_count','wrong_current','bad_mask'])
def test_identity_failures_retain_only_bounded_public_diagnostic(native_uuid_class,monkeypatch,kind):
    observed=native_uuid_class()
    if kind=='missing':observed=None
    if kind=='malformed':observed='not-public-uuid-sensitive-marker'
    if kind=='generic':
        class Generic:
            def __str__(self):raise AssertionError('do not stringify arbitrary objects')
        observed=Generic()
    if kind=='native_bytes_mismatch':observed.data[0]=0
    if kind=='wrong_uuid':observed='00000000-0000-0000-0000-000000000001'
    cpu_identity_properties(monkeypatch,observed)
    if kind=='wrong_count':monkeypatch.setattr(torch.cuda,'device_count',lambda:2)
    if kind=='wrong_current':monkeypatch.setattr(torch.cuda,'current_device',lambda:1)
    if kind=='bad_mask':monkeypatch.setenv('CUDA_VISIBLE_DEVICES','not-public-mask-sensitive-marker')
    with pytest.raises(RuntimeError) as caught:
        backends.assigned_cuda_identity({'physical_gpu':7,'uuid':CANONICAL_GPU7_UUID,'logical_device':'cuda:0'})
    diagnostic=caught.value.identity_diagnostic
    assert diagnostic['schema']=='n23-public-cuda-identity-diagnostic-v1'
    assert diagnostic['expected_uuid']==CANONICAL_GPU7_UUID and diagnostic['expected_physical_gpu']==7
    assert 'sensitive-marker' not in json.dumps(diagnostic)
    if kind not in {'wrong_count','wrong_current','bad_mask'}:
        assert diagnostic['visible_device_count']==1 and diagnostic['current_device']==0
        assert diagnostic['uuid_public_type'] is not None and diagnostic['serialized_raw_uuid'] is not None
    if kind=='wrong_uuid':assert diagnostic['canonical_uuid']=='GPU-00000000-0000-0000-0000-000000000001'
    assert not torch.cuda.is_initialized()


@pytest.mark.parametrize('profile',['C0','N23'])
def test_worker_native_object_identity_survives_receipt_json(owned_job,native_uuid_class,monkeypatch,profile):
    job=owned_job;refresh_job(job,profile=profile);cpu_identity_properties(monkeypatch,native_uuid_class())
    monkeypatch.setattr(worker,'assigned_cuda_identity',backends.assigned_cuda_identity)
    # Wrapper arithmetic is synthetic CPU; device identity uses the real helper on faithful native-object fixture.
    def backend(kind,*,binding=None):
        if kind=='cpu':return backends.create_backend('cpu')
        actual=backends.assigned_cuda_identity(binding)
        return backends.AuditBackend(torch.device('cpu'),{'kind':'cuda',**actual})
    monkeypatch.setattr(worker,'create_backend',backend)
    assert worker.run_worker(job.context_path,job.command[1:])==0
    assert worker.verify_receipt(job.context_path,job.process)['accepted']
    receipt=json.loads((job.output/'eds_eval/in-worker-audit-receipt.json').read_text())
    assert receipt['worker_cuda']['actual_uuid_type']=='torch._C._CUuuid'
    assert receipt['worker_cuda']['actual_uuid']==CANONICAL_GPU7_UUID[4:]
    assert not torch.cuda.is_initialized()


@pytest.mark.parametrize('fault',['unknown_type','native_bad_bytes','native_missing_bytes','str_extra_bytes'])
def test_worker_rejects_serialized_native_type_or_byte_drift(owned_job,fault):
    job=owned_job;assert worker.run_worker(job.context_path,job.command[1:])==0
    path=job.output/'eds_eval/in-worker-audit-receipt.json';receipt=json.loads(path.read_text());actual=receipt['worker_cuda']
    if fault=='unknown_type':actual['actual_uuid_type']='arbitrary.Type'
    if fault=='native_bad_bytes':actual.update(actual_uuid_type='torch._C._CUuuid',actual_uuid_bytes_hex='0'*32)
    if fault=='native_missing_bytes':actual['actual_uuid_type']='torch._C._CUuuid';actual.pop('actual_uuid_bytes_hex')
    if fault=='str_extra_bytes':actual['actual_uuid_bytes_hex']=CANONICAL_GPU7_UUID[4:].replace('-','')
    write_json(path,receipt)
    with pytest.raises(ValueError):worker.verify_receipt(job.context_path,job.process)


def test_v2_preflight_persists_identity_diagnostic_before_any_arithmetic(tmp_path,native_uuid_class,monkeypatch):
    from scripts import qd_ed_n23_v2_backend as b
    attempt='synthetic-native-diagnostic';output=tmp_path/'artifacts/attempts'/attempt
    runtime={'gpu_mapping':{'physical_gpu':7,'uuid':CANONICAL_GPU7_UUID}}
    plan={'artifact_root':str(tmp_path/'artifacts'),'source':{'commit':'fixture'},'runtime':write_json(tmp_path/'runtime.json',runtime),
        'limits':b.LIMITS,'corpus':{},'predecessor_review':{'synthetic':True}}
    planref=write_json(tmp_path/'plan.json',plan)
    context={'schema':'n23-recovery-attempt-context-v2','attempt_id':attempt,'output_dir':str(output),'budget_bucket':'recovery',
        'plan':planref,'timeout_seconds':120,'cleanup_seconds':40}
    ctxref=write_json(tmp_path/'context.json',context)
    release={'schema':'n23-backend-preflight-release-v2','plan':planref,'source':plan['source'],'runtime':plan['runtime'],
        'limits':b.LIMITS,'attempt_id':attempt,'predecessor_review':plan['predecessor_review']}
    relref=write_json(tmp_path/'release.json',release)
    monkeypatch.setattr(b,'validate_plan',lambda _:runtime)
    monkeypatch.setattr(b,'create_backend',backends.create_backend)
    malformed=native_uuid_class();malformed.data.pop();cpu_identity_properties(monkeypatch,malformed)
    monkeypatch.setattr(b,'iter_batches',lambda _:(_ for _ in ()).throw(AssertionError('no arithmetic after identity error')))
    assert b.run_preflight(planref['path'],relref['path'],ctxref['path'])==2
    report=json.loads((output/b.artifact_name(plan,'report')).read_text())
    assert report['accepted'] is False and report['batches']==report['synthetic']==[]
    assert report['errors']==['RuntimeError:audit physical CUDA UUID differs or unavailable']
    assert report['identity_diagnostic']['uuid_public_type']=='torch._C._CUuuid'
    assert report['identity_diagnostic']['serialized_raw_uuid']=='<malformed or unsupported UUID>'
    assert report['identity_diagnostic']['expected_uuid']==CANONICAL_GPU7_UUID
    assert report['identity_diagnostic']['visible_device_count']==1
    assert not torch.cuda.is_initialized()


class CudaScalarDivisionCpuModel(torch.utils._python_dispatch.TorchDispatchMode):
    """Pinned CUDA div branch only; other operations intentionally remain CPU.

    PyTorch v2.7.1 BinaryDivTrueKernel.cu32-50 rounds reciprocal before multiply
    for CPU scalar divisors, unlike device-tensor divisors. This is a falsifiable
    branch model, not a claim to emulate CUDA reductions or pass a GPU preflight.
    """
    def __init__(self):
        super().__init__();self.scalar_divisions=0;self.tensor_divisions=0

    def __torch_dispatch__(self,func,types,args=(),kwargs=None):
        if func==torch.ops.aten.div.Tensor and len(args)>1 and args[0].dtype==torch.float32:
            if isinstance(args[1],(int,float)):
                import numpy as np
                self.scalar_divisions+=1
                reciprocal=float(np.float32(1.)/np.float32(args[1]))
                return torch.mul(args[0],reciprocal)
            if torch.is_tensor(args[1]):self.tensor_divisions+=1
        return func(*args,**(kwargs or {}))


def test_cuda_divisor_branch_model_has_exact_weight_and_bf16_rounding_boundary():
    weights=torch.tensor([1.,1.,1.,1.,3.,3.,3.])
    with CudaScalarDivisionCpuModel() as model:
        direct=weights/weights.sum();reciprocal=weights/13
    assert model.scalar_divisions==model.tensor_divisions==1
    assert direct.view(torch.int32).tolist()==[1033734617]*4+[1047285445]*3
    assert reciprocal.view(torch.int32).tolist()==[1033734617]*4+[1047285446]*3
    distances=torch.tensor([.2421875,.08203125,.08984375,.208984375,.1943359375,.2890625,.2890625],dtype=torch.bfloat16)
    x=-(distances.square()*direct).sum();y=-(distances.square()*reciprocal).sum()
    assert x.item()==-.0562744140625 and y.item()==-.0562744177877903
    assert x.to(torch.bfloat16).item()==-.05615234375
    assert y.to(torch.bfloat16).item()==-.056396484375
    assert not torch.cuda.is_initialized()


def audit_boundary_fixture(index,dtype):
    generator=torch.Generator().manual_seed(230930)
    for _ in range(index+1):actions=(torch.randn(16,64,128,generator=generator)*2).to(dtype)
    origin=torch.tensor([.12317,-.17312,.23141],dtype=torch.float64)
    xyz=torch.stack([torch.cat((origin.to(dtype)[None],origin.to(dtype)+torch.cumsum(a*.01,0)))
        for a in actions[:,:8,[39,40,41]]])
    keypoints=torch.tensor([[.1124,-.071,.3154]],dtype=dtype)
    weights=torch.tensor([1.,1.,1.,1.,3.,3.,3.]);weights=weights/weights.sum()
    raw=torch.stack([(-(torch.norm(v[None,1:8]-keypoints[0],dim=-1)**2*weights).sum(1)).mean().to(dtype) for v in xyz])
    return {'decision_id':'synthetic_branch_boundary_'+str(index),'score_sequence':-1,'samples':actions,
        'projected_xyz':xyz,'keypoints':keypoints,'raw':raw,'origins':[origin]*16}


def old_scalar_check_batch():
    """Load only the exact two historical function bodies from committed source."""
    import ast
    def historical_function(path,name,namespace):
        original=subprocess.check_output(['git','show','fbe5ac996467e00fcbc7a1d7e5f24659725f6b3d:'+path],
            cwd=Path(__file__).resolve().parents[1],text=True)
        function=next(n for n in ast.parse(original).body if isinstance(n,ast.FunctionDef) and n.name==name)
        namespace=dict(namespace);exec(compile(ast.Module(body=[function],type_ignores=[]),path,'exec'),namespace)
        return namespace[name]
    reconstruction=historical_function('scripts/audit_decision_evidence.py','reconstruct_n23_arithmetic',vars(audit))
    oldaudit=SimpleNamespace(**{**vars(audit),'reconstruct_n23_arithmetic':reconstruction})
    return historical_function('scripts/qd_ed_n23_backend_preflight.py','check_batch',{**vars(preflight),'audit':oldaudit})


@pytest.mark.parametrize('index,expected_checks',[(4,{'clipped_quality_or_mask'}),(8,{'raw_score','independent_arithmetic'})])
def test_old_audit_cuda_branch_defect_reproduced_and_corrected_without_tolerance(index,expected_checks):
    batch=audit_boundary_fixture(index,torch.bfloat16);backend=backends.create_backend('cpu')
    previous=old_scalar_check_batch()
    with CudaScalarDivisionCpuModel() as oldmodel:failed=previous(batch,backend)
    assert {v['check'] for v in failed['mismatches']}==expected_checks and not failed['accepted']
    assert failed['production_helper_passed'] and oldmodel.scalar_divisions>0
    with CudaScalarDivisionCpuModel() as fixedmodel:passed=preflight.check_batch(batch,backend)
    assert passed['accepted'] and passed['production_helper_passed'] and passed['independent_passed']
    assert passed['wrong_score_rejected'] and fixedmodel.scalar_divisions==0 and fixedmodel.tensor_divisions>0
    assert not torch.cuda.is_initialized()


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_corrected_exact_audit_survives_layout_and_dtype_boundaries(dtype):
    batch=audit_boundary_fixture(8,dtype);a=batch['samples']
    gathered=a[:,:8,[39,40,41]];view=a[:,:8,39:42]
    assert gathered.stride()==(24,3,1) and view.stride()==(8192,128,1)
    # Different input views produce identical elementwise/projector values on CPU.
    assert torch.equal(gathered,view)
    for row in range(16):
        assert torch.equal(torch.cumsum(gathered[row]*.01,0),torch.cumsum(view[row]*.01,0))
    with CudaScalarDivisionCpuModel() as model:
        checked=preflight.check_batch(batch,backends.create_backend('cpu'))
    assert checked['accepted'] and model.scalar_divisions==0 and model.tensor_divisions==3
    assert not torch.cuda.is_initialized()


@pytest.mark.parametrize('fault',['raw','quality','mask','bounds'])
def test_corrected_branch_keeps_exact_negative_controls(fault):
    batch=audit_boundary_fixture(8,torch.bfloat16);backend=backends.create_backend('cpu')
    with CudaScalarDivisionCpuModel():
        if fault=='raw':
            batch['raw'][0]=torch.nextafter(batch['raw'][0],torch.full_like(batch['raw'][0],float('inf')))
            result=preflight.check_batch(batch,backend)
            assert not result['accepted'] and any(v['check']=='raw_score' for v in result['mismatches'])
        elif fault=='bounds':assert preflight.wrong_bounds_rejected()
        else:
            quality,mask=audit.reconstruct_n23_arithmetic(batch['samples'],batch['projected_xyz'],batch['keypoints'],batch['raw'],batch['origins'])
            effective={'quality':quality.clone(),'clipped_prefix_mask':mask.clone()}
            if fault=='quality':effective['quality'][0]=torch.nextafter(quality[0],torch.full_like(quality[0],float('inf')))
            else:effective['clipped_prefix_mask'][0]=~mask[0]
            with pytest.raises(audit.AuditFailure):audit.verify_n23_quality(quality,mask,effective)
    assert not torch.cuda.is_initialized()


def test_both_original_synthetic_cases_use_tensor_denominator_throughout():
    backend=backends.create_backend('cpu')
    with CudaScalarDivisionCpuModel() as model:
        cases=list(preflight.synthetic_batches(backend))
        rows=[preflight.check_batch(v,backend) for v in cases]
    assert all(v['accepted'] and v['wrong_score_rejected'] for v in rows)
    assert [v['samples'].dtype for v in cases]==[torch.float32,torch.bfloat16]
    assert model.scalar_divisions==0 and model.tensor_divisions==8
    assert not torch.cuda.is_initialized()
