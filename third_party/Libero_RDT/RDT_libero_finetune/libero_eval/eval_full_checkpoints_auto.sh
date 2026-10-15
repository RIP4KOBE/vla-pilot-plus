#!/bin/bash
# ============================================================================
# 通用 Full 微调 Checkpoints 自动评估脚本
# 支持任意数据集和checkpoint目录
# ============================================================================
#
# 使用方法:
#   1. 修改下方的 CHECKPOINT_DIR 和 DATASET_NAME
#   2. 运行: bash eval_full_checkpoints_auto.sh
#
# ============================================================================

# ============================================================================
# 🎯 配置区域 - 只需要修改这两个变量！
# ============================================================================

# Checkpoint 目录（修改这里）
# CHECKPOINT_DIR="./checkpoints/RDT-1B-Full-libero_object-from_libero90-ckpt65k-20251217_002639"
# CHECKPOINT_DIR="./checkpoints/RDT-1B-Full-libero_spatial-from_libero90-ckpt65k-20251205_120229"
CHECKPOINT_DIR="./checkpoints/RDT-1B-Full-libero_10-from_libero90-ckpt65k-20251228_190942"

# CHECKPOINT_DIR="./checkpoints/RDT-1B-Full-libero_goal-from_libero90-ckpt65k-20251221_193952"
# CHECKPOINT_DIR="./checkpoints/RDT-1B-LoRA-libero_spatial-FirstDemo-from_libero_spatial-ckpt5k-20251224_184813"
# 评估数据集（修改这里）
DATASET_NAME="libero_10"

# ============================================================================
# 高级配置（可选修改）
# ============================================================================

# 评估配置
NUM_TRAJ=5                # 每任务的轨迹数
SEED=20241201             # 随机种子
CHECKPOINT_INTERVAL=1000  # checkpoint间隔（例如1000表示评估1000,2000,3000...）
START_STEP=20000           # 开始评估的步数（设置为0表示评估所有）
END_STEP=999999           # 结束评估的步数（设置为999999表示无上限）

# GPU配置
export CUDA_VISIBLE_DEVICES=0

# ============================================================================
# 环境配置（一般不需要修改）
# ============================================================================

# 激活 conda 环境
echo "🔧 激活 conda 环境..."
source /share_data/zhukefei/miniconda3/etc/profile.d/conda.sh
conda activate rdt_libero_eval
echo "✅ conda 环境已激活: $(which python)"
echo ""

# LIBERO 数据集路径
export LIBERO_DATASET_PATH="/home/zhukefei/chensiqi/LIBERO/.libero"

# MuJoCo 渲染配置
export MUJOCO_GL=egl
export PYOPENGL_PLATFORM=egl
export EGL_DEVICE_ID=0

# ============================================================================
# 自动生成输出目录
# ============================================================================

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
CHECKPOINT_BASENAME=$(basename "$CHECKPOINT_DIR")
OUTPUT_BASE_DIR="outs/eef_trajectories/${DATASET_NAME}"
EVAL_DIR="${OUTPUT_BASE_DIR}/${CHECKPOINT_BASENAME}_Eval_${TIMESTAMP}"
METRICS_DIR="outs/metrics/${CHECKPOINT_BASENAME}_eval_${TIMESTAMP}"

mkdir -p "$EVAL_DIR"
mkdir -p "$METRICS_DIR"

# ============================================================================
# 打印配置信息
# ============================================================================

echo "╔═══════════════════════════════════════════════════════════════════════╗"
echo "║           Full 微调 Checkpoints 自动评估                             ║"
echo "╚═══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "📦 Checkpoint 目录:  $CHECKPOINT_DIR"
echo "📊 评估数据集:       $DATASET_NAME"
echo "🎯 评估轨迹数:       $NUM_TRAJ"
echo "🌱 随机种子:         $SEED"
echo "🎮 使用GPU:          $(echo $CUDA_VISIBLE_DEVICES | cut -d',' -f1)"
echo "📏 Checkpoint间隔:   每 $CHECKPOINT_INTERVAL 步"
echo "📍 评估范围:         $START_STEP - $END_STEP"
echo ""
echo "📁 输出目录:         $EVAL_DIR"
echo "📈 指标目录:         $METRICS_DIR"
echo "⏰ 时间戳:           $TIMESTAMP"
echo ""
echo "════════════════════════════════════════════════════════════════════════"

