# 安装、资产与本机配置

**草稿状态：** 下面依赖顺序已在全新的 Python 环境真实安装并完成 CPU 验收。最终文件发布位置、资产验证器接线与三模式入口仍待整合；文中明确标出的候选命令尚未成为公共入口。成绩与来源见 [README](../../README.md)。

## 1. 创建隔离环境

验证平台为 Linux、Python 3.12.12、CUDA 12.6 构建的 Torch 2.7.1。需要 Git、Conda，以及构建 evdev 所需的 C 编译器和 Linux input 头文件；已验证机器提供 GCC 13.3.0。Conda 环境不负责安装宿主 NVIDIA 驱动或提供所有系统编译工具。

在新 clone 根目录初始化固定 RDT/LeRobot 子模块；本流程不需要安装训练、CALVIN 或 LeRobot 的全部可选 extras。

```bash
git submodule update --init third_party/rdt third_party/lerobot

conda create --yes --prefix /path/to/new-env --override-channels -c conda-forge \
  python=3.12.12 pip=25.2 setuptools=80.9.0 ffmpeg=8.0.0 \
  libegl=1.7.0 libgl=1.7.0 libglx=1.7.0 libstdcxx-ng=15.2.0
conda activate /path/to/new-env
```

**待发布文件名：** 下段使用 `requirements-steering.txt`、`constraints-steering.txt`、`requirements-steering-lerobot.txt`。只有将已验证的三个输入移入这些最终位置后才能照抄；当前旧 requirements 不能冒充已验证清单。草稿包的 `validated-inputs/` 保留原始已验证文件，便于审阅逐行映射。

```bash
# 已验证的安装顺序；上述三个最终文件位置待整合。
python -m pip install \
  -c constraints-steering.txt \
  -r requirements-steering.txt \
  -r requirements-steering-lerobot.txt

# 当前已有资产 CLI：取固定 LIBERO 源码并应用本项目固定输入/overlay。
python scripts/prepare_steering_assets.py install-libero

python -m pip install --no-deps --no-build-isolation \
  -e third_party/libero_pro -e third_party/lerobot

# 必须在所有上述安装后执行：两个 distribution 共用 cv2 文件。
python -m pip install --force-reinstall --no-deps opencv-python-headless==4.12.0.88
python -m pip check
python -c "import cv2.version as v; assert v.headless; print(v.opencv_version, v.headless)"
```

验证过程首次安装后补入了 BDDL 漏声明的 `future==1.0.0`；最终清单已包含它。主依赖与 LeRobot base 联合使用172项版本约束，包含 Torch 2.7.1+cu126、TorchVision 0.22.1+cu126、NumPy **2.2.6**、Diffusers 0.35.2、tokenizers 0.21.4、Transformers 4.53.3 的固定 Git commit `dcddb970176382c0fcf4521b0c0e6fc15894dfe0`。完整清单以文件为准；它是版本约束与真实安装证据，不是所有平台的带 wheel hash 发布锁。

OpenCV 同时被 robosuite 与 LeRobot 以不同 distribution 名声明。`pip check` 不能检查谁最后覆盖了 `cv2`；最后安装 headless 与实际标记检查缺一不可。后续安装普通 OpenCV 可能再次改变结果。

## 2. 准备固定资产

模型权重不在仓库中。**待补：** 维护者提供的可访问、许可合规的精确资产包位置。当前文档不能保证仅凭公开模型名称即可取回逐字节相同资产。

| 机器配置逻辑根 | 内容与版本证据 |
| --- | --- |
| `rdt_checkpoint` | `config.json` 与 `ema/model.safetensors`；本地内容已哈希，公开权重 revision **未核实** |
| `text_encoder` | T5 的明确 snapshot，revision `3db67ab1af984cf10548a73467f0e5bca2aaaeb2`；不接受上层 cache root |
| `vision_encoder` | SigLIP 的明确 snapshot，revision `9fdffc58afc957d1a03a25b10dba0329ab15c2a3` |
| `torch_home` | `hub/facebookresearch_dinov2_main/` 源码与 `hub/checkpoints/dinov2_vitb14_pretrain.pth`；DINO 源码 commit **未知**，目录名不构成 commit 证据 |
| `libero_root` | 当前 clone 的固定 LIBERO 代码、资产和 object-swap 输入 |
| `libero_config` | 当前机器的 LIBERO 路径配置目录，由 configure 写入 |

RDT 代码子模块 commit 不等于模型权重 revision。T5/SigLIP 的 revision 来自本地 snapshot/ref 证据，本次没有重查远端可用性。归一化常量在 RDT 源码与动作转换文件中，没有虚构一个外部 normalization sidecar。

以下为主要权重的 **SHA-256**，完整集合需以审阅后固定的 expected manifest 为准：

