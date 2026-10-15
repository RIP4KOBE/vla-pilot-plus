#!/bin/bash
# ==============================================================================
# 评估所有 Best Checkpoints 脚本
# 自动评估 best_checkpoints 目录下所有数据集的最佳模型
# ==============================================================================

NUM_TRAJ=${1:-20}  # 默认每任务 20 条轨迹
SEED=42

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║           评估所有 Best Checkpoints                                  ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "配置:"
echo "  - 每任务轨迹数: $NUM_TRAJ"
echo "  - 随机种子: $SEED"
echo ""
echo "将评估以下数据集:"
echo "  1. LIBERO-Spatial"
echo "  2. LIBERO-Object"
echo "  3. LIBERO-Goal"
echo "  4. LIBERO-Long"
echo ""
read -p "按 Enter 继续，或 Ctrl+C 取消..."
echo ""

# 定义数据集列表
DATASETS=(
    "libero_spatial"
    "libero_object"
    "libero_goal"
    "libero_long"
)

# 激活评估环境
echo "🔧 激活 conda 环境..."
source /share_data/zhukefei/miniconda3/etc/profile.d/conda.sh
conda activate rdt_libero_eval
echo "✅ conda 环境已激活"
echo ""

# 设置环境变量
export LIBERO_DATASET_PATH="/home/zhukefei/chensiqi/LIBERO/.libero"
export MUJOCO_GL=egl
export PYOPENGL_PLATFORM=egl
export EGL_DEVICE_ID=0
export CUDA_VISIBLE_DEVICES=0

# 创建汇总结果目录
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SUMMARY_DIR="libero_eval/outs/all_best_eval_$TIMESTAMP"
mkdir -p "$SUMMARY_DIR"

# 循环评估每个数据集
for dataset in "${DATASETS[@]}"; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 评估: $dataset"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    CHECKPOINT_DIR="./checkpoints/best_checkpoints/${dataset}_best_ckpt"
    
    if [ ! -d "$CHECKPOINT_DIR" ]; then
        echo "⚠️  警告: Checkpoint 不存在: $CHECKPOINT_DIR"
        echo "跳过此数据集..."
        echo ""
        continue
    fi
    
    # 查找实际的 checkpoint 路径
    ACTUAL_CKPT=$(find "$CHECKPOINT_DIR" -name "${dataset}_best_ckpt" -type d | head -1)
    
    if [ -z "$ACTUAL_CKPT" ]; then
        echo "⚠️  警告: 找不到 checkpoint 文件"
        echo "跳过此数据集..."
        echo ""
        continue
    fi
    
    echo "Checkpoint: $ACTUAL_CKPT"
    echo ""
    
    # 运行评估
    cd libero_eval
    python libero_rdt_eval_with_eef_tracking.py \
        --checkpoint_path "$ACTUAL_CKPT" \
        --dataset_name "$dataset" \
        --num_traj "$NUM_TRAJ" \
        --seed "$SEED" \
        --output_dir "../$SUMMARY_DIR/${dataset}_results" \
        2>&1 | tee "../$SUMMARY_DIR/${dataset}_eval.log"
    
    cd ..
    
    # 复制结果到汇总目录
    if [ -f "libero_eval/outs/metrics/latest_results.csv" ]; then
        cp "libero_eval/outs/metrics/latest_results.csv" "$SUMMARY_DIR/${dataset}_metrics.csv"
    fi
    
    echo ""
    echo "✅ $dataset 评估完成"
    echo ""
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 所有评估完成！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "结果保存在: $SUMMARY_DIR/"
echo ""

# 生成汇总报告
echo "生成汇总报告..."
cat > "$SUMMARY_DIR/SUMMARY.md" << EOF
# Best Checkpoints 评估汇总

**评估时间**: $(date '+%Y-%m-%d %H:%M:%S')
**轨迹数**: $NUM_TRAJ 条/任务
**随机种子**: $SEED

## 评估结果

| 数据集 | 平均成功率 | 结果文件 |
|--------|-----------|----------|
EOF

# 添加各数据集结果到汇总
for dataset in "${DATASETS[@]}"; do
    if [ -f "$SUMMARY_DIR/${dataset}_metrics.csv" ]; then
        # 从 CSV 提取平均成功率（简化版，实际需要解析 CSV）
        echo "| $dataset | 见详细结果 | ${dataset}_metrics.csv |" >> "$SUMMARY_DIR/SUMMARY.md"
    else
        echo "| $dataset | 评估失败 | - |" >> "$SUMMARY_DIR/SUMMARY.md"
    fi
done

cat >> "$SUMMARY_DIR/SUMMARY.md" << EOF

## 详细结果

各数据集的详细评估结果请查看对应的 CSV 文件和日志文件。

## 文件说明

- \`{dataset}_metrics.csv\` - 各任务的成功率指标
- \`{dataset}_eval.log\` - 完整的评估日志
- \`{dataset}_results/\` - 末端轨迹和视频（如果启用）

EOF

cat "$SUMMARY_DIR/SUMMARY.md"
echo ""
echo "汇总报告已保存: $SUMMARY_DIR/SUMMARY.md"

