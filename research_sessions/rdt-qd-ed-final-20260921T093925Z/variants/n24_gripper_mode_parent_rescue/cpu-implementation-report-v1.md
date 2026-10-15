N24 Phase A 完成，仅 CPU 准备；任务成功率 **Unknown / not-run**。尚未运行 GPU、模型权重、真实 provider/Stage、API 或仿真环境，未集成 owning study_worktree，未更改状态、预算、账本或 Arbor tree。可审查分支为 `codex/n24-gripper-mode-parent-rescue`，worktree 为本目录的 `implementation/`。

冻结协议先提交于 `591142f`，协议字节 SHA256 为 `77163171815bdade8d05a4010ff59aa24a4157d447d6d7fb430f3163a80c4b3b`。实现提交为 `3f6db2dc3dcc8db45b66a649568b43248c8b5f0e`，base 为 `51104470983cdbafd08feb87f2f39b7553779405`。`source-manifest-cpu-v1.json` 列出相对 base 的 12 个文件（含协议），`source-diff-cpu-v1.patch` 保存完整差异。

实现只有冻结的搜索内父代救援。每个 guided search 创建一条本地 canonical 缓存，按已有 native effective cost 保留前 8 个 gripper 命令全正的最优候选；同成本保持最早 `(iter,row)`。原 archive 分配先原样执行，仅当其 16 个实际父代缺少该模式且缓存存在时，替换 first native worst-cost slot。其他 15 个、原 RNG 调用与全部 16 个的 ED refinement 保持。缓存不插入 archive、不跨搜索、不保证终轮或执行选中。没有新评分或投影调用。

缓存保留 native latent/cost/quality/raw/descriptor/cell 及出生身份；进入父代时沿用原 FP32 cost/quality/raw 容器，BF16 值精确转换。原 `archive_parent_allocation` 证据保留；新增 `gripper_rescue_begin/cache/parents` 明确记录实际替换，并以 `qd_gripper_rescue_offspring` 标记实际来源。原 archive slot/weight/covered-cell 统计与实际 cells/descriptors/unique-cell/source counts 的范围在 metrics 中明示。计数包含 176 个 predicate checks、实际缓存更新次数、替换数和辅助墙钟时间；所有开销仍计入完整 episode wall。关闭时新增 metrics 字段全部省略，provider 默认省略行为保持。

独立 `audit_gripper_parent_rescue.py` 不导入生产 cache/archive helper：从原 canonical native scores、固定 descriptor/cell、历史 fingerprint 和 native latent 重建原 archive replacement、累计访问及稀疏分配；再重建缓存、条件、first-worst slot、其余 15 个、actual raw/quality/cost/cells、ED 来源，并检查最终 archive 未额外插入缓存。原 N23 arithmetic、N7 descriptor、N5 terminal、raw Stage 与 deployed-action audit 继续执行。新 gate 为 `n24_gripper_parent_rescue_audit`；无 rescue 也须完整 11/176/10 覆盖，不设置最小触发次数。

`scientific-byte-parity-v1.json` 证明 main、N23 scorer、原 provider recognizer、QD archive、N5 selector、decoder、adapter、N23/N7/baseline profiles、worker/backend/preflight 等 13 文件与 base 逐字节相同，`_eds_score_population_as_cost` 和 `_eds_qd_allocate_parent_slots` 两个原函数正文逐字节相同。线上 Codex 登录契约及 Poe 禁用规则完全未改；未读取、复制或哈希凭据。

验证证据见 `cpu-test-results-v1.json` 和保留的日志：

- `cpu-final-v1.log`: 37 passed / 42.52s，包括原 C0/Q0 main-policy-adapter 合成 collector 路径、原 N23 接受与故意坏质量/坏 bounds 拒绝，以及 N24。均为合成依赖，不调用真实 simulator。
- 最后审计计数/严格 scalar type 和全 markers 删除负控修改后，`cpu-final-v2.log`: 29 passed / 32.71s，覆盖全部受影响 N24 tests；未重复不受影响旧测试。
- 加强 guard 显式封禁 `/mnt` 物理产物路径与凭据目录后，仅补定向 unit + BF16 rescue：`cpu-guard-v2.log`: 18 passed / 8.05s。0 blocked，CUDA initialized=false，CPU threads=2。
- FP32/BF16 完整生产 guided loop 各测 rescue、empty、already-present；真 rescue 的合成触发分别为 10、2 次，四个 inactive 情况均 0。instrumentation on/off 的选择动作/RNG 相同；inactive 的父代、最终动作、RNG 与 N23 相同。
- 所有完整 loop 保持 176 canonical evaluations / 11 batches、10 denoise / 10 renoise；该 stub 下 16 model calls / 256 rows / 16 denoising steps，各模式一致。真实模型成本未测量。
- 单测验证 earliest tie、first-worst tie、其他 15 个不变、空缓存/已有模式、future/duplicate/context/bounds/nonfinite/cell/descriptor/native cost-quality 失败、profile 仅增一个字段及拒绝偏离；完整审计负控拒绝 fingerprint、slot、predicate、cost、raw、context、descriptor、cell、missing、duplicate、future、final archive 与整组 markers 删除。

复现核心测试（在 implementation 中；每次使用新 basetemp，保留先前 fixture/log）：

```bash
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONPATH=.. TMPDIR=../tmp PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -p n24_cpu_guard_v2 -p no:cacheprovider --basetemp=../fixtures-review-new tests/test_qd_gripper_parent_rescue.py tests/test_n24_native_loop.py -q
```

原失败永久保留：`cpu-unit-v1.log` 在收集前因 pytest 尝试 `/tmp` capture 写入被 guard 拒绝，随后 TMPDIR 改到 variant；`cpu-unit-v2.log` 的两个失败来自 fixture 对 frozen dataclass 的赋值，改为 dataclasses.replace 后通过。无故障被算作任务失败或 GPU 尝试。编辑辅助脚本曾短暂存于 `/tmp/n24_patch.py`，随后迁为当前目录 `implementation-edit-v1.py`；该脚本仅含源码编辑逻辑，没有实验数据或凭据。所有实验与最终审查产物均在此 variant。已有 fkd_class.py invalid-escape SyntaxWarning 未修改。

Phase B 尚需独立实施/审查：C0/Q0/N23/N24 的封闭调度、N24 专属路由与 source/runtime bridge、现有有限预算/资源锁、同进程 native audit、原 typed recovery、公平矩阵/数学 futility、完整 source-bound release。特别是必须从冻结 N24 profile 强制报告含完整 N24 gate；generic audit 不能仅依赖可被整体删去的 marker 来判断期望方法。独立 N24 auditor 已测试全 markers 删除拒绝，controller 需要强制调用/检查该 gate，不能将无 marker 的 inactive 样例降格为 N23。旧 N23 worker/arithmetic 字节不变，但这不自动转移旧 source-bound admission；若根审查要求 native preflight，只能使用 N24 协议单独规定的有限机会。验证/正式集继续关闭。

本阶段没有执行 optional retrospective trigger screen，没有读取任何 N23 原始结果、native tensors 或 protected outcomes；不从合成触发率推断任务收益。源码现冻结，等待根审查和 Phase B 指令。