| 逻辑文件 | SHA-256 |
| --- | --- |
| RDT `config.json` | `3482cc79b3268ccfca9d8cc9b8e32f3925dc71c3bd60f5e6dfcaa564aecde835` |
| RDT `ema/model.safetensors` | `b4e3631db326689297cd2f0b02d32ade9dc6ee9ae09c03171add64b80e86aaa1` |
| T5 `pytorch_model.bin` | `c8407a9ae21075667be98f84f4c93e8a7bfc772a352cd2e6998f5916f7181db8` |
| SigLIP `model.safetensors` | `ea2abad2b7f8a9c1aa5e49a244d5d57ffa71c56f720c94bc5d240ef4d6e1d94a` |
| DINO `dinov2_vitb14_pretrain.pth` | `0b8b82f85de91b424aded121c7e1dcc2b7bc6d0adeea651bf73a13307fad8c73` |

独立资产验证器草案已实际读取 **214文件 / 50,861,376,376字节**及3个归一化源文件并全部匹配，expected manifest SHA为 `de4c7da58023099e7d6c8d2cdbc08736b7ab60e67c8355c3fe354f0bafef4687`。**该完整 expected-hash gate 尚未接入当前 launcher。** 现有配置脚本的文件检查或 `--hash-weights` 输出不能代替与此固定 manifest 比较。

验证器待发布命令形态，当前不要当作已存在文件执行：

```bash
# PROPOSED / 待接入并验证最终路径
python scripts/steering_model_assets.py \
  --local-config /path/to/local.yaml \
  --manifest configs/assets/model-assets.json \
  --repository-root "$PWD" --report /path/to/new-asset-report.json
```

它还检查真正的文件选择优先级：较高优先级的 RDT config、T5 safetensors/tokenizer sidecar 或额外可导入 DINO 源码会改变加载路径，不能只验证“某个权重文件存在”。正常 HF snapshot → blob 符号链接允许使用匹配内容；未被选择的低优先级 checkpoint 和额外说明文档可以保留。

当前兼容检查允许已有 DINO `__pycache__`，但不证明其字节身份。为新的资产分发制作纯源码包时，可另选严格 clean 检查：203个固定文件，不带 bytecode 或符号链接。不要为文档验收删除正在运行环境的 cache。哈希也不防止验证后文件被并发改写，应保持资产只读稳定。

## 3. 配置当前机器

当前已有 CPU 资产检查：

```bash
python scripts/prepare_steering_assets.py verify-libero
python scripts/prepare_steering_assets.py verify-rng

python scripts/prepare_steering_assets.py configure \
  --rdt-checkpoint /path/to/rdt \
  --text-encoder /path/to/t5/snapshots/3db67ab1af984cf10548a73467f0e5bca2aaaeb2 \
  --vision-encoder /path/to/siglip/snapshots/9fdffc58afc957d1a03a25b10dba0329ab15c2a3 \
  --torch-home /path/to/torch-cache \
  --gpu 0 --egl-device-id 0 --output /path/to/local.yaml
```

设备0只是示例。CUDA 可见编号与 EGL 枚举独立，不能根据一个推断另一个，也不能仅凭成功 render 断言两者对应同一物理 GPU。launcher 使用机器配置显式设置设备，覆盖父进程遗留设置；显存 allocator limit 默认48GiB，不等于整进程/整GPU总内存的硬限额。

固定 LIBERO 验证覆盖2308文件；20个 RNG 文件 manifest SHA为 `628c429d457def157c9163be94a1202721673f97f1e43aa6446e5a06889c6043`。初始RNG协议与实际恢复hooks一起定义科学设置，不能用相同seed数值替代。

运行时优先导入当前 clone 的 RDT/LeRobot/LIBERO 源码，并关闭 encoder 在线下载；预先提供完整 DINO 源码和权重，因为其底层 Torch Hub 缺文件时存在下载路径。不要依靠另一 checkout 的 editable 安装恰好补齐依赖。真实 LeRobot processor 必须加载，fallback 不能充当环境验收。

在线 provider 使用使用者现有 Codex CLI 登录；已验证运行记录中的 CLI 为0.156.1，模型请求为 gpt-6-astra/low。这里不发布未经核验的 CLI 安装命令，也不把 CLI 版本固定等同于服务端模型不可变。

## 4. 验收范围

干净安装的真实验收是：`pip check` 无冲突，62项依赖和入口导入通过，当前 clone 的 processor 身份与行为通过，worker `--cfg job` 通过，**1118 passed、1 warning、86.53s**。CPU 检查关闭 CUDA，禁止 socket/provider 命令；没有加载模型权重、创建仿真环境或调用在线服务。

它没有验证新环境的 GPU/EGL reset/render、模型推理、CLI登录/API或 torchcodec 的 FFmpeg native 解码后端。新环境的首次 GPU/API preflight 与完整 cohort 必须单独生成证据；不能沿用另一环境的在线成绩。

精确 CPU harness 与日志见 README 的本地证据索引。一般的 `CUDA_VISIBLE_DEVICES=''` 只隐藏CUDA，**不封锁网络/API**；新集成的公开测试入口待最终验证，不能把一条普通 pytest 命令描述成已经实施了完整离线隔离。
