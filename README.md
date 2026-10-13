# VLA-Pilot++：RDT 推理时引导与在线阶段控制

这个仓库研究如何在不重新训练 RDT 策略的情况下，用视觉语言模型生成任务 reward、判断执行阶段，并在动作采样时进行引导。当前工作是把经过历史审计的 V17 基线整理为可维护、可复现的公共实现。目标方法为 `vls`、`eds`、`eds_qd`；**本阶段的新入口只开放 `eds`**，另外两种方法在 EDS 十任务验收后接入。

**当前状态：EDS 入口、配置解析和预检已落地，新的完整在线验收尚未完成。** CPU 检查 1,118 项通过，包含 26 项新增 runner 回归；Codex 图像响应、GPU2 H200 的 CUDA 运算与 LIBERO reset/render 预检通过。独立设备查询已确认当前机器 GPU2 对应 EGL1。这些检查不等于完成策略 rollout 或十任务评测，历史 3/10 也不是本次整合的新成绩。证据与待完成项见 [整合状态](docs/steering/integration-status.md)。

## 方法与评测范围

| 方法 | 主要机制 | 当前定位 |
| --- | --- | --- |
| `vls` | 在 RDT 去噪中加入关键点 reward 梯度、轨迹多样性作用和可选 FKD 粒子重采样，最终选择动作候选 | 保留既有实现；新入口尚未开放 |
| `eds` | 对动作候选执行评分、父代选择、重新加噪与截断去噪；初始和迭代采样可加入轨迹多样性 | 当前可选入口；V17 设置，QD archive 关闭，完整在线验收待完成 |
| `eds_qd` | 在 EDS 搜索中加入按行为描述符组织的质量多样性 archive，影响候选保留与选择 | 后续实验扩展；新入口尚未开放 |

V17 的关键变化还包括在线 Stage 复查、携带证据、失败接触恢复，以及同一阶段内保持 reward reference。它不是只增加一个采样参数。具体数据流、算法开关和局限见 [架构说明](docs/steering/architecture.md)。

迁移目标评测为 **LIBERO object-swap OOD**：固定 10 个任务，每任务 1 回合，上限 720 动作。历史 V17 在一轮完整在线评测中取得 3/10，QD archive 关闭；这不是 QD 改善性能的证据。标准 `libero_object`、其他策略和不同初始化协议的结果不能直接与它比较。新成绩必须绑定新代码、解析后配置、资产和完整运行证据。

## 安装与资产

支持目标为 Linux、Python 3.12、NVIDIA CUDA 与 EGL 无界面渲染。新依赖声明为 [environment-steering.yml](environment-steering.yml) 和 [requirements-steering.txt](requirements-steering.txt)，依据当前可运行环境固定主要依赖：PyTorch 2.7.1+cu126、torchvision 0.22.1+cu126、transformers 的固定源码版本、diffusers 0.35.2、NumPy 2.2.0、MuJoCo 3.7.0、robosuite 1.4.0。它们是安装配方，尚非经过干净环境复验的完整传递依赖锁。

克隆本仓库后，从仓库根目录在**新环境**中准备依赖。下面是已按脚本接口核对、尚待干净 clone 安装验收的流程；不要用它原地更新共享的旧 `vla-pilot` 环境。

```bash
git submodule update --init --recursive third_party/rdt third_party/lerobot
conda env create -f environment-steering.yml
conda activate vla-steering
python scripts/prepare_steering_assets.py install-libero
python -m pip install --no-deps -e third_party/libero_pro -e third_party/lerobot
python -m pip check
python scripts/prepare_steering_assets.py verify-libero
python scripts/prepare_steering_assets.py verify-rng
```

除 Python 依赖外，运行还需要：

