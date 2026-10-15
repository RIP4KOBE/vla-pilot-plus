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
dataset_name="libero_10"       # 数据集: libero_10, libero_spatial, libero_object, libero_goal, libero_90
finetune_method="Full"             # 微调方法: Full (全参数微调)
model_size="1B"                    # 模型大小: 1B
seed=42                            # 随机种子（用于可复现性）

# 基础模型路径
base_model_name="libero90-ckpt65k" # 基础模型标识
BASE_MODEL_PATH="./checkpoints/rdt-finetune-1b-20251119_122234/checkpoint-65000"

# 全参数微调 checkpoint 恢复路径（从之前的 checkpoint 继续训练）
# RESUME_CHECKPOINT="./checkpoints/RDT-1B-Full-libero_spatial-from_libero90-ckpt65k-20251205_120229/checkpoint-27000"

# 训练超参数
TRAIN_BATCH_SIZE=48                # 训练批次大小
SAMPLE_BATCH_SIZE=32               # 采样批次大小
NUM_SAMPLE_BATCHES=4               # 采样批次数量
LEARNING_RATE=1e-4                 # 学习率
LR_SCHEDULER="constant"            # 学习率调度器
MAX_TRAIN_STEPS=200000             # 最大训练步数
CHECKPOINTING_PERIOD=1000          # 保存checkpoint的间隔
SAMPLE_PERIOD=500                  # 采样评估的间隔
CHECKPOINTS_TOTAL_LIMIT=40         # 保留的checkpoint数量上限
DATALOADER_NUM_WORKERS=8           # 数据加载线程数
STATE_NOISE_SNR=40                 # 状态噪声信噪比

export WANDB_PROJECT="rdt_libero_sft_${dataset_name}"

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
    # 直接使用原训练目录
    TRAINING_DIR=$(dirname "$RESUME_CHECKPOINT")
    export OUTPUT_DIR="$TRAINING_DIR"
else
    # 从头训练才创建新目录
    export OUTPUT_DIR="./checkpoints/RDT-${model_size}-${finetune_method}-${dataset_name}-from_${base_model_name}-${run_id}"
fi

#========================================================================
# 打印训练配置并请求确认
#========================================================================
echo ""
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                  🚀 RDT 全参数微调训练配置                          ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  📊 数据集与模型配置"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  数据集名称:        ${dataset_name}"
echo "  微调方法:          ${finetune_method} (全参数微调)"
echo "  模型大小:          ${model_size}"
echo "  随机种子:          ${seed}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🎯 基础模型"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  模型标识:          ${base_model_name}"
echo "  模型路径:          ${BASE_MODEL_PATH}"
if [ -n "$RESUME_CHECKPOINT" ]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  🔄 恢复训练"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  恢复模式:          是（在原目录继续训练）"
    echo "  Checkpoint:        ${RESUME_CHECKPOINT}"
else
    echo "  训练模式:          从 Base Model 开始全参数微调"
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
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║  ⚠️  请仔细检查以上配置，确认无误后输入 'yes' 继续训练            ║"
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

if [ -n "$RESUME_CHECKPOINT" ]; then
    # Resume 时追加配置
    cat >> "$OUTPUT_DIR/training_config.txt" << EOF

=====================================
恢复训练 - $(date +%Y-%m-%d_%H:%M:%S)
=====================================
从 Checkpoint:   ${RESUME_CHECKPOINT}
继续训练步数:    ${MAX_TRAIN_STEPS}
学习率:          ${LEARNING_RATE}
学习率调度:      ${LR_SCHEDULER}
=====================================
EOF
    
    # 生成恢复训练的详细日志
    cat > "$CONFIG_LOG_FILE" << EOF
╔══════════════════════════════════════════════════════════════════════╗
║               RDT 训练配置日志 - 恢复训练                           ║
╚══════════════════════════════════════════════════════════════════════╝