# ============================================================================
# 检查 Checkpoint 目录
# ============================================================================

echo ""
echo "🔍 检查 Checkpoint 目录..."

if [ ! -d "$CHECKPOINT_DIR" ]; then
    echo "❌ 错误: Checkpoint 目录不存在!"
    echo "   路径: $CHECKPOINT_DIR"
    exit 1
fi
echo "✅ Checkpoint 目录存在"

# ============================================================================
# 检测数据集任务数
# ============================================================================

echo ""
echo "🔍 检测数据集任务数..."

case "$DATASET_NAME" in
    "libero_spatial"|"libero_object"|"libero_goal"|"libero_10")
        NUM_TASKS=10
        ;;
    "libero_90")
        NUM_TASKS=90
        ;;
    *)
        echo "⚠️  未知数据集，默认设置为10个任务"
        NUM_TASKS=10
        ;;
esac

echo "✅ 数据集 $DATASET_NAME 包含 $NUM_TASKS 个任务"

# ============================================================================
# 收集 Checkpoints
# ============================================================================

echo ""
echo "🔍 扫描可用的 checkpoints..."

ALL_CHECKPOINTS=()
for ckpt_dir in "$CHECKPOINT_DIR"/checkpoint-*; do
    if [ -d "$ckpt_dir" ]; then
        ckpt_name=$(basename "$ckpt_dir")
        # 提取步数
        step_str=$(echo "$ckpt_name" | sed 's/checkpoint-//' | cut -d'-' -f1)
        
        # 验证步数是否为数字
        if [[ "$step_str" =~ ^[0-9]+$ ]]; then
            step=$step_str
            
            # 检查是否在评估范围内
            if [ "$step" -ge "$START_STEP" ] && [ "$step" -le "$END_STEP" ]; then
                # 检查是否符合间隔要求
                if [ $((step % CHECKPOINT_INTERVAL)) -eq 0 ]; then
                    ALL_CHECKPOINTS+=("$ckpt_name|$ckpt_dir|$step")
                    echo "  ✓ $ckpt_name (step $step)"
                fi
            fi
        fi
    fi
done

# 按步数排序
IFS=$'\n' ALL_CHECKPOINTS=($(sort -t'|' -k3 -n <<<"${ALL_CHECKPOINTS[*]}"))
unset IFS

