"""Write owner-only closure documentation/state from audited frozen evidence."""
from pathlib import Path
import datetime,json,os,sys,yaml
W=Path('/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z');A=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z')
sys.path.insert(0,str(W/'scripts'));import qd_ed_final_runner as r
ap=A/'analysis/n1w/final-audit.json';a=r.read_json(ap);assert all(a['checks'].values())
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
report=W/'docs/03_evidence/qd_ed_n1w/2026-09-24-final-report.md';report.parent.mkdir(parents=True,exist_ok=True)
report_text=f'''# N1W GPU2 结论：恢复回合总时限触发，未形成完整 N1 结果

N1W 于 2026-09-24 08:56:50 UTC 停止，结论为 **INCOMPLETE_RECOVERY_EPISODE_TIMEOUT_NO_ADOPTION**。
原计划 30 个主回合，实际派发 3 个主回合和 1 个恢复回合；2 个科学有效结果，
27 个主回合未派发，N1 没有完整有效回合。**≥5/10 未证明，不能给出 N1 成功率。**
这次结束于已批准的停止条件，不是预算耗尽，也不是 GPU 故障。

## 本轮实际结果

| task0 / 组别 | 完成步数 | 进程耗时 | Stage 已记录完成/失败 | 科学结论 |
|---|---:|---:|---:|---|
| Q0：RDT+ED+原 QD | 720 | 708.26秒 | 15/0 | 有效任务失败，0/1 |
| C0：RDT+ED，无 QD | 720 | 903.23秒 | 28/0 | 有效任务失败，0/1 |
| N1：距离×夹爪占比，主回合 | 200 | 639.47秒 | 8/1 | 明确 Stage 超时，可恢复中止 |
| N1：同一 task/profile 唯一恢复 | 432 | 1801.56秒 | 22/0 | 整回合总时限，无效、不再恢复 |

N1 的两次尝试不能作为两个独立样本，也不能计为 N1 0/1 或 0/2。
Q0/C0 各只有 task0 一个有效结果，不能据此重排 baseline，不能与旧版本拼成10次。
Q0/C0 的引导块分别为47/29，其余非引导块为43/61；N1两次部分轨迹分别记录5/6个引导块。

## 停止原因与恢复核验

N1主回合第9次Stage调用在step200等待180.184643秒后超时：只记录到thread/turn开始，
没有完成回复和usage，满足已批准的前瞻性 `codex_timeout` 恢复条件。配置、输入身份、
成本记录、数值/选择不变量及无Xid检查通过；原始失败tokens保持UNKNOWN。
恢复计划只改episode_key、recovery分组和明确retry_of，源码、运行时、初始状态、seed、
算法参数不变。独立8项核验见 `analysis/n1w/task00-n1-recovery-audit.json`。

恢复回合已记录的22次Stage调用都完成了回复与usage，单次中位耗时67.44秒，最大170.16秒，
合计1649.74秒，占1801.56秒进程耗时的**91.57%**。其中5次有已允许的编号重连诊断。
第432步进入下一次Stage阶段时，父runner的1800秒整回合时限终止了进程。
因此最后阶段的完整调用数、token总量及完整episode compute均未知，不能用22次已完成
调用的已知小计冒充整回合总量。该回合原始 `event=valid` / `task_failure=true` 是既有
runner的终态记账字段；`outcome_valid=false` 决定其不属于科学有效结果，原记录不改写。

批准协议明确每个task/profile最多恢复1次，且恢复再次失败或不可恢复错误即停止版本。
全N1W还有4个未用恢复名额，不代表可给此cell追加第2次恢复；也不能跳过它、只跑剩余27个
回合后宣称完整比较。未启动validation/formal或新版本。

GPU2所有4次尝试的Xid记录均为空。监督进程3318782、恢复worker3404890已退出，
本研究运行锁已释放；GPU2观察为1MiB显存、0%利用率。未操作其他研究的GPU/进程/状态。

## 工程与算法机制证据

新规则 `completed_transport_fallback_v1` 已按批准启用，冻结源码为
`c75ff0f4eb4c8ae23dfc41b5f7449e99c06ff9ee`。启动前237项CPU检查通过，
模型/源码/输入/Stage公共配置预检通过；未额外添加GPU探针或在线合成Stage调用。
本轮已记录73次成功Stage回复、1次明确超时；**接受的HTTPS回退通知为0次**。
所以不能声称真实回退路径已被本轮验证，也不能把这次停止归因于回退解析器拒绝。
本轮更直接的阻碍是Stage等待及其与整回合时限的冲突；CLI、网络、服务端各自贡献尚未定位。
时间先后及不同轨迹不能证明并行研究导致延迟，也不能证明N1算法使Stage变慢。

所有已记录引导块保持176候选/11评分批次，数值及QD不变量违规均为0。
N1新描述符和轴定义正确，主回合5个、恢复6个引导块均有真实QD活动；占用cell范围均为4–14。
主回合50个父代批次中20个包含不同夹爪占比；恢复60个父代批次中30个包含不同夹爪占比。
这比最初两个块只有duty=0的观察更完整，证明新轴有实际动作模式机会并影响父代集合。
但它们是中止轨迹的机制观测，不能代替完整任务结局或作为N1优于Q0的因果证据。
仅保存的Q0前两个动作trace也不足以推断整回合反事实。未据这些中途数据调整bins或选择任务。

## 冻结证据与独立预算

- 原N1W计划SHA：`{a['plan_sha256']}`。
- 运行时SHA：`{a['runtime_sha256']}`。
- 16项关闭核验全部通过：88个执行源码文件、原计划/运行时及HEAD一致，所有终态文件与
  原账本相符，迁移前GPU2所属历史字节未变，没有在途attempt，保护额度未使用。
- 用户另行批准的资源隔离已完成，GPU2独立250次/48GPU小时，分组13/125/60/40/12；
  GPU3另有独立额度。本报告不修改其状态，也不适用旧共享优先级。
- GPU2本研究累计**44/250次，6.6404783742/48GPU小时**，实际baseline0/development42/
  recovery2，validation/formal均0。本轮N1W4次尝试共**1.1257005423 GPU小时**。
- 验证60次/14小时、正式40次/10小时保留。扣除保护时间后尚余17.3595216258小时，
  但余额不授权重开已关闭版本或增加未注册候选。
- 成本是包含初始化/Stage等待/中止的独占GPU进程wall-time上界及既有健康检查成本，
  不是纯GPU kernel运行时间。迁移按所属研究保留历史成本，未清零。

机器审计：`{ap}`（SHA `{r.digest(ap)}`）。
逐回合运行时：`{A}/analysis/n1w/completed-runtime-audit.json`。
监督状态及退出记录：`{A}/runtime/n1w-gpu2-independent-v1/`。

## 下一步研究优先级

1. **先完成Stage执行层的独立诊断和时限设计，再花费新的整批算法回合。** 当前最强证据是
   恢复回合91.57%的时间用于已完成Stage调用，且最长单次170秒接近180秒。应在新的明确
   诊断协议中区分连接/重连等待、服务延迟和回合总时限，事先规定调用与时间预算、完整
   调用起止日志及中止用量的UNKNOWN口径；不能用一次快速探针宣称长时稳定。
2. **运行环境可用后，优先完成原N1假设的完整同轮对照。** 保留C0/Q0/N1相同Stage条件、
   初始状态和计算量；任何Stage提供方、超时、缓存或状态机调整均应成为新的显式运行条件，
   不能改写N1W或将其部分结果并入新版本。不要继续用无效回合推断算法成功率。
3. **暂不因部分轨迹调整QD参数。** 新轴确实进入父代选择，下一步需要的是完整任务结果。
   只有获得有效同轮比较后，再按预先规定的成功门槛和对照结果判断是否值得研究空间信息
   损失、离散动作模式表示或ED评分时刻；本轮不支持给这些方向排性能名次。

当前交付的是可复核的未达标/比较未完成结论，尚无正式RDT+QD+ED算法版本可发布。
'''
report.write_text(report_text)
with r.locked(W/'data/qd-ed-state.lock'):
 s=r.read_state(W/'research-state.yaml');assert s['budget']['running']==0
 s['n1w'].update(status=a['decision'],closed_at=now,termination_utc='2026-09-24T08:56:50.048150+00:00',report_path=str(report),audit_path=str(ap),audit_sha256=r.digest(ap),primary_dispatched=3,recovery_dispatched=1,valid_scientific_cells=2,n1_valid_scientific_cells=0,undispatched_primary=27,do_not_auto_resume=True,close_reason='The only allowed N1/task0 recovery reached the frozen 1800-second episode timeout. Version stop condition applies; no second recovery, skipped cell, protected evaluation or new candidate.')
 s['n1w']['original_status_path']=s['n1w']['status_path'];s['n1w']['status_path']=str(A/'runtime/n1w-gpu2-independent-v1/status.json')
 s['n1w']['independent_launch_result_path']=str(A/'runtime/n1w-gpu2-independent-v1/launch-result.json')
 s['study']['status']=a['decision'];s['candidate'].update(status='N1_PARTIAL_MECHANISM_OBSERVED_NO_VALID_EPISODE',online_score=None,scientific_decision='NO_ADOPTION_EFFECTIVENESS_UNKNOWN')
 s['next_action']='N1W closed by registered stop rule. Review Stage latency/deadline evidence and a prospective execution protocol before any new GPU2 cohort. Do not resume N1W, relabel outcomes, tune from partial results, or mutate peer resources.'
 s['updated_at']=now;s['resource_isolation']['owned_supervisor']['lifecycle_status']='EXITED_AFTER_N1W_STOP_CONDITION';s['resource_isolation']['owned_supervisor']['exit_code']=1
 s['resource_isolation']['initial_resume_status']='COMPLETED_LIFECYCLE_SUPERVISOR_EXITED'
 temp=W/'research-state.yaml.n1w-close-tmp'
 with temp.open('w') as f:yaml.safe_dump(s,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(temp,W/'research-state.yaml')
notice=f'''# CURRENT — N1W closed incomplete; GPU2 idle

{now}: N1W stopped at08:56:50UTC by its registered rule: N1/task0 primary Stage180s timeout, then its sole authorized recovery hit episode1800s timeout at432steps. Status `{a['decision']}`. 30main planned;3main+1recovery dispatched;2scientifically valid cells (Q0/task0 failure,C0/task0 failure);N1zero valid;27main undispatched. No ≥5/10 claim, no adoption, no validation/formal. New descriptor and mixed-duty parent sampling observed only in partial N1 trajectories. Recovery recorded22completed Stage calls totaling1649.74s (91.57%wall); incomplete final activity/tokens/compute unknown. No HTTPSfallback notice accepted in this cohort, noXid.

Owned supervisor3318782 and recoveryworker3404890 exited; local runner lease released; GPU2idle. Do not auto-resume this closed N1W queue or spend its remaining4 recovery slots on a second retry of thiscell. Original terminal bytes and all historical costs preserved. GPU2private budget44/250attempts,6.6404783742/48GPUh; caps13/125/60/40/12; validation60/14h and formal40/10hprotected. Resource isolation stays ACTIVE; GPU3 has independent authority and must not be modified/preempted.

Executed sourcec75ff0f4eb4c8ae23dfc41b5f7449e99c06ff9ee; original N1Wplan/runtime unchanged. Report `{report}`; machine audit `{ap}` (16checksPASS). Latest lifecycle evidence `{A}/runtime/n1w-gpu2-independent-v1/launch-result.json`. Next priority is Stage latency/deadline diagnosis under a prospective explicit protocol, then a complete comparable N1 evaluation. No new scientific version is launched by this closeout. All older running/pending/shared-priority notices below are historical.

---

'''
for relative in ('HANDOFF_GPU6_GOAL.md','to_human/current-status.md','docs/01_specs/2026-09-22-rdt-qd-ed-object-swap-next-round-experiment-plan.md'):
 p=W/relative;p.write_text(notice+p.read_text())
print(json.dumps({'report':str(report),'report_sha256':r.digest(report),'state_status':a['decision'],'touched_peer':False},ensure_ascii=False))
