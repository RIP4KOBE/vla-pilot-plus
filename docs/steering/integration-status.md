# Steering 整合状态

更新时间：2026-10-13。本文是整合期间的状态记录；每项结论只对应已经完成并留下证据的工作。

**当前结论：EDS 入口、配置解析与预检已落地，新的完整在线验收尚未完成。** 本阶段只开放 `eds`，`vls`/`eds_qd` 在 EDS 十任务验收后接入。没有把历史成功率登记为整合版本的新成绩。

## 交付与验证

| 项目 | 当前状态 | 完成条件 |
| --- | --- | --- |
| 历史实现与结果审计 | 已完成只读核验 | 明确 V17、历史控制组和标准 Object 的边界 |
| 公共方法接口 | `eds` 已开放；另两模式未开放 | EDS 十任务验收后再接入另外两种方法 |
| V17 算法与 Stage 迁移 | 已迁移，在线行为待验收 | 代码合同、冻结设置、provider 与初始化保持可追溯 |
| 环境与资产准备 | 新配方、准备/校验脚本与机器模板已落地 | 干净环境安装及资产完整性继续验证 |
| README 与贡献说明 | 已按当前 CLI 更新 | 跟随最终验证结果更新，不预填成绩 |
| 主迁移与 runner 离线回归 | 1,118 passed，2 warnings，82.42 秒 | 含 26 项新增 runner 检查；不证明在线任务成功率 |
| LIBERO 资产离线重建 | 2,308 个文件哈希全部一致 | 从固定公开版本的本地 Git 对象重建；不是新网络下载或完整新环境安装 |
| Hydra worker 配置检查 | 通过 | 解析后科学设置与机器路径可被 worker 接受 |
| 第三方导入位置 | 已核验 | LeRobot 与 LIBERO 均从当前仓库的 `third_party/` 导入，不沿用旧 editable 工作区 |
| Codex 图像请求预检 | 通过，1 次有效响应 | gpt-6-astra / low 的一次接入检查，不代表长期稳定性 |
| CUDA 与环境 reset/render | 通过；配置 GPU2 H200 NVL / EGL1 | 运算与图像生成可用 |
| CUDA/EGL 物理设备对应关系 | 独立查询通过 | GPU2 UUID、PCI 地址、visible cuda:0 与 EGL1 双向关联一致 |
| 完整策略 smoke | 尚无完成结果登记 | 模型加载及动作 rollout 与环境预检分别报告 |
| 完整在线 cohort | 待完成 | 同一冻结代码/配置完成所有指定任务，保留所有失败 |
| 干净 clone 安装 | 待完成 | 按公开说明准备依赖与资产，安装过程不借用隐式旧目录 |

状态更新应附上实际命令、结果和证据位置。未执行的检查写“未执行”或“待完成”，不要用预计通过替代。

## 本次预检记录

2026-10-13 08:40:00–08:40:48 UTC 完成一次组合预检：Codex 对红色测试图返回 `red`，记录 1 个完成 turn、0 个失败调用；GPU 为 NVIDIA H200 NVL，PyTorch 2.7.1+cu126 / CUDA 12.6；ObjectSwap task 0 reset/render 返回 `[128,128,3]` 图像。该记录的类型为 `preflight_not_performance`。实际 `codex --version` 为 **0.156.1**，不采用历史注释中的版本号。

该预检之外，已独立核验 CUDA GPU2 / EGL1 的关联：visible cuda:0 的 UUID 为 GPU-a5d6a5f8-b6df-7f3a-c3dc-19734c41ec0e，PCI 地址为 0000:41:00.0；EGL1 的 display/device 查询映射到同一个 CUDA 设备。运行环境显式设置 CUDA_DEVICE_ORDER=PCI_BUS_ID。证据见 [设备映射](validation/gpu-mapping.json)。

另行导入位置核验确认，LeRobot 使用当前仓库 `third_party/lerobot/src`，LIBERO 使用当前仓库 `third_party/libero_pro`。这排除了本次检查静默沿用旧工作区 editable 安装的情况，但仍不是新 clone 安装验收。

本机记录位于 `.worktrees/exp/steering-integration/preflight-service/report.json`，worker 配置日志为同目录上级的 `worker-config-check.log`。这些是本次机器上的检查产物，不是需要新 clone 依赖的资源。公开预检命令为：

