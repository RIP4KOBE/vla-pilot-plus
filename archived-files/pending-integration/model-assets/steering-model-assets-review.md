# 新 clone 模型资产身份与准备审阅稿

结论：当前机器已经具备候选运行所需资产，但新 clone 不能只靠现有 `configure --hash-weights` 证明它拿到同一份模型。该选项记录输入文件哈希，尚未对照维护者认可的 expected manifest；DINO 目前只检查 `hubconf.py`，没有检查其导入的整棵源码树。本稿只审阅本地资料并在 `/tmp` 生成草案，未修改仓库、现有缓存或运行目录，未下载模型、联网查询、执行模型、访问 GPU/API，也没有读取登录凭据。

## 交付物与证据边界

- `/tmp/steering-model-assets-portable-draft.json`：4 个逻辑根 `rdt_checkpoint`、`text_encoder`、`vision_encoder`、`torch_home`，214 个相对路径、大小、SHA-256 条目；总计 50,861,376,376 bytes，另附一个 RDT 模型卡记录。无机器绝对路径、resolved_path 或凭据。草案状态为 `review_draft_not_implemented_or_enforced`，没有新增已生效的预检入口。
- 原始依据：仓库 `.worktrees/exp/steering-integration/environment/model-assets.json`，SHA-256 `b9701e584d6e3522716063af8ea5874007d352d1af620cdbc868afcd55ba0c7e`，对应迁移候选 `cfecb12db736f1a3408d9528d9336aadcb7e41b5` 的环境记录；不是 full10 成绩或最终接纳结论。
- 原记录 189 项均只读核对了存在性和 byte length；RDT/T5/SigLIP 大权重 SHA 直接沿用原记录，没有再读取约 50 GB 权重计算一遍。DINO 的 203 个非 bytecode 文件及 346 MB 权重已由并行只读审计重新计算 SHA，原有 178 项源码 SHA 全部匹配。新增 25 个文件逐项标记 `supplemental_local_source_rehash`。
- `/tmp/dinov2-source-portable-manifest.json` 与 `/tmp/dinov2-source-audit.md`：DINO 完整源码内容身份和逐行加载路径审查。203 文件映射的规范 JSON SHA 为 `317ea4c4766462192095a32a5850b571a7df607d5979215da7de6878a203a9ca`。
- 模型包总大小约 47.37 GiB；T5 单文件约 41.48 GiB。新 clone 准备空间必须包含这些文件，若下载、解压或复制过程保留多份，还要另计峰值空间。不可因为文件大而删掉 T5、DINO 权重或 tokenizer 文件。

## 可获取性与身份

| 逻辑根 | 需要的内容 | 本地可证实的来源线索 | 未证实的部分 |
| --- | --- | --- | --- |
| `rdt_checkpoint` | `config.json`、`ema/model.safetensors`；分发时保留 `README.md` | 本地模型卡第 45–48 行明确使用 `TJ-chen/RDT-1B-LIBERO-Object`。模型卡第 2/77 行声明 Apache-2.0 | 无 `.git`，本地 HF 下载目录只有 `.gitignore` 与 `CACHEDIR.TAG`，无下载 revision/etag metadata。未查询远端，不能断言目前公开可下载，更不能断言远端某个 revision 等于本次 SHA |
| `text_encoder` | 清单 5 文件，包含 `pytorch_model.bin`、tokenizer 配置、特殊 token 映射、SentencePiece 文件 | 本地 HF cache repo 名 `google/t5-v1_1-xxl`；`refs/main` 与实际 snapshot 都是 `3db67ab1af984cf10548a73467f0e5bca2aaaeb2`，大权重 blob 名等于记录 SHA | 本轮没有验证远端可用性；其他 `refs`（本地另有 PR ref）不能替代已用 snapshot |
| `vision_encoder` | 清单 3 文件，`model.safetensors`、config、preprocessor config | 本地 HF cache repo 名 `google/siglip-so400m-patch14-384`；`refs/main` 与 snapshot 都是 `9fdffc58afc957d1a03a25b10dba0329ab15c2a3`，权重 blob 名等于记录 SHA | 本轮没有验证远端可用性 |
| `torch_home` | `hub/facebookresearch_dinov2_main/` 的完整 203 文件源码树，含 LICENSE；`hub/checkpoints/dinov2_vitb14_pretrain.pth` | 源码及模型名与 `facebookresearch/dinov2` 对应；真实源文件内容和权重 SHA 已核对 | 无 `.git`、archive commit receipt、下载 zip 或 ref metadata。目录名 `main` 和包版本 `0.0.1` 都不能证明 commit；草案记录 `source_revision: null` |

