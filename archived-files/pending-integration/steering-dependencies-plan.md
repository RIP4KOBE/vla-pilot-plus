> 后续已完成真实隔离安装与 CPU 验收。以下保留第一阶段 metadata 审计记录；最终修正、1118 项测试结果和安装命令见 `/tmp/steering-clean-install-report.md`。实际安装额外发现并补齐 future==1.0.0，且确认须最后安装 headless OpenCV。

# EDS 新环境依赖候选与只读审计

日期：2026-10-13。受测源码：`cfecb12db736f1a3408d9528d9336aadcb7e41b5`。本次只写 `/tmp`，没有修改仓库、正在运行的 cohort、共享 Python 环境或既有 `environment.json`；没有安装包、创建仿真环境、初始化 CUDA、请求模型 API 或下载大 Torch wheel。

**结论：依赖 metadata 可以在固定核心版本下解析，但当前 README 的 53 项清单不能直接声称来自实际运行版本，也不足以支持干净安装。推荐候选已纠正 6 个实际导入版本，补齐直接必需和 processor 依赖，并保留精确 Transformers Git 来源。两个 metadata-only pip dry-run 都成功；尚未验证干净安装或二进制 ABI。**

## 交付文件

- `/tmp/steering-requirements-candidate.txt`：可供下一阶段安装使用的候选 requirements，53 项核心加 8 项明确缺失或需冻结的 processor 依赖。保留真实外部索引与 Transformers Git URL，不引用伪 wheel。
- `/tmp/steering-constraints-candidate.txt`：171 项完整 LeRobot base 解析闭包的版本候选。它是版本约束候选，不是经过干净安装验证、带 wheel 哈希的发布 lock。
- `/tmp/runtime-import-versions.json`：53 项核心和 10 项补充包的实际 CPU 导入证据，含模块路径、版本标记、入口文件 SHA256、所有同名 dist-info、入口文件与 RECORD 的对应关系。可作为当前 cohort 的补充环境证据；不要替换最初冻结的环境记录。
- `/tmp/steering-dependency-review/candidate-resolution-summary.json`：推荐解析的版本汇总、逐项约束校验、两个 profile 的差异。
- `/tmp/steering-dependency-review/observed-full-base-report.json`、`observed-runtime-minimum-report.json`：真实 pip 生成的 dry-run reports；同目录对应 `*-command.json` 和 `.log` 记录命令、exit code 和 stdout。

## 1. 实际运行环境的 6 个版本更正

导入进程使用 `scripts.steering_runtime.runtime_environment()` 和当前 `.worktrees/exp/steering-integration/local.yaml` 构造与 worker 相同的根目录、LIBERO、RDT、LeRobot `PYTHONPATH`，再设置 `CUDA_VISIBLE_DEVICES=''`、`PYTHONDONTWRITEBYTECODE=1`。Numba 缓存单独放 `/tmp/steering-dependency-review/numba-cache`，避免受限沙箱尝试写共享 site-packages。`torch.cuda.is_initialized()` 最终为 `false`。

| 包 | 当前 requirements | 实际导入 / 推荐候选 |
|---|---:|---:|
| accelerate | 1.12.0 | 1.13.0 |
| einops | 0.8.1 | 0.8.2 |
| gymnasium | 1.2.2 | 1.2.3 |
| numpy | 2.2.0 | 2.2.6 |
| pillow | 11.3.0 | 12.2.0 |
| psutil | 7.1.3 | 7.2.2 |

这些包均存在旧、新 dist-info 并存，而代码来自表中实际版本。不能取 `importlib.metadata.version()` 返回的第一个版本，或对 dist-info 取最高值代替真实 import。本候选推荐 NumPy **2.2.6**，不推荐先前错误记录的 2.2.0。

其余 47 项核心 pin 保持，包括 Torch `2.7.1+cu126`、TorchVision `0.22.1+cu126`、Transformers Git `dcddb970176382c0fcf4521b0c0e6fc15894dfe0`（实际模块 4.53.3）、Diffusers 0.35.2、tokenizers 0.21.4、MuJoCo 3.7.0、robosuite 1.4.0。这里的“保持”不等于 47 项全部提供可独立导出的 `__version__`：bddl、easydict、jsonlines、kmeans-pytorch、python-dotenv、pytorch-kinematics、rich、termcolor、typing-extensions 只证明实际 import 路径/文件 hash，并记录对应 distribution metadata；报告没有把缺失的版本标记伪装成实际源码版本。

两个需单独解释的标记差异：

- **draccus**：源码 `__version__` 是 0.8.0，但官方 0.10.0 wheel 本身就含此标记。读取 PyPI 官方小 wheel（71,783 字节）后，`draccus/__init__.py` 与当前文件 SHA256 完全一致。因此保留 **draccus==0.10.0**，不能误降为 0.8.0。证据：`/tmp/steering-dependency-review/draccus-version-marker-proof.json`。
- **OpenCV**：`cv2.__version__` 为 4.12.0，`cv2/version.py` 的完整 `opencv_version` 为 4.12.0.88，且 **headless=True**。这是发行 build 后缀与实际 active variant 的区别；不是版本应降到 4.12.0。

