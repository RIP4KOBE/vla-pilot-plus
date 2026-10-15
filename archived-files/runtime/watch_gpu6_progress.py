#!/usr/bin/env python3
"""Read-only terminal progress display. Never dispatches or stops experiments."""
import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ARTIFACT = Path(__file__).resolve().parents[1]
WORKTREE = Path('/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z')
RUNTIME = ARTIFACT / 'runtime'


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


def records(path, tail_bytes=None):
    try:
        with Path(path).open('rb') as stream:
            if tail_bytes and os.fstat(stream.fileno()).st_size > tail_bytes:
                stream.seek(-tail_bytes, os.SEEK_END)
                stream.readline()
            text = stream.read().decode('utf-8', errors='replace')
        result = []
        for line in text.splitlines():
            try:
                result.append(json.loads(line))
            except ValueError:
                pass  # A concurrent append can leave the last display line incomplete.
        return result
    except OSError:
        return []


def alive(process):
    try:
        fields = Path(f"/proc/{process['pid']}/stat").read_text().rsplit(')', 1)[1].split()
        return fields[0] not in {'Z', 'X'} and fields[19] == process['proc_start_ticks']
    except (OSError, KeyError, IndexError):
        return False


def nvidia(query):
    try:
        result = subprocess.run(['nvidia-smi', '-i', '6', query, '--format=csv,noheader,nounits'],
                                capture_output=True, text=True, timeout=5)
        if result.returncode:
            return []
        return [[value.strip() for value in row] for row in csv.reader(result.stdout.splitlines())]
    except (OSError, subprocess.TimeoutExpired):
        return []


