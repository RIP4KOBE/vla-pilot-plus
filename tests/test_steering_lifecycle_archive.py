"""Narrow CPU regressions for externally staged fixes; no real run writes."""
from copy import deepcopy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

import psutil
import pytest
import yaml

STAGE = Path(__file__).resolve().parents[1]
CANDIDATE = STAGE/'candidate' if (STAGE/'candidate').is_dir() else STAGE
ROOT = STAGE.parents[4] if CANDIDATE != STAGE else STAGE
sys.path.insert(0, str(CANDIDATE))
sys.path.append(str(ROOT))
from scripts import steering_archive as archive
from scripts import audit_steering as audit
from scripts.audit_steering_contract import instruction_for_task
from scripts.steering_process import LauncherInterrupted, worker_lifecycle


def write_json(path, value):
    Path(path).write_text(json.dumps(value,sort_keys=True)+'\n')


def not_running(pid):
    try: return not psutil.Process(pid).is_running() or psutil.Process(pid).status()==psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess: return True


@pytest.mark.parametrize('signum', [signal.SIGTERM, signal.SIGINT])
def test_cancel_owned_tree_separate_session_and_preserve_unrelated(tmp_path, signum):
    env=dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1',
             PYTHONPATH=str(CANDIDATE))
    other=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],start_new_session=True)
    launcher=subprocess.Popen([sys.executable,str(STAGE/'tests/lifecycle_child.py'),'launcher',str(tmp_path)],
                              env=env,start_new_session=True)
    owned=[]
    try:
        deadline=time.monotonic()+10
        while not (tmp_path/'ready').exists():
            assert launcher.poll() is None
            assert time.monotonic()<deadline
            time.sleep(.02)
        owned=[json.loads((tmp_path/f'{role}.json').read_text())['pid'] for role in ('worker','grandchild')]
        assert os.getsid(owned[0]) != os.getsid(owned[1])
        os.kill(launcher.pid, signum)
        time.sleep(.1)
        with (tmp_path/'gpu.lock').open('a+') as lock:
            with pytest.raises(BlockingIOError): fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        os.kill(launcher.pid, signum)  # Repeated cancellation must not bypass cleanup.
        assert launcher.wait(timeout=10)==128+signum
        status=json.loads((tmp_path/'status.json').read_text())
        assert status['state']=='interrupted' and status['launcher_signal']==signum
        assert status['partial_steps']==7 and status['partial_evidence_preserved'] is True
        assert status['automatic_retry'] is False
        assert status['worker_cleanup']['cleanup_complete'] is True
        assert set(status['worker_cleanup']['discovered_pids'])==set(owned)
        assert all(not_running(pid) for pid in owned)
        assert other.poll() is None
        with (tmp_path/'gpu.lock').open('a+') as lock: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        assert not (tmp_path/'audit.json').exists()
    finally:
        if launcher.poll() is None: launcher.kill(); launcher.wait()
        for pid in owned:
            if not not_running(pid):
                try: os.kill(pid,signal.SIGKILL)
                except ProcessLookupError: pass
        other.terminate(); other.wait()


def test_preflight_interrupt_is_terminal_and_restores_handlers(tmp_path):
    old={s:signal.getsignal(s) for s in (signal.SIGINT,signal.SIGTERM)}
    with pytest.raises(LauncherInterrupted):
        with worker_lifecycle(tmp_path) as owner:
            owner.interrupt(signal.SIGTERM,None)
    status=json.loads((tmp_path/'status.json').read_text())
    assert status['state']=='interrupted' and status['exit_code'] is None
    assert status['worker_cleanup']['discovered_pids']==[]
    assert all(signal.getsignal(s)==handler for s,handler in old.items())


def test_monitor_failure_cleans_owned_worker_and_preserves_exception(tmp_path):
    with pytest.raises(RuntimeError, match='test monitor failure'):
        with worker_lifecycle(tmp_path,grace_seconds=.1) as owner:
            proc=owner.spawn([sys.executable,'-c','import time; time.sleep(60)'])
            raise RuntimeError('test monitor failure')
    assert not_running(proc.pid)
    status=json.loads((tmp_path/'status.json').read_text())
    assert status['state']=='launcher_failed' and status['error_type']=='RuntimeError'


