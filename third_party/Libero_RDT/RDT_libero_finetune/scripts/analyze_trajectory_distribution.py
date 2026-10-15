#!/usr/bin/env python3
"""
完整分析不同微调方法的轨迹分布
对比: Basemodel, LoRA demo0 SFT, Full SFT demo0 (1eps vs 3eps), 训练数据
"""

import json
import os
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 数据路径
PATHS = {
    'basemodel': '/home/zhukefei/chensiqi/RDT_libero_finetune/outs/eef_trajectories/libero_spatial/20251205_003837_checkpoint-65000_seed20241201_eps1',
    'lora_demo0_4k_3eps': '/home/zhukefei/chensiqi/RDT_libero_finetune/outs/eef_trajectories/libero_spatial/20251205_160255_checkpoint-4000_seed20241201_eps3',
    'full_demo0_4k_3eps': '/home/zhukefei/chensiqi/RDT_libero_finetune/outs/eef_trajectories/libero_spatial/20251205_124936_checkpoint-4000_seed20241201_eps3',
    'full_all_2k_3eps': '/home/zhukefei/chensiqi/RDT_libero_finetune/outs/eef_trajectories/libero_spatial/20251205_200626_checkpoint-2000_seed20241201_eps3',
    'train_data': '/home/zhukefei/chensiqi/RDT_libero_finetune/outs/dataset_eef_trajectories/libero_spatial/20251205_122311',
}

def load_eval_trajectories(base_path):
    """加载评估轨迹数据"""
    trajectories = {}
    for task_id in range(10):
        file_path = os.path.join(base_path, f'task{task_id}_eef_trajectories.json')
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
                trajectories[task_id] = {
                    'task_name': data['task_name'],
                    'instruction': data['instruction'],
                    'success_rate': data['success_rate'],
                    'num_success': data.get('num_success', int(data['success_rate'] > 0)),
                    'num_trajectories': len(data['trajectories']),
                    'trajectories': data['trajectories'],
                    'success_flags': data.get('success_flags', [])
                }
    return trajectories

def load_train_trajectories(base_path):
    """加载训练数据轨迹"""
    trajectories = {}
    for task_id in range(10):
        file_path = os.path.join(base_path, f'task{task_id:02d}_eef_trajectories.json')
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
                # 训练数据格式不同
                all_trajs = []
                for demo in data.get('demos', []):
                    traj = []
                    for step in demo['trajectory']:
                        traj.append({
                            'step': step['step'],
                            'pos': step['pos']
                        })
                    all_trajs.append(traj)
                trajectories[task_id] = {
                    'task_name': data['task_name'],
                    'instruction': data['instruction'],
                    'num_demos': data['num_demos'],
                    'trajectories': all_trajs
                }
    return trajectories

def extract_positions(trajectories, is_train=False):
    """提取所有位置点"""
    all_positions = []
    task_positions = {}
    
    for task_id, data in trajectories.items():
        task_pos = []
        for traj in data['trajectories']:
            for step in traj:
                pos = step['pos']
                all_positions.append(pos)
                task_pos.append(pos)
        task_positions[task_id] = np.array(task_pos)
    
    return np.array(all_positions), task_positions

def compute_statistics(positions):
    """计算统计量"""
    if len(positions) == 0:
        return {}
    
    return {
        'X': {
            'min': float(np.min(positions[:, 0])),
            'max': float(np.max(positions[:, 0])),
            'mean': float(np.mean(positions[:, 0])),
            'std': float(np.std(positions[:, 0])),
            'range': float(np.max(positions[:, 0]) - np.min(positions[:, 0]))
        },
        'Y': {
            'min': float(np.min(positions[:, 1])),
            'max': float(np.max(positions[:, 1])),
            'mean': float(np.mean(positions[:, 1])),
            'std': float(np.std(positions[:, 1])),
            'range': float(np.max(positions[:, 1]) - np.min(positions[:, 1]))
        },
        'Z': {
            'min': float(np.min(positions[:, 2])),
            'max': float(np.max(positions[:, 2])),
            'mean': float(np.mean(positions[:, 2])),
            'std': float(np.std(positions[:, 2])),
            'range': float(np.max(positions[:, 2]) - np.min(positions[:, 2]))
        },
        'total_points': len(positions)
    }

def get_end_positions(trajectories):
    """获取每条轨迹的末端位置"""
    end_positions = {}
    for task_id, data in trajectories.items():
        ends = []
        for traj in data['trajectories']:
            if traj:
                ends.append(traj[-1]['pos'])
        end_positions[task_id] = np.array(ends) if ends else np.array([]).reshape(0, 3)
    return end_positions

