# P2 Adaptive EDS+RBF Task 11 回归与静态 Gate 报告

## 1. 结论摘要

- 验证窗口（UTC）：`2026-08-02T11:30:59Z` 至 `2026-08-02T11:37:59Z`。
- Git revision：`ed1faa9f7486d5916377844f66318a30bc9302a0`。
- 最终核心 CPU 回归通过 `672` 个测试，ancillary obs/stage 回归通过 `52` 个测试，无失败。
- legacy parent complete-loop RNG/determinism 测试在两个独立 pytest invocation 中各通过 `2` 个参数化 case。
- `git diff --check`、目标模块 `py_compile`、QD/MAP-Elites 静态 gate、生产代码凭据静态 gate、P2 GPU 白名单、进程和存储 gate 均通过。
- 本 Task 未运行 GPU 实验，未修改实现代码，未 commit，也未回退 worktree 中已有 dirty 修改。

## 2. Revision 与代码状态

验证开始时执行：

```bash
date -u '+%Y-%m-%dT%H:%M:%SZ'
git rev-parse HEAD
git status --short
```

代码状态摘要：

| 项目 | 数量 |
|---|---:|
| modified | 20 |
| added | 0 |
| deleted | 1 |
| renamed | 2 |
| untracked | 26 |
| 合计 | 49 |

该 worktree 在 Task 11 开始前已为 dirty 状态。本次验证保留全部既有修改，没有执行 reset、checkout、revert 或 commit。

## 3. 测试与静态检查结果

| # | 命令 | 结果 | 计数/输出 | 耗时 |
|---:|---|---|---|---:|
| 1 | `pytest tests/test_rdt_steer.py tests/test_eds_eval_metrics.py tests/test_eds_mechanism_trace.py tests/test_eds_mechanism_pretest_vis.py tests/test_main_rdt_startup.py tests/test_eds_eval_runner.py -q` | PASS | `593 passed` | `99.39 s`（pytest `96.07 s`） |
| 2 | `pytest tests/test_rdt_libero_obs_processor.py tests/test_stage_recognition_trace.py tests/test_stage_recognition_eval_runner.py -q` | PASS | `52 passed` | `17.57 s`（pytest `15.50 s`） |
| 3a | `pytest tests/test_rdt_steer.py::test_eds_legacy_parent_complete_loop_reuses_scores_and_preserves_rng_exact -q` | PASS | `2 passed` | `1.99 s` |
| 3b | 与 3a 完全相同、第二个独立 pytest invocation | PASS | `2 passed` | `2.01 s` |
| 4 | `git diff --check` | PASS | `0` 个 whitespace error | `0.02 s` |
| 5 | `python -m py_compile core/rdt_policy_steer.py core/eds_eval_metrics.py core/eds_mechanism_trace.py main.py scripts/rdt_eds_eval_runner.py utils/eds_mechanism_pretest_vis.py` | PASS | `6/6` 文件编译通过 | `0.11 s` |
| 6a | 新增生产实现行扫描 `QD-ED` / `MAP-Elites` 及命名变体 | PASS | `0` 个命中 | `<0.1 s` |
| 6b | `configs/ core/ main.py scripts/ utils/` 常见 credential token pattern 扫描 | PASS | `0` 个生产文件命中 | `<0.1 s` |
| 7 | `/proc` 中按本 worktree cwd 筛选 `pytest` / `main.py` / `rdt_eds_eval_runner.py` | PASS | `0` 个残留进程 | `26.4 s` |
| 8 | shared2 软链接、目录、可写性、精确 target 与 `>=20 GiB` gate | PASS | `free_kib=4369620832` | `<0.1 s` |

说明：两次 determinism 命令虽然指定了单个 test node，但该测试本身参数化，因此每次输出均为 `2 passed`。两次均启动了独立 pytest 进程，没有复用同一 invocation。

### 3.1 Task 12 Runner Validity Hotfix 回归

在 mechanism pretest 首次启动前，独立审查发现 P2 validity/report 对真实 telemetry 字段和跨层证据一致性的覆盖不足。修复采用先写失败反例、再最小实现的方式，覆盖：

- 真实 `selection_ess_ratio_mean`、`adaptive_rbf_scale_requested_mean`、`anchor_count_observed` 字段；
- adaptive RBF per-iteration 与 chunk-level active count 一致性；
- k-center/elite 的显式 anchor shortfall；
- memory metrics、相同 episode/global-step trace 与 memory artifacts 三方一致性；
- profile-specific qualitative artifact 的 JSON/CSV/PNG/PT 可读性；
- runner log 必需性及 P2 pretest 专用 report writer。
- 畸形/nonfinite 组件 telemetry 的统一 schema gate、Stage B fail-closed eligibility，以及核心 evidence symlink 拒绝。
- Hydra 特殊 `hydra.run.dir` 的 runtime 配置核验，以及 credential token regex 自然语言边界。

复核时间为 `2026-08-02T13:27:00Z`，revision 仍为 `ed1faa9f7486d5916377844f66318a30bc9302a0`，worktree dirty state 继续由 runner code-state fingerprint 绑定。

| 命令 | 结果 | 计数 |
|---|---|---:|
| `pytest tests/test_eds_eval_runner.py -q` | PASS | `208 passed in 78.72 s` |
| `python -m py_compile scripts/rdt_eds_eval_runner.py` | PASS | `1/1` |
| `git diff --check` | PASS | `0` 个 whitespace error |

