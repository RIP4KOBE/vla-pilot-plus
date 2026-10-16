# 安装、资产与本机配置

本页是 Linux 新合作者的安装路径。三模式命令见 [README](../../README.md)，实际验证范围、环境和结果见[新合作者验收报告](onboarding-validation.md)。请使用新 clone 和新环境；精确模型资产仍需由维护者提供，不能仅凭仓库 clone 完成模型准备。

## Codex CLI 与宿主前提

在线路径需要单独安装 [Codex CLI](https://learn.chatgpt.com/docs/codex/cli) 并加入 PATH；下方 Conda/pip 配方不安装它。验收使用 **0.156.1**。官方默认安装方式可能取得更新版本，应记录实际版本，并为不同版本重新验证 exec 参数、事件格式及本项目预检。已有有效登录可使用；新账号登录与模型权限需要使用者自行完成。当前机器的验证不能代替其他账号的授权。

```bash
command -v codex
codex --version
# 已有有效登录可直接检查；新使用者完成自己的登录。
codex login
codex login status
```

无浏览器服务器可参考[官方鉴权说明](https://learn.chatgpt.com/docs/auth#login-on-headless-devices)，使用 `codex login --device-auth`；这需要账户或工作区允许设备码登录。登录凭据留在使用者自己的CLI环境中，不复制到机器配置或Git。

## 创建新环境

验证平台为 Linux x86_64、Python 3.12.12、Torch 2.7.1+cu126，GPU 为 NVIDIA H200 NVL、驱动 580.65.06。尚未测定最低显存或验证其他 GPU 型号。宿主需要 Conda、Git 与 Git LFS、C 编译器和 Linux input 头文件（验证机器以 GCC 13.3.0 构建 evdev），以及适用的 NVIDIA 驱动；Conda 文件不供应所有宿主工具。

在 clone 根目录操作。示例目录必须替换成容量充足的新目录；下载、构建缓存也应放到该盘。不要改动共享环境。

```bash
STEERING_ENV_ROOT=/path/on/large-disk/vla-steering-clean
mkdir -p "$STEERING_ENV_ROOT"/{conda-pkgs,pip-cache,tmp,xdg-cache,numba-cache}
export CONDA_PKGS_DIRS="$STEERING_ENV_ROOT/conda-pkgs"
export PIP_CACHE_DIR="$STEERING_ENV_ROOT/pip-cache"
export TMPDIR="$STEERING_ENV_ROOT/tmp"
export XDG_CACHE_HOME="$STEERING_ENV_ROOT/xdg-cache"
export NUMBA_CACHE_DIR="$STEERING_ENV_ROOT/numba-cache"
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
export PYTHON_DOTENV_DISABLED=1
unset PYTHONPATH PYTHONHOME
# Explicit package index; do not inherit an unrecorded pip configuration.
export PIP_CONFIG_FILE=/dev/null
export PIP_INDEX_URL=https://pypi.org/simple
unset PIP_EXTRA_INDEX_URL

git submodule update --init --depth 1 third_party/rdt third_party/lerobot
conda env create --prefix "$STEERING_ENV_ROOT/env" --file environment-steering.yml
# If Conda is not initialized in this shell, source its etc/profile.d/conda.sh first.
conda activate "$STEERING_ENV_ROOT/env"

# Includes the validated constraints and the fixed LeRobot base dependencies.
python -m pip install -r requirements-steering.txt
python scripts/prepare_steering_assets.py install-runtime-compat
python scripts/prepare_steering_assets.py verify-runtime-compat
python scripts/prepare_steering_assets.py install-libero
python scripts/prepare_steering_assets.py verify-libero
python scripts/prepare_steering_assets.py verify-rng
python -m pip install --no-deps --no-build-isolation \
  -e third_party/libero_pro -e third_party/lerobot

# Run LAST: both OpenCV distributions share the actual cv2 files.
python -m pip install --force-reinstall --no-deps opencv-python-headless==4.12.0.88
python -m pip check
python -c "import cv2.version as v; assert v.headless; print(v.opencv_version, v.headless)"
```

[environment-steering.yml](../../environment-steering.yml) 只安装 Conda 层，使用 conda-forge、排除默认渠道。[requirements-steering.txt](../../requirements-steering.txt) 包含62项直接依赖，并引用 [172项约束](../../constraints-steering.txt) 与 [固定 LeRobot base依赖](../../requirements-steering-lerobot-base.txt)。不混用历史环境文件，不安装 LeRobot optional extras、CALVIN 或训练扩展。RDT 子模块直接导入，不另行 pip 安装。

关键版本为 NumPy **2.2.6**、TorchVision 0.22.1+cu126、Diffusers 0.35.2、tokenizers 0.21.4、Transformers 4.53.3 的固定 Git revision `dcddb970176382c0fcf4521b0c0e6fc15894dfe0`。`future==1.0.0` 补足 BDDL 未声明的真实 import 依赖。完整配方已包含该依赖。历史安装修订记录保存在[整合记录](integration-status.md)，不需要新使用者重复历史补丁步骤。

版本约束不等于 wheel 哈希锁或跨平台保证；Conda传递依赖构建号没有锁定。两个 OpenCV distribution 都被上游声明且共享文件，`pip check` 无法检查最终实际 variant，故最后覆盖 headless 与实际 import 检查必须保留。后续若重新安装普通 OpenCV，应重新核验。

## Robosuite 兼容补丁

固定的 Robosuite 1.4.0 wheel 还需要仓库提供的兼容补丁。目前保留的旧在线环境包含这些修改；此前安装配方遗漏了这一步，新环境会在 CUDA/EGL 编号不同时拒绝导入。

`install-runtime-compat` 显式安装两份文件的受控修改：区分 CUDA 与 EGL 编号、为 NumPy 2 的分割图整数运算使用足够位宽、修正 EGL 配置数组传参，并保持历史上下文释放行为。它只接受已知原版或已补丁文件，先核验全部输入，再验证补丁输出哈希；不会覆盖未知本地修改，也不会修改当前 Python 环境以外的包。

补丁输出与目前保留的旧在线环境对应文件逐字节一致；历史运行没有保存这两份包内文件的哈希，不能倒推每次历史执行的完整依赖身份。补丁及输入/输出身份见 [compatibility manifest](../../scripts/dependency_patches/robosuite-1.4.0.json)。预检和正式 launcher 都会检查安装结果并记录哈希。重装 Robosuite 后需要重新执行安装与核验；不要靠 `pip check` 判断补丁是否存在。

## 固定模型与源码资产

大模型不在仓库中。完整身份由 [steering_model_assets_manifest.json](../../scripts/steering_model_assets_manifest.json) 定义，包含214个文件、50,861,376,376字节和3个归一化源文件约束。校验会流式读取模型文件，不通过反序列化执行模型。**目前未配置公开的精确资产包**。维护者本机的逻辑根由ignored `configs/local.yaml`记录；新使用者需取得对应文件副本并自行填写新路径，不保证仅凭模型名称可取回相同字节。

| 机器配置逻辑根 | 必需内容与来源边界 |
| --- | --- |
| `rdt_checkpoint` | `config.json`、`ema/model.safetensors`；没有已核实的公开下载来源；需维护者交付与清单匹配的准确文件 |
| `text_encoder` | T5明确 snapshot，revision `3db67ab1af984cf10548a73467f0e5bca2aaaeb2`，不能指向上层 cache root |
| `vision_encoder` | SigLIP明确 snapshot，revision `9fdffc58afc957d1a03a25b10dba0329ab15c2a3` |
| `torch_home` | `hub/facebookresearch_dinov2_main/` 源码及 `hub/checkpoints/dinov2_vitb14_pretrain.pth`；源码 commit 未知，需维护者交付hash匹配的源码；目录名不证明版本 |
| `libero_root` | 当前 clone 的固定 LIBERO 代码、资产和 object-swap 输入，默认 `third_party/libero_pro` |
| `libero_config` | 当前机器的 LIBERO路径配置目录，默认 `.libero_config` |

T5/SigLIP revision 来自本地 cache证据，远端可用性未重新核验。RDT 代码 revision 不等于模型 revision。归一化常量来自固定 RDT 源码和动作转换文件，不存在凭空补出的 checkpoint normalization sidecar。第三方权重、数据与源码的分发许可需分别确认。

## 配置机器并严格校验

准备上述资产后执行。GPU和EGL枚举应先通过设备身份和实际render确认。`list_steering_devices.py` 使用 NVIDIA UUID、CUDA 可见设备与 EGL 扩展查询返回对应关系；不靠编号相同来猜测。配置后的 `check_steering.py --gpu` 再检查实际渲染 display 的设备身份。下面使用待替换的设备变量；配置写入新文件，不提交机器配置。

```bash
STEERING_GPU="REPLACE_WITH_ASSIGNED_GPU"
python scripts/list_steering_devices.py --gpu "$STEERING_GPU"
# Fill in egl_device_id from the report above.
STEERING_EGL="REPLACE_WITH_VERIFIED_EGL_INDEX"
python scripts/prepare_steering_assets.py configure \
  --rdt-checkpoint /path/to/rdt \
  --text-encoder /path/to/t5/snapshots/3db67ab1af984cf10548a73467f0e5bca2aaaeb2 \
  --vision-encoder /path/to/siglip/snapshots/9fdffc58afc957d1a03a25b10dba0329ab15c2a3 \
  --torch-home /path/to/torch-cache \
  --gpu "$STEERING_GPU" --egl-device-id "$STEERING_EGL" --output configs/local.yaml

# Optional standalone report; the identical model check is always enforced by
# configure, preflight and the real launcher. A new report filename is required.
python scripts/steering_model_assets.py --local-config configs/local.yaml \
  --repository-root "$PWD" --report outputs-model-assets-001.json
```

校验器不只检查某个文件存在：它比较固定大小/SHA-256，并核对真实加载优先级。更高优先级的 RDT config、T5 safetensors、tokenizer sidecar 或新增可导入 DINO 源码会被拒绝。正常 HF snapshot→blob 符号链接允许；未选中的低优先级权重和额外说明文件可以保留。`--hash-weights` 仅为兼容选项，省略它也必须完成完整模型校验。

默认兼容已有 DINO `__pycache__`，并明确不证明解释器实际使用的 bytecode身份。新分发包可在独立报告命令加 `--clean-distribution`，验证203个纯源码/配置文件的准确集合、无bytecode或符号链接；不要删除正在使用的缓存。验证后资产仍须保持稳定只读，hash检查不防止并发改写。

`install-libero` 使用固定版本、补丁和输入overlay，已做2308文件离线重建核验；也可用 `--source /path/to/verified-tree` 复制已有合格树。`verify-rng` 校验20个固定状态文件，真正运行时还校验规定的两个恢复时点。安装不会重新生成 object-swap 任务。

运行时优先导入当前 clone 的 `third_party/rdt`、`third_party/lerobot/src` 和指定LIBERO源码，并用 `VLA_LIBERO_ROOT` 显式绑定实际LIBERO根，关闭encoder在线下载。`libero_config/config.yaml` 的 `benchmark_root`、`assets`、`bddl_files`、`init_states` 四项必须指向已通过内容校验的同一树；preflight和launcher会校验绑定并在 `environment.json.libero_paths` 保存配置hash与解析路径。使用外置LIBERO树也必须满足这一约束，不能借旧机器路径配置绕过内容身份。完整 DINO源码和权重必须预先提供，避免底层缺文件走Torch Hub下载路径。真实 LeRobot processor必须导入，fallback不能当作安装通过。

GPU编号与EGL枚举独立，一次成功render也不证明二者对应同一设备。allocator默认48GiB只限制PyTorch分配器，不是整个进程/设备总显存硬限额。在线调用使用自己的 Codex CLI 登录；当前协议使用 CLI 0.156.1、`gpt-6-astra/ultra`。历史 low 为另一协议，不作为本页默认。CLI 版本和请求名不能使服务端模型永久不可变。

## 分层验证

1. **CPU配置预览：** 按[README](../../README.md#开始使用)对三种方法使用 `--print-config`。这一步不验证模型内容或设备。
2. **本机资产预检：** 运行下面不带GPU/API标志的命令，保存独立报告。
3. **GPU/API预检：** 已获设备分配且空闲时，在另一个新目录显式增加 `--gpu --api`。
4. **完整cohort：** 每种方法用自己的新目录与冻结源码，单独完成十任务和审计。

```bash
python scripts/check_steering.py --local-config configs/local.yaml \
  --output-dir outputs/preflight-assets-001

env -u VLA_CODEX_ONLY CUDA_VISIBLE_DEVICES='' PYTHON_DOTENV_DISABLED=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  python -m pytest tests -q --disable-warnings -p no:cacheprovider
```

普通 CPU pytest 命令不封锁网络/API。实际导入应来自本次新环境与当前 clone；LIBERO、RDT、LeRobot 必须对应固定源码。CPU 检查通过不代表 GPU、真实模型或在线服务可用，应继续运行 GPU/API 预检及完整评测。最新验证和未覆盖项见[验收报告](onboarding-validation.md)；历史环境检查见[整合记录](integration-status.md)。

## 下载缓存与连接故障

可以复用下载缓存，但不能复用旧环境的 `site-packages`。对已经核对来源和版本的 wheel 缓存，可在完整 requirements 安装前执行以下可选步骤；约束冲突时应停止并检查，不能放宽版本解决。

```bash
python -m pip install --no-deps -c constraints-steering.txt /path/to/verified-wheel-cache/*.whl
python -m pip install -r requirements-steering.txt
```

缓存不完整时仍需要网络，Git 来源依赖的缓存也必须对应固定 revision。将软件源、缓存使用、安装日志和最终 `pip freeze` 记入验收报告。使用镜像时显式设置并记录 `PIP_INDEX_URL`，不要继承未说明的全局 pip 配置。

LeRobot 的 Git LFS 测试媒体也可能在子模块 checkout 时下载；网络较慢时这一步会等待较久。它们不是本项目的 RDT 模型资产，不能替代下文的固定模型准备。

GitHub TLS 中断或软件源超时属于下载基础设施问题。保留错误记录，在同一固定提交/版本上重试；不要禁用 TLS 证书校验或静默换版本。子模块使用浅克隆降低下载量；`git submodule status third_party/rdt third_party/lerobot` 应显示规定 revision，且没有前导 `+` 或 `-`。

`install-libero` 下载失败时，可以按前述 `--source` 方式使用维护者交付的固定源码副本，但必须说明这一替代来源，不能声称公共下载已通过。