def main():
    print("=" * 100)
    print("轨迹分布完整分析 (包含 3 episodes 评估结果)")
    print("=" * 100)
    
    # 加载所有数据
    print("\n加载数据...")
    
    data = {}
    stats = {}
    
    # 加载评估数据
    eval_models = ['basemodel', 'lora_demo0_4k_3eps', 'full_demo0_4k_3eps', 'full_all_2k_3eps']
    for name in eval_models:
        print(f"  加载 {name}...")
        trajectories = load_eval_trajectories(PATHS[name])
        positions, task_positions = extract_positions(trajectories)
        end_positions = get_end_positions(trajectories)
        data[name] = {
            'trajectories': trajectories,
            'positions': positions,
            'task_positions': task_positions,
            'end_positions': end_positions
        }
        stats[name] = compute_statistics(positions)
    
    # 加载训练数据
    print("  加载训练数据...")
    train_trajectories = load_train_trajectories(PATHS['train_data'])
    train_positions, train_task_positions = extract_positions(train_trajectories, is_train=True)
    train_end_positions = get_end_positions(train_trajectories)
    data['train_data'] = {
        'trajectories': train_trajectories,
        'positions': train_positions,
        'task_positions': train_task_positions,
        'end_positions': train_end_positions
    }
    stats['train_data'] = compute_statistics(train_positions)
    
    # 打印统计信息
    print("\n" + "=" * 100)
    print("整体轨迹分布统计")
    print("=" * 100)
    
    print("\n{:<25} {:>10} {:>10} {:>10} {:>10} {:>10} {:>10}".format(
        "模型", "X范围", "Y范围", "Z_min", "Z_max", "Z范围", "点数"))
    print("-" * 100)
    
    for name in ['train_data'] + eval_models:
        s = stats[name]
        print("{:<25} {:>10.3f} {:>10.3f} {:>10.3f} {:>10.3f} {:>10.3f} {:>10}".format(
            name, 
            s['X']['range'], 
            s['Y']['range'],
            s['Z']['min'],
            s['Z']['max'],
            s['Z']['range'],
            s['total_points']
        ))
    
    # 成功率统计
    print("\n" + "=" * 120)
    print("任务成功率对比 (LoRA demo0 vs Full demo0 vs Full 全部demo)")
    print("=" * 120)
    
    print("\n{:<8} {:<18} {:<18} {:<18} {:<18}".format(
        "Task", "Base(1eps)", "LoRA_demo0(3eps)", "Full_demo0(3eps)", "Full_ALL(3eps)"))
    print("-" * 120)
    
    total_success = {name: 0 for name in eval_models}
    total_episodes = {name: 0 for name in eval_models}
    
    for task_id in range(10):
        row = f"Task {task_id}"
        for name in eval_models:
            task_data = data[name]['trajectories'][task_id]
            sr = task_data['success_rate']
            num_success = task_data.get('num_success', int(sr > 0))
            num_traj = task_data.get('num_trajectories', 1)
            
            symbol = "✓" if sr > 0 else "✗"
            row += f"     {symbol} {num_success}/{num_traj}         "
            
            total_success[name] += num_success
            total_episodes[name] += num_traj
        print(row)
    
    print("-" * 100)
    print("{:<8}".format("总计"), end="")
    for name in eval_models:
        total_ep = total_episodes[name]
        total_suc = total_success[name]
        rate = total_suc / total_ep * 100 if total_ep > 0 else 0
        print(f" {total_suc}/{total_ep} ({rate:.0f}%)          ", end="")
    print()
    
    # 每个任务的 Z 轴分布对比
    print("\n" + "=" * 120)
    print("每个任务的 Z 轴最大值对比 (与训练数据对比)")
    print("=" * 120)
    
    print("\n{:<8} {:>12} {:>12} {:>15} {:>15} {:>15}".format(
        "Task", "Train_Zmax", "Base", "LoRA_demo0", "Full_demo0", "Full_ALL"))
    print("-" * 120)
    
    z_deviation = {name: [] for name in eval_models}
    
    for task_id in range(10):
        train_z_max = np.max(data['train_data']['task_positions'][task_id][:, 2])
        
        row = f"Task {task_id}  {train_z_max:>12.3f}"
        
        for name in eval_models:
            task_z_max = np.max(data[name]['task_positions'][task_id][:, 2])
            deviation = abs(task_z_max - train_z_max)
            z_deviation[name].append(deviation)
            
            # 标记超出训练范围的情况
            marker = " ⚠" if deviation > 0.05 else ""
            row += f" {task_z_max:>12.3f}{marker}"
        
        print(row)
    
    print("-" * 100)
    print("{:<8} {:>12}".format("平均偏差", ""), end="")
    for name in eval_models:
        print(f" {np.mean(z_deviation[name]):>12.3f}     ", end="")
    print()
    
    # 末端位置偏差分析
    print("\n" + "=" * 120)
    print("末端位置偏差分析 (与训练数据 demo0 的欧氏距离)")
    print("=" * 120)
    
    print("\n{:<8} {:>12} {:>15} {:>15} {:>15}".format(
        "Task", "Base", "LoRA_demo0", "Full_demo0", "Full_ALL"))
    print("-" * 120)
    
    end_distances = {name: [] for name in eval_models}
    
    for task_id in range(10):
        # 训练数据 demo0 的末端位置作为目标
        train_end = data['train_data']['end_positions'][task_id][0]
        
        row = f"Task {task_id}"
        
        for name in eval_models:
            # 计算所有 episodes 的平均末端位置
            ends = data[name]['end_positions'][task_id]
            avg_end = np.mean(ends, axis=0)
            dist = np.linalg.norm(avg_end - train_end)
            end_distances[name].append(dist)
            
            marker = " ⚠" if dist > 0.15 else ""
            row += f" {dist:>12.3f}{marker}"
        
        print(row)
    
    print("-" * 100)
    print("{:<8}".format("平均距离"), end="")
    for name in eval_models:
        print(f" {np.mean(end_distances[name]):>12.3f}     ", end="")
    print()
    
    # 3 episodes 一致性分析 - 三种方法对比
    print("\n" + "=" * 120)
    print("3 episodes 评估一致性对比: LoRA demo0 vs Full demo0 vs Full ALL")
    print("=" * 120)
    
    print("\n{:<8} {:>20} {:>20} {:>20}".format("", "--- LoRA demo0 ---", "--- Full demo0 ---", "--- Full ALL ---"))
    print("{:<8} {:>8} {:>6} {:>6} {:>8} {:>6} {:>6} {:>8} {:>6} {:>6}".format(
        "Task", "距离", "标准差", "成功", "距离", "标准差", "成功", "距离", "标准差", "成功"))
    print("-" * 120)
    
    lora_consistency = []
    full_demo0_consistency = []
    full_all_consistency = []
    
    for task_id in range(10):
        train_end = data['train_data']['end_positions'][task_id][0]
        
        # LoRA demo0 3eps
        lora_ends = data['lora_demo0_4k_3eps']['end_positions'][task_id]
        lora_success_flags = data['lora_demo0_4k_3eps']['trajectories'][task_id].get('success_flags', [])
        lora_dists = [np.linalg.norm(end - train_end) for end in lora_ends]
        lora_mean = np.mean(lora_dists)
        lora_std = np.std(lora_dists)
        lora_success = sum(lora_success_flags) if lora_success_flags else 0
        lora_consistency.append(lora_std)
        
        # Full demo0 3eps
        full_d0_ends = data['full_demo0_4k_3eps']['end_positions'][task_id]
        full_d0_success_flags = data['full_demo0_4k_3eps']['trajectories'][task_id].get('success_flags', [])
        full_d0_dists = [np.linalg.norm(end - train_end) for end in full_d0_ends]
        full_d0_mean = np.mean(full_d0_dists)
        full_d0_std = np.std(full_d0_dists)
        full_d0_success = sum(full_d0_success_flags) if full_d0_success_flags else 0
        full_demo0_consistency.append(full_d0_std)
        
        # Full ALL 3eps
        full_all_ends = data['full_all_2k_3eps']['end_positions'][task_id]
        full_all_success_flags = data['full_all_2k_3eps']['trajectories'][task_id].get('success_flags', [])
        full_all_dists = [np.linalg.norm(end - train_end) for end in full_all_ends]
        full_all_mean = np.mean(full_all_dists)
        full_all_std = np.std(full_all_dists)
        full_all_success = sum(full_all_success_flags) if full_all_success_flags else 0
        full_all_consistency.append(full_all_std)
        
        print(f"Task {task_id}  {lora_mean:>8.3f} {lora_std:>6.3f} {lora_success}/3   "
              f"{full_d0_mean:>8.3f} {full_d0_std:>6.3f} {full_d0_success}/3   "
              f"{full_all_mean:>8.3f} {full_all_std:>6.3f} {full_all_success}/3")
    
    print("-" * 120)
    print(f"{'平均':<8} {np.mean(end_distances['lora_demo0_4k_3eps']):>8.3f} {np.mean(lora_consistency):>6.3f} {'':>6} "
          f"{np.mean(end_distances['full_demo0_4k_3eps']):>8.3f} {np.mean(full_demo0_consistency):>6.3f} {'':>6} "
          f"{np.mean(end_distances['full_all_2k_3eps']):>8.3f} {np.mean(full_all_consistency):>6.3f}")
    
    # 创建可视化
    print("\n" + "=" * 100)
    print("生成可视化图表...")
    print("=" * 100)
    
    output_dir = '/home/zhukefei/chensiqi/RDT_libero_finetune/outs/trajectory_analysis'
    os.makedirs(output_dir, exist_ok=True)
    
    # 图1: XY平面分布对比 (5个模型)
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    axes = axes.flatten()
    
    names = ['train_data'] + eval_models
    titles = ['Training Data (500 demos)', 'Basemodel 65K', 'LoRA demo0 4K', 'Full demo0 4K', 'Full ALL 2K']
    colors = ['green', 'blue', 'red', 'orange', 'purple']
    
    for i, (ax, name, title, color) in enumerate(zip(axes, names, titles, colors)):
        positions = data[name]['positions']
        ax.scatter(positions[:, 0], positions[:, 1], alpha=0.3, s=1, c=color)
        ax.set_xlabel('X (m)')
        ax.set_ylabel('Y (m)')
        ax.set_title(title)
        ax.set_xlim(-0.35, 0.25)
        ax.set_ylim(-0.35, 0.5)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
    
    # 隐藏多余的子图
    if len(names) < len(axes):
        for i in range(len(names), len(axes)):
            axes[i].set_visible(False)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'xy_distribution_comparison.png'), dpi=150)
    print(f"  保存: {output_dir}/xy_distribution_comparison.png")
    
    # 图2: 末端位置偏差柱状图
    fig, ax = plt.subplots(figsize=(14, 6))
    
    x = np.arange(10)
    width = 0.2
    
    for i, (name, title, color) in enumerate(zip(eval_models, titles[1:], colors[1:])):
        dists = end_distances[name]
        ax.bar(x + i * width, dists, width, label=title, color=color, alpha=0.7)
    
    ax.set_xlabel('Task ID')
    ax.set_ylabel('End Position Distance (m)')
    ax.set_title('End Position Distance from Training Data (demo0)')
    ax.set_xticks(x + width * 1.5)
    ax.set_xticklabels([f'Task {i}' for i in range(10)])
    ax.legend()
    ax.axhline(y=0.15, color='r', linestyle='--', alpha=0.5, label='Threshold')
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'end_position_distances.png'), dpi=150)
    print(f"  保存: {output_dir}/end_position_distances.png")
    
    # 图3: 每个任务的 3D 轨迹对比 (LoRA demo0 vs Full demo0 vs Full ALL)
    fig = plt.figure(figsize=(24, 20))
    
    for task_id in range(10):
        ax = fig.add_subplot(4, 3, task_id + 1, projection='3d')
        
        # 绘制训练数据 demo0
        train_traj = data['train_data']['trajectories'][task_id]['trajectories'][0]
        train_pos = np.array([s['pos'] for s in train_traj])
        ax.plot(train_pos[:, 0], train_pos[:, 1], train_pos[:, 2], 
                'g-', linewidth=2, alpha=0.8, label='Train demo0')
        
        # 绘制 Full ALL 3eps 的第一条轨迹
        full_all_traj = data['full_all_2k_3eps']['trajectories'][task_id]['trajectories'][0]
        full_all_pos = np.array([s['pos'] for s in full_all_traj])
        ax.plot(full_all_pos[:, 0], full_all_pos[:, 1], full_all_pos[:, 2], 
                'purple', linewidth=2, alpha=0.8, label='Full ALL 2K')
        
        # 绘制 Full demo0 3eps 的第一条轨迹
        full_d0_traj = data['full_demo0_4k_3eps']['trajectories'][task_id]['trajectories'][0]
        full_d0_pos = np.array([s['pos'] for s in full_d0_traj])
        ax.plot(full_d0_pos[:, 0], full_d0_pos[:, 1], full_d0_pos[:, 2], 
                'orange', linewidth=1.5, alpha=0.7, label='Full demo0 4K')
        
        # 绘制 LoRA demo0 3eps 的第一条轨迹
        lora_traj = data['lora_demo0_4k_3eps']['trajectories'][task_id]['trajectories'][0]
        lora_pos = np.array([s['pos'] for s in lora_traj])
        ax.plot(lora_pos[:, 0], lora_pos[:, 1], lora_pos[:, 2], 
                'red', linewidth=1.5, alpha=0.7, label='LoRA demo0 4K')
        
        # 标记成功
        full_all_success = data['full_all_2k_3eps']['trajectories'][task_id]['success_rate'] > 0
        title_suffix = " ✓" if full_all_success else " ✗"
        ax.set_title(f'Task {task_id}{title_suffix}')
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        
        if task_id == 0:
            ax.legend(loc='upper right', fontsize=8)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'task_trajectory_comparison.png'), dpi=150)
    print(f"  保存: {output_dir}/task_trajectory_comparison.png")
    
    # 生成分析结论
    print("\n" + "=" * 100)
    print("分析结论")
    print("=" * 100)
    
    # 计算各模型的综合指标
    avg_z_dev = {name: np.mean(z_deviation[name]) for name in eval_models}
    avg_end_dist = {name: np.mean(end_distances[name]) for name in eval_models}
    success_rates = {name: total_success[name] / total_episodes[name] * 100 
                     for name in eval_models}
    
    # 找出最佳模型
    best_z = min(avg_z_dev, key=avg_z_dev.get)
    best_end = min(avg_end_dist, key=avg_end_dist.get)
    best_success = max(success_rates, key=success_rates.get)
    
    print(f"""
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                      libero_spatial SFT 完整分析结论 (数据量对比)                                 │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│  模型配置                    │ 成功率        │ Z偏差(m)    │ 末端距离(m)  │ 评估次数           │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│  Basemodel 65K               │ {success_rates['basemodel']:>6.1f}%      │ {avg_z_dev['basemodel']:>8.3f}   │ {avg_end_dist['basemodel']:>8.3f}     │ 10 (1eps/task)     │
│  LoRA demo0 4K (3eps)        │ {success_rates['lora_demo0_4k_3eps']:>6.1f}%      │ {avg_z_dev['lora_demo0_4k_3eps']:>8.3f}   │ {avg_end_dist['lora_demo0_4k_3eps']:>8.3f}     │ 30 (3eps/task)     │
│  Full demo0 4K (3eps)        │ {success_rates['full_demo0_4k_3eps']:>6.1f}%      │ {avg_z_dev['full_demo0_4k_3eps']:>8.3f}   │ {avg_end_dist['full_demo0_4k_3eps']:>8.3f}     │ 30 (3eps/task)     │
│  Full ALL 2K (3eps)          │ {success_rates['full_all_2k_3eps']:>6.1f}%      │ {avg_z_dev['full_all_2k_3eps']:>8.3f}   │ {avg_end_dist['full_all_2k_3eps']:>8.3f}     │ 30 (3eps/task)     │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘

数据量影响分析:
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│  最高成功率: {best_success:<25} ({success_rates[best_success]:.1f}%)                              │
│  Z轴稳定性最佳: {best_z:<25} (平均偏差: {avg_z_dev[best_z]:.3f}m)                                 │
│  末端位置最接近: {best_end:<25} (平均距离: {avg_end_dist[best_end]:.3f}m)                         │
│                                                                                                  │
│  一致性对比 (标准差越小越稳定):                                                                    │
│  ├─ LoRA demo0:    {np.mean(lora_consistency):.3f}m                                               │
│  ├─ Full demo0:    {np.mean(full_demo0_consistency):.3f}m                                         │
│  └─ Full ALL:      {np.mean(full_all_consistency):.3f}m                                           │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘

关键发现:
1. demo0 (10条) vs 全部demo (500条):
   - demo0 成功率: 0%
   - 全部demo 成功率: {success_rates['full_all_2k_3eps']:.1f}%
   - 数据量增加50倍，成功率从0%提升到{success_rates['full_all_2k_3eps']:.1f}%

2. 训练步数不是关键:
   - demo0 4K步: 0%
   - 全部demo 2K步: {success_rates['full_all_2k_3eps']:.1f}%
   - 更少的步数但更多数据 → 更好的结果

3. 微调方法对比 (数据量相同时):
   - LoRA demo0: 0%
   - Full demo0: 0%
   - 数据量不足时，微调方法差异不大
""")
    
    plt.close('all')
    print("\n分析完成!")

if __name__ == '__main__':
    main()