53 项核心最终全部成功 import。初次 robosuite 导入因受限目录的 Numba cache 失败，改用独立 `/tmp` 缓存后成功；未因此改动代码、JIT 设置或共享环境。

## 2. 必须补齐的直接导入与 processor 依赖

- `main.py:443` 无条件导入 `vlm_query.vlm_agent`，后者 `:11` 无条件 `import parse`。必须显式补 **parse==1.20.2**。
- `core/env_adapters/libero_adapter.py:49-52` 导入 LeRobot processor；LeRobot `processor/__init__.py` 会进一步引入 HIL/motors 和 normalize/dataset 模块，因此需要 **pyserial 3.5、deepdiff 8.6.2、datasets 4.1.1、pandas 3.0.2、pyarrow 23.0.1**。同时冻结实际 **attrs 25.4.0、fsspec 2025.9.0**，避免重复 dist-info 使解析选择不同版本。
- 缺这些包可能触发 adapter 的 `ModuleNotFoundError` fallback，运行继续但 processor 已改变；不能只凭入口能启动判定环境相同。
- 本次实际确认 adapter 中两类的 module 为 `lerobot.processor.pipeline`、`lerobot.processor.env_processor`；真实文件在当前根目录 `third_party/lerobot/src`。LIBERO 内层包在当前根目录 `third_party/libero_pro/libero/libero/__init__.py`。没有继承历史 worktree 的已安装 editable 源码。
- 完整 base metadata 还需要当前环境缺失的 `etils[epath]`（MuJoCo 声明）及其 `importlib-resources`；候选选择 1.13.0、6.5.2，仅公共 metadata 解析已验证。MuJoCo 顶层当前能 import 不证明所有子功能的 metadata 依赖已完整安装。

## 3. pip dry-run 的方法与准确边界

为了不下载大型 Torch/CUDA 包，本次从现有 dist-info 的 `METADATA` 构建只含依赖描述的临时 wheel 容器；LeRobot base `Requires-Dist` 替换为当前固定子模块 `715debf6c1723a28f1a57d4274a8c4ec35b6a417` 的 `pyproject.toml` 内容，未请求 optional extras。LIBERO 本地 `setup.py` 声明 `install_requires=[]`。Torch/TorchVision metadata 的版本补上源码 `version.py` 中的 `+cu126`，其依赖关系未改。Transformers 的解析镜像采用 4.53.3，但安装候选仍是精确 Git URL。所有这些转写都在 `/tmp/steering-dependency-review/metadata-manifest.json` 记录。

这些容器位于 `METADATA_ONLY_DO_NOT_INSTALL`，没有包代码，标明 **NEVER INSTALL**；只能用于以下 dry-run。小量公共 PyPI JSON 补齐 etils、importlib-resources、networkx 的原始依赖 metadata，另读取上述 draccus 小 wheel 以审计版本标记。

实际命令（`PROFILE` 分别为 `observed-full-base` 和 `observed-runtime-minimum`）：

```bash
/home/hynx/miniconda3/envs/vla-pilot/bin/python -m pip --isolated install \
  --dry-run --ignore-installed --no-index \
  --find-links /tmp/steering-dependency-review/METADATA_ONLY_DO_NOT_INSTALL \
  --report /tmp/steering-dependency-review/PROFILE-report.json \
  -r /tmp/steering-dependency-review/resolver-PROFILE.txt
```

| Profile | 包数 | exit code | 证明范围 |
|---|---:|---:|---|
| observed-full-base | 171 | 0 | 候选核心 + 固定源码 LeRobot 全部基础依赖 + LIBERO 的版本约束可满足 |
| observed-runtime-minimum | 151 | 0 | 候选核心和 processor 直接所需依赖的约束可满足，不安装 LeRobot/LIBERO distribution |

两次解析均没有升级冻结的 Torch、TorchVision、Transformers、tokenizers、Diffusers 或 NumPy 2.2.6。成功只证明所提供 **metadata 的版本约束**可满足。它没有检查真实轮子是否可获取、Python/平台 wheel tag、sdist 编译、ELF/FFmpeg/CUDA ABI、下载安装或新环境 import，更不是在线 EDS 复现。初期 `full-base` / `runtime-minimum` 文件保留为探索记录；推荐结论只基于上述 `observed-*` 报告。

## 4. 完整 base 与最小源码路径方案

推荐先验证完整 base profile：按固定子模块安装 LeRobot **不带 extras**，在候选 constraints 下正常解析依赖。没有发现这一 base profile 与固定核心版本的数学冲突。多出的 cmake、wandb、rerun-sdk、pynput、torchcodec 等是该固定源码写在基础声明里的依赖；这不代表 EDS 推理会执行这些服务/训练路径。

