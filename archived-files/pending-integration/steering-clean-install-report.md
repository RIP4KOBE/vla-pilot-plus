# EDS 全新隔离环境安装与 CPU 验收报告

**已完成真实安装和 CPU 验收：1118 passed、1 warning、86.53 秒；最终 pip check 无损坏依赖。** 本报告不提供新的在线成功率，不将当前旧环境 cohort 的结果归给这个新环境。

环境：`/mnt/data/shared2/hynx/steering-integration-envs/clean-20261013-01/env`。源码：`/home/hynx/lizhuo/VLA-Pilot++`，提交 `cfecb12db736f1a3408d9528d9336aadcb7e41b5`。Conda 与 pip 下载、构建临时目录、测试缓存、日志全部位于 `/mnt/data/shared2/hynx/steering-integration-envs/clean-20261013-01`；这是新建 Conda prefix，没有克隆共享环境或使用 system-site-packages。真实 import 报告 `enable_user_site=false`，62 项直接候选依赖全部来自新前缀。没有修改共享 `vla-pilot`、仓库文件或冻结 cohort；各 CPU 验收前后源码 hash 一致。

## 验收结果

| 检查 | 实际结果 |
|---|---|
| README 系统库配方 | Python 3.12.12、pip 25.2、setuptools 80.9.0、FFmpeg 8.0.0、libegl/libgl/libglx 1.7.0、libstdcxx-ng 15.2.0，Conda create exit 0 |
| 完整依赖安装 | 真实 PyPI/PyTorch wheels 和固定 Transformers Git commit；pip install exit 0；没有安装 metadata-only 伪 wheel |
| 本地源码注册 | 固定 LeRobot 0.4.2 / LIBERO 0.1.0，`--no-deps` 成功 |
| 最终 pip check | `No broken requirements found.` |
| 版本约束 | 172 项全部匹配；53 项核心按实际运行版本修正后的 pin 保持固定 |
| 真实 import | main、RDT model factory、62 项候选依赖成功；RDT factory 来自当前 root 的 third_party/rdt |
| processor 来源和行为 | 当前 root 的真实 LeRobot 类，无 fallback；图像翻转与 8 维状态断言通过 |
| worker 配置 | 当前冻结配置的 `scripts/steering_worker.py ... --cfg job` exit 0 |
| 全套 CPU 测试 | **1118 passed, 1 warning in 86.53s** |
| networkx | 3.6 在新 Python 3.12 环境实际 import 成功 |
| GPU / API 边界 | CUDA_VISIBLE_DEVICES 为空，torch.cuda.is_initialized=false；socket 和 Codex/GPU 命令防护启用；没有创建仿真环境、加载模型权重或运行 API |

核心保留：Torch 2.7.1+cu126、TorchVision 0.22.1+cu126、NumPy **2.2.6**、Transformers 4.53.3（精确 Git `dcddb970176382c0fcf4521b0c0e6fc15894dfe0`）、Diffusers 0.35.2、tokenizers 0.21.4。实际数据依赖为 datasets 4.1.1、pandas 3.0.2、pyarrow 23.0.1、deepdiff 8.6.2、attrs 25.4.0、fsspec 2025.9.0。

## 真实安装暴露并修正的两处问题

1. **BDDL 漏声明 future。** 初次 pip check 已通过，但 adapter 实际导入 `bddl.backend_abc` 报 `ModuleNotFoundError: future`。新增显式 **future==1.0.0**，与旧环境的实际 module 版本一致；修订后的候选重新完成全部验收。初始 requirements/constraints 保留为 `inputs/*-candidate-v1.txt`，首次失败保留在 `logs/imports-attempt1.log`。
2. **OpenCV 安装顺序会改变实际实现。** robosuite 要 opencv-python，固定 LeRobot base 要 opencv-python-headless。完整安装默认先 headless 后普通版本，实测 `cv2/version.py` 为 headless=False。最后执行同版 `--force-reinstall --no-deps opencv-python-headless==4.12.0.88` 后，真实导入确认 headless=True；pip check 仍通过。两种 distribution 共用 cv2 文件，因此该最后一步必须明确，之后若再次安装普通 OpenCV，应重新核验实际 variant。

这两个问题证明仅通过依赖解析或 pip check 不能代替真实入口 import。六个旧 core pin 的更正、parse 与 processor 依赖补齐详见先前审计；本次真实新环境确认了修订版本可用。

## 可复现输入与命令