生成时间: $(date '+%Y-%m-%d %H:%M:%S')
运行ID:   ${run_id}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  恢复训练信息
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
恢复模式:              是
原训练目录:            $(dirname "$RESUME_CHECKPOINT")
恢复Checkpoint:        ${RESUME_CHECKPOINT}
Checkpoint存在性:      $([ -d "$RESUME_CHECKPOINT" ] && echo "✓ 存在" || echo "✗ 不存在")

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  数据集配置
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
数据集名称:            ${dataset_name}
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
文本编码器:            ${TEXT_ENCODER_NAME}
视觉编码器:            ${VISION_ENCODER_NAME}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  训练超参数
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
训练批次大小:          ${TRAIN_BATCH_SIZE}
采样批次大小:          ${SAMPLE_BATCH_SIZE}
采样批次数量:          ${NUM_SAMPLE_BATCHES}
学习率:                ${LEARNING_RATE}
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
CUDA可见设备:          ${CUDA_VISIBLE_DEVICES:-"未设置 (使用默认)"}
NCCL配置:              IB启用, Socket=${NCCL_SOCKET_IFNAME}
DeepSpeed配置:         configs/zero2.json

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  训练命令
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
$(cat << 'COMMAND'
deepspeed --exclude="localhost:0" main_sft.py \\
    --deepspeed="./configs/zero2.json" \\
    --pretrained_model_name_or_path=${BASE_MODEL_PATH} \\
    --pretrained_text_encoder_name_or_path=${TEXT_ENCODER_NAME} \\
    --pretrained_vision_encoder_name_or_path=${VISION_ENCODER_NAME} \\
    --output_dir=${OUTPUT_DIR} \\
    --seed=${seed} \\
    --dataset_name=${dataset_name} \\
    --train_batch_size=${TRAIN_BATCH_SIZE} \\
    --sample_batch_size=${SAMPLE_BATCH_SIZE} \\
    --num_sample_batches=${NUM_SAMPLE_BATCHES} \\
    --max_train_steps=${MAX_TRAIN_STEPS} \\
    --checkpointing_period=${CHECKPOINTING_PERIOD} \\
    --sample_period=${SAMPLE_PERIOD} \\
    --checkpoints_total_limit=${CHECKPOINTS_TOTAL_LIMIT} \\
    --lr_scheduler="${LR_SCHEDULER}" \\
    --learning_rate=${LEARNING_RATE} \\
    --mixed_precision="bf16" \\
    --dataloader_num_workers=${DATALOADER_NUM_WORKERS} \\
    --image_aug \\
    --dataset_type="finetune" \\
    --state_noise_snr=${STATE_NOISE_SNR} \\
    --load_from_hdf5 \\
    --report_to=wandb \\
    --precomp_lang_embed \\
    --resume_from_checkpoint=$(basename "$RESUME_CHECKPOINT")
COMMAND
)

╚══════════════════════════════════════════════════════════════════════╝
EOF
else
    # 新训练时创建配置文件
cat > "$OUTPUT_DIR/training_config.txt" << EOF
训练配置信息
=====================================
数据集:          ${dataset_name}
微调方法:        ${finetune_method}
模型大小:        ${model_size}
Base Model:      ${BASE_MODEL_PATH}
随机种子:        ${seed}
训练批次大小:    ${TRAIN_BATCH_SIZE}
采样批次大小:    ${SAMPLE_BATCH_SIZE}
采样批次数量:    ${NUM_SAMPLE_BATCHES}
学习率:          ${LEARNING_RATE}
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

    # 生成新训练的详细日志
    cat > "$CONFIG_LOG_FILE" << EOF
╔══════════════════════════════════════════════════════════════════════╗
║                  RDT 训练配置日志 - 新训练                          ║
╚══════════════════════════════════════════════════════════════════════╝

