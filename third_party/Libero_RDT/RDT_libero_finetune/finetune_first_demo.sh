#!/bin/bash
# ============================================================================
# First Demo Only 训练脚本
# 每个任务只使用第一个demo (demo_0) 进行训练
# ============================================================================
# 
# 使用场景：
#   - 快速实验：用少量数据快速验证想法
#   - 小数据集研究：研究极小数据集下的模型表现
#   - LoRA微调：LoRA在小数据集上更不易过拟合
#
# 数据量对比 (以libero_spatial为例):
#   - 完整数据集: 10 tasks × 50 demos = 500 episodes
#   - First Demo Only: 10 tasks × 1 demo = 10 episodes
#   - 数据量减少 98%，训练速度大幅提升
#
# ============================================================================

export run_id=$(date +%Y%m%d_%H%M%S)

# 强制使用 GPU 0
export CUDA_VISIBLE_DEVICES=0

# 禁用 NCCL（单 GPU 不需要）
export NCCL_P2P_DISABLE=1
export NCCL_IB_DISABLE=1

export TEXT_ENCODER_NAME="google/t5-v1_1-xxl"
export VISION_ENCODER_NAME="google/siglip-so400m-patch14-384"
export CFLAGS="-I/usr/include"
export LDFLAGS="-L/usr/lib/x86_64-linux-gnu"

#========================================================================
# 训练配置：数据集和微调方法
#========================================================================
dataset_name="libero_goal"     # 数据集: libero_10, libero_spatial, libero_object, libero_goal, libero_90
first_demo_only=true               # 是否只使用每个任务的demo_0 (true/false)
finetune_method="LoRA"             # 微调方法: Full (全参数微调) 或 LoRA
model_size="1B"                    # 模型大小: 1B
seed=42                            # 随机种子（用于可复现性）

# 基础模型路径（object 40K checkpoint - 最佳性能点: 92% SR）
base_model_name="libero_goal-ckpt30k" # 基础模型标识
BASE_MODEL_PATH="./checkpoints/RDT-1B-Full-libero_goal-from_libero90-ckpt65k-20251221_193952/checkpoint-30000"

# 全参数微调 checkpoint 恢复路径（从之前的 checkpoint 继续训练）
# RESUME_CHECKPOINT="./checkpoints/RDT-1B-Full-libero_spatial-FirstDemo-20251216_120000/checkpoint-5000"

# 训练超参数（libero_object 1-demo 强化训练配置）
TRAIN_BATCH_SIZE=8                 # 训练批次大小（增大到8，更稳定的梯度）
SAMPLE_BATCH_SIZE=16               # 采样批次大小
NUM_SAMPLE_BATCHES=2               # 采样批次数量
LEARNING_RATE=1e-6                 # 学习率（保持低LR，避免破坏base model）
LR_WARMUP_STEPS=300                # Warmup步数（延长至300，占比7.5%）
LR_SCHEDULER="constant_with_warmup" # 学习率调度器: constant（更温和）
MAX_TRAIN_STEPS=40000               # 最大训练步数（延长至4000步，更充分学习）
CHECKPOINTING_PERIOD=1000            # 保存checkpoint的间隔（更密集监控）
SAMPLE_PERIOD=50                   # 采样评估的间隔（频繁监控防止过拟合）
CHECKPOINTS_TOTAL_LIMIT=80         # 保留的checkpoint数量上限（4000步/50=80个）
DATALOADER_NUM_WORKERS=4           # 数据加载线程数
STATE_NOISE_SNR=30                 # 状态噪声信噪比（降低噪声，提高稳定性）

# LoRA 配置（方案1: 保守型 - 平衡表达能力与稳定性）
USE_LORA=true                      # 是否使用LoRA (true/false)
LORA_RANK=16                       # LoRA rank（增加表达能力，捕获更多模式）
LORA_ALPHA=32                      # LoRA alpha（保持 alpha/rank=2 的比例）
LORA_TARGET_MODULES="cross_attn"   # LoRA目标模块（标准cross_attn，效果更好）
LORA_DROPOUT=0.1                   # LoRA dropout（降低dropout，数据太少时过强正则化有害）