| 资产 | 用途与要求 |
| --- | --- |
| RDT 与 LeRobot 源码 | 使用仓库记录的版本；不要用另一份全局安装静默替代 |
| LIBERO-PRO 源码、BDDL、init states、模型和纹理资产 | 环境运行必需；安装应生成当前 clone 自己的 `LIBERO_CONFIG_PATH`，不能指向历史实验目录 |
| RDT-1B-LIBERO-Object EMA checkpoint | 连同模型配置、动作/状态约定一起固定 |
| T5 与 SigLIP | 固定到完整 encoder snapshot；仅提供 HF 缓存根目录不足以锁定版本 |
| DINOv2 代码与权重 | 关键点提取依赖；离线运行前准备 Torch Hub 缓存 |
| 历史初始化 fixture | 已放在 `tests/fixtures/steering_rng/`；manifest 和 20 个 RNG 状态文件共同定义初始化协议 |
| Codex CLI 与 ChatGPT 登录 | V17 在线身份、reward 和 Stage 查询使用的提供方；需要验证 CLI 参数兼容性和模型可用性 |

`install-libero` 下载固定的公开 LIBERO-PRO 版本、应用受校验的补丁与 ObjectSwap 输入包，再校验文件；已有合法本地副本可用 `--source /path/to/libero_pro` 复制。已有目标目录只校验，不覆盖。大模型与 DINO 缓存仍由使用者提供，脚本不会下载它们。旧 `requirements.txt`、`environment.yml` 和 `setup.sh` 不要与新配方混用。SAM3、CALVIN 和 PI05 是可选路径，不是当前 RDT EDS 的必需依赖。

已完成一次从固定公开版本的本地 Git 对象出发、使用相同规范化/补丁/输入包流程的离线重建，2,308 个文件哈希全部一致。该检查没有进行新的网络下载，也不能替代干净 clone 的完整安装验收。

## 机器配置

机器路径与设备编号放在忽略提交的 `configs/local.yaml`，格式见 [local.example.yaml](configs/local.example.yaml)。用资产脚本生成该文件及当前 clone 的 LIBERO 路径配置；以下 `/path/to/` 必须换成实际路径，encoder 必须是明确的 snapshot 目录：

```bash
python scripts/prepare_steering_assets.py configure --help
python scripts/prepare_steering_assets.py configure \
  --rdt-checkpoint /path/to/RDT-1B-LIBERO-Object \
  --text-encoder /path/to/t5/snapshots/3db67ab1af984cf10548a73467f0e5bca2aaaeb2 \
  --vision-encoder /path/to/siglip/snapshots/9fdffc58afc957d1a03a25b10dba0329ab15c2a3 \
  --torch-home /path/to/torch/cache \
  --gpu 0 --egl-device-id 0 \
  --output configs/local.yaml \
  --hash-weights --report outputs/steering/asset-check.json
```

示例中的 GPU0/EGL0 只是待替换编号，必须改成当前机器实证确认的映射，二者编号不一定相同。本机独立设备查询已确认 GPU2/EGL1，运行入口显式使用 PCI_BUS_ID 的 CUDA 排序。其他机器需重新确认。`configure` 只检查文件并写配置，不验证 GPU。`--hash-weights` 记录所提供权重的哈希，不能单靠“文件存在”证明权重与历史版本相同。新配置内容与已有文件不同时默认拒绝覆盖，检查后才使用 `--replace-config`。

Codex CLI 使用本机 ChatGPT 登录；机器配置中不放 API key 或登录 token。本次预检实际使用 CLI **0.156.1** 与 `gpt-6-astra / low`，不是历史代码注释中的旧版本。其他安装需用 `codex --version` 记录版本，并通过下方显式预检确认参数和模型可用。不要提交模型权重、登录凭据或本机环境文件。

## 运行入口

当前只接受 `--method eds`。先解析配置，不使用 GPU、不调用模型：

```bash
python scripts/run_steering.py \
  --method eds \
  --local-config configs/local.yaml \
  --output-dir outputs/steering/config-check-001 \
  --print-config
```