生成时间: $(date '+%Y-%m-%d %H:%M:%S')
运行ID:   ${run_id}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  数据集配置
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
数据集名称:            ${dataset_name}
数据集类型:            finetune
数据集路径:            data/datasets/${dataset_name}/
图像增强:              开启
使用HDF5:              是
预计算语言嵌入:        是

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  模型配置
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
微调方法:              ${finetune_method} (全参数微调)
模型大小:              ${model_size}
基础模型标识:          ${base_model_name}
基础模型路径:          ${BASE_MODEL_PATH}
基础模型存在性:        $([ -d "$BASE_MODEL_PATH" ] && echo "✓ 存在" || echo "✗ 不存在")
文本编码器:            ${TEXT_ENCODER_NAME}
视觉编码器:            ${VISION_ENCODER_NAME}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  训练超参数
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
训练批次大小:          ${TRAIN_BATCH_SIZE}
采样批次大小:          ${SAMPLE_BATCH_SIZE}
采样批次数量:          ${NUM_SAMPLE_BATCHES}
学习率:                ${LEARNING_RATE}
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
CUDA可见设备:          ${CUDA_VISIBLE_DEVICES:-"未设置 (使用默认)"}
NCCL配置:              IB启用, Socket=${NCCL_SOCKET_IFNAME}
DeepSpeed配置:         configs/zero2.json

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  训练命令
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
deepspeed --exclude="localhost:0" main_sft.py \\
    --deepspeed="./configs/zero2.json" \\
    --pretrained_model_name_or_path=${BASE_MODEL_PATH} \\
    --pretrained_text_encoder_name_or_path=${TEXT_ENCODER_NAME} \\
    --pretrained_vision_encoder_name_or_path=${VISION_ENCODER_NAME} \\
    --output_dir=${OUTPUT_DIR} \\
    --seed=${seed} \\
    --dataset_name=${dataset_name} \\
    --train_batch_size=${TRAIN_BATCH_SIZE} \\
    --sample_batch_size=${SAMPLE_BATCH_SIZE} \\
    --num_sample_batches=${NUM_SAMPLE_BATCHES} \\
    --max_train_steps=${MAX_TRAIN_STEPS} \\
    --checkpointing_period=${CHECKPOINTING_PERIOD} \\
    --sample_period=${SAMPLE_PERIOD} \\
    --checkpoints_total_limit=${CHECKPOINTS_TOTAL_LIMIT} \\
    --lr_scheduler="${LR_SCHEDULER}" \\
    --learning_rate=${LEARNING_RATE} \\
    --mixed_precision="bf16" \\
    --dataloader_num_workers=${DATALOADER_NUM_WORKERS} \\
    --image_aug \\
    --dataset_type="finetune" \\
    --state_noise_snr=${STATE_NOISE_SNR} \\
    --load_from_hdf5 \\
    --report_to=wandb \\
    --precomp_lang_embed

╚══════════════════════════════════════════════════════════════════════╝
EOF
fi

echo "📝 训练配置已保存:"
echo "   简要配置: $OUTPUT_DIR/training_config.txt"
echo "   详细日志: $CONFIG_LOG_FILE"
echo ""

# 构建恢复训练参数
RESUME_ARG=""
if [ -n "$RESUME_CHECKPOINT" ]; then
    # 使用相对路径（只传 basename）
    resume_basename=$(basename "$RESUME_CHECKPOINT")
    RESUME_ARG="--resume_from_checkpoint=$resume_basename"
fi

echo "🔄 开始训练..."
echo ""

# 激活 conda 环境
echo "🔧 激活 conda 环境..."
source /share_data/zhukefei/miniconda3/etc/profile.d/conda.sh
conda activate rdt
echo "✅ conda 环境已激活: $(which python)"
echo "✅ DeepSpeed 路径: $(which deepspeed)"
echo ""

# 清理Python缓存
echo "🧹 清理Python缓存..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
echo "✅ Python缓存已清理"
echo ""

# deepspeed --include="localhost:0,1,2,3,4,5,6,7" main_sft.py \
deepspeed --exclude="localhost:0" main_sft.py \
    --deepspeed="./configs/zero2.json" \
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
    --mixed_precision="bf16" \
    --dataloader_num_workers=${DATALOADER_NUM_WORKERS} \
    --image_aug \
    --dataset_type="finetune" \
    --state_noise_snr=${STATE_NOISE_SNR} \
    --load_from_hdf5 \
    --report_to=wandb \
    --precomp_lang_embed \
    $RESUME_ARG