export WANDB_PROJECT="rdt_libero_first_demo_${dataset_name}"

#========================================================================
# 数据集信息（预计算episodes数量）
#========================================================================
case "$dataset_name" in
    "libero_spatial")
        TOTAL_TASKS=10
        DEMOS_PER_TASK=50
        ;;
    "libero_object")
        TOTAL_TASKS=10
        DEMOS_PER_TASK=50
        ;;
    "libero_goal")
        TOTAL_TASKS=10
        DEMOS_PER_TASK=50
        ;;
    "libero_10")
        TOTAL_TASKS=10
        DEMOS_PER_TASK=50
        ;;
    "libero_90")
        TOTAL_TASKS=90
        DEMOS_PER_TASK=50
        ;;
    *)
        TOTAL_TASKS=10
        DEMOS_PER_TASK=50
        ;;
esac

if [ "$first_demo_only" = "true" ]; then
    TOTAL_EPISODES=$TOTAL_TASKS
    DATA_MODE="FirstDemoOnly"
else
    TOTAL_EPISODES=$((TOTAL_TASKS * DEMOS_PER_TASK))
    DATA_MODE="FullDataset"
fi

#========================================================================
# 生成输出目录名称
#========================================================================
if [ -n "$RESUME_CHECKPOINT" ]; then
    # 直接使用原训练目录
    TRAINING_DIR=$(dirname "$RESUME_CHECKPOINT")
    export OUTPUT_DIR="$TRAINING_DIR"
else
    # 从头训练才创建新目录
    if [ "$first_demo_only" = "true" ]; then
        export OUTPUT_DIR="./checkpoints/RDT-${model_size}-${finetune_method}-${dataset_name}-FirstDemo-from_${base_model_name}-${run_id}"
    else
        export OUTPUT_DIR="./checkpoints/RDT-${model_size}-${finetune_method}-${dataset_name}-FullDataset-from_${base_model_name}-${run_id}"
    fi
fi

#========================================================================
# 打印训练配置并请求确认
#========================================================================
echo ""
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║              🚀 RDT First Demo Only 训练配置                        ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  📊 数据集与训练模式"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  数据集名称:        ${dataset_name}"
echo "  训练模式:          ${DATA_MODE}"
if [ "$first_demo_only" = "true" ]; then
    echo "  数据选择:          每个任务仅使用 demo_0"
    echo "  总任务数:          ${TOTAL_TASKS}"
    echo "  总Episodes:        ${TOTAL_EPISODES} (每任务1个demo)"
    echo "  数据量:            ~$(echo "scale=1; $TOTAL_EPISODES * 100 / ($TOTAL_TASKS * $DEMOS_PER_TASK)" | bc)% of 完整数据集"
else
    echo "  数据选择:          使用所有demos"
    echo "  总任务数:          ${TOTAL_TASKS}"
    echo "  总Episodes:        ${TOTAL_EPISODES} (每任务${DEMOS_PER_TASK}个demos)"
    echo "  数据量:            100% of 完整数据集"
fi
echo "  微调方法:          ${finetune_method}"
if [ "$USE_LORA" = "true" ]; then
    echo "  LoRA配置:          Rank=${LORA_RANK}, Alpha=${LORA_ALPHA}"
fi
echo "  模型大小:          ${model_size}"
echo "  随机种子:          ${seed}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🎯 基础模型"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  模型标识:          ${base_model_name}"
echo "  模型路径:          ${BASE_MODEL_PATH}"
echo "  模型存在性:        $([ -d "$BASE_MODEL_PATH" ] && echo "✓ 存在" || echo "✗ 不存在")"
if [ -n "$RESUME_CHECKPOINT" ]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  🔄 恢复训练"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  恢复模式:          是（在原目录继续训练）"
    echo "  Checkpoint:        ${RESUME_CHECKPOINT}"