RDT 的公开仓库名是**本地模型卡给出的候选来源**，并不是不存在来源线索。准确表述应为：“已有仓库名线索，缺少该次文件的固定 revision 与公开内容等同性证据”。本轮不提供猜测的下载地址或将上游通用 `robotics-diffusion-transformer/rdt-1b` 当成这份 LIBERO Object fine-tune。

四份主要权重 SHA：

| 相对路径 | bytes | SHA-256 |
| --- | ---: | --- |
| `rdt_checkpoint/ema/model.safetensors` | 2,456,705,456 | `b4e3631db326689297cd2f0b02d32ade9dc6ee9ae09c03171add64b80e86aaa1` |
| `text_encoder/pytorch_model.bin` | 44,541,587,809 | `c8407a9ae21075667be98f84f4c93e8a7bfc772a352cd2e6998f5916f7181db8` |
| `vision_encoder/model.safetensors` | 3,511,950,624 | `ea2abad2b7f8a9c1aa5e49a244d5d57ffa71c56f720c94bc5d240ef4d6e1d94a` |
| `torch_home/hub/checkpoints/dinov2_vitb14_pretrain.pth` | 346,378,731 | `0b8b82f85de91b424aded121c7e1dcc2b7bc6d0adeea651bf73a13307fad8c73` |

维护者在可核验公开发布信息补齐前，需提供：

1. 上述两份 RDT 推理文件及模型卡，保证 expected SHA 不变，说明模型来源与分发许可；仅交 checkpoint 目录名不足以复现。
2. DINO 203 文件无 bytecode 源码包及该权重；保留 LICENSE、导入闭包及相对布局。若以后找到上游 commit，必须验证它重建出的全树与清单一致，再将未知 revision 更新为有证据的 revision。
3. T5/SigLIP 指定 revision 的清单内文件，或让使用者取得这些精确 revision 后比较全部内容 SHA。若复制 HF snapshot，应解引用 symlink 或同时携带它指向的 blobs，避免只有 snapshot 文件名但链接悬空。
4. 与模型一同固定的仓库源码/协议：RDT 子模块 `b896f4dcac8ed1c3fae4a056200db267607f131f`、清单中的 `maniskill_model.py`/`state_vec.py`/`rdt_libero_action_converter.py` 及 DATA_STAT。这里没有额外 checkpoint normalization sidecar，统计常量写在 RDT 源码里，不能省掉源码契约。

## 当前预检的具体缺口

- `scripts/prepare_steering_assets.py:160–180` 检查文件存在、encoder 不是 cache 根、RDT `pred_horizon=64` 和 `action_dim=128`；`202–204` 仅记录可选 SHA。
- 同文件 `166` 在 T5 同时存在 `.bin` 和 `.safetensors` 时先记录 `.bin`。实际固定 Transformers 的 `modeling_utils.py:1035–1055` 会优先选择 safetensors；因此记录正确 `.bin` 不能排除加载了额外 safetensors。
- 当前 `model_files` 也没有覆盖实际 T5 `special_tokens_map.json` 或完整 DINO 源码。`core/rdt_policy_steer.py:1095–1110` 会先寻找 `ema/config.yaml`、`ema/config.json`、根 `config.yaml` 等候选；一个额外配置可遮蔽已验收根 `config.json`。
- `scripts/steering_runtime.py:122–144` 每次运行记录所提供模型 SHA、子模块 commit/dirty，但并不与 expected 模型 SHA 对比。`run_steering.py:55` 在 worker 前调用它，适合加入失败即拒绝的核验。
- `scripts/check_steering.py:24–37` 当前只加载目录配置，然后可发 API 请求；没有独立 expected model identity gate。因此不能把现有 preflight PASS 解读为模型内容对照 PASS。
- `core/keypoint_detector.py:120–132` 若 hubconf 缺失会进入未固定远端 repo fallback。DINO `backbones.py:73–77` 即使源码以 `source=local` 导入，也会在权重缺失时走 `load_state_dict_from_url`；HF 的 offline 环境变量并不自动禁止 Torch Hub 下载。
- 当前缓存还包含 75 个 `__pycache__/*.pyc`（三个 Python 版本各 25）。原 178 文件清单未覆盖它们；`PYTHONDONTWRITEBYTECODE=1` 只禁止写入，不能防止读取已有 bytecode。本轮未更动这些缓存；新 clone 应使用干净源码包。