本次 hotfix 尚未运行正式 GPU episode；被提前终止的不完整启动输出已保留在 shared2 的 `attempts/pretest_aborted_validator_schema_20260802T1152Z/`，不会计入正式 pretest。

### 3.2 实验后 Validity/Report Fail-Closed 加固

Stage A 和 immutable integration manifest 完成并审计后，独立代码审查进一步发现 evidence validator 的边界条件。修复继续采用先写失败反例、再最小实现的 TDD 流程，只修改 runner validity/report 层，没有改变算法、配置或已有实验输出：

- 拒绝重复 `(episode, global_step)` metrics identity；
- 拒绝重复 `(episode_id, global_step)` stage-event identity；
- metric identity 必须是非 `bool` 的整数且位于合法范围；
- P2 metrics、episode metadata、stage events 使用 strict JSONL reader，损坏 JSON、`null` 和数组均结构化判 invalid，不再静默跳过或崩溃；
- memory report 同时存在 invalid 与 missing reset evidence 时，invalid 优先判 FAIL。

最终复核：

| 命令 | 结果 | 计数 |
|---|---|---:|
| 核心 6-file pytest regression | PASS | `672 passed in 143.87 s` |
| `pytest tests/test_eds_eval_runner.py -q` | PASS | `228 passed in 88.41 s` |
| Obs/stage ancillary regression | PASS | `52 passed in 17.75 s` |
| 最终 validity 反例矩阵 | PASS | `16 passed` |
| 目标模块 `py_compile` | PASS | `6/6` |
| `git diff --check` | PASS | 0 个 whitespace error |

Stage A 的冻结 code-state SHA256 为 `e7931dc95b5ed6f525ef86f83778fb93677a749cb08fa18db626d1f24eeabb7f`。上述实验后 validator-only hardening 会改变当前 code-state，因此 manifest loader 按设计 fail-closed；immutable manifest 未被重写。实验结果仍引用 hardening 前已经完成并记录的 11/11 evidence audit。

## 4. Static Gate 细节

### 4.1 算法范围

对以下新增生产实现的 diff-added lines 扫描 `QD-ED`、`MAP-Elites`、`MAP_Elites`、`map-elites` 和 `map_elites`：

- `configs/config.yaml`
- `core/eds_eval_metrics.py`
- `core/eds_mechanism_trace.py`
- `core/rdt_policy_steer.py`
- `main.py`
- `scripts/rdt_eds_eval_runner.py`
- `utils/eds_mechanism_pretest_vis.py`

结果为 `QD_STATIC_GATE_PASS`，未发现本轮禁用的 QD/MAP-Elites 实现。

### 4.2 Credential

生产代码和配置目录未命中常见 OpenAI/Google/GitHub/AWS credential token pattern，结果为 `PRODUCTION_CREDENTIAL_GATE_PASS`。扫描过程只输出文件名或 gate 状态，没有打印环境变量或 token 内容。

测试目录 `tests/test_eds_eval_runner.py` 的两行凭据检测单元测试夹具会故意匹配扫描正则；人工复核确认它们是用于验证 redaction/detection 的合成测试字符串，不是运行凭据。报告不记录其原始值。

### 4.3 P2 GPU 白名单

P2 runner 将允许集合固定为 `P2_ALLOWED_GPUS = {"2", "3", "4", "5"}`，且 `run_level()` 对 P2 levels 拒绝集合外设备、重复设备及超过四个 worker。主回归包含 P2 GPU policy 和 legacy level GPU 环境回归测试，均已包含在 `593 passed` 中。未发现 GPU `0/1/6/7` 被设置为 P2 默认执行设备。

## 5. Storage Gate

兼容软链接：

```text
outputs/ood_eval/p2_adaptive_eds_rbf
  -> /mnt/data/shared2/hynx/VLA-Pilot++/eds-init-pg-diverse-sampling/outputs/ood_eval/p2_adaptive_eds_rbf
```

复核结果：软链接存在、未悬空、解析目标与批准路径完全一致，目标目录存在且可写。

| Filesystem | 挂载点 | 可用空间 | 使用率 |
|---|---|---:|---:|
| `/dev/sda3` | `/`（home/worktree） | `58,352,980 KiB`，约 `55.6 GiB` | 87% |
| `/dev/sdc1` | `/mnt/data/shared2` | `4,369,620,832 KiB`，约 `4.07 TiB` | 70% |

shared2 可用空间显著高于 `20 GiB` gate。

## 6. Process Gate

通过 `/proc/<pid>/cwd` 限定当前 worktree，再筛选 `pytest`、`main.py` 和 `rdt_eds_eval_runner.py` 相关 Python 进程。结果为：

```text
NO_MATCHING_WORKTREE_PROCESSES
```

未终止任何进程，也未检查或干预其他 worktree/用户的任务。

## 7. Warning 与后续边界

- 本报告只证明 Task 2-10 当前代码通过指定 CPU 回归与静态 gate；不代表 mechanism pretest、Stage A、Stage B 或 LIBERO-PRO OOD GPU 实验已经完成。
- 本轮没有发现需要修复的 Task 2-10 scoped defect，因此没有新增实现改动。
- worktree 保持 dirty；后续实验必须继续绑定当前 revision 与代码状态 fingerprint，不能只用 HEAD 判断实验代码身份。