else
    echo "  训练模式:          从 Base Model 开始微调"
fi
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ⚙️  训练超参数"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  训练批次大小:      ${TRAIN_BATCH_SIZE}"
echo "  采样批次大小:      ${SAMPLE_BATCH_SIZE}"
echo "  采样批次数量:      ${NUM_SAMPLE_BATCHES}"
echo "  学习率:            ${LEARNING_RATE}"
echo "  学习率调度器:      ${LR_SCHEDULER}"
echo "  混合精度:          bf16"
echo "  最大训练步数:      ${MAX_TRAIN_STEPS}"
echo "  保存间隔:          ${CHECKPOINTING_PERIOD} 步"
echo "  采样间隔:          ${SAMPLE_PERIOD} 步"
echo "  数据加载线程:      ${DATALOADER_NUM_WORKERS}"
echo "  状态噪声SNR:       ${STATE_NOISE_SNR}"
echo "  Checkpoint上限:    ${CHECKPOINTS_TOTAL_LIMIT}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  📁 输出配置"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  输出目录:          ${OUTPUT_DIR}"
echo "  WandB项目:         ${WANDB_PROJECT}"
if [ -z "$RESUME_CHECKPOINT" ]; then
    echo "  运行时间戳:        ${run_id}"
fi
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🎮 GPU配置"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  训练模式:          单GPU (GPU 0)"
echo "  DeepSpeed:         不使用"
echo "  NCCL:              已禁用"
echo ""
echo "╔══════════════════════════════════════════════════════════════════════╗"
if [ "$first_demo_only" = "true" ]; then
    echo "║  ⚠️  First Demo Only模式: 仅使用${TOTAL_EPISODES}个episodes训练       ║"
    echo "║  📊 数据量仅为完整数据集的 ~2%                                       ║"
    echo "║  💡 适合快速实验，但泛化能力可能受限                                 ║"
    echo "╠══════════════════════════════════════════════════════════════════════╣"
fi
echo "║  请仔细检查以上配置，确认无误后输入 'yes' 继续训练                  ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
read -p "👉 是否继续? (yes/no): " confirm
echo ""

if [ "$confirm" != "yes" ]; then
    echo "❌ 训练已取消"
    exit 0
fi

echo "✅ 配置已确认，开始训练..."
echo "=========================================================================="

if [ ! -d "$OUTPUT_DIR" ]; then
    mkdir -p "$OUTPUT_DIR"
    echo "✅ 输出文件夹已创建: '$OUTPUT_DIR'"
else
    echo "✓ 输出文件夹已存在: '$OUTPUT_DIR'"
fi

# 创建logs目录
mkdir -p "$OUTPUT_DIR/logs"

# 生成详细的训练配置日志文件
CONFIG_LOG_FILE="$OUTPUT_DIR/logs/training_config_${run_id}.log"

# 生成训练配置文件
cat > "$OUTPUT_DIR/training_config.txt" << EOF
训练配置信息
=====================================
数据集:          ${dataset_name}
训练模式:        ${DATA_MODE}
$(if [ "$first_demo_only" = "true" ]; then
    echo "数据选择:        每个任务仅使用 demo_0"
    echo "总Episodes:      ${TOTAL_EPISODES} (${TOTAL_TASKS} tasks × 1 demo)"
else
    echo "数据选择:        使用所有demos"
    echo "总Episodes:      ${TOTAL_EPISODES} (${TOTAL_TASKS} tasks × ${DEMOS_PER_TASK} demos)"
fi)
微调方法:        ${finetune_method}
模型大小:        ${model_size}
Base Model:      ${BASE_MODEL_PATH}
随机种子:        ${seed}
训练批次大小:    ${TRAIN_BATCH_SIZE}
采样批次大小:    ${SAMPLE_BATCH_SIZE}
采样批次数量:    ${NUM_SAMPLE_BATCHES}
学习率:          ${LEARNING_RATE}
学习率Warmup:    ${LR_WARMUP_STEPS} 步
学习率调度:      ${LR_SCHEDULER}
混合精度:        bf16
最大训练步数:    ${MAX_TRAIN_STEPS}
保存周期:        ${CHECKPOINTING_PERIOD}
采样周期:        ${SAMPLE_PERIOD}
数据加载线程:    ${DATALOADER_NUM_WORKERS}
状态噪声SNR:     ${STATE_NOISE_SNR}
Checkpoint上限:  ${CHECKPOINTS_TOTAL_LIMIT}
运行时间戳:      ${run_id}
=====================================
EOF

