export run_id=$(date +%Y%m%d_%H%M%S)
export NCCL_IB_HCA=mlx5_0:1,mlx5_1:1,mlx5_2:1,mlx5_3:1,mlx5_4:1,mlx5_7:1,mlx5_8:1,mlx5_9:1
export NCCL_IB_DISABLE=0
export NCCL_SOCKET_IFNAME=bond0
export NCCL_DEBUG=INFO
export NCCL_NVLS_ENABLE=0
export DS_BUILD_EVOFORMER_ATTN=0
# export CUDA_VISIBLE_DEVICES="1,2,3,4,5,6,7"
# export CUDA_VISIBLE_DEVICES=0

export TEXT_ENCODER_NAME="google/t5-v1_1-xxl"
export VISION_ENCODER_NAME="google/siglip-so400m-patch14-384"
export CFLAGS="-I/usr/include"
export LDFLAGS="-L/usr/lib/x86_64-linux-gnu"

#========================================================================
# 训练配置：数据集和微调方法
#========================================================================
dataset_name="libero_spatial"           # 数据集: libero_10, libero_spatial, libero_object, libero_goal, libero_90
finetune_method="Full"             # 微调方法: Full (全参数微调)
model_size="1B"                    # 模型大小: 1B
seed=42                            # 随机种子（用于可复现性）

# 基础模型路径
base_model_name="libero90-ckpt65k"           # 基础模型标识
BASE_MODEL_PATH="./checkpoints/rdt-finetune-1b-20251119_122234/checkpoint-65000"

# 全参数微调 checkpoint 恢复路径（如果要从之前的 checkpoint 继续训练）
# RESUME_CHECKPOINT="./checkpoints/xxx/checkpoint-xxx"
RESUME_CHECKPOINT=""

export WANDB_PROJECT="rdt_libero_finetune_csq"

#========================================================================
# 全参数微调模式
#========================================================================
# 特点：
#   - 更新所有模型参数
#   - 通常能获得更好的性能
#   - 需要更多显存和训练时间
#   - 权重文件较大
#========================================================================

# 生成清晰的输出文件夹名称
# 格式: RDT-{model_size}-{method}-{dataset}-from_{base_model}-{timestamp}
if [ -n "$RESUME_CHECKPOINT" ]; then
    # 从 checkpoint 继续训练
    export OUTPUT_DIR="./checkpoints/RDT-${model_size}-${finetune_method}-${dataset_name}-from_${base_model_name}-${run_id}"
else
    # 从头训练
    export OUTPUT_DIR="./checkpoints/RDT-${model_size}-${finetune_method}-${dataset_name}-from_${base_model_name}-${run_id}"
fi

#========================================================================
# 打印训练配置
#========================================================================
echo "=========================================================================="
echo "🚀 RDT 全参数微调训练"
echo "=========================================================================="
echo "📊 数据集:        ${dataset_name}"
echo "🔧 微调方法:      ${finetune_method}"
echo "📦 模型大小:      ${model_size}"
echo "📂 Base Model:   ${BASE_MODEL_PATH}"
if [ -n "$RESUME_CHECKPOINT" ]; then
    echo "🔄 恢复训练:      是"
    echo "📥 Checkpoint:   ${RESUME_CHECKPOINT}"
else
    echo "🆕 训练模式:      从 Base Model 开始全参数微调"
fi
echo "🌱 随机种子:      ${seed}"
echo "📁 输出目录:      ${OUTPUT_DIR}"
echo "⏰ 运行时间戳:    ${run_id}"
echo "=========================================================================="

if [ ! -d "$OUTPUT_DIR" ]; then
    mkdir -p "$OUTPUT_DIR"
    echo "✅ 输出文件夹已创建: '$OUTPUT_DIR'"
else
    echo "⚠️  输出文件夹已存在: '$OUTPUT_DIR'"
fi

# 保存训练配置到输出目录
cat > "$OUTPUT_DIR/training_config.txt" << EOF
训练配置信息
=====================================
数据集:          ${dataset_name}
微调方法:        ${finetune_method}
模型大小:        ${model_size}
Base Model:      ${BASE_MODEL_PATH}
恢复训练:        ${RESUME_CHECKPOINT:-从头开始}
随机种子:        ${seed}
训练批次大小:    48
采样批次大小:    32
学习率:          1e-4
学习率调度:      constant
混合精度:        bf16
最大训练步数:    200000
保存周期:        5000
采样周期:        500
数据加载线程:    8
状态噪声SNR:     40
运行时间戳:      ${run_id}
=====================================
EOF

echo ""
echo "🔄 开始训练..."
echo ""

# 构建恢复训练参数
RESUME_ARG=""
if [ -n "$RESUME_CHECKPOINT" ]; then
    echo "🔄 从 checkpoint 恢复训练: ${RESUME_CHECKPOINT}"
    
    # 将 checkpoint 复制到新的输出目录
    resume_basename=$(basename "$RESUME_CHECKPOINT")
    target_checkpoint="$OUTPUT_DIR/$resume_basename"
    
    if [ ! -d "$target_checkpoint" ]; then
        echo "📋 复制 checkpoint 到输出目录: $resume_basename"
        rsync -a --info=progress2 "$RESUME_CHECKPOINT" "$OUTPUT_DIR/"
        echo "✅ Checkpoint 复制完成"
    else
        echo "✓ Checkpoint 已存在于输出目录"
    fi
    
    # 使用相对路径（只传 basename）
    RESUME_ARG="--resume_from_checkpoint=$resume_basename"
else
    echo "🆕 从 Base Model 开始全参数微调"
fi

echo "📥 加载 Base Model: ${BASE_MODEL_PATH}"

# deepspeed --include="localhost:0,1,2,3,4,5,6,7" main.py \
deepspeed --exclude="localhost:0" main.py \
    --deepspeed="./configs/zero2.json" \
    --pretrained_model_name_or_path=$BASE_MODEL_PATH \
    --pretrained_text_encoder_name_or_path=$TEXT_ENCODER_NAME \
    --pretrained_vision_encoder_name_or_path=$VISION_ENCODER_NAME \
    --output_dir=$OUTPUT_DIR \
    --seed=${seed} \
    --train_batch_size=48 \
    --sample_batch_size=32 \
    --num_sample_batches=4 \
    --max_train_steps=200000 \
    --checkpointing_period=1000 \
    --sample_period=500 \
    --checkpoints_total_limit=40 \
    --lr_scheduler="constant" \
    --learning_rate=1e-4 \
    --mixed_precision="bf16" \
    --dataloader_num_workers=8 \
    --image_aug \
    --dataset_type="finetune" \
    --state_noise_snr=40 \
    --load_from_hdf5 \
    --report_to=wandb \
    --precomp_lang_embed \
    $RESUME_ARG
