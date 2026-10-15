"""Install the reviewed recheck, validate installed code, freeze and run full10."""
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

import yaml

ROOT = Path.cwd()
ART = ROOT/'artifacts/stage_closed_loop_20260929'
DRAFT = ART/'drafts/codex_failed_contact_recheck'
PREVIOUS = ART/'runs/codex_fused_carry_v16_historical_initialization_online_full10'
NAME = 'codex_failed_contact_v17_historical_initialization_online_full10'
FOLDER = ART/'runs'/NAME
QUEUE = ART/'codex-v17-continuation'
spec = importlib.util.spec_from_file_location('v17_owned_helpers', ART/'drafts/codex_partial_visibility_v14/continue_after_v13.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
h.QUEUE = QUEUE


def differences(left, right, prefix=''):
    if isinstance(left, dict) and isinstance(right, dict):
        result = []
        for key in sorted(set(left) | set(right)):
            result.extend(differences(left.get(key), right.get(key), prefix+'.'+key if prefix else key))
        return result
    return [] if left == right else [dict(path=prefix, before=left, after=right)]


def main():
    QUEUE.mkdir(exist_ok=False)
    h.status('VERIFYING_REVIEWED_V16_PARENT')
    assert json.loads((ART/'codex-only-provider-authorization-20260930.json').read_text())['poe_allowed'] is False
    isolation = yaml.safe_load((ROOT/'research-state.yaml').read_text())['resource_isolation']
    assert isolation['status'] == 'ACTIVE' and isolation['validation_status'] == 'PASS'
    previous = json.loads((PREVIOUS/'output/status.json').read_text())
    audit = json.loads((PREVIOUS/'audit.json').read_text())
    deep = json.loads((PREVIOUS/'deep-audit.json').read_text())
    review = json.loads((PREVIOUS/'final-review.json').read_text())
    assert previous['status'] == 'exited' and previous['exit_code'] == 0
    assert previous['completed'] == audit['episodes'] == deep['episodes'] == 10
    assert audit['valid'] and deep['valid'] and audit['success'] == 2
    assert review['full_report_written'] and review['success_videos_reviewed'] and review['all_task_keyframes_reviewed']
    assert h.digest(ROOT/review['report']) == review['report_sha256']
    assert json.loads((ART/'codex-v16-continuation/status.json').read_text())['phase'] == 'V16_FINISHED_REVIEW_REQUIRED'
    identities = json.loads((ART/'codex-v16-continuation/process-identities.json').read_text())['processes']
    assert all(h.process_identity(int(pid)) is None for pid in identities)
    assert not FOLDER.exists()
    base = json.loads((PREVIOUS/'manifest.json').read_text())
    changes = json.loads((DRAFT/'source-changes.json').read_text())
    validation = json.loads((DRAFT/'cpu-validation.json').read_text())
    assert validation['tests_passed'] == 33 and validation['source_changes'] == changes
    assert validation['test_sha256'] == h.digest(DRAFT/'test_failed_contact_recheck.py')
    proposal = json.loads((DRAFT/'proposal.json').read_text())
    argv = list(json.loads((PREVIOUS/'launch.json').read_text())['argv'])
    argv[argv.index('--name')+1] = NAME
    argv += ['--override', '+main.stage_failed_contact_recheck_enabled=true']
    h.write(QUEUE/'launch-command.json', dict(name=NAME, argv=argv, provider='codex_cli'))
    with (ROOT/'data/qd-ed-runner.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert all(h.digest(ROOT/p) == sha for p,sha in base['source_sha256'].items())
        for rel, hashes in changes.items():
            assert (not (ROOT/rel).exists()) if hashes['base_sha256'] is None else h.digest(ROOT/rel) == hashes['base_sha256']
            assert h.digest(DRAFT/rel) == hashes['candidate_sha256']
        h.reserve_own_hours()
        backup = QUEUE/'original-source'
        backup.mkdir()
        for rel, hashes in changes.items():
            destination = ROOT/rel
            if hashes['base_sha256'] is not None:
                saved = backup/rel
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination,saved)
            temporary = destination.with_name(destination.name+'.v17-install.tmp')
            temporary.write_bytes((DRAFT/rel).read_bytes())
            temporary.replace(destination)
        test = ROOT/'tests/test_stage_failed_contact_recheck.py'
        assert not test.exists()
        shutil.copy2(DRAFT/'test_failed_contact_recheck.py',test)
        h.write(QUEUE/'applied-source.json',dict(utc=h.utc(),files=changes,test=str(test),test_sha256=h.digest(test)))
        h.status('V17_INSTALLED_CPU_REGRESSION_RUNNING')
        tests = ['tests/test_stage_failed_contact_recheck.py','tests/test_stage_fused_carry_hold.py',
            'tests/test_stage_partial_visibility.py','tests/test_stage_evidence.py','tests/test_stage_grasp_guard.py',
            'tests/test_stage_robot_evidence.py','tests/test_stage_recovery_priority.py',
            'tests/test_stage_reward_progress_handoff.py','tests/test_stage_reward_reference.py',
            'tests/test_stage_carry_hold.py','tests/test_stage_carry_runtime.py','tests/test_stage_gripper_passthrough.py',
            'tests/test_stage_release_guard.py','tests/test_stage_target_marker_runtime.py',
            'tests/test_codex_online_observation.py','tests/test_codex_stage.py','tests/test_main_rdt_startup.py']
        environment = os.environ.copy()
        environment['CUDA_VISIBLE_DEVICES'] = ''
        environment['PYTHONPATH'] = str(ROOT)+os.pathsep+str(ROOT/'tests')
        command = [sys.executable,'-m','pytest','-q','-p','no:cacheprovider',*tests]
        with (QUEUE/'v17-installed-tests.log').open('x') as log:
            result = subprocess.run(command,cwd=ROOT,env=environment,stdout=log,stderr=subprocess.STDOUT)
        assert result.returncode == 0, 'Installed regression failed; no GPU dispatch'
        passed = re.findall(r'(\d+) passed',(QUEUE/'v17-installed-tests.log').read_text())
        assert passed and int(passed[-1]) >= 456
        h.write(QUEUE/'installed-cpu-validation.json',dict(utc=h.utc(),passed=int(passed[-1]),cpu_only=True,
            command=command,source_changes=changes,gpu_dispatched=False))
        prepare = list(argv)
        prepare[2] = 'prepare'
        h.execute(prepare,'v17-prepare.log')
        candidate = json.loads((FOLDER/'manifest.json').read_text())
        assert candidate['tasks'] == base['tasks'] and candidate['seeds'] == base['seeds']
        assert set(candidate['source_sha256']) == set(base['source_sha256']) | {'core/stage_failed_contact_recheck.py'}
        for rel,sha in candidate['source_sha256'].items():
            assert sha == (changes[rel]['candidate_sha256'] if rel in changes else base['source_sha256'][rel])
        before = yaml.safe_load((PREVIOUS/'resolved-config.yaml').read_text())
        after = yaml.safe_load((FOLDER/'resolved-config.yaml').read_text())
        delta = differences(before,after)
        bookkeeping = {'main.eds_eval.job_id','main.eds_eval.output_dir','perception.gemini.capture_dir'}
        assert [x for x in delta if x['path'] not in bookkeeping] == [dict(path='main.stage_failed_contact_recheck_enabled',before=None,after=True)]
        h.write(FOLDER/'parent-config-comparison.json',delta)
        proposal.update(status='INSTALLED_TESTED_FROZEN_READY_FOR_GPU2',production_installed=True,
            gpu_dispatch_prepared=True,installed_tests_passed=int(passed[-1]))
        h.write(FOLDER/'proposal.json',proposal)
        shutil.copy2(QUEUE/'installed-cpu-validation.json',FOLDER/'installed-cpu-validation.json')
        h.write(FOLDER/'parent-evidence.json',dict(parent=PREVIOUS.name,review=review,
            evidence='offline-failed-contact-reopening-screen.json'))
    with (ART/'codex-failed-contact-v17-supervisor.log').open('x') as log:
        process = subprocess.Popen(argv,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                                   start_new_session=True,close_fds=True)
    h.write(FOLDER/'launch.json',dict(utc=h.utc(),supervisor_pid=process.pid,queue_pid=os.getpid(),
        argv=argv,provider='codex_cli',scientific_parent=PREVIOUS.name))
    h.record_state(status='ACTIVE_CODEX_FAILED_CONTACT_V17',current_condition=NAME,active_candidate=NAME,
        active_supervisor_pid=process.pid,active_worker_pid=None,current_source_frozen=True,
        required_provider='codex_cli_chatgpt_managed_login',poe_allowed=False,
        latest_complete_condition=PREVIOUS.name,latest_complete_score='2/10 valid',selected_scientific_parent=PREVIOUS.name)
    h.prepend_status(f'# GPU2 Codex V17已启动 — {h.utc()}\n\nV16完整有效2/10，58+56审计和所有任务视频复核/报告保存。V17仅增加空抓后开爪复查，保留V16其余设置；安装后{passed[-1]}项CPU检查通过，已冻结完整十任务。supervisor{process.pid}、queue{os.getpid()}；读run/output/status.json。仅Codex，Poe禁止，goal未完成。')
    accounted = False
    while process.poll() is None:
        path = FOLDER/'output/status.json'
        if path.exists():
            progress = json.loads(path.read_text())
            h.status('V17_RUNNING',run=NAME,supervisor_pid=process.pid,progress=progress)
            if not accounted:
                h.execute([sys.executable,'scripts/stage_closed_loop_account.py'],'v17-start-accounting.log')
                accounted = True
            h.record_state(active_worker_pid=progress.get('pid'))
        time.sleep(30)
    h.write(QUEUE/'v17-supervisor-exit.json',dict(utc=h.utc(),returncode=process.returncode))
    if process.returncode != 0:
        raise RuntimeError('V17 supervisor failed; preserve evidence and do not auto-retry')
    for script,label in [('stage_closed_loop_deep_audit.py','deep-audit'),
                         ('stage_initialization_compare.py','initialization'),
                         ('stage_motion_diagnose.py','motion'),
                         ('stage_reward_reference_diagnose.py','reward-reference')]:
        h.execute([sys.executable,'scripts/'+script,NAME],'v17-'+label+'.log')
    h.execute([sys.executable,'scripts/stage_closed_loop_account.py'],'v17-accounting.log')
    h.execute([sys.executable,'scripts/stage_closed_loop_results_index.py'],'v17-results-index.log')
    audit=json.loads((FOLDER/'audit.json').read_text())
    deep=json.loads((FOLDER/'deep-audit.json').read_text())
    valid=audit['valid'] and deep['valid']
    h.record_state(status='CODEX_V17_COMPLETE_AWAITING_TRAJECTORY_REVIEW',active_worker_pid=None,
        active_supervisor_pid=None,current_source_frozen=False,latest_complete_condition=NAME,
        latest_complete_score=f'{audit["success"]}/10; valid={valid}')
    h.status('V17_FINISHED_REVIEW_REQUIRED',run=NAME,success=audit['success'],valid=valid,
             goal_not_automatically_marked_complete=True)
    h.prepend_status(f'# Codex V17完整结束，需继续复核 — {h.utc()}\n\n环境成功{audit["success"]}/10，两层审计valid={valid}；worker已退出。保留结果并完成视频/报告/目标审计，未自动标记goal完成。Poe禁止。')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        if QUEUE.exists(): h.status('CONTINUATION_ERROR_REVIEW_REQUIRED',error_type=type(exc).__name__,detail=str(exc))
        raise