def display():
    status = read_json(RUNTIME / 'gpu6-c0-xid-queue-status.json')
    process = read_json(RUNTIME / 'gpu6-c0-xid-queue-process.json')
    queue_gpu = next((g for g in status.get('gpu_inventory', []) if g.get('physical_gpu') == 6), {})
    device = nvidia('--query-gpu=memory.used,memory.total,utilization.gpu')
    apps = nvidia('--query-compute-apps=pid,used_gpu_memory')
    queue_state = status.get('status', '未知')
    labels = {'starting': '核验冻结输入', 'waiting': '等待 GPU6 释放', 'selected': '准备派发',
              'running': '正在运行诊断', 'completed': '诊断队列完成，待结果审查',
              'episode_completed': '诊断已结束', 'failed': '队列失败，待处理', 'interrupted': '队列已暂停'}
    heartbeat = max(0, time.time() - status.get('updated_unix', time.time()))
    lines = ['RDT + QD + ED | GPU6 实时进度',
             datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC') + '  | 显示每5秒刷新；队列每30秒扫描',
             '', f"队列：{labels.get(queue_state, queue_state)} | PID {process.get('pid', '?')} | "
             f"{'存活' if alive(process) else '未运行'}",
             f"状态文件更新时间：{heartbeat:.0f}秒前（运行中不代表GPU任务无进展）"]
    if device and len(device[0]) == 3:
        used, total, utilization = device[0]
        lines.append(f'GPU6：显存 {used}/{total} MiB | 利用率 {utilization}%')
    else:
        lines.append('GPU6：本次 NVIDIA 元数据查询不可用')
    lines.append('GPU计算进程：' + ('；'.join(f'PID {r[0]} / {r[1]} MiB' for r in apps if len(r) == 2) or '无 / 查询暂不可用'))
    if queue_state == 'waiting':
        lines.append(f"稳定空闲：{queue_gpu.get('idle_observed_seconds', 0):.0f}/{status.get('idle_stability_seconds', 120)}秒"
                     '（按队列快照；需无计算进程、无CUDA预约、显存<1024MiB）')
    lines.extend(['', f"当前诊断：{status.get('current_episode_key', 'gpu6_native_c0_t00_r1')}",
                  f"队列完成：{len(status.get('completed_keys', []))}/{len(status.get('episode_keys', [1]))}；单次上限720步 / 1800秒"])
    journal = records(WORKTREE / 'data/attempt-ledger.jsonl')
    groups = {}
    for event in journal:
        groups.setdefault(event.get('attempt_id'), []).append(event)
    current = [v for v in groups.values() if v[0].get('episode_key') == 'gpu6_native_c0_t00_r1'
               and v[0].get('output_dir', '').startswith(str(ARTIFACT) + '/')]
    if current:
        group = current[-1]
        last = group[-1]
        output = Path(last['output_dir'])
        phases = records(output / 'eds_eval/phase_timing.jsonl', 131072)
        nested = records(output / 'eds_eval/mujoco_phase_timing.jsonl', 65536)
        steps = [p['global_step'] + 1 for p in phases if p.get('name') == 'adapter_step' and p.get('event') == 'exit']
        dispatch = next((e for e in group if e.get('event') == 'dispatched'), {})
        elapsed = last.get('gpu_process_wall_seconds', max(0, time.time() - dispatch.get('time_unix', time.time())))
        lines.append(f"本次尝试：{last.get('event')} | 已完成环境步 {max(steps, default=0)}/720 | 耗时 {elapsed:.0f}秒")
        if phases:
            p = phases[-1]
            lines.append(f"最近阶段：step {p.get('global_step')} / {p.get('name')} / {p.get('event')} / {p.get('elapsed_s', 0):.3f}秒")
        if nested:
            p = nested[-1]
            lines.append(f"最近渲染：{p.get('name')} / {p.get('event')} / {p.get('elapsed_s', 0):.3f}秒")
        faults = read_json(output / 'gpu-kernel-xid.json').get('records', [])
        lines.append('本次 Xid：' + (', '.join(str(f['xid']) for f in faults) or '尚未记录'))
        if last.get('reason'):
            lines.append('尝试停止原因：' + str(last['reason']))
    else:
        lines.append('本次恢复尚未派发；历史C0已中止，完成13步。')
    finals = [g[-1] for g in groups.values() if g[-1].get('event') in {'valid', 'aborted'}]
    dispatched = sum(any(e.get('event') == 'dispatched' for e in g) for g in groups.values())
    valid = sum(f.get('event') == 'valid' and f.get('outcome_valid') is True for f in finals)
    invalid = sum(f.get('event') == 'valid' and f.get('outcome_valid') is not True for f in finals)
    aborted = sum(f.get('event') == 'aborted' for f in finals)
    health = records(WORKTREE / 'data/gpu-healthcheck-ledger.jsonl')
    closed_seconds = sum(float(f.get('gpu_process_wall_seconds', 0)) for f in finals)
    closed_seconds += sum(float(e.get('gpu_process_wall_seconds', 0)) for e in health if e.get('event') in {'completed', 'aborted'})
    comparison = [f for f in finals if f.get('identity', {}).get('iteration') == 'N1R' and f.get('outcome_valid') is True]
    lines.extend(['', f'首轮算法比较：有效 {len(comparison)}/30（C0/Q0/N1各10）；等待运行环境就绪',
                  f'累计尝试：{dispatched}/240 | 有效 {valid} / 无效 {invalid} / 中止 {aborted}',
                  f'已结算 GPU成本：{closed_seconds / 3600:.4f}/48小时（正在运行的成本于结束后结算）',
                  '故障排查：历史已确认Xid31/109；新增细分计时与故障监控；根因/修复未验证。'])
    if status.get('reason'):
        lines.append('队列停止原因：' + str(status['reason']))
    lines.extend(['', 'Ctrl+B 再按 D：离开监视终端；实验队列继续运行。'])
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    try:
        while True:
            page = display()
            if sys.stdout.isatty() and not args.once:
                print('\033[2J\033[H', end='')
            print(page, flush=True)
            if args.once:
                break
            time.sleep(5)
    except KeyboardInterrupt:
        print('\n监视器结束；实验队列保持独立运行。')


if __name__ == '__main__':
    main()