# 检查是否找到checkpoints
if [ ${#ALL_CHECKPOINTS[@]} -eq 0 ]; then
    echo ""
    echo "❌ 错误: 未找到符合条件的 checkpoints!"
    echo "   检查目录: $CHECKPOINT_DIR"
    echo "   评估范围: $START_STEP - $END_STEP"
    echo "   间隔要求: 每 $CHECKPOINT_INTERVAL 步"
    exit 1
fi

echo ""
echo "✅ 找到 ${#ALL_CHECKPOINTS[@]} 个 checkpoints 待评估"
echo ""

# ============================================================================
# 评估所有 Checkpoints
# ============================================================================

# 统计变量
TOTAL_CKPTS=${#ALL_CHECKPOINTS[@]}
COMPLETED_CKPTS=0
SKIPPED_CKPTS=0
FAILED_CKPTS=0
FAILED_LIST=()

echo "════════════════════════════════════════════════════════════════════════"
echo "🚀 开始评估 checkpoints..."
echo "════════════════════════════════════════════════════════════════════════"
echo ""

START_TIME=$(date +%s)

for ckpt_info in "${ALL_CHECKPOINTS[@]}"; do
    # 解析 checkpoint 信息
    IFS='|' read -r ckpt_name ckpt_path step <<< "$ckpt_info"
    
    echo "────────────────────────────────────────────────────────────────────────"
    echo "📍 评估 $ckpt_name ($((COMPLETED_CKPTS + SKIPPED_CKPTS + 1))/$TOTAL_CKPTS)"
    echo "────────────────────────────────────────────────────────────────────────"
    
    # 检查是否已经评估过（所有任务的结果都存在）
    ALL_TASKS_DONE=true
    for task_id in $(seq 0 $((NUM_TASKS - 1))); do
        # 查找该任务的JSON文件
        json_file=$(find "$EVAL_DIR/$ckpt_name" -name "task${task_id}_eef_trajectories.json" 2>/dev/null | head -1)
        if [ ! -f "$json_file" ]; then
            ALL_TASKS_DONE=false
            break
        fi
    done
    
    if [ "$ALL_TASKS_DONE" = true ]; then
        echo "⏭️  跳过 $ckpt_name (已评估所有 $NUM_TASKS 个任务)"
        SKIPPED_CKPTS=$((SKIPPED_CKPTS + 1))
        echo ""
        continue
    fi
    
    # 创建任务列表
    TASK_IDS=($(seq 0 $((NUM_TASKS - 1))))
    
    # 评估所有任务
    echo "🎯 评估 $NUM_TASKS 个任务..."
    echo "   Checkpoint: $ckpt_name"
    TASK_SUCCESS=true
    
    for task_id in "${TASK_IDS[@]}"; do
        # 检查是否已经评估过这个任务
        json_file=$(find "$EVAL_DIR/$ckpt_name" -name "task${task_id}_eef_trajectories.json" 2>/dev/null | head -1)
        if [ -f "$json_file" ]; then
            echo "  ⏭️  Task $task_id 已评估，跳过"
            continue
        fi
        
        echo "  🔄 评估 Task $task_id..."
        
        # 运行评估
        python libero_eval/libero_rdt_eval_with_eef_tracking.py \
            --pretrained-path "$ckpt_path" \
            --config libero_eval/config/eval_config_with_eef.yaml \
            --num-traj $NUM_TRAJ \
            --task-ids $task_id \
            --eef-save-dir "$EVAL_DIR/${ckpt_name}" \
            --seed $SEED \
            --dataset-name $DATASET_NAME \
            > /dev/null 2>&1
        
        if [ $? -eq 0 ]; then
            echo "  ✅ Task $task_id 评估成功"
        else
            echo "  ❌ Task $task_id 评估失败"
            TASK_SUCCESS=false
        fi
    done
    
    if [ "$TASK_SUCCESS" = true ]; then
        COMPLETED_CKPTS=$((COMPLETED_CKPTS + 1))
        echo "✅ $ckpt_name 评估完成"
        
        # ====================================================================
        # 生成该 checkpoint 的成功率统计
        # ====================================================================
        echo "📊 生成成功率统计..."
        
        CKPT_OUTPUT_DIR="$EVAL_DIR/${ckpt_name}"
        CKPT_SUMMARY_FILE="$CKPT_OUTPUT_DIR/success_rate_summary.txt"
        CKPT_CSV_FILE="$CKPT_OUTPUT_DIR/success_rate_details.csv"
        
        # 初始化统计变量
        TOTAL_SUCCESS=0
        TOTAL_TRIALS=0
        
        # 创建CSV header
        echo "Task_ID,Task_Success,Task_Total,Task_Success_Rate" > "$CKPT_CSV_FILE"
        
        # 分析每个任务的JSON文件
        for task_id in $(seq 0 $((NUM_TASKS - 1))); do
            JSON_FILE=$(find "$CKPT_OUTPUT_DIR" -name "task${task_id}_eef_trajectories.json" 2>/dev/null | head -1)
            
            if [ -f "$JSON_FILE" ]; then
                TASK_STATS=$(python3 -c "
import json
try:
    with open('$JSON_FILE', 'r') as f:
        data = json.load(f)
    success_rate = data.get('success_rate', 0)
    num_success = data.get('num_success', 0)
    num_traj = data.get('num_trajectories', 0)
    print(f'{num_success},{num_traj},{success_rate:.2f}')
except:
    print('0,0,0.00')
" 2>/dev/null)
                
                if [ -n "$TASK_STATS" ]; then
                    IFS=',' read -r task_success task_total task_rate <<< "$TASK_STATS"
                    echo "$task_id,$task_success,$task_total,$task_rate" >> "$CKPT_CSV_FILE"
                    TOTAL_SUCCESS=$((TOTAL_SUCCESS + task_success))
                    TOTAL_TRIALS=$((TOTAL_TRIALS + task_total))
                fi
            fi
        done
        
        # 计算总体成功率
        if [ $TOTAL_TRIALS -gt 0 ]; then
            AVG_SUCCESS_RATE=$(echo "scale=2; $TOTAL_SUCCESS * 100 / $TOTAL_TRIALS" | bc)
        else
            AVG_SUCCESS_RATE="0.00"
        fi
        
        # 生成汇总文件
        cat > "$CKPT_SUMMARY_FILE" << EOF
╔═══════════════════════════════════════════════════════════════════════╗
║           $ckpt_name 成功率统计                    
╚═══════════════════════════════════════════════════════════════════════╝

评估时间:     $(date '+%Y-%m-%d %H:%M:%S')
模型类型:     Full 微调
Checkpoint:   $ckpt_name
训练步数:     $step
数据集:       $DATASET_NAME
轨迹数/任务:  $NUM_TRAJ
随机种子:     $SEED

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  整体性能
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
总成功率:     ${AVG_SUCCESS_RATE}%
总成功数:     ${TOTAL_SUCCESS}/${TOTAL_TRIALS}
评估任务数:   $NUM_TASKS

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  逐任务成功率
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EOF
        
        # 添加每个任务的详情
        while IFS=',' read -r task_id task_success task_total task_rate; do
            if [ "$task_id" != "Task_ID" ]; then
                printf "Task %2d:       %6.1f%%  (%d/%d)\n" "$task_id" "$task_rate" "$task_success" "$task_total" >> "$CKPT_SUMMARY_FILE"
            fi
        done < "$CKPT_CSV_FILE"
        
        cat >> "$CKPT_SUMMARY_FILE" << EOF

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  文件位置
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
详细CSV:      $CKPT_CSV_FILE
轨迹JSON:     $CKPT_OUTPUT_DIR/task*_eef_trajectories.json
可视化:       $CKPT_OUTPUT_DIR/visualizations/

╚═══════════════════════════════════════════════════════════════════════╝
EOF
        
        echo "  ✅ 成功率统计已保存"
        echo "  📊 总体成功率: ${AVG_SUCCESS_RATE}%"
        
    else
        FAILED_CKPTS=$((FAILED_CKPTS + 1))
        FAILED_LIST+=("$ckpt_name")
        echo "❌ $ckpt_name 评估部分失败"
    fi
    echo ""
done

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
ELAPSED_MIN=$((ELAPSED / 60))
ELAPSED_SEC=$((ELAPSED % 60))

# ============================================================================
# 生成全局汇总统计
# ============================================================================

echo "📊 生成全局汇总统计..."

GLOBAL_SUMMARY_FILE="$EVAL_DIR/all_checkpoints_summary.csv"
GLOBAL_REPORT_FILE="$EVAL_DIR/evaluation_report.txt"

# 创建全局CSV header
echo "Checkpoint,Step,Success_Rate,Success_Count,Total_Trials,Num_Tasks" > "$GLOBAL_SUMMARY_FILE"

# 收集所有checkpoint的统计数据
declare -A CKPT_STATS

for ckpt_info in "${ALL_CHECKPOINTS[@]}"; do
    IFS='|' read -r ckpt_name ckpt_path step <<< "$ckpt_info"
    
    CKPT_CSV_FILE="$EVAL_DIR/${ckpt_name}/success_rate_details.csv"
    
    if [ -f "$CKPT_CSV_FILE" ]; then
        total_success=0
        total_trials=0
        num_tasks=0
        
        while IFS=',' read -r task_id task_success task_total task_rate; do
            if [ "$task_id" != "Task_ID" ]; then
                total_success=$((total_success + task_success))
                total_trials=$((total_trials + task_total))
                num_tasks=$((num_tasks + 1))
            fi
        done < "$CKPT_CSV_FILE"
        
        if [ $total_trials -gt 0 ]; then
            success_rate=$(echo "scale=4; $total_success / $total_trials" | bc)
            echo "$ckpt_name,$step,$success_rate,$total_success,$total_trials,$num_tasks" >> "$GLOBAL_SUMMARY_FILE"
            CKPT_STATS[$step]="$success_rate|$total_success|$total_trials"
        fi
    fi
done

# 生成全局报告
cat > "$GLOBAL_REPORT_FILE" << EOF
╔═══════════════════════════════════════════════════════════════════════╗
║           Full 微调全局评估报告                    
╚═══════════════════════════════════════════════════════════════════════╝

评估完成时间: $(date '+%Y-%m-%d %H:%M:%S')
评估总用时:   ${ELAPSED_MIN}分${ELAPSED_SEC}秒

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  评估配置
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
模型类型:         Full 微调
Checkpoint目录:   $(basename $CHECKPOINT_DIR)
数据集:           $DATASET_NAME
任务数:           $NUM_TASKS
轨迹数/任务:      $NUM_TRAJ
随机种子:         $SEED
评估间隔:         每 $CHECKPOINT_INTERVAL 步

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  评估统计
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
总checkpoints:    $TOTAL_CKPTS
成功评估:         $COMPLETED_CKPTS
跳过:             $SKIPPED_CKPTS
失败:             $FAILED_CKPTS

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  各Checkpoint成功率汇总
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step      Success Rate    Success/Total
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EOF

# 按步数排序输出
for step in $(echo "${!CKPT_STATS[@]}" | tr ' ' '\n' | sort -n); do
    IFS='|' read -r rate success total <<< "${CKPT_STATS[$step]}"
    rate_pct=$(echo "scale=1; $rate * 100" | bc)
    printf "%-8s  %6s%%        %d/%d\n" "$step" "$rate_pct" "$success" "$total" >> "$GLOBAL_REPORT_FILE"
done

# 找出最佳checkpoint
BEST_STEP=""
BEST_RATE=0
for step in "${!CKPT_STATS[@]}"; do
    IFS='|' read -r rate success total <<< "${CKPT_STATS[$step]}"
    if (( $(echo "$rate > $BEST_RATE" | bc -l) )); then
        BEST_RATE=$rate
        BEST_STEP=$step
    fi
done

if [ -n "$BEST_STEP" ]; then
    IFS='|' read -r best_rate best_success best_total <<< "${CKPT_STATS[$BEST_STEP]}"
    best_rate_pct=$(echo "scale=1; $best_rate * 100" | bc)
    
    cat >> "$GLOBAL_REPORT_FILE" << EOF

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🏆 最佳 Checkpoint
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Checkpoint:       checkpoint-${BEST_STEP}
训练步数:         ${BEST_STEP}
成功率:           ${best_rate_pct}%
成功/总数:        ${best_success}/${best_total}

详细信息:         $EVAL_DIR/checkpoint-${BEST_STEP}/success_rate_summary.txt
EOF
fi

cat >> "$GLOBAL_REPORT_FILE" << EOF

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📁 文件位置
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
全局汇总CSV:      $GLOBAL_SUMMARY_FILE
全局报告:         $GLOBAL_REPORT_FILE
各checkpoint详情: $EVAL_DIR/checkpoint-*/success_rate_summary.txt

╚═══════════════════════════════════════════════════════════════════════╝
EOF

echo "✅ 全局汇总已生成"
echo ""

# ============================================================================
# 生成汇总报告
# ============================================================================

echo "════════════════════════════════════════════════════════════════════════"
echo "📊 评估汇总"
echo "════════════════════════════════════════════════════════════════════════"
echo ""
echo "数据集:       $DATASET_NAME"
echo "总计:         $TOTAL_CKPTS 个 checkpoints"
echo "完成:         $COMPLETED_CKPTS 个 ✅"
echo "跳过:         $SKIPPED_CKPTS 个 ⏭️"
echo "失败:         $FAILED_CKPTS 个 ❌"
echo ""
echo "用时:         ${ELAPSED_MIN}分${ELAPSED_SEC}秒"
echo ""

if [ ${#FAILED_LIST[@]} -gt 0 ]; then
    echo "失败列表:"
    for failed in "${FAILED_LIST[@]}"; do
        echo "  - $failed"
    done
    echo ""
fi

if [ -n "$BEST_STEP" ]; then
    echo "🏆 最佳Checkpoint: checkpoint-${BEST_STEP} (${best_rate_pct}%)"
    echo ""
fi

echo "════════════════════════════════════════════════════════════════════════"
echo "📁 结果保存位置:"
echo "   轨迹数据:   $EVAL_DIR"
echo "   评估指标:   $METRICS_DIR"
echo "   全局汇总:   $GLOBAL_SUMMARY_FILE"
echo "   全局报告:   $GLOBAL_REPORT_FILE"
echo "════════════════════════════════════════════════════════════════════════"
echo ""
echo "💡 查看结果:"
echo "   cat $GLOBAL_REPORT_FILE"
if [ -n "$BEST_STEP" ]; then
    echo "   cat $EVAL_DIR/checkpoint-${BEST_STEP}/success_rate_summary.txt"
fi
echo ""
echo "✅ Full 微调评估完成！"
echo ""