def test_output_claim_race_never_rewrites_winning_status(tmp_path,monkeypatch):
    from scripts import run_steering
    from types import SimpleNamespace
    folder=tmp_path/'cohort';winner=b'{"state":"running","owner":"other-launcher"}\n'
    monkeypatch.setattr(run_steering,'ROOT',tmp_path/'code')
    monkeypatch.setattr(run_steering,'load_local',lambda _: {'gpu':0})
    monkeypatch.setattr(run_steering,'load_config',lambda *a,**kw: {})
    def admission(*a,**kw):
        folder.mkdir();(folder/'status.json').write_bytes(winner)
        return 'SYNTHETIC, CPU, 0'
    monkeypatch.setattr(run_steering.subprocess,'check_output',admission)
    args=SimpleNamespace(local_config='unused',output_dir=str(folder),tasks=None,method='eds',print_config=False)
    with pytest.raises(FileExistsError):run_steering.run(args)
    assert (folder/'status.json').read_bytes()==winner


def test_busy_gpu_admission_does_not_claim_output(tmp_path,monkeypatch):
    from scripts import run_steering
    from types import SimpleNamespace
    folder=tmp_path/'cohort'
    monkeypatch.setattr(run_steering,'ROOT',tmp_path/'code')
    monkeypatch.setattr(run_steering,'load_local',lambda _: {'gpu':0})
    monkeypatch.setattr(run_steering,'load_config',lambda *a,**kw: {})
    monkeypatch.setattr(run_steering.subprocess,'check_output',lambda *a,**kw:'SYNTHETIC, CPU, 1024')
    with pytest.raises(RuntimeError,match='not idle'):
        run_steering.run(SimpleNamespace(local_config='unused',output_dir=str(folder),tasks=None,method='eds',print_config=False))
    assert not folder.exists()


def test_normal_worker_same_argv_environment_and_no_retry(tmp_path):
    report=tmp_path/'child.json'
    code='import json,os,sys; open(sys.argv[1],"w").write(json.dumps([sys.argv[2:],os.environ["TEST_SCIENTIFIC_VALUE"]]))'
    with worker_lifecycle(tmp_path) as owner:
        proc=owner.spawn([sys.executable,'-c',code,str(report),'--original-worker-arg'],
                        env=dict(os.environ,TEST_SCIENTIFIC_VALUE='unchanged',CUDA_VISIBLE_DEVICES=''))
        assert proc.wait(timeout=10)==0
        with pytest.raises(RuntimeError,match='retries are forbidden'):
            owner.spawn([sys.executable,'-c','raise SystemExit(99)'])
    assert json.loads(report.read_text())==[['--original-worker-arg'],'unchanged']
    assert not (tmp_path/'status.json').exists()


@pytest.fixture
def frozen_archive(tmp_path):
    """Synthetic original receipts with real frozen profile YAML; no performance claim."""
    run=tmp_path/'original'/'science-run';run.mkdir(parents=True)
    from scripts import steering_runtime
    machine=dict(gpu=0,egl_device_id=2,rdt_checkpoint='/assets/rdt',text_encoder='/assets/text',vision_encoder='/assets/vision')
    config=steering_runtime.load_config(machine,method='eds',output_dir=run/'output')
    config['hydra']['run']['dir']=str(run/'output')
    config['main']['eds_eval']['job_id']=run.name
    originals=tmp_path/'original-assets'; originals.mkdir()
    fixture=originals/'fixture-manifest.json';write_json(fixture,{'schema':'synthetic_hash_binding_test','fixtures':{}})
    config['main']['episode_rng_fixture_manifest']=str(fixture)
    config['main']['episode_rng_fixture_manifest_sha256']=archive.digest(fixture)
    # Protocol reconstruction expects this source-relative path. Copy the frozen
    # evaluation YAML and modify only its synthetic fixture binding below.
    taskmap=originals/archive.TASK_MAP;taskmap.parent.mkdir(parents=True)
    taskmap.write_text("libero_task_map = {'libero_object': ['pick_up_the_mug_and_place_it_in_the_basket']}\n")
    (run/'resolved-config.yaml').write_text(yaml.safe_dump(config))
    source={}
    for rel in ('configs/evaluation/libero_object_swap.yaml','configs/steering/eds.yaml'):
        p=run/'source'/rel;p.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/rel,p)
        if 'evaluation' in rel:
            base=yaml.safe_load(p.read_text())
            base['main']['episode_rng_fixture_manifest']=str(fixture)
            base['main']['episode_rng_fixture_manifest_sha256']=archive.digest(fixture)
            p.write_text(yaml.safe_dump(base))
        source[rel]=archive.digest(p)
    assets=run/'source/scripts/steering_assets_manifest.json';assets.parent.mkdir(parents=True)
    write_json(assets,{'files':{archive.TASK_MAP:archive.digest(taskmap)}})
    source['scripts/steering_assets_manifest.json']=archive.digest(assets)
    write_json(run/'environment.json',{'rng':{'sha256':archive.digest(fixture)},'libero':{'root':str(originals)}})
    manifest=dict(schema='steering_cohort_v2',method='eds',code_root=str(steering_runtime.ROOT),
        tasks=config['backend']['libero']['task_ids_filter'],seeds=config['main']['episode_seed_schedule'],
        config_sha256=archive.digest(run/'resolved-config.yaml'),
        environment_sha256=archive.digest(run/'environment.json'),source_sha256=source)
    write_json(run/'manifest.json',manifest)
    write_json(run/'status.json',{'state':'finished','exit_code':0,'run_dir':str(run),'source_unchanged':True})
    return run,originals,config,manifest


