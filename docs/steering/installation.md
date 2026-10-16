# Installation

Run commands from the repository root in a **new environment**. RDT and π0.5 use the same pinned dependency recipe; separate environments are recommended when developing either backend. Model-specific setup is below. Runtime commands and results are in [README](../../README.md).

## 1. Requirements

Linux x86_64, an NVIDIA GPU and compatible driver, Conda, Git/Git LFS, `patch`, a C compiler, and Linux input headers. The tested stack is Python 3.12.12, PyTorch 2.7.1+cu126 and H200 NVL with driver 580.65.06. A minimum VRAM requirement and other GPU models have not been validated. Use a disk with room for assets, the environment, download caches and videos; [asset sizes and access terms](model-assets.md) are listed separately.

## 2. Get the code

```bash
git clone --depth 1 --single-branch --branch main --no-tags https://github.com/RIP4KOBE/vla-pilot-plus.git
cd vla-pilot-plus
git submodule update --init --depth 1 third_party/rdt third_party/lerobot
```

## 3. Install the environment

Conda must be initialized in this shell. This recipe installs the fixed LeRobot/Transformers versions needed by both models; do not install upstream optional extras over it.

```bash
conda env create --prefix "$PWD/.venv" --file environment-steering.yml
conda activate "$PWD/.venv"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHON_DOTENV_DISABLED=1
unset PYTHONPATH PYTHONHOME
export PIP_CONFIG_FILE=/dev/null PIP_INDEX_URL=https://pypi.org/simple
unset PIP_EXTRA_INDEX_URL
python -m pip install -r requirements-steering.txt
python scripts/prepare_steering_assets.py install-runtime-compat
python scripts/prepare_steering_assets.py verify-runtime-compat
python scripts/prepare_steering_assets.py install-libero
python scripts/prepare_steering_assets.py verify-libero
python scripts/prepare_steering_assets.py verify-rng
python -m pip install --no-deps --no-build-isolation -e third_party/libero_pro -e third_party/lerobot
# Install last: upstream packages share the cv2 files.
python -m pip install --force-reinstall --no-deps opencv-python-headless==4.12.0.88
python -m pip check
python -c "import cv2.version as v; assert v.headless; print(v.opencv_version, v.headless)"
```

The explicit Robosuite compatibility installation and headless OpenCV check are required. Version numbers alone do not establish them. [Compatibility details and download troubleshooting](installation-troubleshooting.md) explain the checks and verified-cache alternatives.

## 4. Download models and perception assets

Choose one or both model commands. The downloader fixes revisions and verifies all file hashes; [Model assets](model-assets.md) lists direct sources, filenames, sizes and proof of correspondence with tested weights.

```bash
STEERING_ASSETS=/absolute/path/on/large-disk/vla-assets
# RDT: LIBERO Object checkpoint + T5 + SigLIP + DINO.
python scripts/prepare_public_models.py download --model rdt --directory "$STEERING_ASSETS"
# PI05: LIBERO checkpoint + PaliGemma tokenizer + DINO.
# First obtain access to google/paligemma-3b-pt-224 and log in yourself.
hf auth login
python scripts/prepare_public_models.py download --model pi05 --directory "$STEERING_ASSETS"
```

RDT does not require π0.5; π0.5 does not require RDT, T5, a separate SigLIP model, or separate PaliGemma model weights. Both need DINO and the LIBERO assets installed in step 3. Do not substitute a generic pretrained checkpoint for these LIBERO checkpoints.

## 5. Configure the device, paths and online service

Choose an assigned idle GPU. CUDA and EGL indices can differ; use the mapping report, not matching numbers by assumption.

```bash
STEERING_GPU=4  # Replace with your assigned idle GPU.
python scripts/list_steering_devices.py --gpu "$STEERING_GPU"
STEERING_EGL=6  # Replace with egl_device_id from that report.
mkdir -p .local
# RDT machine configuration:
python scripts/prepare_steering_assets.py configure \
  --rdt-checkpoint "$STEERING_ASSETS/rdt_checkpoint" \
  --text-encoder "$STEERING_ASSETS/text_encoder" \
  --vision-encoder "$STEERING_ASSETS/vision_encoder" \
  --torch-home "$STEERING_ASSETS/torch_home" \
  --gpu "$STEERING_GPU" --egl-device-id "$STEERING_EGL" --output .local/rdt.yaml
# PI05 machine configuration:
python scripts/prepare_public_models.py configure-pi05 --directory "$STEERING_ASSETS" \
  --gpu "$STEERING_GPU" --egl-device-id "$STEERING_EGL" --output .local/pi05.yaml
```

Run only the configure command for models you downloaded. These commands verify the assets and write local paths; they do not execute an episode. Keep machine files outside `configs/` except the supported ignored `configs/local.yaml`, so source freezing does not capture private paths. `.local/` is ignored.

Install [Codex CLI](https://learn.chatgpt.com/docs/codex/cli) separately and complete your own authentication. The protocol uses CLI **0.156.1**, model **`gpt-6-astra`**, effort **`ultra`**. Credentials stay in your own CLI login, never in Git or the local YAML. Model/account permissions require a real online check; changing CLI or service settings creates a new condition.

```bash
codex --version
codex login                  # Omit if already authenticated.
codex login status
# For an authorized headless account: codex login --device-auth
```

## 6. Preflight

Use new output directories. The RDT preflight explicitly tests the CUDA/render mapping and a real Codex image request. PI05 preflight checks fixed assets, dependencies and device identity; its following single-task diagnostic additionally tests model loading, rendering, online access and steering.

```bash
python scripts/check_steering.py --local-config .local/rdt.yaml \
  --output-dir outputs/rdt-preflight-001 --gpu --api
python scripts/run_pi05.py --local-config .local/pi05.yaml \
  --output-dir outputs/pi05-preflight-001 --preflight
```

## 7. Run and evaluate

Follow the [RDT three-mode commands](../../README.md#quick-start) or [π0.5 + VLS commands](../../README.md#π05--vls). Configuration previews are CPU-only; diagnostics are real online episodes; full evaluations use all ten declared tasks. A diagnostic never supplies a missing formal episode.

Successful installation does not guarantee task success. Report environment outcomes separately from infrastructure failures and validity checks. [Fresh RDT environment validation](onboarding-validation.md), [π0.5 evaluation](pi05-evaluation.md), and [asset verification](model-assets.md) define the actual tested coverage.
