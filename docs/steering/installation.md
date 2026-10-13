# 安装、资产与本机配置

依赖配方已在新的 Conda 环境真实安装并完成 CPU 入口、processor 和 1118 项测试验收。该结果绑定迁移提交；最终公共代码的完整验证仍见[整合状态](integration-status.md)。本页提供已接入的安装与资产入口，不把 CPU 成功当作 GPU/API 或任务成绩。

## 创建新环境

验证平台为 Linux x86_64、Python 3.12.12、Torch 2.7.1+cu126。宿主需要 Conda、Git、C 编译器和 Linux input 头文件（验证机器以 GCC 13.3.0 构建 evdev），以及适用的 NVIDIA 驱动；Conda 文件不供应所有宿主工具。

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

git submodule update --init third_party/rdt third_party/lerobot
conda env create --prefix "$STEERING_ENV_ROOT/env" --file environment-steering.yml
conda activate "$STEERING_ENV_ROOT/env"

# Includes the validated constraints and the fixed LeRobot base dependencies.
python -m pip install -r requirements-steering.txt
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

关键版本为 NumPy **2.2.6**、TorchVision 0.22.1+cu126、Diffusers 0.35.2、tokenizers 0.21.4、Transformers 4.53.3 的固定 Git revision `dcddb970176382c0fcf4521b0c0e6fc15894dfe0`。`future==1.0.0` 补足 BDDL 未声明的真实 import 依赖。原真实安装先完成基础配方，再补 future；最终清单已纳入修正，没有另建第二个环境伪称“一次安装验证”。

版本约束不等于 wheel 哈希锁或跨平台保证；Conda传递依赖构建号没有锁定。两个 OpenCV distribution 都被上游声明且共享文件，`pip check` 无法检查最终实际 variant，故最后覆盖 headless 与实际 import 检查必须保留。后续若重新安装普通 OpenCV，应重新核验。

## 固定模型与源码资产

大模型不在仓库中。完整身份由 [steering_model_assets_manifest.json](../../scripts/steering_model_assets_manifest.json) 定义，包含214个文件、50,861,376,376字节和3个归一化源文件约束。此前 CPU 校验已真实流式读取并匹配，未反序列化或执行模型。**精确资产分发的可访问位置仍待维护者提供**，不保证仅凭模型名称可取回相同字节。

| 机器配置逻辑根 | 必需内容与来源边界 |
| --- | --- |
| `rdt_checkpoint` | `config.json`、`ema/model.safetensors`；公开 checkpoint revision 未核实，需维护者提供准确文件或验证固定远端版本 |
| `text_encoder` | T5明确 snapshot，revision `3db67ab1af984cf10548a73467f0e5bca2aaaeb2`，不能指向上层 cache root |
| `vision_encoder` | SigLIP明确 snapshot，revision `9fdffc58afc957d1a03a25b10dba0329ab15c2a3` |
| `torch_home` | `hub/facebookresearch_dinov2_main/` 源码及 `hub/checkpoints/dinov2_vitb14_pretrain.pth`；源码 commit 未知，目录名不证明版本 |
| `libero_root` | 当前 clone 的固定 LIBERO 代码、资产和 object-swap 输入，默认 `third_party/libero_pro` |
| `libero_config` | 当前机器的 LIBERO路径配置目录，默认 `.libero_config` |

T5/SigLIP revision 来自本地 cache证据，远端可用性未重新核验。RDT 代码 revision 不等于模型 revision。归一化常量来自固定 RDT 源码和动作转换文件，不存在凭空补出的 checkpoint normalization sidecar。第三方权重、数据与源码的分发许可需分别确认。

## 配置机器并严格校验

准备上述资产后执行。GPU和EGL编号均为示例，应先确认当前机器的物理对应关系；配置写入新文件，不提交机器配置。

```bash
python scripts/prepare_steering_assets.py configure \
  --rdt-checkpoint /path/to/rdt \
  --text-encoder /path/to/t5/snapshots/3db67ab1af984cf10548a73467f0e5bca2aaaeb2 \
  --vision-encoder /path/to/siglip/snapshots/9fdffc58afc957d1a03a25b10dba0329ab15c2a3 \
  --torch-home /path/to/torch-cache \
  --gpu 0 --egl-device-id 0 --output configs/local.yaml

# Optional standalone report; the identical model check is always enforced by
# configure, preflight and the real launcher. A new report filename is required.
python scripts/steering_model_assets.py --local-config configs/local.yaml \
  --repository-root "$PWD" --report outputs-model-assets-001.json
```

校验器不只检查某个文件存在：它比较固定大小/SHA-256，并核对真实加载优先级。更高优先级的 RDT config、T5 safetensors、tokenizer sidecar 或新增可导入 DINO 源码会被拒绝。正常 HF snapshot→blob 符号链接允许；未选中的低优先级权重和额外说明文件可以保留。`--hash-weights` 仅为兼容选项，省略它也必须完成完整模型校验。

默认兼容已有 DINO `__pycache__`，并明确不证明解释器实际使用的 bytecode身份。新分发包可在独立报告命令加 `--clean-distribution`，验证203个纯源码/配置文件的准确集合、无bytecode或符号链接；不要删除正在使用的缓存。验证后资产仍须保持稳定只读，hash检查不防止并发改写。

`install-libero` 使用固定版本、补丁和输入overlay，已做2308文件离线重建核验；也可用 `--source /path/to/verified-tree` 复制已有合格树。`verify-rng` 校验20个固定状态文件，真正运行时还校验规定的两个恢复时点。安装不会重新生成 object-swap 任务。

运行时优先导入当前 clone 的 `third_party/rdt`、`third_party/lerobot/src` 和指定LIBERO源码，并用 `VLA_LIBERO_ROOT` 显式绑定实际LIBERO根，关闭encoder在线下载。`libero_config/config.yaml` 的 `benchmark_root`、`assets`、`bddl_files`、`init_states` 四项必须指向已通过内容校验的同一树；preflight和launcher会校验绑定并在 `environment.json.libero_paths` 保存配置hash与解析路径。使用外置LIBERO树也必须满足这一约束，不能借旧机器路径配置绕过内容身份。完整 DINO源码和权重必须预先提供，避免底层缺文件走Torch Hub下载路径。真实 LeRobot processor必须导入，fallback不能当作安装通过。

GPU编号与EGL枚举独立，一次成功render也不证明二者对应同一设备。allocator默认48GiB只限制PyTorch分配器，不是整个进程/设备总显存硬限额。在线调用使用自己的Codex CLI登录；迁移验收记录CLI0.156.1，固定请求gpt-6-astra/low，但CLI版本不使服务端模型永久不可变。

## 分层验证

1. **CPU配置预览：** 按[README](../../README.md#从安装到运行)对三种方法使用 `--print-config`。这一步不验证模型内容或设备。
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

普通CPU pytest命令不封锁网络/API；正式隔离验收使用专门的socket/provider防护，并检查真实processor身份与图像翻转/8维状态行为。原真实干净安装的结果是 `pip check` 无冲突、62项依赖/入口import、真实root processor、worker `--cfg job`和 **1118 passed、1 warning、86.53s**。其source与日志索引在[README provenance](../../README.md#provenance来源与本地证据)。新集成测试数量使用新一轮结果。

该新环境没有验证GPU/EGL reset/render、模型权重加载/策略推理、Codex登录/API或torchcodec的native解码后端；不能沿用另一个环境的在线成绩。依赖成功、资产身份、机制正确和任务成功分别提供证据。