**当前运行证据与未来分发规则须分开。** 现有 cohort 的 `runs/eds-migration-20261013/console.log:84–89` 已记录真实选中的 RDT `ema/model.safetensors`、根 `config.json` 和 5 个 HF local-only 调用；第 107–110 行记录从当前本地 Torch Hub 目录加载 `dinov2_vitb14` 并成功返回。以上是已观察到的实际加载路径证据。当前全部 157 个 DINO Python 源码文件也与已有记录相符。存在旧 `.pyc` 不足以推出本次导入了错误代码，更不能据此追溯性判定当前 cohort 无效；本轮没有捕获 Python 导入每个字节码文件的取用行为。“clean 包不含 bytecode、精确全树核验”是后续可移植分发与严格预检的建议，不能包装成当前运行已违反的既定门槛。

## 最小实现建议（尚未落盘到仓库）

1. 审阅后将逻辑根 manifest 作为版本化 expected 身份文件放入仓库。核验器只读 manifest + `local.yaml`，CPU 流式核对所有文件大小/SHA，输出每项实际与 expected 的对比及 manifest 自身 SHA。不要只记录输入，不能把目录名或 mtime 当内容身份。
2. 对 RDT/T5/SigLIP 使用独立、最小目录；列出允许的清单文件及无行为影响的分发说明，拒绝清单外的模型、配置、tokenizer、index、adapter 文件。RDT 解析后必须明确得到 `config.json` 与 `ema/model.safetensors`；T5 明确得到记录的 bin，SigLIP 得到记录的 safetensors。HF snapshot 可以保留跨到 blobs 的 symlink，但必须核对其最终文件内容；portable manifest 不记录这些机器路径。
3. DINO 源目录精确比较 203 文件相对路径集合和 SHA，拒绝额外/缺失文件、外部源码 symlink、`.pyc/.pyo/.so`。从干净包准备源码，使用不写源码目录的 bytecode 配置，例如禁写或独立 pycache 目录。新进程导入后另外记录 `dinov2` 来源，防止已装同名包遮蔽。
4. 在 `configure` 完成前、`check_steering` 的 GPU/API 探针之前、正式 runner 启动 worker 之前复用该 gate；无法匹配即报具体逻辑路径并退出。拒绝缺失资产的远端自动补齐。保留提供来源记录与内容验证记录，两者不能混为同一结论。
5. 将 gate 的 expected manifest SHA、实际 verified SHA、源码契约 commit/dirty 和解析选中的文件写入运行环境证据。使用受控只读资产树避免预检后被替换；若资产可被并发更改，须再核对，不能依赖初次 stat。
6. 最小回归覆盖：同大小单字节错误权重、缺少 tokenizer map、额外 T5 safetensors、额外 RDT `ema/config.yaml`、DINO 任一源码篡改/额外 Python/旧 pyc、缺 hubconf/权重、HF 悬空 symlink。各项必须在模型加载、GPU、API、网络之前失败。这里只建议测试，没有运行或声称实现通过。

## 新 clone 准备指南（供 README 后续整合）

1. 先按已验收的独立 Python 配方及固定子模块建立环境；不要用模型包替代仓库、submodule 和 processor 来源校验。独立环境的 CPU 通过不等于已执行模型推理。
2. 用维护者 manifest 配套资产包填充四个逻辑根。RDT/T5/SigLIP 用独立目录；Torch root 保持 `hub/facebookresearch_dinov2_main` 与 `hub/checkpoints` 布局。不要把历史机器 cache 根、`main` 分支名或目录创建时间作为版本选择依据。
3. 获取模型时固定上述 encoder revision，并按清单比较全部文件。RDT/DINO 未补齐可验证公开 revision 时，从维护者取得匹配内容包；遇到任何 SHA 差异先停在资产准备阶段。尚未实现自动 gate 前，不能把 `--hash-weights` 的成功输出当作等同性判定。
4. 安装固定 LIBERO 资产，验证 LIBERO 与 RNG 夹具，然后调用现有 `prepare_steering_assets.py configure` 将实际四根写入当前 clone 的 `configs/local.yaml`。README 的 encoder snapshot 示例可沿用；GPU/EGL 编号仍需当前机器独立确认。只复制必要模型内容，不复制登录信息、历史运行输出、旧 `.env` 或 whole-home cache。
5. 用 `run_steering.py --method eds --local-config configs/local.yaml --output-dir <新目录> --print-config` 查看解析结果；模型身份 gate 加入并通过后，再执行显式服务/GPU预检与正式在线 cohort。该顺序是建议流程，本次没有启动新运行。

`configure`/runner 的 expected manifest 补强须在当前冻结 cohort 完成后另行提交，并把新增受测 commit 写入之后的证据；不能静默改写正在运行的候选或历史 environment.json。
