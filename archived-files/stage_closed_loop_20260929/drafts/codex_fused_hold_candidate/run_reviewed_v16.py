"""Install and test the reviewed fusion candidate, then run one frozen full10."""
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
ART = ROOT / 'artifacts/stage_closed_loop_20260929'
DRAFT = ART / 'drafts/codex_fused_hold_candidate'
PREVIOUS = ART / 'runs/codex_contact_radius_v15_historical_initialization_online_full10'
BASE = ART / 'runs/codex_partial_visibility_v14_historical_initialization_online_full10'
NAME = 'codex_fused_carry_v16_historical_initialization_online_full10'
FOLDER = ART / 'runs' / NAME
QUEUE = ART / 'codex-v16-continuation'
spec = importlib.util.spec_from_file_location('owned_v16_helpers', ART / 'drafts/codex_partial_visibility_v14/continue_after_v13.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
h.QUEUE = QUEUE


def differences(left, right, prefix=''):
    if isinstance(left, dict) and isinstance(right, dict):
        result = []
        for key in sorted(set(left) | set(right)):
            result.extend(differences(left.get(key), right.get(key), prefix + '.' + key if prefix else key))
        return result
    return [] if left == right else [dict(path=prefix, before=left, after=right)]


def main():
    QUEUE.mkdir(exist_ok=False)
    h.status('CHECKING_REVIEWED_V15_AND_V14_PARENT')
    authority = json.loads((ART / 'codex-only-provider-authorization-20260930.json').read_text())
    assert authority['poe_allowed'] is False
    for folder in (PREVIOUS, BASE):
        status = json.loads((folder / 'output/status.json').read_text())
        audit = json.loads((folder / 'audit.json').read_text())
        deep = json.loads((folder / 'deep-audit.json').read_text())
        review = json.loads((folder / 'final-review.json').read_text())
        assert status['status'] == 'exited' and status['exit_code'] == 0
        assert status['completed'] == audit['episodes'] == deep['episodes'] == 10
        assert audit['valid'] and deep['valid'] and audit['success'] == 2
        assert review['full_report_written'] and review['success_videos_reviewed']
        assert h.digest(ROOT / review['report']) == review['report_sha256']
    previous_queue = json.loads((ART / 'codex-v15-continuation/status.json').read_text())
    assert previous_queue['phase'] == 'V15_FINISHED_REVIEW_REQUIRED'
    for pid in (previous_queue['queue_pid'], 3198619, 3199447):
        assert h.process_identity(pid) is None
    assert not FOLDER.exists()
    base_manifest = json.loads((BASE / 'manifest.json').read_text())
    previous_manifest = json.loads((PREVIOUS / 'manifest.json').read_text())
    assert base_manifest['source_sha256'] == previous_manifest['source_sha256']
    changes = json.loads((DRAFT / 'source-changes.json').read_text())
    validation = json.loads((DRAFT / 'cpu-validation.json').read_text())
    assert validation['tests_passed'] == 183 and validation['source_changes'] == changes
    proposal = json.loads((DRAFT / 'proposal.json').read_text())
    proposal.update(name=NAME, status='SELECTED_AFTER_VALID_V15_FULL10_REVIEW', selected_utc=h.utc(),
                    scientific_parent=BASE.name, rejected_predecessor=PREVIOUS.name,
                    parent_score='2/10 valid', predecessor_score='2/10 valid',
                    rationale='6cm added no successes and increased guided chunks230to380; retainV14 and test fusion alone',
                    source_changes=changes, base_setting_not_selected=False,
                    protected_reserves_preserved=True)
    argv = list(json.loads((PREVIOUS / 'launch.json').read_text())['argv'])
    filtered = []
    i = 0
    while i < len(argv):
        if argv[i] == '--override' and 'contact_reward_max_distance_m=' in argv[i + 1]:
            i += 2
            continue
        filtered.append(argv[i])
        i += 1
    argv = filtered
    argv[argv.index('--name') + 1] = NAME
    argv += ['--override', '+main.stage_fused_carry_hold_enabled=true']
    h.write(QUEUE / 'launch-command.json', dict(name=NAME, argv=argv, provider='codex_cli'))
    with (ROOT / 'data/qd-ed-runner.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert all(h.digest(ROOT / p) == sha for p, sha in base_manifest['source_sha256'].items())
        for rel, hashes in changes.items():
            source = ROOT / rel
            if hashes['base_sha256'] is None:
                assert not source.exists()
            else:
                assert h.digest(source) == hashes['base_sha256']
            assert h.digest(DRAFT / rel) == hashes['candidate_sha256']
        h.reserve_own_hours()
        backup = QUEUE / 'original-source'
        backup.mkdir()
        for rel, hashes in changes.items():
            destination = ROOT / rel
            if hashes['base_sha256'] is not None:
                saved = backup / rel
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, saved)
            temp = destination.with_name(destination.name + '.v16-install.tmp')
            temp.write_bytes((DRAFT / rel).read_bytes())
            temp.replace(destination)
        test = ROOT / 'tests/test_stage_fused_carry_hold.py'
        assert not test.exists()
        shutil.copy2(DRAFT / 'test_fused_carry_hold.py', test)
        h.write(QUEUE / 'applied-source.json', dict(utc=h.utc(), files=changes,
                test=str(test), test_sha256=h.digest(test), scientific_parent=BASE.name))
        h.status('V16_INSTALLED_CPU_REGRESSION_RUNNING')
        tests = ['tests/test_stage_fused_carry_hold.py', 'tests/test_stage_partial_visibility.py',
                 'tests/test_stage_evidence.py', 'tests/test_stage_grasp_guard.py',
                 'tests/test_stage_robot_evidence.py', 'tests/test_stage_recovery_priority.py',
                 'tests/test_stage_reward_progress_handoff.py', 'tests/test_stage_reward_reference.py',
                 'tests/test_stage_carry_hold.py', 'tests/test_stage_carry_runtime.py',
                 'tests/test_stage_gripper_passthrough.py', 'tests/test_stage_release_guard.py',
                 'tests/test_stage_target_marker_runtime.py', 'tests/test_codex_online_observation.py',
                 'tests/test_codex_stage.py', 'tests/test_main_rdt_startup.py']
        test_env = os.environ.copy()
        test_env['CUDA_VISIBLE_DEVICES'] = ''
        test_env['PYTHONPATH'] = str(ROOT) + os.pathsep + str(ROOT / 'tests')
        command = [sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', *tests]
        with (QUEUE / 'v16-installed-tests.log').open('x') as log:
            result = subprocess.run(command, cwd=ROOT, env=test_env, stdout=log, stderr=subprocess.STDOUT)
        assert result.returncode == 0, 'Installed CPU regression failed; no GPU dispatch'
        test_log = (QUEUE / 'v16-installed-tests.log').read_text()
        passed = re.findall(r'(\d+) passed', test_log)
        assert passed and int(passed[-1]) >= 377
        h.write(QUEUE / 'installed-cpu-validation.json', dict(utc=h.utc(), passed=int(passed[-1]),
                cpu_only=True, command=command, source_changes=changes, gpu_dispatched=False))
        prepare = list(argv)
        prepare[2] = 'prepare'
        h.execute(prepare, 'v16-prepare.log')
        candidate = json.loads((FOLDER / 'manifest.json').read_text())
        assert candidate['tasks'] == base_manifest['tasks'] and candidate['seeds'] == base_manifest['seeds']
        assert set(candidate['source_sha256']) == set(base_manifest['source_sha256']) | {'core/stage_fused_carry_hold.py'}
        for rel, sha in candidate['source_sha256'].items():
            assert sha == (changes[rel]['candidate_sha256'] if rel in changes else base_manifest['source_sha256'][rel])
        before = yaml.safe_load((BASE / 'resolved-config.yaml').read_text())
        after = yaml.safe_load((FOLDER / 'resolved-config.yaml').read_text())
        delta = differences(before, after)
        bookkeeping = {'main.eds_eval.job_id', 'main.eds_eval.output_dir', 'perception.gemini.capture_dir'}
        scientific = [row for row in delta if row['path'] not in bookkeeping]
        assert scientific == [dict(path='main.stage_fused_carry_hold_enabled', before=None, after=True)]
        assert after['main']['contact_reward_max_distance_m'] == .10
        h.write(FOLDER / 'parent-config-comparison.json', delta)
        proposal.update(status='INSTALLED_TESTED_FROZEN_READY_FOR_GPU2', production_installed=True,
                        gpu_dispatch_prepared=True, installed_tests_passed=int(passed[-1]))
        h.write(FOLDER / 'proposal.json', proposal)
        shutil.copy2(QUEUE / 'installed-cpu-validation.json', FOLDER / 'installed-cpu-validation.json')
        h.write(FOLDER / 'parent-evidence.json', dict(parent=BASE.name,
                parent_event='milk task7 step376', parent_report=json.loads((BASE / 'final-review.json').read_text()),
                reviewed_predecessor=json.loads((PREVIOUS / 'final-review.json').read_text())))
    with (ART / 'codex-fused-carry-v16-supervisor.log').open('x') as log:
        process = subprocess.Popen(argv, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
    h.write(FOLDER / 'launch.json', dict(utc=h.utc(), supervisor_pid=process.pid, queue_pid=os.getpid(),
                                       argv=argv, provider='codex_cli', scientific_parent=BASE.name))
    h.record_state(status='ACTIVE_CODEX_FUSED_CARRY_V16', current_condition=NAME, active_candidate=NAME,
                   active_supervisor_pid=process.pid, active_worker_pid=None, current_source_frozen=True,
                   required_provider='codex_cli_chatgpt_managed_login', poe_allowed=False,
                   latest_complete_condition=PREVIOUS.name, latest_complete_score='2/10 valid',
                   selected_scientific_parent=BASE.name)
    h.prepend_status(f'# GPU2 Codex V16已启动 — {h.utc()}\n\nV15完整有效2/10，54+53审计通过，所有视频和报告已复核保存；6cm不采用。V16回到V14父版本，仅增加融合携带Stage规则；原生7D、完成判据、reward、模型保持。安装后{passed[-1]}项CPU检查通过，已冻结完整十任务。supervisor{process.pid}、queue{os.getpid()}；读取run/output/status.json获取worker和实时值，勿重复启动。Poe禁止，goal未完成。')
    accounted = False
    while process.poll() is None:
        path = FOLDER / 'output/status.json'
        if path.exists():
            progress = json.loads(path.read_text())
            h.status('V16_RUNNING', run=NAME, supervisor_pid=process.pid, progress=progress)
            if not accounted:
                h.execute([sys.executable, 'scripts/stage_closed_loop_account.py'], 'v16-start-accounting.log')
                accounted = True
            h.record_state(active_worker_pid=progress.get('pid'))
        time.sleep(30)
    h.write(QUEUE / 'v16-supervisor-exit.json', dict(utc=h.utc(), returncode=process.returncode))
    if process.returncode != 0:
        raise RuntimeError('V16 supervisor failed; preserve all evidence and do not auto-retry')
    for script, label in [('stage_closed_loop_deep_audit.py', 'deep-audit'),
                          ('stage_initialization_compare.py', 'initialization'),
                          ('stage_motion_diagnose.py', 'motion'),
                          ('stage_reward_reference_diagnose.py', 'reward-reference')]:
        h.execute([sys.executable, 'scripts/' + script, NAME], 'v16-' + label + '.log')
    h.execute([sys.executable, 'scripts/stage_closed_loop_account.py'], 'v16-accounting.log')
    h.execute([sys.executable, 'scripts/stage_closed_loop_results_index.py'], 'v16-results-index.log')
    audit = json.loads((FOLDER / 'audit.json').read_text())
    deep = json.loads((FOLDER / 'deep-audit.json').read_text())
    valid = audit['valid'] and deep['valid']
    h.record_state(status='CODEX_V16_COMPLETE_AWAITING_TRAJECTORY_REVIEW', active_worker_pid=None,
                   active_supervisor_pid=None, current_source_frozen=False, latest_complete_condition=NAME,
                   latest_complete_score=f'{audit["success"]}/10; valid={valid}')
    h.status('V16_FINISHED_REVIEW_REQUIRED', run=NAME, success=audit['success'], valid=valid,
             goal_not_automatically_marked_complete=True)
    h.prepend_status(f'# Codex V16完整结束，需继续复核 — {h.utc()}\n\n环境成功{audit["success"]}/10，两层审计valid={valid}；worker已退出。所有结果保留。请完成视频/报告与目标审计；未自动标记goal完成。Poe禁用。')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        if QUEUE.exists():
            h.status('CONTINUATION_ERROR_REVIEW_REQUIRED', error_type=type(exc).__name__, detail=str(exc))
        raise