# 生成详细日志
cat > "$CONFIG_LOG_FILE" << EOF
╔══════════════════════════════════════════════════════════════════════╗
║              RDT First Demo Only 训练配置日志                        ║
╚══════════════════════════════════════════════════════════════════════╝

生成时间: $(date '+%Y-%m-%d %H:%M:%S')
运行ID:   ${run_id}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  数据集配置
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
数据集名称:            ${dataset_name}
训练模式:              ${DATA_MODE}
First Demo Only:       $first_demo_only
总任务数:              ${TOTAL_TASKS}
总Episodes数:          ${TOTAL_EPISODES}
$(if [ "$first_demo_only" = "true" ]; then
    echo "数据量占比:            ~2% (完整数据集: $((TOTAL_TASKS * DEMOS_PER_TASK)) episodes)"
else
    echo "数据量占比:            100%"
fi)
数据集类型:            finetune
数据集路径:            data/datasets/${dataset_name}/
图像增强:              开启
使用HDF5:              是
预计算语言嵌入:        是

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  模型配置
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
微调方法:              ${finetune_method}
模型大小:              ${model_size}
基础模型标识:          ${base_model_name}
基础模型路径:          ${BASE_MODEL_PATH}
基础模型存在性:        $([ -d "$BASE_MODEL_PATH" ] && echo "✓ 存在" || echo "✗ 不存在")
文本编码器:            ${TEXT_ENCODER_NAME}
视觉编码器:            ${VISION_ENCODER_NAME}
$(if [ "$USE_LORA" = "true" ]; then
    echo "LoRA配置:              Rank=${LORA_RANK}, Alpha=${LORA_ALPHA}, Target=${LORA_TARGET_MODULES}"
fi)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  训练超参数
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
训练批次大小:          ${TRAIN_BATCH_SIZE}
采样批次大小:          ${SAMPLE_BATCH_SIZE}
采样批次数量:          ${NUM_SAMPLE_BATCHES}
学习率:                ${LEARNING_RATE}
学习率Warmup步数:      ${LR_WARMUP_STEPS}
学习率调度器:          ${LR_SCHEDULER}
混合精度训练:          bf16
最大训练步数:          ${MAX_TRAIN_STEPS}
随机种子:              ${seed}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  检查点与日志配置
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
输出目录:              ${OUTPUT_DIR}
保存间隔:              每 ${CHECKPOINTING_PERIOD} 步
采样间隔:              每 ${SAMPLE_PERIOD} 步
Checkpoint上限:        ${CHECKPOINTS_TOTAL_LIMIT}
WandB项目:             ${WANDB_PROJECT}
WandB报告:             开启

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  数据加载配置
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
数据加载线程数:        ${DATALOADER_NUM_WORKERS}
状态噪声SNR:           ${STATE_NOISE_SNR} dB

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  系统环境
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
主机名:                $(hostname)
用户:                  $(whoami)
工作目录:              $(pwd)
训练模式:              单GPU训练 (GPU 0)
CUDA可见设备:          0
NCCL配置:              已禁用（单GPU模式）
DeepSpeed:             不使用

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  预计训练信息
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
预计Epochs:            ~$((MAX_TRAIN_STEPS * TRAIN_BATCH_SIZE / TOTAL_EPISODES)) epochs
$(if [ "$first_demo_only" = "true" ]; then
    echo "注意事项:              First Demo Only模式数据量极小"
    echo "                       容易过拟合，建议使用LoRA或较强正则化"
    echo "                       泛化能力可能受限，仅适合快速实验"
fi)