```bash
python scripts/check_steering.py \
  --local-config configs/local.yaml \
  --output-dir outputs/steering/preflight-001 \
  --api --gpu
```

主迁移加 26 项新增 runner 回归后的最终 CPU 命令与结果如下，退出码 0。真实标准输出已保存为 `.worktrees/exp/steering-integration/checks/cpu-migration.log`；该记录取代先前 1,092 项、仅保留会话输出的检查数量。

```bash
CUDA_VISIBLE_DEVICES='' /home/hynx/miniconda3/envs/vla-pilot/bin/python \
  -m pytest tests -q --disable-warnings
# 1118 passed, 2 warnings in 82.42s
```

资产重建记录为 `.worktrees/exp/steering-integration/environment/libero-clean-reconstruction.json`：通过 `git archive` 从本地固定公开版本对象导出，使用正式准备流程的规范化、补丁和 overlay，2,308 个文件哈希全部通过。该证据明确不包含新的网络下载；完整干净环境安装仍待完成。

## 历史证据边界

| 历史结果 | 条件 | 本次可以据此说明什么 |
| --- | --- | --- |
| V17 3/10 | RDT、ObjectSwap OOD、完整十任务、新在线 Codex、历史 RNG 初始化、QD OFF | 提供已审计的迁移目标；不是新代码成绩，也不是 QD 收益 |
| P2 同轮控制 4/10 | RDT、ObjectSwap OOD、旧在线 Stage/缓存条件 | 是有效历史控制结果；provider、reward 来源和控制器与 V17 不同 |
| RDT 无引导 9/10 | 标准 `libero_object` | 是标准 Object 历史基线，不能数值压过或否定 OOD 结果 |
| RDT VLS 7/10 | 标准 Object、历史调参设置、Stage OFF | 说明该历史 guided 设置未超过同报告的无引导基线；不是当前整合版复测 |

来源的精确工作区、版本与冻结快照在 [README 追溯节](../../README.md#来源与追溯) 统一登记。迁移后的证据索引尚待整理。

## 在线验收规则

完整评测入口已实现。以下命令默认使用全部十任务；截至本状态记录，完整新 cohort 的结果尚未登记，不能视为已复现历史 3/10：

```bash
python scripts/evaluate_steering.py \
  --method eds \
  --local-config configs/local.yaml \
  --output-dir outputs/steering/eds-full10-001
```

`scripts/run_steering.py` 使用同一参数与 launcher。追加 `--print-config` 仅解析配置，不创建评测；追加 `--tasks 0,1` 仅运行指定子集，不能作为完整十任务验收。实际运行与预检要求输出目录不存在，禁止覆盖上一轮记录。

开始验收前，明确待验证方法、suite、任务/seed、初始化、动作预算、模型与完整配置。运行期间冻结科学代码，使用独立输出目录。完整记录准备失败、运行异常和任务失败，不从不同尝试中选择成功来组成分数。

验收应分别回答：

1. **安装与链路是否可用：** 输入输出、资产、模型、GPU/EGL 和 provider 是否可用。
2. **执行机制是否正确：** 实际方法、QD archive、Stage、reward reference 和 RNG restore 是否符合冻结配置。
3. **任务结果是什么：** 完整 cohort 的环境 success 与失败、错误情况。
4. **结论可以外推多远：** 是否为开发暴露过的固定任务、是否有重复种子或独立验证。

离线测试不证明在线性能；模型调用全部成功不证明 Stage 全部正确；与历史相同的成功数量也不证明轨迹严格重现。若新结果低于迁移目标，应报告差异并定位原因，不能继续引用旧分数掩盖新结果。

## 仍待完成的文档项

- 在全新环境验证新依赖配方与资产准备流程；当前已有机器的成功预检不能代替该检查。
- 将本机已有 CPU、资产与预检日志整理为可随仓库查看的证据索引。
- 运行期间持续保持已确认的 CUDA/EGL 设备配置。
- 补充完整策略 smoke 和完整在线 cohort 的真实运行记录。
- EDS 十任务验收后再接入 `vls`、`eds_qd`，并分别验证实际机制与在线结果。
- 将历史来源与新整合结果分别登记到可随仓库查看的证据索引。

算法本身的保留限制见 [架构说明](architecture.md#已知限制)。整合完成不等于所有历史控制缺陷或泛化问题已经解决。
