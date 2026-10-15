#!/bin/bash
# ============================================================================
# RDT LoRA 微调脚本
# 基于预训练模型进行参数高效微调
# ============================================================================

export run_id=$(date +%Y%m%d_%H%M%S)
export NCCL_IB_HCA=mlx5_0:1,mlx5_1:1,mlx5_2:1,mlx5_3:1,mlx5_4:1,mlx5_7:1,mlx5_8:1,mlx5_9:1
export NCCL_IB_DISABLE=0
export NCCL_SOCKET_IFNAME=bond0
export NCCL_DEBUG=INFO
export NCCL_NVLS_ENABLE=0
export DS_BUILD_EVOFORMER_ATTN=0

export TEXT_ENCODER_NAME="google/t5-v1_1-xxl"
export VISION_ENCODER_NAME="google/siglip-so400m-patch14-384"
export CFLAGS="-I/usr/include"
export LDFLAGS="-L/usr/lib/x86_64-linux-gnu"

#========================================================================
# 训练配置
#========================================================================
dataset_name="libero_spatial"      # 数据集: libero_10, libero_spatial, libero_object, libero_goal, libero_90
finetune_method="LoRA"             # 微调方法: LoRA
model_size="1B"                    # 模型大小: 1B
seed=42                            # 随机种子

#========================================================================
# LoRA 配置（500 episodes 中等数据集推荐）
#========================================================================
# 目标模块选项:
#   - all: 全模块（注意力 + FFN + 适配器）← 500+ episodes 推荐
#   - adaptor_only: 仅条件适配器
#   - cross_attn: 仅交叉注意力
#   - adaptor_cross: 适配器 + 交叉注意力（小数据集 <50 episodes）
#   - attn_adaptor: 注意力 + 适配器（中等数据集 50-200 episodes）
#========================================================================
lora_rank=32                        # LoRA rank（500 episodes 可以用较大 rank）
lora_alpha=64                       # LoRA alpha（rank 的 2 倍）
lora_dropout=0.05                   # 数据量大，可以减少 dropout
lora_target_modules="all"           # 500 episodes 足够训练全模块

#========================================================================
# 基础模型配置
#========================================================================
base_model_name="libero90-ckpt65k"
BASE_MODEL_PATH="./checkpoints/rdt-finetune-1b-20251119_122234/checkpoint-65000"

# LoRA checkpoint 恢复路径（可选，用于继续训练）
RESUME_CHECKPOINT=""

export WANDB_PROJECT="rdt_libero_lora_finetune"

#========================================================================
# 训练超参数（500 episodes 中等数据集推荐）
#========================================================================
# 500 episodes × ~150 步/episode ≈ 75,000 步
# 有效 batch = 48 × 2 = 96
# 每 epoch ≈ 75000 / 96 ≈ 781 步
# 训练 30-50 epochs → 25000-40000 步
#========================================================================
train_batch_size=48
gradient_accumulation_steps=2
learning_rate=5e-5                  # 数据量大，可以用稍高学习率
lr_scheduler="cosine"
lr_warmup_steps=500                 # 更长 warmup
max_train_steps=30000               # 约 38 epochs
checkpointing_period=2000           # 减少保存频率
sample_period=1000
state_noise_snr=40                  # 数据量大，减少噪声

#========================================================================
# 生成输出目录名称
#========================================================================
export OUTPUT_DIR="./checkpoints/RDT-${model_size}-${finetune_method}-${dataset_name}-${lora_target_modules}-r${lora_rank}a${lora_alpha}-${run_id}"

#========================================================================
# 打印训练配置
#========================================================================
echo "=========================================================================="
echo "🚀 RDT LoRA 微调训练"
echo "=========================================================================="
echo ""
echo "📊 数据集配置:"
echo "   数据集:        ${dataset_name}"
echo "   微调方法:      ${finetune_method}"
echo "   模型大小:      ${model_size}"
echo ""
echo "🎯 LoRA 配置:"
echo "   目标模块:      ${lora_target_modules}"
echo "   Rank:          ${lora_rank}"
echo "   Alpha:         ${lora_alpha}"
echo "   Dropout:       ${lora_dropout}"
echo ""
echo "📦 模型配置:"
echo "   Base Model:    ${BASE_MODEL_PATH}"
if [ -n "$RESUME_CHECKPOINT" ]; then
    echo "   恢复训练:      ${RESUME_CHECKPOINT}"
else
    echo "   恢复训练:      否（从头开始 LoRA）"
