#!/bin/bash
# ==============================================================================
# 快速评估脚本 - 简化版评估启动器
# ==============================================================================
#
# 使用方法:
#   bash scripts/quick_eval.sh <checkpoint_type> <dataset_name> [num_traj]
#
# 示例:
#   # 评估 best checkpoint
#   bash scripts/quick_eval.sh best libero_spatial 20
#   
#   # 评估指定训练目录的所有 checkpoints
#   bash scripts/quick_eval.sh training libero_spatial 5 ./checkpoints/RDT-xxx
#
# ==============================================================================

# 参数检查
if [ $# -lt 2 ]; then
    echo "Usage: bash scripts/quick_eval.sh <checkpoint_type> <dataset_name> [num_traj] [checkpoint_dir]"
    echo ""
    echo "Checkpoint types:"
    echo "  - best     - 评估 best_checkpoints 目录下的最佳模型"
    echo "  - training - 评估训练目录下的所有 checkpoints"
    echo ""
    echo "Examples:"
    echo "  bash scripts/quick_eval.sh best libero_spatial 20"
    echo "  bash scripts/quick_eval.sh training libero_spatial 5 ./checkpoints/RDT-xxx"
    exit 1
fi

CHECKPOINT_TYPE=$1
DATASET_NAME=$2
NUM_TRAJ=${3:-20}
CHECKPOINT_DIR=$4

echo "=========================================="
echo "📊 RDT Quick Evaluation"
echo "=========================================="
echo "Type:     $CHECKPOINT_TYPE"
echo "Dataset:  $DATASET_NAME"
echo "Num Traj: $NUM_TRAJ"
echo "=========================================="
echo ""

cd libero_eval

if [ "$CHECKPOINT_TYPE" == "best" ]; then
    # 评估 best checkpoint
    BEST_CKPT_DIR="../checkpoints/best_checkpoints/${DATASET_NAME}_best_ckpt"
    
    if [ ! -d "$BEST_CKPT_DIR" ]; then
        echo "Error: Best checkpoint not found at $BEST_CKPT_DIR"
        exit 1
    fi
    
    echo "Evaluating best checkpoint..."
    echo "Checkpoint: $BEST_CKPT_DIR"
    
    # 修改评估脚本配置
    sed -i "s|CHECKPOINT_DIR=.*|CHECKPOINT_DIR=\"$BEST_CKPT_DIR\"|" eval_full_checkpoints_auto.sh
    sed -i "s/DATASET_NAME=.*/DATASET_NAME=\"$DATASET_NAME\"/" eval_full_checkpoints_auto.sh
    sed -i "s/NUM_TRAJ=.*/NUM_TRAJ=$NUM_TRAJ/" eval_full_checkpoints_auto.sh
    
    bash eval_full_checkpoints_auto.sh
    
elif [ "$CHECKPOINT_TYPE" == "training" ]; then
    # 评估训练目录
    if [ -z "$CHECKPOINT_DIR" ]; then
        echo "Error: Please provide checkpoint directory for training evaluation"
        echo "Usage: bash scripts/quick_eval.sh training <dataset> <num_traj> <checkpoint_dir>"
        exit 1
    fi
    
    if [ ! -d "$CHECKPOINT_DIR" ]; then
        echo "Error: Checkpoint directory not found: $CHECKPOINT_DIR"
        exit 1
    fi
    
    echo "Evaluating training checkpoints..."
    echo "Directory: $CHECKPOINT_DIR"
    
    # 修改评估脚本配置
    sed -i "s|CHECKPOINT_DIR=.*|CHECKPOINT_DIR=\"$CHECKPOINT_DIR\"|" eval_full_checkpoints_auto.sh
    sed -i "s/DATASET_NAME=.*/DATASET_NAME=\"$DATASET_NAME\"/" eval_full_checkpoints_auto.sh
    sed -i "s/NUM_TRAJ=.*/NUM_TRAJ=$NUM_TRAJ/" eval_full_checkpoints_auto.sh
    
    bash eval_full_checkpoints_auto.sh
    
else
    echo "Error: Unknown checkpoint type '$CHECKPOINT_TYPE'"
    echo "Available types: best, training"
    exit 1
fi

cd ..
echo ""
echo "✅ Evaluation complete!"
echo "Results saved in: libero_eval/outs/"