用于主线整合的文本文件：

- `/tmp/steering-requirements-validated.txt`：62 项直接 pin / 精确 Git 来源。
- `/tmp/steering-constraints-validated.txt`：172 项版本约束。
- `/tmp/steering-lerobot-base-validated.txt`：固定 LeRobot 子模块的原始 base 依赖，没有新增 optional extras。

上述 validated 文件只改变候选文件的说明注释，版本行与实际受测 v2 一致。实际受测输入、其 v1 和 SHA256 记录全部保留在外置 `inputs/` 及 `logs/dependency-candidate-revisions.json`。

实际命令采用以下顺序（每次完整 argv 与环境覆盖另见 `logs/*-command.json`）：

```bash
conda create --yes --prefix <new-prefix> --override-channels -c conda-forge \
  python=3.12.12 pip=25.2 setuptools=80.9.0 ffmpeg=8.0.0 \
  libegl=1.7.0 libgl=1.7.0 libglx=1.7.0 libstdcxx-ng=15.2.0

<new-prefix>/bin/python -m pip install \
  -c steering-constraints-validated.txt \
  -r steering-requirements-validated.txt \
  -r steering-lerobot-base-validated.txt

<new-prefix>/bin/python -m pip install --no-deps --no-build-isolation \
  -e <fixed-libero-source> -e <fixed-lerobot-source>

<new-prefix>/bin/python -m pip install --force-reinstall --no-deps \
  opencv-python-headless==4.12.0.88

<new-prefix>/bin/python -m pip check
```

实际 first install 使用 v1，随后单独安装 future==1.0.0；最终 validated 输入已纳入该修正，未重新创建第二个环境。缓存/TMP 使用 `CONDA_PKGS_DIRS`、`PIP_CACHE_DIR`、`TMPDIR`、`XDG_CACHE_HOME` 指向外置盘。实际构建 evdev 使用本机 `/usr/bin/gcc` 13.3.0 及现有 Linux input 头文件；Conda/Python 隔离不等于从零供应操作系统编译工具。没有为本次修改或安装宿主系统包。

为避免 `pip -e` 在运行中的 root 写 egg-info，实际注册的是外置源码副本：LeRobot 393 个、LIBERO 145 个代码/配置文件逐一 hash 与固定 root 相同。**运行时仍通过与入口一致的 PYTHONPATH 导入当前 root 的源码**，其路径已实际断言，不依赖副本替代算法。正常新 clone 可注册该 clone 内的固定源码；本报告不把外置副本路径当作可发布的 requirements。

CPU 测试实际参数为 `python -m pytest tests -q --disable-warnings -p no:cacheprovider --basetemp=<external-path>`，cwd 保持当前 root。测试关闭 `.env` 读取、隐藏 CUDA、禁网络/provider 命令；入口 import 与 worker --cfg 使用 runtime_environment 的生产开关。首轮测试错误继承 VLA_CODEX_ONLY=1 导致 7 个兼容配置用例失败，随后只修正验收 harness 并完整重跑；保留 `logs/pytest-attempt1.log` 与解释，没有修改产品代码或测试。processor helper 曾直接 inspect typing alias，亦保留首次失败并用 get_origin 修正了检查器。

## 证据位置与边界

主摘要：`/mnt/data/shared2/hynx/steering-integration-envs/clean-20261013-01/validation-summary.json`。

主要证据为 `logs/pytest.log`、`logs/pip-check.log`、`logs/clean-import-versions.json`、`logs/processor-behavior.log`、`logs/worker-cfg.log`、`logs/final-constraint-check.json`、`logs/pip-install-report.json` 和 `logs/pip-source-report.json`。全量包表为 `logs/pip-list.json` / `pip-freeze.txt`；60 个保留的真实 wheel 均与 pip 安装报告中的 SHA256 匹配，见 `logs/verified-wheel-cache.json`。早先 `/tmp/steering-dependency-review/METADATA_ONLY_DO_NOT_INSTALL` 未用于本次安装。

本次未验证新环境的 GPU/EGL reset/render、模型权重加载/策略推理、Codex 登录/API，或 torchcodec 的 native FFmpeg 解码后端。torchcodec 仅确认真实版本文件为 0.5；没有宣称其后端可用。模型目录、LIBERO 资产/RNG fixture 与宿主 Codex CLI 仍须按项目配置提供。这是**新环境安装和 CPU 入口验收**，不是新的机器人任务评测。