╚══════════════════════════════════════════════════════════════════════╝
EOF

echo "📝 训练配置已保存:"
echo "   简要配置: $OUTPUT_DIR/training_config.txt"
echo "   详细日志: $CONFIG_LOG_FILE"
echo ""

# 构建恢复训练参数
RESUME_ARG=""
if [ -n "$RESUME_CHECKPOINT" ]; then
    resume_basename=$(basename "$RESUME_CHECKPOINT")
    RESUME_ARG="--resume_from_checkpoint=$resume_basename"
fi

# 构建LoRA参数
LORA_ARGS=""
if [ "$USE_LORA" = "true" ]; then
    LORA_ARGS="--use_lora --lora_rank=${LORA_RANK} --lora_alpha=${LORA_ALPHA} --lora_target_modules=${LORA_TARGET_MODULES} --lora_dropout=${LORA_DROPOUT}"
fi

# 构建first_demo_only参数
FIRST_DEMO_ARG=""
if [ "$first_demo_only" = "true" ]; then
    FIRST_DEMO_ARG="--first_demo_only"
fi

echo "🔄 开始训练..."
echo ""

# 激活 conda 环境
echo "🔧 激活 conda 环境..."
source /share_data/zhukefei/miniconda3/etc/profile.d/conda.sh
conda activate rdt
echo "✅ conda 环境已激活: $(which python)"
echo ""

# 清理Python缓存
echo "🧹 清理Python缓存..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
echo "✅ Python缓存已清理"
echo ""

# 确认 GPU 设置
echo "🎮 使用 GPU: $(echo $CUDA_VISIBLE_DEVICES)"
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader | head -1
echo ""

# 单GPU训练（不使用 deepspeed）
python main_sft.py \
    --pretrained_model_name_or_path=$BASE_MODEL_PATH \
    --pretrained_text_encoder_name_or_path=$TEXT_ENCODER_NAME \
    --pretrained_vision_encoder_name_or_path=$VISION_ENCODER_NAME \
    --output_dir=$OUTPUT_DIR \
    --seed=${seed} \
    --dataset_name=${dataset_name} \
    --train_batch_size=${TRAIN_BATCH_SIZE} \
    --sample_batch_size=${SAMPLE_BATCH_SIZE} \
    --num_sample_batches=${NUM_SAMPLE_BATCHES} \
    --max_train_steps=${MAX_TRAIN_STEPS} \
    --checkpointing_period=${CHECKPOINTING_PERIOD} \
    --sample_period=${SAMPLE_PERIOD} \
    --checkpoints_total_limit=${CHECKPOINTS_TOTAL_LIMIT} \
    --lr_scheduler="${LR_SCHEDULER}" \
    --learning_rate=${LEARNING_RATE} \
    --lr_warmup_steps=${LR_WARMUP_STEPS} \
    --mixed_precision="bf16" \
    --dataloader_num_workers=${DATALOADER_NUM_WORKERS} \
    --image_aug \
    --dataset_type="finetune" \
    --state_noise_snr=${STATE_NOISE_SNR} \
    --load_from_hdf5 \
    --report_to=wandb \
    --precomp_lang_embed \
    $FIRST_DEMO_ARG \
    $LORA_ARGS \
    $RESUME_ARG

echo ""
echo "=========================================================================="
echo "✅ 训练完成！"
echo "=========================================================================="
echo ""
echo "📁 Checkpoints 保存在: ${OUTPUT_DIR}"
echo "📊 查看详细配置: ${CONFIG_LOG_FILE}"
echo ""
if [ "$first_demo_only" = "true" ]; then
    echo "💡 First Demo Only 模式提示:"
    echo "   • 数据量极小 (${TOTAL_EPISODES} episodes)"
    echo "   • 容易过拟合，注意监控验证集性能"
    echo "   • 建议配合LoRA使用以提高泛化能力"
    echo "   • 用于快速实验验证想法"
fi
echo "=========================================================================="

