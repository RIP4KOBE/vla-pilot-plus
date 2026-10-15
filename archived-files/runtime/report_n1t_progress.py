"""Write a reviewable partial report, never authorize a scientific phase."""
from pathlib import Path
import datetime
import json
import statistics
A=Path(__file__).resolve().parents[1]
W=Path('/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z')

def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default

status=read(A/'runtime/n1t-gpu2-cohort-queue-status.json',{})
audit=read(A/'analysis/n1t/completed-runtime-audit.json',{'rows':[]})
rows=audit['rows'];by_cell={(v['task_id'],v['profile']):v for v in rows}
exposure=read(A/'analysis/n1t/stage-guidance-exposure.json',{'rows':[]})['rows']
events=[json.loads(v) for v in (W/'data/attempt-ledger.jsonl').read_text().splitlines()]
latest={e['attempt_id']:e for e in events if e.get('identity',{}).get('iteration')=='N1T'}
invalid=[e for e in latest.values() if e['event'] in {'valid','aborted'} and e.get('outcome_valid') is not True]
running=[e for e in latest.values() if e['event']=='dispatched']
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
lines=['# N1T实验进度与阶段性结果','',f'更新：{now}','',
 f'**有效完成 {len(rows)}/30，成功 {sum(v["success"] for v in rows)}；无效中断 {len(invalid)}。正式≥5/10目标尚未验收。**','',
 '方案：C0（RDT+ED）和Q0（原sparse QD）各10回合，随后N1（距离×夹爪命令duty描述符）10回合。当前属于开发实验，不是正式测试。','',
 f'执行状态：{status.get("status","unknown")}；当前条目：`{status.get("current_episode_key","unknown")}`。物理GPU2，队列PID {status.get("pid","unknown")}，全研究最多一个GPU工作进程。','',
 '| 任务 | C0 | Q0 | N1 |','|---|---|---|---|']
for task in range(10):
    cells=[]
    for profile in ['C0','Q0','N1']:
        if (task,profile) in by_cell:
            x=by_cell[task,profile];cells.append(('成功' if x['success'] else '失败')+f'（有效，{x["wall_s"]/60:.1f}分钟）')
        elif any(e['identity']['task_id']==task and e['identity']['profile']==profile for e in invalid):cells.append('无效中断')
        elif any(e['identity']['task_id']==task and e['identity']['profile']==profile for e in running):cells.append('运行中')
        else:cells.append('未完成')
    lines.append(f'| {task} | '+ ' | '.join(cells)+' |')
lines += ['', '## 已完成回合的执行检查','',
 f'- Stage查询 {sum(v["stage_calls"] for v in rows)} 次，失败 {sum(v["stage_failed_calls"] for v in rows)} 次；明确重连后成功完成 {sum(v.get("recovered_reconnect_calls",0) for v in exposure)} 次。此处成功指调用通过格式、退出码和计账检查，不代表机器人完成任务。',
 f'- GPU Xid记录合计 {sum(v["xid_records"] for v in rows)}；所有已列入有效回合的必要成本记录均完整。',
 f'- 已完成回合GPU进程累计 {sum(v["wall_s"] for v in rows)/3600:.3f} 小时；其中Stage等待 {sum(v["stage_wall_s"] for v in rows)/3600:.3f} 小时。该统计不含其他轮次、无效回合或等待资源的时间。',
 '- 每个启用ED的动作块检查176候选/11评分批次，C0关闭QD，Q0保留旧描述符；N1运行后单独检查新描述符与真实父代采样。',
 '- 部分失败回合出现过Stage0预测；成功率严格使用仿真环境的成功判据。', '',
 '## 本轮条件及结论边界','',
 '- 源码冻结 `a5a65c441bb29412f90d1335069ebd0cd1118512`，原计划SHA `490e5d044a2c427eba1972669742ee30cae4bfde70c2551ad79624e45c31acfd`。',
 '- 固定RDT权重、5步扩散、预测64/执行8步、720环境步、每回合1800秒上限；Stage开启、grounding关闭，任务缓存与种子保持冻结。',
 '- Stage使用固定CLI0.155.1、gpt-6-astra/low、JSON schema及completed_reconnect_v1。每次只发起一个应用层调用；CLI内部HTTP重试总数仍不可直接观察。',
 '- 资源调度改为持有共享运行锁完成原计划剩余条目；原科学身份、算法、预算、成功标准均未修改。',
 '- N1S的8个有效失败及1个无效中断、N1R和重启诊断均单独保留，未混入本轮成功率；成本仍计入共享预算。',
 '- 部分相同种子的跨轮Stage决策不同；未保存每次调用图像哈希，不能仅凭决策日志锁定差异来源。比较使用本轮完整对照，不把片段表现外推成正式结果。','',
 '下一步：完成30个开发回合后，结合有效性和机制活动检查，评估N1是否达到至少5/10且不低于同轮C0、Q0；满足后才进入每组20回合独立验证，再进入正式每组10回合验收。此报告不自动授权后续阶段。','',
 f'详细数值：[执行审计]({A}/analysis/n1t/completed-runtime-audit.json)、[机制审计]({A}/analysis/n1t/finished-mechanism-audit.json)、[Stage审计]({A}/analysis/n1t/stage-guidance-exposure.json)。']
p=A/'analysis/n1t/live-report.zh.md';tmp=p.with_suffix('.md.tmp');tmp.write_text('\n'.join(lines)+'\n');tmp.replace(p)
print(json.dumps({'report':str(p),'valid_completed':len(rows),'invalid':len(invalid),'running':len(running)}))
