#!/usr/bin/env bash
set -euo pipefail

REQUIRED_CONDA_ENV="${RDT_CONDA_ENV:-rdt}"
CURRENT_CONDA_ENV="${CONDA_DEFAULT_ENV:-}"
if [ -z "$CURRENT_CONDA_ENV" ] && [ -n "${CONDA_PREFIX:-}" ]; then
    CURRENT_CONDA_ENV="$(basename "$CONDA_PREFIX")"
fi
if [ "$CURRENT_CONDA_ENV" != "$REQUIRED_CONDA_ENV" ]; then
    echo "finetune_libero.sh must run inside conda env '$REQUIRED_CONDA_ENV' (current: '${CURRENT_CONDA_ENV:-none}')." >&2
    echo "Activate it with: conda activate $REQUIRED_CONDA_ENV" >&2
    exit 2
fi

export NCCL_IB_DISABLE="${NCCL_IB_DISABLE:-0}"
export NCCL_DEBUG="${NCCL_DEBUG:-INFO}"
export NCCL_NVLS_ENABLE="${NCCL_NVLS_ENABLE:-0}"
export MASTER_ADDR="${MASTER_ADDR:-127.0.0.1}"
export MASTER_PORT="${MASTER_PORT:-29500}"
export RANK="${RANK:-0}"
export WORLD_SIZE="${WORLD_SIZE:-1}"
export LOCAL_RANK="${LOCAL_RANK:-0}"

export RDT_HDF5_BACKEND="${RDT_HDF5_BACKEND:-libero}"
export RDT_LIBERO_DATA_ROOT="${RDT_LIBERO_DATA_ROOT:-/mnt/data/hf_cache/hub}"
export RDT_LIBERO_SUITES="${RDT_LIBERO_SUITES:-libero_10}"

export TEXT_ENCODER_NAME="${TEXT_ENCODER_NAME:-google/t5-v1_1-xxl}"
export VISION_ENCODER_NAME="${VISION_ENCODER_NAME:-google/siglip-so400m-patch14-384}"
export RDT_MODEL_NAME="${RDT_MODEL_NAME:-/mnt/data/hf_cache/hub/robotics-diffusion-transformer--rdt-1b}"
export OUTPUT_DIR="${OUTPUT_DIR:-./checkpoints/rdt-libero-${RDT_LIBERO_SUITES}}"
if [ -n "${CUTLASS_PATH:-}" ]; then
    export CUTLASS_PATH
fi
export CFLAGS="${CFLAGS:--I/usr/include}"
export LDFLAGS="${LDFLAGS:--L/usr/lib/x86_64-linux-gnu}"
export WANDB_PROJECT="${WANDB_PROJECT:-robotics_diffusion_transformer_libero}"

TRAIN_BATCH_SIZE="${TRAIN_BATCH_SIZE:-2}"
SAMPLE_BATCH_SIZE="${SAMPLE_BATCH_SIZE:-2}"
MAX_TRAIN_STEPS="${MAX_TRAIN_STEPS:-10}"
CHECKPOINTING_PERIOD="${CHECKPOINTING_PERIOD:-1000}"
SAMPLE_PERIOD="${SAMPLE_PERIOD:-5}"
CHECKPOINTS_TOTAL_LIMIT="${CHECKPOINTS_TOTAL_LIMIT:-4}"
GRADIENT_ACCUMULATION_STEPS="${GRADIENT_ACCUMULATION_STEPS:-1}"
DATALOADER_NUM_WORKERS="${DATALOADER_NUM_WORKERS:-2}"
REPORT_TO="${REPORT_TO:-tensorboard}"
MIXED_PRECISION="${MIXED_PRECISION:-bf16}"
LEARNING_RATE="${LEARNING_RATE:-1e-4}"

mkdir -p "$OUTPUT_DIR"

accelerate launch main.py \
    --deepspeed="./configs/zero2.json" \
    --pretrained_model_name_or_path="$RDT_MODEL_NAME" \
    --pretrained_text_encoder_name_or_path="$TEXT_ENCODER_NAME" \
    --pretrained_vision_encoder_name_or_path="$VISION_ENCODER_NAME" \
    --output_dir="$OUTPUT_DIR" \
    --train_batch_size="$TRAIN_BATCH_SIZE" \
    --sample_batch_size="$SAMPLE_BATCH_SIZE" \
    --max_train_steps="$MAX_TRAIN_STEPS" \
    --checkpointing_period="$CHECKPOINTING_PERIOD" \
    --sample_period="$SAMPLE_PERIOD" \
    --checkpoints_total_limit="$CHECKPOINTS_TOTAL_LIMIT" \
    --gradient_accumulation_steps="$GRADIENT_ACCUMULATION_STEPS" \
    --lr_scheduler="constant" \
    --learning_rate="$LEARNING_RATE" \
    --mixed_precision="$MIXED_PRECISION" \
    --dataloader_num_workers="$DATALOADER_NUM_WORKERS" \
    --dataset_type="finetune" \
    --state_noise_snr=40 \
    --load_from_hdf5 \
    --report_to="$REPORT_TO"