def test_original_audit_bindings_unchanged(frozen_archive):
    run,_,config,manifest=frozen_archive
    assert audit.protocol_config(run,manifest,config)==config
    assert instruction_for_task(run,0,manifest)=='pick up the mug and place it in the basket'
    assert archive.support_asset(run,'rng_manifest').read_bytes()==Path(config['main']['episode_rng_fixture_manifest']).read_bytes()


@pytest.mark.parametrize('new_name',['science-run','renamed-archive'])
def test_moved_archive_without_original_assets_validates_exact_support(frozen_archive,tmp_path,new_name):
    run,originals,config,manifest=frozen_archive
    original_hashes={p.name:archive.digest(p) for p in run.iterdir() if p.is_file()}
    support=tmp_path/'support'
    archive.prepare_support(run,support)
    moved=tmp_path/'moved'/new_name;shutil.copytree(run,moved)
    shutil.rmtree(run);shutil.rmtree(originals)
    assert audit.protocol_config(moved,manifest,config)==config
    assert archive.execution_identity(moved)['job_id']=='science-run'
    assert instruction_for_task(moved,0,manifest,archive_support=support)=='pick up the mug and place it in the basket'
    assert archive.digest(archive.support_asset(moved,'rng_manifest',archive_support=support))==config['main']['episode_rng_fixture_manifest_sha256']
    assert {p.name:archive.digest(p) for p in moved.iterdir() if p.is_file()}==original_hashes


@pytest.mark.parametrize('schema,job_id,valid',[
    ('steering_cohort_v1','output',True),
    ('steering_cohort_v1','science-run',False),
    ('steering_cohort_v2','output',False),
    ('steering_cohort_v2','science-run',True),
    ('steering_cohort_v1','arbitrary',False),
    ('steering_cohort_v3','science-run',False),
])
def test_archive_original_job_id_follows_exact_recorded_schema(frozen_archive,tmp_path,schema,job_id,valid):
    run,_,config,manifest=frozen_archive
    config['main']['eds_eval']['job_id']=job_id
    (run/'resolved-config.yaml').write_text(yaml.safe_dump(config))
    manifest['schema']=schema
    manifest['config_sha256']=archive.digest(run/'resolved-config.yaml')
    write_json(run/'manifest.json',manifest)
    if not valid:
        with pytest.raises(ValueError):archive.prepare_support(run,tmp_path/'support')
        assert not (tmp_path/'support').exists()
        return
    support=tmp_path/'support';archive.prepare_support(run,support)
    moved=tmp_path/'renamed-archive';shutil.copytree(run,moved)
    assert archive.execution_identity(moved)['job_id']==job_id
    assert instruction_for_task(moved,0,manifest,archive_support=support)=='pick up the mug and place it in the basket'
    assert archive.digest(archive.support_asset(moved,'rng_manifest',archive_support=support))==config['main']['episode_rng_fixture_manifest_sha256']
    status=json.loads((moved/'status.json').read_text());status['run_dir']=str(moved)
    write_json(moved/'status.json',status)
    with pytest.raises(ValueError,match='status/config'):
        archive.support_asset(moved,'rng_manifest',archive_support=support)


@pytest.mark.parametrize('kind',['task_map','rng_manifest'])
@pytest.mark.parametrize('damage',['same_size_corruption','missing','symlink_escape'])
def test_bad_support_rejected_even_when_original_assets_exist(frozen_archive,tmp_path,kind,damage):
    run,_,_,_=frozen_archive;support=tmp_path/'support';archive.prepare_support(run,support)
    p=support/archive.SUPPORT_FILES[kind]
    if damage=='same_size_corruption':
        data=p.read_bytes();p.write_bytes(bytes([data[0]^1])+data[1:])
    elif damage=='missing': p.unlink()
    else:
        external=tmp_path/'outside';shutil.copyfile(p,external);p.unlink();p.symlink_to(external)
    with pytest.raises((ValueError,FileNotFoundError)):
        archive.support_asset(run,'task_map',archive_support=support)


