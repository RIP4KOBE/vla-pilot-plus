"""Run one reviewed, frozen Codex-only contact-radius comparison; no auto-retry."""
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import yaml

ROOT = Path.cwd()
ART = ROOT / 'artifacts/stage_closed_loop_20260929'
DRAFT = ART / 'drafts/codex_contact_radius_v15'
PREVIOUS = ART / 'runs/codex_partial_visibility_v14_historical_initialization_online_full10'
QUEUE = ART / 'codex-v15-continuation'
HELPERS = ART / 'drafts/codex_partial_visibility_v14/continue_after_v13.py'
spec = importlib.util.spec_from_file_location('owned_continuation_helpers', HELPERS)
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
    h.status('CHECKING_REVIEWED_PREDECESSOR')
    authority = json.loads((ART / 'codex-only-provider-authorization-20260930.json').read_text())
    assert authority['poe_allowed'] is False
    previous_status = json.loads((PREVIOUS / 'output/status.json').read_text())
    audit = json.loads((PREVIOUS / 'audit.json').read_text())
    deep = json.loads((PREVIOUS / 'deep-audit.json').read_text())
    review = json.loads((PREVIOUS / 'final-review.json').read_text())
    previous_queue = json.loads((ART / 'codex-v14-continuation/status.json').read_text())
    assert previous_status['status'] == 'exited' and previous_status['exit_code'] == 0
    assert previous_status['completed'] == audit['episodes'] == deep['episodes'] == 10
    assert audit['valid'] and deep['valid'] and audit['success'] < 3
    assert review['full_report_written'] and review['success_videos_reviewed']
    assert review['environment_success'] == audit['success']
    assert previous_queue['phase'] == 'V14_FINISHED_REVIEW_REQUIRED'
    assert h.process_identity(previous_queue['queue_pid']) is None
    launch = json.loads((DRAFT / 'launch-command.json').read_text())
    proposal = json.loads((DRAFT / 'proposal.json').read_text())
    assert launch['name'] == proposal['name']
    folder = ART / 'runs' / launch['name']
    assert not folder.exists()
    manifest = json.loads((PREVIOUS / 'manifest.json').read_text())
    with (ROOT / 'data/qd-ed-runner.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert all(h.digest(ROOT / p) == sha for p, sha in manifest['source_sha256'].items())
        h.reserve_own_hours()
        command = list(launch['argv'])
        command[2] = 'prepare'
        h.execute(command, 'v15-prepare.log')
        candidate = json.loads((folder / 'manifest.json').read_text())
        assert candidate['source_sha256'] == manifest['source_sha256']
        assert candidate['tasks'] == manifest['tasks'] and candidate['seeds'] == manifest['seeds']
        before = yaml.safe_load((PREVIOUS / 'resolved-config.yaml').read_text())
        after = yaml.safe_load((folder / 'resolved-config.yaml').read_text())
        delta = differences(before, after)
        bookkeeping = {'main.eds_eval.job_id', 'main.eds_eval.output_dir', 'perception.gemini.capture_dir'}
        scientific = [row for row in delta if row['path'] not in bookkeeping]
        assert scientific == [dict(path='main.contact_reward_max_distance_m', before=.10, after=.06)]
        h.write(folder / 'predecessor-config-comparison.json', delta)
        proposal.update(status='ADOPTED_AFTER_VALID_V14_FULL10_REVIEW', adopted_utc=h.utc(),
                        predecessor_score=audit['success'], source_changes=[])
        h.write(folder / 'proposal.json', proposal)
        shutil.copy2(DRAFT / 'observed-input-predicate-check.json', folder / 'observed-input-predicate-check.json')
    with (ART / 'codex-contact-radius-v15-supervisor.log').open('x') as log:
        process = subprocess.Popen(launch['argv'], cwd=ROOT, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
    h.write(folder / 'launch.json', dict(utc=h.utc(), supervisor_pid=process.pid, queue_pid=os.getpid(),
                                       argv=launch['argv'], provider='codex_cli', predecessor=PREVIOUS.name))
    h.record_state(status='ACTIVE_CODEX_CONTACT_RADIUS_V15', current_condition=launch['name'],
                   active_candidate=launch['name'], active_supervisor_pid=process.pid, active_worker_pid=None,
                   current_source_frozen=True, required_provider='codex_cli_chatgpt_managed_login', poe_allowed=False,
                   latest_complete_condition=PREVIOUS.name, latest_complete_score=f'{audit["success"]}/10 valid')
    h.prepend_status(f'# GPU2 Codex V15 已启动 — {h.utc()}\n\nV14完整有效{audit["success"]}/10，完整报告与两项成功视频复核已保存。V15只将reward交接最大距离从0.10m改为已有0.06m；源码与其余科学设置完全相同，每任务fresh reward和在线Stage均为Codex，Poe禁用。\n\n当前{launch["name"]}，supervisor{process.pid}，queue{os.getpid()}。读取run/output/status.json获取worker和进度；不要重复启动或修改冻结源码。完整十任务结束后自动审计/记账，本会话再评估，未提前宣称达到3/10。')
    start_accounted = False
    while process.poll() is None:
        status_path = folder / 'output/status.json'
        if status_path.exists():
            progress = json.loads(status_path.read_text())
            h.status('V15_RUNNING', run=launch['name'], supervisor_pid=process.pid, progress=progress)
            if not start_accounted:
                h.execute([sys.executable, 'scripts/stage_closed_loop_account.py'], 'v15-start-accounting.log')
                start_accounted = True
            h.record_state(active_worker_pid=progress.get('pid'))
        time.sleep(30)
    h.write(QUEUE / 'v15-supervisor-exit.json', dict(utc=h.utc(), returncode=process.returncode))
    if process.returncode != 0:
        raise RuntimeError('V15 supervisor failed; preserve partial evidence and do not retry')
    for script, log in [('stage_closed_loop_deep_audit.py', 'deep-audit'),
                        ('stage_initialization_compare.py', 'initialization'),
                        ('stage_motion_diagnose.py', 'motion'),
                        ('stage_reward_reference_diagnose.py', 'reward-reference')]:
        h.execute([sys.executable, 'scripts/' + script, launch['name']], 'v15-' + log + '.log')
    h.execute([sys.executable, 'scripts/stage_closed_loop_account.py'], 'v15-accounting.log')
    h.execute([sys.executable, 'scripts/stage_closed_loop_results_index.py'], 'v15-results-index.log')
    audit = json.loads((folder / 'audit.json').read_text())
    deep = json.loads((folder / 'deep-audit.json').read_text())
    valid = audit['valid'] and deep['valid']
    h.record_state(status='CODEX_V15_COMPLETE_AWAITING_TRAJECTORY_REVIEW', active_worker_pid=None,
                   active_supervisor_pid=None, current_source_frozen=False, latest_complete_condition=launch['name'],
                   latest_complete_score=f'{audit["success"]}/10; valid={valid}')
    h.status('V15_FINISHED_REVIEW_REQUIRED', run=launch['name'], success=audit['success'], valid=valid,
             goal_not_automatically_marked_complete=True)
    h.prepend_status(f'# Codex V15 完整结束，需继续复核 — {h.utc()}\n\n环境成功{audit["success"]}/10，两层审计valid={valid}；worker已退出。结果、视频、配置和记账保留，未自动标记goal完成。请继续视频复核、结果报告与必要迭代。Poe仍禁用。')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        if QUEUE.exists():
            h.status('CONTINUATION_ERROR_REVIEW_REQUIRED', error_type=type(exc).__name__, detail=str(exc))
        raise
