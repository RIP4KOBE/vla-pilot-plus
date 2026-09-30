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
    runtime = write_json(tmp_path/'runtime.json', {'gpu_mapping': {'physical_gpu': 7, 'uuid': 'GPU-synthetic-7'}})
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
        return {**binding, 'actual_uuid': binding['uuid'], 'device_name': 'synthetic',
                'cuda_visible_devices': '7', 'torch_version': 'cpu-fixture', 'cuda_version': 'synthetic'}
    def backend(kind, *, binding=None):
        calls.append(kind)
        # Explicit fake metadata for wrapper tests; all arithmetic stays CPU.
        meta = {'kind': kind, 'logical_device': 'cuda:0' if kind == 'cuda' else 'cpu',
                'physical_uuid': 'GPU-synthetic-7' if kind == 'cuda' else None,
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
    binding={'physical_gpu':7,'uuid':'GPU-expected','logical_device':'cuda:0'}
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES','5' if fault=='visible' else '7')
    monkeypatch.setattr(torch.cuda,'is_available',lambda:True)
    monkeypatch.setattr(torch.cuda,'device_count',lambda:2 if fault=='count' else 1)
    monkeypatch.setattr(torch.cuda,'current_device',lambda:1 if fault=='current' else 0)
    props=SimpleNamespace(name='fake',uuid='GPU-wrong' if fault=='uuid' else 'GPU-expected')
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
        'physical_uuid':'GPU-synthetic-7','torch_version':'cpu-fixture','cuda_version':'synthetic'})
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
