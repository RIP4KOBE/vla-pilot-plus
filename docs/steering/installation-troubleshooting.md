# Installation details and troubleshooting

Follow [Installation](installation.md) first. This page explains compatibility requirements and download recovery, without changing the evaluation protocol.

## Robosuite 兼容补丁

固定的 Robosuite 1.4.0 wheel 还需要仓库提供的兼容补丁。目前保留的旧在线环境包含这些修改；此前安装配方遗漏了这一步，新环境会在 CUDA/EGL 编号不同时拒绝导入。

`install-runtime-compat` 显式安装两份文件的受控修改：区分 CUDA 与 EGL 编号、为 NumPy 2 的分割图整数运算使用足够位宽、修正 EGL 配置数组传参，并保持历史上下文释放行为。它只接受已知原版或已补丁文件，先核验全部输入，再验证补丁输出哈希；不会覆盖未知本地修改，也不会修改当前 Python 环境以外的包。

补丁输出与目前保留的旧在线环境对应文件逐字节一致；历史运行没有保存这两份包内文件的哈希，不能倒推每次历史执行的完整依赖身份。补丁及输入/输出身份见 [compatibility manifest](../../scripts/dependency_patches/robosuite-1.4.0.json)。预检和正式 launcher 都会检查安装结果并记录哈希。重装 Robosuite 后需要重新执行安装与核验；不要靠 `pip check` 判断补丁是否存在。

## 下载缓存与连接故障

可以复用下载缓存，但不能复用旧环境的 `site-packages`。对已经核对来源和版本的 wheel 缓存，可在完整 requirements 安装前执行以下可选步骤；约束冲突时应停止并检查，不能放宽版本解决。

```bash
python -m pip install --no-deps -c constraints-steering.txt /path/to/verified-wheel-cache/*.whl
python -m pip install -r requirements-steering.txt
```

缓存不完整时仍需要网络，Git 来源依赖的缓存也必须对应固定 revision。将软件源、缓存使用、安装日志和最终 `pip freeze` 记入验收报告。使用镜像时显式设置并记录 `PIP_INDEX_URL`，不要继承未说明的全局 pip 配置。

LeRobot 的 Git LFS 测试媒体也可能在子模块 checkout 时下载；网络较慢时这一步会等待较久。它们不是本项目的 RDT 模型资产，不能替代[固定模型准备](model-assets.md)。

GitHub TLS 中断或软件源超时属于下载基础设施问题。保留错误记录，在同一固定提交/版本上重试；不要禁用 TLS 证书校验或静默换版本。子模块使用浅克隆降低下载量；`git submodule status third_party/rdt third_party/lerobot` 应显示规定 revision，且没有前导 `+` 或 `-`。

`install-libero` 下载失败时，可以执行 `python scripts/prepare_steering_assets.py install-libero --source /path/to/verified-libero-tree`使用维护者交付的固定源码副本，但必须说明这一替代来源，不能声称公共下载已通过。


## Model downloads and reproducibility

The fixed model manifest distinguishes complete cached-file hashing from fresh network downloads. Large matching cached weights may be reused; their provenance and checks remain recorded. The PaliGemma tokenizer requires the user's own approved account access, even though its metadata is public. See [Model assets](model-assets.md).

The latest public LIBERO installation was also tested in a new directory: all 2308 files matched the fixed asset manifest. A temporary network failure in an older report does not mean the public source is unavailable permanently. Preserve an error log and retry the same pinned revision; do not substitute another asset version.

The installation recipe pins versions and Git revisions, but is not a complete wheel-hash or platform lock. Record `pip freeze`, the interpreter, GPU/driver, compatibility receipt and asset manifest for every accepted run. The online service's fixed model name cannot guarantee identical future outputs.