不要为了 `pip check` 使用 `lerobot[all]`、训练策略 extras、datasets[audio]、datasets[dev] 或 LeRobot 测试 extras：当前 datasets 4.1.1 的 audio 要 `torch>=2.8.0`、`torchcodec>=0.6.0`，与固定 Torch 2.7.1 / LeRobot `<2.8.0`、torchcodec `<0.6.0` 冲突；LeRobot `[test]` 要 `pytest>=8.1,<9`，与现有 9.0.3 冲突。这些 extras 不属于当前 EDS 推理所需。

若后续选择更小环境，可以**不注册 LeRobot distribution**，仅通过 runner 已有的根目录 `third_party/lerobot/src` 源码路径加载，并安装本次明确 processor 依赖。这能保持 processor 源文件/类路径，不需要启用本地 fallback。代价是 LeRobot `__version__.py` 将因没有 distribution metadata 返回 `unknown`；不能把 `pip check` 的成功解释成 LeRobot 全基础依赖已装。该方案只做了 metadata 解析，尚未在无 editable 遗留的隔离环境验证，当前没有推荐替换正式安装方案。

CALVIN/calvin_env、PyBullet、PI05/Diffusion 的其他推理训练包、SAM3/GroundingDINO、ROS/SAPIEN 不属于当前 RDT + Codex-only EDS 的直接必需路径，不应为它们添加整套训练 extras。

## 5. 干净安装前仍需解决/验证的具体事项

1. **OpenCV 共用文件**：robosuite 1.4.0 metadata 要 `opencv-python`，固定 LeRobot base 要 `opencv-python-headless`；完整 profile 因此包含两个 4.12.0.88 distribution，二者拥有同一 `cv2` 路径。当前 active source 是 headless。pip 的约束解析看不出文件覆盖问题。隔离安装必须记录安装顺序，并验证 `cv2/version.py` 的 headless 标记和 `cv2.getBuildInformation()`；不能默认 `pip check` 已确认实际 implementation。若需要一个 distribution 的规范方案，应独立评审第三方 packaging metadata 调整，并记录其来源差异，不能在当前运行期间静默修改。
2. **networkx**：共享环境 2.2 在 Python 3.12 import 报 `cannot import name 'Mapping' from 'collections'`。候选显式约束 3.6（公共 metadata 要 Python>=3.11）作为新环境兼容候选；这是明确的新环境差异，并非当前成功加载版本。没有修改共享环境，也没有据此宣称当前 cohort 失效。bddl 的 object_taxonomy 子模块会引用 networkx；本次验证的 processor import 没有靠成功导入 networkx 才通过。
3. **torchcodec**：当前有 `0.5` 与 `0.5+cu118` 两套 metadata，实际 `version.py` 是 0.5。候选使用 `torchcodec===0.5` 排除错误选择 `+cu118`；本次没有导入其 native backend，也没有确认 FFmpeg/CUDA ABI 或视频解码成功。当前 processor import 成功不等于此后端可用。
4. **真实安装和二进制**：171 项闭包来自 metadata，必须在新的隔离环境验证实际下载/安装、wheel 构建（例如 evdev）、`pip check` 和 import。优先保留 conda 的 Python 3.12.12、pip 25.2、setuptools 80.9.0 及当前 environment-steering 的系统库声明；本次没有验证它们的完整平台解或 FFmpeg ABI。
5. **资产与外部前提**：新 clone 仍须初始化固定 RDT/LeRobot 子模块、重建并验 hash 的 LIBERO-Pro overlay、按配置提供真实模型目录和 RNG fixture；本候选不会下载模型或代替 Codex CLI 登录。RDT 子模块为 `b896f4dcac8ed1c3fae4a056200db267607f131f`。

## 6. 下一阶段执行顺序（本次未执行）

1. 保留当前 frozen cohort 和本报告的补充导入证据。先完成当前结果归档，再改 README/环境声明。
2. 在独立环境（可另行授权使用 `/mnt/data/shared2`）创建 Python/系统库层；不要对正在运行的 `vla-pilot` 做 pip 升降级。
3. 从当前根目录按候选 requirements 与 constraints 安装固定本地源码，不使用本报告的 metadata-only wheel 目录。可审阅的命令形态：

```bash
python -m pip install \
  -c /tmp/steering-constraints-candidate.txt \
  -r /tmp/steering-requirements-candidate.txt \
  -e third_party/libero_pro -e third_party/lerobot
```

此命令是**待验证候选**，当前未运行；其正常网络安装会下载真实 CUDA/torch 等大包，需在后续授权环境中执行。

4. 检查 `pip check`、53 项真实版本/源码路径、OpenCV active variant、真实 LeRobot processor 无 fallback、RDT worker 配置和 CPU 测试。网络/下载失败与 ABI/processor 差异分别记录，不能以删除依赖或启用 fallback 隐藏。
5. 只有隔离环境本身通过后，才能将 README 的安装段标为实测；新的 GPU/渲染或在线性能验收应单独运行、单独归档。本报告不提供任何新的成功率结论。
