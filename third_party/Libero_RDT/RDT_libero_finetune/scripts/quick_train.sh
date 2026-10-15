#!/bin/bash
# ==============================================================================
# 快速训练脚本 - 简化版训练启动器
# ==============================================================================
#
# 使用方法:
#   bash scripts/quick_train.sh <dataset_name> [method]
#
# 示例:
#   bash scripts/quick_train.sh libero_spatial full    # 全参数微调
#   bash scripts/quick_train.sh libero_object lora     # LoRA 微调
#
# ==============================================================================

# 参数检查
if [ $# -lt 1 ]; then
    echo "Usage: bash scripts/quick_train.sh <dataset_name> [method]"
    echo ""
    echo "Available datasets:"
    echo "  - libero_spatial"
    echo "  - libero_object"
    echo "  - libero_goal"
    echo "  - libero_long"
    echo "  - libero_10"
    echo "  - libero_90"
    echo ""
    echo "Available methods:"
    echo "  - full (default) - 全参数微调"
    echo "  - lora          - LoRA 微调"
    exit 1
fi

DATASET_NAME=$1
METHOD=${2:-full}

echo "=========================================="
echo "🚀 RDT Quick Training"
echo "=========================================="
echo "Dataset: $DATASET_NAME"
echo "Method:  $METHOD"
echo "=========================================="
echo ""

# 根据方法选择脚本
if [ "$METHOD" == "full" ]; then
    echo "Starting full finetuning..."
    # 修改 finetune_sft.sh 中的数据集配置
    sed -i "s/dataset_name=.*/dataset_name=\"$DATASET_NAME\"/" finetune_sft.sh
    bash finetune_sft.sh
elif [ "$METHOD" == "lora" ]; then
    echo "Starting LoRA finetuning..."
    # 修改 finetune_lora_sft.sh 中的数据集配置
    sed -i "s/dataset_name=.*/dataset_name=\"$DATASET_NAME\"/" finetune_lora_sft.sh
    bash finetune_lora_sft.sh
else
    echo "Error: Unknown method '$METHOD'"
    echo "Available methods: full, lora"
    exit 1
fi