@pytest.mark.parametrize('damage',['receipt_hash','receipt_path','config_output','environment','status_original_path'])
def test_archive_binding_changes_rejected(frozen_archive,tmp_path,damage):
    run,_,_,_=frozen_archive;support=tmp_path/'support';archive.prepare_support(run,support)
    if damage.startswith('receipt'):
        p=support/'manifest.json';x=json.loads(p.read_text())
        if damage=='receipt_hash':x['original_manifest_sha256']='0'*64
        else:x['files']['../elsewhere']='0'*64
        write_json(p,x)
    elif damage=='config_output':
        p=run/'resolved-config.yaml';x=yaml.safe_load(p.read_text());x['hydra']['run']['dir']='/arbitrary/output';p.write_text(yaml.safe_dump(x))
    elif damage=='environment':
        p=run/'environment.json';x=json.loads(p.read_text());x['libero']['root']='/arbitrary';write_json(p,x)
    else:
        p=run/'status.json';x=json.loads(p.read_text());x['run_dir']='/arbitrary';write_json(p,x)
    with pytest.raises(ValueError):archive.support_asset(run,'rng_manifest',archive_support=support)


def test_support_creation_refuses_running_or_wrong_source(frozen_archive,tmp_path):
    run,_,_,_=frozen_archive
    wrong=tmp_path/'wrong';wrong.write_text('incorrect')
    with pytest.raises(ValueError,match='hash mismatch'):
        archive.prepare_support(run,tmp_path/'support',task_map=wrong)
    assert not (tmp_path/'support').exists()
    p=run/'status.json';x=json.loads(p.read_text());x['state']='running';write_json(p,x)
    with pytest.raises(ValueError,match='running cohort'):archive.prepare_support(run,tmp_path/'support')


def test_support_creation_never_writes_inside_preserved_run(frozen_archive):
    run,_,_,_=frozen_archive
    with pytest.raises(ValueError,match='outside the preserved source run'):
        archive.prepare_support(run,run/'archive-support')
    assert not (run/'archive-support').exists()


@pytest.mark.parametrize('damage',['missing','corrupt','symlink_escape'])
def test_archive_raw_frame_cannot_borrow_original_file(tmp_path,damage):
    original=tmp_path/'original.png';original.write_bytes(b'original fixture PNG bytes')
    marker={'raw_png_path':str(original),'raw_png_sha256':archive.digest(original)}
    evaluation=tmp_path/'archive/output/evaluation'
    frame=evaluation/'stage_unmarked_frames/episode_000/step_000008.png'
    frame.parent.mkdir(parents=True)
    if damage=='corrupt':frame.write_bytes(b'changed! fixture PNG bytes')
    elif damage=='symlink_escape':frame.symlink_to(original)
    with pytest.raises(ValueError):archive.marker_frame(evaluation,0,8,marker)
    assert original.exists()


def test_archive_raw_frame_reads_local_hash_matched_copy(tmp_path):
    evaluation=tmp_path/'archive/output/evaluation'
    frame=evaluation/'stage_unmarked_frames/episode_000/step_000008.png'
    frame.parent.mkdir(parents=True);frame.write_bytes(b'fixture PNG bytes')
    marker={'raw_png_path':'/unavailable/original.png','raw_png_sha256':archive.digest(frame)}
    assert archive.marker_frame(evaluation,0,8,marker)==frame.resolve()


@pytest.mark.skipif(CANDIDATE == ROOT, reason='Staging-only before/after source comparison; not a self-comparison after integration')
@pytest.mark.parametrize('method',['eds','vls','eds_qd'])
def test_public_print_config_scientific_fields_unchanged(method,tmp_path):
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1')
    local=tmp_path/'local.yaml'
    machine={key:str(tmp_path/'assets'/key) for key in ('rdt_checkpoint','text_encoder','vision_encoder','libero_root','libero_config','torch_home')}
    for value in machine.values():Path(value).mkdir(parents=True)
    machine.update(gpu=0,egl_device_id=2)
    local.write_text(yaml.safe_dump(machine))
    configs=[]
    for script in (ROOT/'scripts/run_steering.py',CANDIDATE/'scripts/run_steering.py'):
        raw=subprocess.check_output([sys.executable,str(script),'--method',method,'--local-config',str(local),
            '--output-dir',str(tmp_path/'not-created'),'--print-config'],env=env,cwd=ROOT,text=True)
        configs.append(yaml.safe_load(raw))
    # Only installation-root lookup paths differ in this external staging copy.
    for config in configs:
        config['main']['episode_rng_fixture_manifest']='<repo>/tests/fixtures/steering_rng/fixture-manifest.json'
        config['perception']['vlm_agent']['query_template_dir']='<repo>/vlm_query/target_distance'
    assert configs[0]==configs[1]
    assert not (tmp_path/'not-created').exists()
