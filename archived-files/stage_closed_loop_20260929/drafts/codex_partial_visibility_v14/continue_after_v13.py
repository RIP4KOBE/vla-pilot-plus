"""Owned-study continuation: finish/audit V13, then test one frozen V14 fix."""
import datetime
import fcntl
import hashlib
import json
import math
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time

import yaml

ROOT=Path.cwd()
ART=ROOT/'artifacts/stage_closed_loop_20260929'
DRAFT=ART/'drafts/codex_partial_visibility_v14'
PREVIOUS=ART/'runs/codex_only_v13_historical_initialization_online_full10'
QUEUE=ART/'codex-v14-continuation'
PYTHON=sys.executable


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def write(path, value):
    path=Path(path);temp=path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');temp.replace(path)


def status(phase, **values):
    record=dict(utc=utc(),phase=phase,queue_pid=os.getpid(),**values)
    write(QUEUE/'status.json',record);print(json.dumps(record,ensure_ascii=False),flush=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def process_identity(pid):
    try:
        fields=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
        return None if fields[0]=='Z' else fields[19]
    except FileNotFoundError:
        return None


def execute(command, log_name):
    with (QUEUE/log_name).open('x') as log:
        result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError('Command failed; see '+log_name)


def record_state(**changes):
    with (ROOT/'data/qd-ed-state.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        path=ROOT/'research-state.yaml';text=path.read_text();data=yaml.safe_load(text)
        assert data['resource_isolation']['status']=='ACTIVE'
        assert data['resource_isolation']['validation_status']=='PASS'
        section=data['stage_closed_loop_recovery_20260929'];section.update(updated_utc=utc(),**changes)
        path.write_text(text.split('\nstage_closed_loop_recovery_20260929:\n')[0]+'\n'+
            yaml.safe_dump({'stage_closed_loop_recovery_20260929':section},sort_keys=False))


def prepend_status(message):
    for rel in ('HANDOFF_GPU6_GOAL.md','to_human/current-status.md'):
        path=ROOT/rel;path.write_text(message+'\n\n以下旧状态保留为历史：\n\n'+path.read_text())


def reserve_own_hours():
    # User waived budget stopping; keep the protected 24 GPUh separate in the
    # local accounting representation instead of silently consuming that reserve.
    with (ROOT/'data/qd-ed-state.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        path=ROOT/'research-state.yaml';text=path.read_text();data=yaml.safe_load(text)
        assert data['resource_isolation']['status']=='ACTIVE' and data['resource_isolation']['validation_status']=='PASS'
        consumed=data['stage_closed_loop_recovery_20260929']['effective_gpu_hours_upper_bound']
        old=data['budget']['max_gpu_hours'];new=max(old,float(math.ceil(consumed+24+5)))
        updated,count=re.subn(r'(?m)^  max_gpu_hours: [0-9.]+$',f'  max_gpu_hours: {new}',text,count=1)
        assert count==1;path.write_text(updated)
        write(QUEUE/'own-hour-accounting-reservation.json',dict(utc=utc(),old_cap=old,new_cap=new,
            consumed_upper_bound=consumed,protected_gpu_hours=24,next_candidate_reservation_hours=5,
            authority='User: 不用管预算，只要完成任务就好',peer_state_changed=False))


def main():
    authorization=json.loads((ART/'codex-only-provider-authorization-20260930.json').read_text())
    assert authorization['poe_allowed'] is False
    identities=json.loads((QUEUE/'predecessor-identities.json').read_text())
    status('WAITING_FOR_FROZEN_V13_COMPLETION')
    while any(process_identity(int(pid))==identity for pid,identity in identities.items()):
        if (QUEUE/'cancel.json').exists():
            status('CANCELLED_BEFORE_DISPATCH');return
        time.sleep(20)
    if (QUEUE/'cancel.json').exists():
        status('CANCELLED_BEFORE_DISPATCH');return
    previous_status=json.loads((PREVIOUS/'output/status.json').read_text())
    previous_audit=json.loads((PREVIOUS/'audit.json').read_text())
    assert previous_status['status']=='exited' and previous_status['exit_code']==0
    assert previous_status['completed']==10 and previous_audit['valid']
    execute([PYTHON,'scripts/stage_closed_loop_deep_audit.py',PREVIOUS.name],'v13-deep-audit.log')
    assert json.loads((PREVIOUS/'deep-audit.json').read_text())['valid']
    execute([PYTHON,'scripts/stage_initialization_compare.py',PREVIOUS.name],'v13-initialization.log')
    execute([PYTHON,'scripts/stage_motion_diagnose.py',PREVIOUS.name],'v13-motion.log')
    execute([PYTHON,'scripts/stage_reward_reference_diagnose.py',PREVIOUS.name],'v13-reward-reference.log')
    execute([PYTHON,'scripts/stage_closed_loop_account.py'],'v13-accounting.log')
    execute([PYTHON,'scripts/stage_closed_loop_results_index.py'],'v13-results-index.log')
    write(QUEUE/'v13-completed.json',dict(utc=utc(),status=previous_status,audit=previous_audit,
        note='Environment metric only; gallery saved for visual review. No result rewriting or episode retries.'))
    if previous_audit['success']>=3:
        record_state(status='CODEX_COHORT_COMPLETE_AWAITING_VIDEO_REVIEW',active_worker_pid=None,
            active_supervisor_pid=None,current_source_frozen=False)
        status('V13_SCORE_GATE_REACHED_VIDEO_REVIEW_REQUIRED',success=previous_audit['success'])
        prepend_status(f'# Codex V13 已完成，等待视频复核 — {utc()}\n\n完整有效环境成功数 {previous_audit["success"]}/10。未自动安装V14；结果与视频已保存，需继续复核实际目标搬运。Poe保持禁用。')
        return
    status('INSTALLING_TESTED_PARTIAL_VISIBILITY_FIX',v13_success=previous_audit['success'])
    reserve_own_hours()
    with (ROOT/'data/qd-ed-runner.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        manifest=json.loads((PREVIOUS/'manifest.json').read_text())
        assert all(digest(ROOT/p)==h for p,h in manifest['source_sha256'].items())
        assert '137 passed' in (DRAFT/'tests-r2.log').read_text()
        changes=json.loads((DRAFT/'source-changes.json').read_text())
        for rel, hashes in changes.items():
            assert digest(ROOT/rel)==hashes['base_sha256']
            assert digest(DRAFT/rel)==hashes['candidate_sha256']
        backup=QUEUE/'original-source';backup.mkdir()
        for rel in changes:
            destination=backup/rel;destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/rel,destination)
            temp=(ROOT/rel).with_name(Path(rel).name+'.codex-v14.tmp')
            temp.write_bytes((DRAFT/rel).read_bytes());temp.replace(ROOT/rel)
        test=ROOT/'tests/test_stage_partial_visibility.py'
        assert not test.exists();shutil.copy2(DRAFT/'test_partial_visibility.py',test)
        write(QUEUE/'applied-source.json',dict(utc=utc(),files=changes,tests=str(test)))
        tests=['tests/test_stage_partial_visibility.py','tests/test_stage_evidence.py',
            'tests/test_stage_grasp_guard.py','tests/test_stage_robot_evidence.py',
            'tests/test_stage_recovery_priority.py','tests/test_stage_reward_progress_handoff.py',
            'tests/test_stage_reward_reference.py','tests/test_stage_carry_hold.py',
            'tests/test_stage_carry_runtime.py','tests/test_stage_gripper_passthrough.py',
            'tests/test_stage_release_guard.py','tests/test_stage_target_marker_runtime.py',
            'tests/test_codex_online_observation.py','tests/test_codex_stage.py','tests/test_main_rdt_startup.py']
        execute([PYTHON,'-m','pytest','-q',*tests],'v14-installed-tests.log')
        launch=json.loads((DRAFT/'launch-command.json').read_text())
        command=list(launch['argv']);command[2]='prepare'
        execute(command,'v14-prepare.log')
    folder=ART/'runs'/launch['name']
    assert not (folder/'output').exists()
    shutil.copy2(DRAFT/'proposal.json',folder/'proposal.json')
    shutil.copy2(DRAFT/'observed-failure-evidence.json',folder/'predecessor-failure-evidence.json')
    with (ART/'codex-partial-visibility-v14-supervisor.log').open('x') as log:
        process=subprocess.Popen(launch['argv'],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,
            stderr=subprocess.STDOUT,start_new_session=True,close_fds=True)
    write(folder/'launch.json',dict(utc=utc(),supervisor_pid=process.pid,argv=launch['argv'],
        provider='codex_cli',queue_pid=os.getpid(),predecessor=PREVIOUS.name))
    record_state(status='ACTIVE_CODEX_PARTIAL_VISIBILITY_V14',current_condition=launch['name'],
        active_candidate=launch['name'],active_supervisor_pid=process.pid,active_worker_pid=None,
        current_source_frozen=True,required_provider='codex_cli_chatgpt_managed_login',poe_allowed=False,
        latest_complete_condition=PREVIOUS.name,latest_complete_score=f'{previous_audit["success"]}/10 valid')
    prepend_status(f'# GPU2 Codex V14 已自动启动 — {utc()}\n\nV13完整有效 {previous_audit["success"]}/10，审计、视频索引和记账已保存。V14仅修复明确抓持且悬空、但目标部分遮挡时被错误留在Stage1的问题；完成判定不放宽。\n\n当前 {launch["name"]}，supervisor {process.pid}，通过Codex账号调用gpt-6-astra/low，Poe禁用。冻结代码运行中不要修改。进度位于对应run/output/status.json；接续记录为artifacts/stage_closed_loop_20260929/codex-v14-continuation/status.json。')
    start_accounted=False
    while process.poll() is None:
        path=folder/'output/status.json'
        if path.exists():
            progress=json.loads(path.read_text())
            status('V14_RUNNING',run=launch['name'],supervisor_pid=process.pid,progress=progress)
            if not start_accounted:
                execute([PYTHON,'scripts/stage_closed_loop_account.py'],'v14-start-accounting.log')
                start_accounted=True
            record_state(active_worker_pid=progress.get('pid'))
        time.sleep(30)
    write(QUEUE/'v14-supervisor-exit.json',dict(utc=utc(),returncode=process.returncode))
    if process.returncode!=0:
        raise RuntimeError('V14 supervisor failed; preserve all partial results')
    execute([PYTHON,'scripts/stage_closed_loop_deep_audit.py',launch['name']],'v14-deep-audit.log')
    execute([PYTHON,'scripts/stage_initialization_compare.py',launch['name']],'v14-initialization.log')
    execute([PYTHON,'scripts/stage_motion_diagnose.py',launch['name']],'v14-motion.log')
    execute([PYTHON,'scripts/stage_reward_reference_diagnose.py',launch['name']],'v14-reward-reference.log')
    execute([PYTHON,'scripts/stage_closed_loop_account.py'],'v14-accounting.log')
    execute([PYTHON,'scripts/stage_closed_loop_results_index.py'],'v14-results-index.log')
    audit=json.loads((folder/'audit.json').read_text());deep=json.loads((folder/'deep-audit.json').read_text())
    record_state(status='CODEX_V14_COMPLETE_AWAITING_TRAJECTORY_REVIEW',active_worker_pid=None,
        active_supervisor_pid=None,current_source_frozen=False,latest_complete_condition=launch['name'],
        latest_complete_score=f'{audit["success"]}/10; valid={audit["valid"] and deep["valid"]}')
    status('V14_FINISHED_REVIEW_REQUIRED',run=launch['name'],success=audit['success'],
        valid=audit['valid'] and deep['valid'],goal_not_automatically_marked_complete=True)
    prepend_status(f'# Codex V14 已完成，需继续结果/视频复核 — {utc()}\n\n本轮环境结果 {audit["success"]}/10；两层审计valid={audit["valid"] and deep["valid"]}。GPU worker已退出。结果、失败、视频索引及记账已保存。不能自动视为研究目标完成；请继续视频复核/必要闭环分析。Poe仍禁用。')


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        status('CONTINUATION_ERROR_REVIEW_REQUIRED',error_type=type(exc).__name__,detail=str(exc))
        raise