以下预检会发出一次真实模型图像请求，并执行 CUDA 运算与 LIBERO reset/render；不是完整策略 rollout：

```bash
python scripts/check_steering.py \
  --local-config configs/local.yaml \
  --output-dir outputs/steering/preflight-001 \
  --api --gpu
```

`--api` 与 `--gpu` 可分别使用。不带这两个标志只检查本地配置加载与环境构造，不能据此宣称模型或 GPU 可用。

准备完成后，完整十任务的主线命令如下。**CLI 已落地，新的十任务结果仍待验收**：

```bash
python scripts/evaluate_steering.py \
  --method eds \
  --local-config configs/local.yaml \
  --output-dir outputs/steering/eds-full10-001
```

`run_steering.py` 与 `evaluate_steering.py` 当前调用同一 launcher，均默认运行全部十任务。若要限定子集，显式追加 `--tasks 0,1`；子集结果不能称为 full10。当前整合机器可将上述 `python` 替换为 `/home/hynx/miniconda3/envs/vla-pilot/bin/python`，其他机器使用自己的已验证环境。

预检和实际评测都要求新的输出目录。评测保存 `resolved-config.yaml`、`manifest.json`、源码快照、`console.log`、`status.json`、`progress.json` 和结束后的 `audit.json`。`status=finished` 只表示进程退出；还需查看 audit 与完整任务结果。运行中保持科学源码和配置不变，失败后保留原目录并另取新运行标识。

旧的 `python main.py`、`run.sh` 仍有各自默认值，不能据此声称启动了 V17。V17 要求新生成的每任务 reward、真实在线 Stage、固定初始化协议和归档关闭；配置中仍含旧 provider 名称的字段不代表实际启用了那个 provider。

## 合作开发

阅读 [贡献说明](CONTRIBUTING.md) 后提交变更。算法、感知、Stage、初始化和评测配置的变化应分别说明；每轮正式评测开始后冻结源码与配置。保留全部失败、异常和完整任务列表，不拼接不同版本或重复运行中的成功。

文档入口：

- [架构与方法机制](docs/steering/architecture.md)
- [整合状态与验收条件](docs/steering/integration-status.md)
- [贡献与证据规则](CONTRIBUTING.md)

## 来源与追溯

项目保留 VLS 的历史实现与文档。原始研究背景见 [VLS 论文](https://arxiv.org/abs/2602.03973) 和 [项目页面](https://vision-language-steering.github.io/webpage/)。论文中的实验结论不自动适用于本仓库新增的 RDT/EDS/Stage 设置。

本次整合开始时，主仓库提交为 `d51cb85f485502e0429c79529872efef2ec59981`，已具备 RDT + LIBERO + VLS；整合分支为 `codex/rdt-steering-integration`。

V17 来源目录为 `.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-gpu6-20260922T063626Z/study_worktree`，来源分支为 `exp/rdt-qd-ed-gpu6-20260922T063626Z`，审计时 HEAD 为 `77761b4cda78ac3b6762a6aa60f97b07fde7c1dc`。该目录包含后续工作区修改，**HEAD 本身不完整代表 V17**。

实际来源以该目录下 `artifacts/stage_closed_loop_20260929/runs/codex_failed_contact_v17_historical_initialization_online_full10/` 的 `accepted-setting.json`、`manifest.json`、`resolved-config.yaml` 和 `source/` 冻结快照为准；报告为 `docs/03_evidence/stage_consistency/2026-09-30-codex-v17-full10-report.md`。这些来源路径用于本地审计，不要求新 clone 依赖原实验工作区。迁移后的证据位置将在验收记录中给出。

## 许可证

仓库现有 [LICENSE](LICENSE) 为 MIT，保留原有版权声明 `Copyright (c) 2025 Shuo Liu`。本次文档整理未变更该许可证。第三方源码、仿真资产与模型权重仍受各自许可证和使用条款约束；项目的 MIT 许可证不替代它们。