fi
echo ""
echo "⚙️  训练超参数:"
echo "   Batch Size:    ${train_batch_size} x ${gradient_accumulation_steps} = $((train_batch_size * gradient_accumulation_steps))"
echo "   学习率:        ${learning_rate}"
echo "   调度器:        ${lr_scheduler}"
echo "   Warmup:        ${lr_warmup_steps} 步"
echo "   最大步数:      ${max_train_steps}"
echo "   Checkpoint:    每 ${checkpointing_period} 步"
echo "   状态噪声 SNR:  ${state_noise_snr}"
echo ""
echo "📁 输出目录:      ${OUTPUT_DIR}"
echo "🌱 随机种子:      ${seed}"
echo "⏰ 运行时间戳:    ${run_id}"
echo "=========================================================================="

# 创建输出目录
if [ ! -d "$OUTPUT_DIR" ]; then
    mkdir -p "$OUTPUT_DIR"
    echo "✅ 输出文件夹已创建: '$OUTPUT_DIR'"
else
    echo "⚠️  输出文件夹已存在: '$OUTPUT_DIR'"
fi

# 保存训练配置
cat > "$OUTPUT_DIR/training_config.txt" << EOF
训练配置信息
=====================================
数据集:          ${dataset_name}
微调方法:        ${finetune_method}
模型大小:        ${model_size}

LoRA 配置:
  目标模块:      ${lora_target_modules}
  Rank:          ${lora_rank}
  Alpha:         ${lora_alpha}
  Dropout:       ${lora_dropout}

模型:
  Base Model:    ${BASE_MODEL_PATH}
  恢复训练:      ${RESUME_CHECKPOINT:-从头开始}

训练超参数:
  Batch Size:    ${train_batch_size} x ${gradient_accumulation_steps}
  学习率:        ${learning_rate}
  调度器:        ${lr_scheduler}
  Warmup:        ${lr_warmup_steps}
  最大步数:      ${max_train_steps}
  Checkpoint:    每 ${checkpointing_period} 步
  状态噪声:      SNR=${state_noise_snr}

随机种子:        ${seed}
运行时间戳:      ${run_id}
=====================================
EOF

echo ""
echo "🔄 开始训练..."
echo ""

# 构建恢复训练参数
RESUME_ARG=""
if [ -n "$RESUME_CHECKPOINT" ]; then
    echo "🔄 从 LoRA checkpoint 恢复训练: ${RESUME_CHECKPOINT}"
    
    resume_basename=$(basename "$RESUME_CHECKPOINT")
    target_checkpoint="$OUTPUT_DIR/$resume_basename"
    
    if [ ! -d "$target_checkpoint" ]; then
        echo "📋 复制 checkpoint 到输出目录: $resume_basename"
        rsync -a --info=progress2 "$RESUME_CHECKPOINT" "$OUTPUT_DIR/"
        echo "✅ Checkpoint 复制完成"
    else
        echo "✓ Checkpoint 已存在于输出目录"
    fi
    
    RESUME_ARG="--resume_from_checkpoint=$resume_basename"
else
    echo "🆕 从 Base Model 开始 LoRA 微调"
fi

echo "📥 加载 Base Model: ${BASE_MODEL_PATH}"

# 启动 DeepSpeed 训练
deepspeed --exclude="localhost:0" main_sft.py \
    --deepspeed="./configs/zero2.json" \
    --pretrained_model_name_or_path=$BASE_MODEL_PATH \
    --pretrained_text_encoder_name_or_path=$TEXT_ENCODER_NAME \
    --pretrained_vision_encoder_name_or_path=$VISION_ENCODER_NAME \
    --output_dir=$OUTPUT_DIR \
    --seed=${seed} \
    --use_lora \
    --lora_rank=${lora_rank} \
    --lora_alpha=${lora_alpha} \
    --lora_dropout=${lora_dropout} \
    --lora_target_modules="${lora_target_modules}" \
    --train_batch_size=${train_batch_size} \
    --gradient_accumulation_steps=${gradient_accumulation_steps} \
    --sample_batch_size=32 \
    --num_sample_batches=4 \
    --max_train_steps=${max_train_steps} \
    --checkpointing_period=${checkpointing_period} \
    --sample_period=${sample_period} \
    --checkpoints_total_limit=20 \
    --lr_scheduler="${lr_scheduler}" \
    --learning_rate=${learning_rate} \
    --lr_warmup_steps=${lr_warmup_steps} \
    --mixed_precision="bf16" \
    --dataloader_num_workers=8 \
    --image_aug \
    --dataset_type="finetune" \
    --state_noise_snr=${state_noise_snr} \
    --load_from_hdf5 \
    --report_to=tensorboard \
    --precomp_lang_embed \
    $RESUME_ARG

echo ""
echo "=========================================================================="
echo "✅ 训练完成！"
echo "📁 Checkpoints 保存在: ${OUTPUT_DIR}"
echo ""
echo "📋 下一步: 运行批量评估"
echo "   ./batch_eval_checkpoints.sh ${OUTPUT_DIR}"
echo "=========================================================================="

