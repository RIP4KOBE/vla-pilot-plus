#!/usr/bin/env bash
# ============================================================================
# RDT-LIBERO Eval 环境安装脚本
# 基于现有 rdt 环境添加 LIBERO 评估所需依赖
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."
GROOT_ROOT="$PROJECT_ROOT/../Isaac-GR00T"
LIBERO_ROOT="$GROOT_ROOT/external_dependencies/LIBERO"

ENV_NAME="rdt_libero_eval_fast"
CONDA_BASE="/share_data/chensiqi/miniconda3"

echo "=============================================="
echo "RDT-LIBERO Eval 环境安装"
echo "=============================================="
echo "Project Root: $PROJECT_ROOT"
echo "GROOT Root: $GROOT_ROOT"
echo "LIBERO Root: $LIBERO_ROOT"
echo "Env Name: $ENV_NAME"
echo "=============================================="

# 检查 LIBERO 是否存在
if [ ! -d "$LIBERO_ROOT" ]; then
    echo "[INFO] LIBERO submodule not found, initializing..."
    cd "$GROOT_ROOT"
    git submodule update --init external_dependencies/LIBERO
fi

# 激活 conda
source "$CONDA_BASE/etc/profile.d/conda.sh"

# 检查是否已有环境
if conda env list | grep -q "^$ENV_NAME "; then
    echo "[INFO] Environment $ENV_NAME already exists."
    read -p "Do you want to remove and recreate it? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        conda env remove -n $ENV_NAME -y
    else
        echo "Skipping environment creation..."
        echo "Activate with: conda activate $ENV_NAME"
        exit 0
    fi
fi

echo ""
echo "[STEP 1/6] Creating conda environment with Python 3.10..."
conda create -n $ENV_NAME python=3.10 -y

echo ""
echo "[STEP 2/6] Activating environment..."
conda activate $ENV_NAME

echo ""
echo "[STEP 3/6] Installing PyTorch with CUDA 12.1..."
pip install torch==2.1.2+cu121 torchvision==0.16.2+cu121 --index-url https://download.pytorch.org/whl/cu121

echo ""
echo "[STEP 4/6] Installing LIBERO and its dependencies..."
# LIBERO 需要的依赖
pip install robosuite==1.4.0
pip install mujoco==3.3.7
pip install gymnasium==0.29.1
pip install h5py
pip install hydra-core==1.2.0
pip install opencv-python
pip install -e "$LIBERO_ROOT"

echo ""
echo "[STEP 5/6] Installing RDT model dependencies..."
pip install accelerate==0.27.2 \
    diffusers==0.26.3 \
    transformers==4.38.2 \
    peft==0.10.0 \
    einops==0.8.1 \
    deepspeed==0.14.2 \
    safetensors \
    sentencepiece \
    timm \
    pyyaml \
    tqdm \
    wandb \
    matplotlib \
    scipy \
    scikit-image

echo ""
echo "[STEP 6/6] Installing Isaac-GR00T (no deps)..."
pip install -e "$GROOT_ROOT" --no-deps

echo ""
echo "[INFO] Fixing numpy version for compatibility..."
pip install numpy==1.24.3

echo ""
echo "[INFO] Installing flash-attn (optional)..."
pip install flash-attn==2.5.0 --no-build-isolation 2>/dev/null || echo "[WARN] flash-attn installation failed, continuing..."

echo ""
echo "=============================================="
echo "Installation Complete!"
echo "=============================================="
echo ""
echo "To activate the environment:"
echo "  conda activate $ENV_NAME"
echo ""
echo "To verify LIBERO is working:"
echo "  python -c 'from libero.libero import benchmark; print(benchmark.get_benchmark_dict().keys())'"
echo ""
echo "To run evaluation:"
echo "  cd $PROJECT_ROOT"
echo "  python eval_fast/eval_rdt_libero.py --config eval_fast/config/eval_config.yaml"
echo ""
echo "=============================================="
