"""
评估脚本 + End Effector 轨迹追踪与可视化
基于 libero_rdt_eval.py，增加了：
1. 记录每条轨迹的 end effector pose (position + quaternion)
2. 保存轨迹数据为 JSON 文件
3. 自动生成多种可视化图表
"""
import os
import csv
import json
import random
import time
import datetime

import numpy as np
import sys
import torch
import yaml
import argparse
from collections import deque
from PIL import Image

import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.patches as mpatches

LIBERO_REPO_ROOT = "/home/zhukefei/chensiqi/LIBERO"

if LIBERO_REPO_ROOT not in sys.path:
    sys.path.insert(0, LIBERO_REPO_ROOT)

from libero.libero import get_libero_path
from libero.libero.benchmark import get_benchmark_dict
from libero.libero.envs import OffScreenRenderEnv, SubprocVectorEnv
from libero_rdt_model import create_model, RoboticDiffusionTransformerModel
from libero.libero.utils.video_utils import VideoWriter 


def load_config(config_path):
    """从YAML文件加载配置"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config


def parse_args():
    parser = argparse.ArgumentParser(description="评估所有任务（带 End Effector 轨迹追踪）")
    
    # 配置文件参数（优先级最高）
    parser.add_argument("--config", type=str, default=None,
                        help="配置文件路径（YAML格式），如果提供则其他参数可选")
    
    # 原有参数（可通过配置文件或命令行指定）
    parser.add_argument("--num-traj", type=int, default=None, help="每个任务的评估轨迹数")
    parser.add_argument("--pretrained-path", type=str, default=None, help="预训练模型路径")
    parser.add_argument("--dataset-name", type=str, default=None, 
                        choices=["libero_10", "libero_90", "libero_object", "libero_spatial", "libero_goal"], 
                        help="数据集名称")
    parser.add_argument("--lora-adapter", type=str, default=None, 
                        help="LoRA adapter 路径（如果使用 LoRA）")
    parser.add_argument("--metrics-path", type=str, default=None,
                        help="评估结果保存的 CSV 路径")
    parser.add_argument("--seed", type=int, default=None, 
                        help="随机种子（用于复现）")
    parser.add_argument("--video-save-interval", type=int, default=None,
                        help="视频保存间隔（0=不保存，10=每10个任务保存一次）")
    parser.add_argument("--video-root-dir", type=str, default=None,
                        help="视频保存根目录")
    parser.add_argument("--gpu", type=int, default=None,
                        help="指定使用的 GPU 编号（例如：0, 1, 2...），默认使用 cuda:0")
    parser.add_argument("--exec-horizon", type=int, default=None,
                        help="执行horizon：每次推理后执行多少步动作（1=每步推理，8=推荐值）")
    
    # EEF 追踪相关参数
    parser.add_argument("--eef-save-dir", type=str, default="outs/eef_trajectories",
                        help="End Effector 轨迹保存目录")
    parser.add_argument("--task-ids", type=str, default=None,
                        help="指定评估的任务ID，用逗号分隔（例如：0,1,2）。不指定则评估全部任务")
    
    args = parser.parse_args()
    
    # 如果提供了配置文件，从配置文件加载参数
    if args.config:
        if not os.path.exists(args.config):
            raise FileNotFoundError(f"配置文件不存在: {args.config}")
        
        config = load_config(args.config)

        # 读取 LIBERO_REPO_ROOT 配置
        global LIBERO_REPO_ROOT
        libero_root = config.get('environment', {}).get('libero_repo_root')
        if libero_root:
            LIBERO_REPO_ROOT = libero_root
        
        # 将 LIBERO_REPO_ROOT 添加到 sys.path（如果尚未添加）
        if LIBERO_REPO_ROOT not in sys.path:
            sys.path.insert(0, LIBERO_REPO_ROOT)
            
        # 从配置文件读取参数（命令行参数优先）
        if args.dataset_name is None:
            args.dataset_name = config.get('dataset', {}).get('name', 'libero_10')
        
        if args.pretrained_path is None:
            args.pretrained_path = config.get('model', {}).get('pretrained_path')
        
        if args.lora_adapter is None:
            args.lora_adapter = config.get('model', {}).get('lora_adapter')
        
        if args.num_traj is None:
            args.num_traj = config.get('evaluation', {}).get('num_traj', 20)
        
        if args.seed is None:
            args.seed = config.get('evaluation', {}).get('seed', 20241201)
        
        if args.video_save_interval is None:
            args.video_save_interval = config.get('evaluation', {}).get('video', {}).get('save_interval', 10)
        
        if args.video_root_dir is None:
            args.video_root_dir = config.get('evaluation', {}).get('video', {}).get('root_dir', 'outs/eval_videos')
        
        if args.gpu is None:
            args.gpu = config.get('evaluation', {}).get('gpu', 0)
        
        if args.exec_horizon is None:
            args.exec_horizon = config.get('evaluation', {}).get('exec_horizon', 1)
        
        # 从配置文件读取 EEF 追踪相关配置
        eef_config = config.get('eef_tracking', {})
        if args.eef_save_dir == "outs/eef_trajectories":  # 如果是默认值，则从配置文件读取
            args.eef_save_dir = eef_config.get('save_dir', 'outs/eef_trajectories')
        
        if args.task_ids is None:
            task_ids_from_config = eef_config.get('task_ids')
            if task_ids_from_config and task_ids_from_config != 'null':
                args.task_ids = str(task_ids_from_config)
        
        # 自动生成metrics_path（如果未指定）
        if args.metrics_path is None:
            metrics_dir = config.get('output', {}).get('metrics_dir', 'outs/metrics')
            prefix = config.get('output', {}).get('prefix', '')
            
            # 确定checkpoint名称
            if args.lora_adapter:
                checkpoint_name = os.path.basename(args.lora_adapter)
            else:
                checkpoint_name = os.path.basename(args.pretrained_path)
            
            # 生成文件名
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{prefix}{args.dataset_name}_eval{args.num_traj}eps_{checkpoint_name}_seed{args.seed}_{timestamp}.csv"
            args.metrics_path = os.path.join(metrics_dir, filename)
    
    # 检查必填参数
    if args.pretrained_path is None:
        parser.error("必须提供 --pretrained-path 或在配置文件中指定 model.pretrained_path")
    
    if args.metrics_path is None:
        parser.error("必须提供 --metrics-path 或使用配置文件（会自动生成）")
    
    # 设置默认值（如果仍为None）
    if args.num_traj is None:
        args.num_traj = 20
    if args.dataset_name is None:
        args.dataset_name = "libero_10"
    if args.seed is None:
        args.seed = 20241201
    if args.video_save_interval is None:
        args.video_save_interval = 10
    if args.video_root_dir is None:
        args.video_root_dir = "outs/eval_videos"
    if args.gpu is None:
        args.gpu = 0
    if args.exec_horizon is None:
        args.exec_horizon = 1
    
    return args


def _get_obs_item(obs, key, idx):
    """兼容两种 vector obs 结构"""
    if isinstance(obs, dict):
        return obs[key][idx]
    else:
        return obs[idx][key]


def set_global_seeds(seed: int):
    """统一控制随机种子"""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def get_task_name_from_bddl(bddl_file_path):
    """从 BDDL 文件路径提取任务名称"""
    filename = os.path.basename(bddl_file_path)
    return filename.replace('.bddl', '')


def extract_instruction_from_task_name(task_name):
    """从任务名称提取指令"""
    if task_name[0].isupper():
        scene_pos = task_name.find("SCENE")
        if scene_pos != -1:
            if "SCENE10" in task_name:
                language_part = task_name[scene_pos + 8:]
            else:
                language_part = task_name[scene_pos + 7:]
            return language_part.replace('_', ' ')
    return task_name.replace('_', ' ')


def load_language_embedding(task_name, dataset_name, policy, device):
    """加载语言嵌入"""
    lang_embed_path = os.path.join("outs/libero_embeddings", dataset_name, f"{task_name}.pt")

    if os.path.exists(lang_embed_path):
        print(f"  ✓ 加载预计算嵌入: {task_name}")
        lang_data = torch.load(lang_embed_path)
        if isinstance(lang_data, dict):
            embeddings = lang_data['embeddings']
        else:
            embeddings = lang_data
        
        if embeddings.dim() == 2:
            embeddings = embeddings.unsqueeze(0)
        
        return embeddings.to(device=device, dtype=torch.bfloat16)
    else:
        print(f"  ⚠ 实时编码嵌入: {task_name}")
        instruction = extract_instruction_from_task_name(task_name)
        return policy.encode_instruction(instruction).to(device=device, dtype=torch.bfloat16)


# ==================== 工具函数 ====================

def quaternion_to_euler(quat):
    """
    将四元数转换为欧拉角 (roll, pitch, yaw)
    输入: quat = [w, x, y, z] 或 [x, y, z, w] (会自动检测)
    输出: [roll, pitch, yaw] in radians
    """
    quat = np.array(quat)
    
    # 检测四元数格式 (robosuite 通常是 [x, y, z, w])
    # 如果 w 分量在最后一位且接近 1（单位四元数），则认为是 [x, y, z, w] 格式
    if abs(quat[3]) > abs(quat[0]):
        x, y, z, w = quat
    else:
        w, x, y, z = quat
    
    # Roll (x-axis rotation)
    sinr_cosp = 2 * (w * x + y * z)
    cosr_cosp = 1 - 2 * (x * x + y * y)
    roll = np.arctan2(sinr_cosp, cosr_cosp)
    
    # Pitch (y-axis rotation)
    sinp = 2 * (w * y - z * x)
    if abs(sinp) >= 1:
        pitch = np.sign(sinp) * np.pi / 2
    else:
        pitch = np.arcsin(sinp)
    
    # Yaw (z-axis rotation)
    siny_cosp = 2 * (w * z + x * y)
    cosy_cosp = 1 - 2 * (y * y + z * z)
    yaw = np.arctan2(siny_cosp, cosy_cosp)
    
    return np.array([roll, pitch, yaw])


# ==================== 可视化函数 ====================

def visualize_eef_trajectories_3d(trajectories, success_flags, task_name, instruction, save_path):
    """
    绘制 3D End Effector 轨迹图
    成功轨迹为绿色，失败轨迹为红色
    """
    fig = plt.figure(figsize=(14, 10))
    ax = fig.add_subplot(111, projection='3d')
    
    # 自定义颜色
    success_color = '#2ecc71'  # 绿色
    fail_color = '#e74c3c'     # 红色
    
    num_success = 0
    num_fail = 0
    
    for i, traj in enumerate(trajectories):
        positions = np.array([step["pos"] for step in traj])
        is_success = success_flags[i]
        
        if is_success:
            color = success_color
            alpha = 0.7
            num_success += 1
        else:
            color = fail_color
            alpha = 0.5
            num_fail += 1
        
        # 绘制轨迹线
        ax.plot(positions[:, 0], positions[:, 1], positions[:, 2], 
                color=color, alpha=alpha, linewidth=1.5)
        
        # 标记起点和终点
        ax.scatter(positions[0, 0], positions[0, 1], positions[0, 2], 
                   color='blue', s=30, marker='o', alpha=0.8)
        ax.scatter(positions[-1, 0], positions[-1, 1], positions[-1, 2], 
                   color=color, s=50, marker='*', alpha=0.9)
    
    # 图例
    success_patch = mpatches.Patch(color=success_color, label=f'Success ({num_success})')
    fail_patch = mpatches.Patch(color=fail_color, label=f'Fail ({num_fail})')
    start_marker = plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='blue', 
                               markersize=8, label='Start')
    ax.legend(handles=[success_patch, fail_patch, start_marker], loc='upper left')
    
    ax.set_xlabel('X (m)', fontsize=12)
    ax.set_ylabel('Y (m)', fontsize=12)
    ax.set_zlabel('Z (m)', fontsize=12)
    
    # 标题
    title = f"End Effector Trajectories\n{instruction}"
    ax.set_title(title, fontsize=14, fontweight='bold')
    
    # 设置视角
    ax.view_init(elev=25, azim=45)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  📊 3D轨迹图已保存: {save_path}")


def visualize_eef_trajectories_2d_projections(trajectories, success_flags, task_name, instruction, save_path):
    """
    绘制 2D 投影图 (XY, XZ, YZ 三个平面)
    """
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    
    success_color = '#2ecc71'
    fail_color = '#e74c3c'
    
    projections = [
        (0, 1, 'X (m)', 'Y (m)', 'XY Plane (Top View)'),
        (0, 2, 'X (m)', 'Z (m)', 'XZ Plane (Front View)'),
        (1, 2, 'Y (m)', 'Z (m)', 'YZ Plane (Side View)')
    ]
    
    for ax, (dim1, dim2, xlabel, ylabel, title) in zip(axes, projections):
        for i, traj in enumerate(trajectories):
            positions = np.array([step["pos"] for step in traj])
            is_success = success_flags[i]
            color = success_color if is_success else fail_color
            alpha = 0.6 if is_success else 0.4
            
            ax.plot(positions[:, dim1], positions[:, dim2], 
                    color=color, alpha=alpha, linewidth=1.2)
            
            # 起点
            ax.scatter(positions[0, dim1], positions[0, dim2], 
                       color='blue', s=20, marker='o', alpha=0.7, zorder=5)
            # 终点
            ax.scatter(positions[-1, dim1], positions[-1, dim2], 
                       color=color, s=40, marker='*', alpha=0.9, zorder=5)
        
        ax.set_xlabel(xlabel, fontsize=11)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal', adjustable='box')
    
    # 图例 (只在第一个子图)
    num_success = sum(success_flags)
    num_fail = len(success_flags) - num_success
    success_patch = mpatches.Patch(color=success_color, label=f'Success ({num_success})')
    fail_patch = mpatches.Patch(color=fail_color, label=f'Fail ({num_fail})')
    axes[0].legend(handles=[success_patch, fail_patch], loc='upper left', fontsize=9)
    
    fig.suptitle(f"EEF Trajectory Projections: {instruction}", fontsize=14, fontweight='bold', y=1.02)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  📊 2D投影图已保存: {save_path}")


def visualize_eef_position_heatmap(trajectories, success_flags, task_name, instruction, save_path):
    """
    绘制 End Effector 位置热力图 (XY 平面)
    展示机器人活动的热点区域
    """
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    
    # 收集所有位置点
    all_positions = []
    success_positions = []
    fail_positions = []
    
    for i, traj in enumerate(trajectories):
        positions = np.array([step["pos"] for step in traj])
        all_positions.extend(positions)
        if success_flags[i]:
            success_positions.extend(positions)
        else:
            fail_positions.extend(positions)
    
    all_positions = np.array(all_positions)
    
    # 确定范围
    x_range = [all_positions[:, 0].min() - 0.05, all_positions[:, 0].max() + 0.05]
    y_range = [all_positions[:, 1].min() - 0.05, all_positions[:, 1].max() + 0.05]
    
    # 子图1: 所有轨迹的热力图
    ax1 = axes[0]
    h1 = ax1.hist2d(all_positions[:, 0], all_positions[:, 1], 
                    bins=50, range=[x_range, y_range], 
                    cmap='YlOrRd', density=True)
    ax1.set_xlabel('X (m)', fontsize=11)
    ax1.set_ylabel('Y (m)', fontsize=11)
    ax1.set_title('All Trajectories', fontsize=12, fontweight='bold')
    plt.colorbar(h1[3], ax=ax1, label='Density')
    
    # 子图2: 成功轨迹热力图
    ax2 = axes[1]
    if len(success_positions) > 0:
        success_positions = np.array(success_positions)
        h2 = ax2.hist2d(success_positions[:, 0], success_positions[:, 1], 
                        bins=50, range=[x_range, y_range], 
                        cmap='Greens', density=True)
        plt.colorbar(h2[3], ax=ax2, label='Density')
    ax2.set_xlabel('X (m)', fontsize=11)
    ax2.set_ylabel('Y (m)', fontsize=11)
    ax2.set_title(f'Success Trajectories ({sum(success_flags)})', fontsize=12, fontweight='bold')
    
    # 子图3: 失败轨迹热力图
    ax3 = axes[2]
    if len(fail_positions) > 0:
        fail_positions = np.array(fail_positions)
        h3 = ax3.hist2d(fail_positions[:, 0], fail_positions[:, 1], 
                        bins=50, range=[x_range, y_range], 
                        cmap='Reds', density=True)
        plt.colorbar(h3[3], ax=ax3, label='Density')
    ax3.set_xlabel('X (m)', fontsize=11)
    ax3.set_ylabel('Y (m)', fontsize=11)
    ax3.set_title(f'Fail Trajectories ({len(success_flags) - sum(success_flags)})', fontsize=12, fontweight='bold')
    
    fig.suptitle(f"EEF Position Heatmap (XY): {instruction}", fontsize=14, fontweight='bold', y=1.02)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  📊 热力图已保存: {save_path}")


def visualize_eef_z_over_time(trajectories, success_flags, task_name, instruction, save_path):
    """
    绘制 Z 轴高度随时间的变化曲线
    用于分析抬起/放下物体的动作模式
    """
    fig, ax = plt.subplots(figsize=(14, 6))
    
    success_color = '#2ecc71'
    fail_color = '#e74c3c'
    
    max_steps = max(len(traj) for traj in trajectories)
    
    for i, traj in enumerate(trajectories):
        positions = np.array([step["pos"] for step in traj])
        steps = np.array([step["step"] for step in traj])
        is_success = success_flags[i]
        
        color = success_color if is_success else fail_color
        alpha = 0.6 if is_success else 0.4
        
        ax.plot(steps, positions[:, 2], color=color, alpha=alpha, linewidth=1.2)
    
    ax.set_xlabel('Time Step', fontsize=12)
    ax.set_ylabel('Z Position (m)', fontsize=12)
    ax.set_title(f'End Effector Height Over Time\n{instruction}', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # 图例
    num_success = sum(success_flags)
    num_fail = len(success_flags) - num_success
    success_patch = mpatches.Patch(color=success_color, label=f'Success ({num_success})')
    fail_patch = mpatches.Patch(color=fail_color, label=f'Fail ({num_fail})')
    ax.legend(handles=[success_patch, fail_patch], loc='upper right')
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  📊 Z轴时间图已保存: {save_path}")


def visualize_endpoint_distribution(trajectories, success_flags, task_name, instruction, save_path):
    """
    绘制轨迹终点分布图
    分析成功和失败轨迹的终点位置差异
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    success_endpoints = []
    fail_endpoints = []
    
    for i, traj in enumerate(trajectories):
        endpoint = traj[-1]["pos"]
        if success_flags[i]:
            success_endpoints.append(endpoint)
        else:
            fail_endpoints.append(endpoint)
    
    success_endpoints = np.array(success_endpoints) if success_endpoints else np.array([]).reshape(0, 3)
    fail_endpoints = np.array(fail_endpoints) if fail_endpoints else np.array([]).reshape(0, 3)
    
    # 左图: XY 平面终点分布
    ax1 = axes[0]
    if len(success_endpoints) > 0:
        ax1.scatter(success_endpoints[:, 0], success_endpoints[:, 1], 
                    c='#2ecc71', s=80, alpha=0.7, label=f'Success ({len(success_endpoints)})', marker='o')
    if len(fail_endpoints) > 0:
        ax1.scatter(fail_endpoints[:, 0], fail_endpoints[:, 1], 
                    c='#e74c3c', s=80, alpha=0.7, label=f'Fail ({len(fail_endpoints)})', marker='x')
    
    ax1.set_xlabel('X (m)', fontsize=11)
    ax1.set_ylabel('Y (m)', fontsize=11)
    ax1.set_title('Endpoint Distribution (XY)', fontsize=12, fontweight='bold')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    ax1.set_aspect('equal', adjustable='box')
    
    # 右图: XZ 平面终点分布
    ax2 = axes[1]
    if len(success_endpoints) > 0:
        ax2.scatter(success_endpoints[:, 0], success_endpoints[:, 2], 
                    c='#2ecc71', s=80, alpha=0.7, label=f'Success ({len(success_endpoints)})', marker='o')
    if len(fail_endpoints) > 0:
        ax2.scatter(fail_endpoints[:, 0], fail_endpoints[:, 2], 
                    c='#e74c3c', s=80, alpha=0.7, label=f'Fail ({len(fail_endpoints)})', marker='x')
    
    ax2.set_xlabel('X (m)', fontsize=11)
    ax2.set_ylabel('Z (m)', fontsize=11)
    ax2.set_title('Endpoint Distribution (XZ)', fontsize=12, fontweight='bold')
    ax2.legend(loc='upper left')
    ax2.grid(True, alpha=0.3)
    
    fig.suptitle(f"Trajectory Endpoints: {instruction}", fontsize=14, fontweight='bold', y=1.02)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  📊 终点分布图已保存: {save_path}")


def visualize_eef_dimension_over_time(trajectories, success_flags, task_name, instruction, save_dir, prefix):
    """
    为每个 EEF 维度（x, y, z, rx, ry, rz）生成随时间变化的图片
    每个维度单独一张图，共生成 6 张图
    """
    success_color = '#2ecc71'
    fail_color = '#e74c3c'
    
    # 预处理：提取所有轨迹的位置和姿态数据
    all_traj_data = []
    for i, traj in enumerate(trajectories):
        positions = np.array([step["pos"] for step in traj])
        quats = np.array([step["quat"] for step in traj])
        steps = np.array([step["step"] for step in traj])
        
        # 将四元数转换为欧拉角
        eulers = np.array([quaternion_to_euler(q) for q in quats])
        
        all_traj_data.append({
            "steps": steps,
            "positions": positions,
            "eulers": eulers,
            "is_success": success_flags[i]
        })
    
    # 定义要绘制的维度
    dimensions = [
        ("x", "positions", 0, "X Position (m)", "End Effector X Position Over Time"),
        ("y", "positions", 1, "Y Position (m)", "End Effector Y Position Over Time"),
        ("z", "positions", 2, "Z Position (m)", "End Effector Z Position Over Time"),
        ("rx", "eulers", 0, "Roll (rad)", "End Effector Roll (rx) Over Time"),
        ("ry", "eulers", 1, "Pitch (rad)", "End Effector Pitch (ry) Over Time"),
        ("rz", "eulers", 2, "Yaw (rad)", "End Effector Yaw (rz) Over Time"),
    ]
    
    for dim_name, data_key, dim_idx, ylabel, title in dimensions:
        fig, ax = plt.subplots(figsize=(14, 6))
        
        for traj_data in all_traj_data:
            steps = traj_data["steps"]
            values = traj_data[data_key][:, dim_idx]
            is_success = traj_data["is_success"]
            
            color = success_color if is_success else fail_color
            alpha = 0.6 if is_success else 0.4
            
            ax.plot(steps, values, color=color, alpha=alpha, linewidth=1.2)
        
        ax.set_xlabel('Time Step', fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(f'{title}\n{instruction}', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        # 图例
        num_success = sum(success_flags)
        num_fail = len(success_flags) - num_success
        success_patch = mpatches.Patch(color=success_color, label=f'Success ({num_success})')
        fail_patch = mpatches.Patch(color=fail_color, label=f'Fail ({num_fail})')
        ax.legend(handles=[success_patch, fail_patch], loc='upper right')
        
        plt.tight_layout()
        save_path = os.path.join(save_dir, f"{prefix}_{dim_name}_over_time.png")
        plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        print(f"  📊 {dim_name.upper()} 时间图已保存: {save_path}")


def generate_all_visualizations(eef_data, save_dir):
    """
    生成单个任务的可视化图表（已弃用，改用汇总可视化）
    """
    pass  # 不再为每个任务单独生成图片


def generate_summary_visualizations(all_eef_data, save_dir, dataset_name, checkpoint_name, is_lora=False, num_traj_per_task=1):
    """
    生成汇总可视化图表：包含所有任务所有轨迹
    - 1 张 3D 轨迹图（所有任务的所有轨迹）
    - 6 张 EEF 各维度随时间变化图 (x, y, z, rx, ry, rz)
    
    Args:
        all_eef_data: 所有任务的 EEF 数据
        save_dir: 保存目录
        dataset_name: 数据集名称
        checkpoint_name: checkpoint 名称
        is_lora: 是否使用 LoRA
        num_traj_per_task: 每个任务的轨迹数
    """
    vis_dir = os.path.join(save_dir, "visualizations")
    os.makedirs(vis_dir, exist_ok=True)
    
    # 收集所有轨迹数据
    all_trajectories = []
    all_success_flags = []
    all_task_ids = []
    
    for eef_data in all_eef_data:
        task_id = eef_data["task_id"]
        trajectories = eef_data["trajectories"]
        success_flags = eef_data["success_flags"]
        
        for i, traj in enumerate(trajectories):
            all_trajectories.append(traj)
            all_success_flags.append(success_flags[i])
            all_task_ids.append(task_id)
    
    num_tasks = len(all_eef_data)
    num_total_traj = len(all_trajectories)
    num_success = sum(all_success_flags)
    num_fail = num_total_traj - num_success
    
    # 构建模型信息字符串
    model_type = "LoRA" if is_lora else "Full"
    model_info = f"{model_type} | {checkpoint_name}"
    
    print(f"\n🎨 生成汇总可视化图表...")
    print(f"   任务数: {num_tasks}, 轨迹总数: {num_total_traj} (成功: {num_success}, 失败: {num_fail})")
    print(f"   模型信息: {model_info}")
    
    # 1. 汇总 3D 轨迹图
    _generate_summary_3d_plot(
        all_trajectories, all_success_flags, all_task_ids,
        dataset_name, num_tasks, model_info, num_traj_per_task,
        os.path.join(vis_dir, "summary_3d_trajectories.png")
    )
    
    # 2-7. 汇总各维度时间图
    _generate_summary_dimension_plots(
        all_trajectories, all_success_flags, all_task_ids,
        dataset_name, num_tasks, model_info, num_traj_per_task, vis_dir
    )
    
    print(f"   ✅ 汇总可视化完成，保存在: {vis_dir}")


def _generate_summary_3d_plot(trajectories, success_flags, task_ids, dataset_name, num_tasks, model_info, num_traj_per_task, save_path):
    """
    生成包含所有轨迹的 3D 汇总图
    """
    fig = plt.figure(figsize=(16, 12))
    ax = fig.add_subplot(111, projection='3d')
    
    success_color = '#2ecc71'
    fail_color = '#e74c3c'
    
    num_success = 0
    num_fail = 0
    
    for i, traj in enumerate(trajectories):
        positions = np.array([step["pos"] for step in traj])
        is_success = success_flags[i]
        
        if is_success:
            color = success_color
            alpha = 0.5
            num_success += 1
        else:
            color = fail_color
            alpha = 0.3
            num_fail += 1
        
        ax.plot(positions[:, 0], positions[:, 1], positions[:, 2],
                color=color, alpha=alpha, linewidth=0.8)
    
    # 图例
    success_patch = mpatches.Patch(color=success_color, label=f'Success ({num_success})')
    fail_patch = mpatches.Patch(color=fail_color, label=f'Fail ({num_fail})')
    ax.legend(handles=[success_patch, fail_patch], loc='upper left', fontsize=12)
    
    ax.set_xlabel('X (m)', fontsize=12)
    ax.set_ylabel('Y (m)', fontsize=12)
    ax.set_zlabel('Z (m)', fontsize=12)
    
    # 计算成功率
    success_rate = num_success / len(trajectories) * 100 if len(trajectories) > 0 else 0
    
    ax.set_title(f"All EEF Trajectories - {dataset_name}\n"
                 f"Model: {model_info}\n"
                 f"{num_tasks} tasks × {num_traj_per_task} eps = {len(trajectories)} traj | "
                 f"Success Rate: {success_rate:.1f}%", 
                 fontsize=13, fontweight='bold')
    
    ax.view_init(elev=25, azim=45)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"   📊 3D 汇总图已保存: {save_path}")


def _generate_summary_dimension_plots(trajectories, success_flags, task_ids, dataset_name, num_tasks, model_info, num_traj_per_task, save_dir):
    """
    生成包含所有轨迹的各维度汇总图（共 6 张）
    """
    success_color = '#2ecc71'
    fail_color = '#e74c3c'
    
    # 预处理：提取所有轨迹的位置和姿态数据
    all_traj_data = []
    for i, traj in enumerate(trajectories):
        positions = np.array([step["pos"] for step in traj])
        quats = np.array([step["quat"] for step in traj])
        steps = np.array([step["step"] for step in traj])
        
        # 将四元数转换为欧拉角
        eulers = np.array([quaternion_to_euler(q) for q in quats])
        
        all_traj_data.append({
            "steps": steps,
            "positions": positions,
            "eulers": eulers,
            "is_success": success_flags[i],
            "task_id": task_ids[i]
        })
    
    num_success = sum(success_flags)
    num_fail = len(success_flags) - num_success
    
    # 计算成功率
    success_rate = num_success / len(trajectories) * 100 if len(trajectories) > 0 else 0
    
    # 定义要绘制的维度
    dimensions = [
        ("x", "positions", 0, "X Position (m)", "End Effector X Position"),
        ("y", "positions", 1, "Y Position (m)", "End Effector Y Position"),
        ("z", "positions", 2, "Z Position (m)", "End Effector Z Position"),
        ("rx", "eulers", 0, "Roll (rad)", "End Effector Roll (rx)"),
        ("ry", "eulers", 1, "Pitch (rad)", "End Effector Pitch (ry)"),
        ("rz", "eulers", 2, "Yaw (rad)", "End Effector Yaw (rz)"),
    ]
    
    for dim_name, data_key, dim_idx, ylabel, title in dimensions:
        fig, ax = plt.subplots(figsize=(16, 8))
        
        for traj_data in all_traj_data:
            steps = traj_data["steps"]
            values = traj_data[data_key][:, dim_idx]
            is_success = traj_data["is_success"]
            
            color = success_color if is_success else fail_color
            alpha = 0.4 if is_success else 0.25
            
            ax.plot(steps, values, color=color, alpha=alpha, linewidth=0.8)
        
        ax.set_xlabel('Time Step', fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(f'{title} - {dataset_name}\n'
                     f'Model: {model_info}\n'
                     f'{num_tasks} tasks × {num_traj_per_task} eps = {len(trajectories)} traj | '
                     f'Success Rate: {success_rate:.1f}%', 
                     fontsize=13, fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        # 图例
        success_patch = mpatches.Patch(color=success_color, label=f'Success ({num_success})')
        fail_patch = mpatches.Patch(color=fail_color, label=f'Fail ({num_fail})')
        ax.legend(handles=[success_patch, fail_patch], loc='upper right', fontsize=11)
        
        plt.tight_layout()
        save_path = os.path.join(save_dir, f"summary_{dim_name}_over_time.png")
        plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        print(f"   📊 {dim_name.upper()} 汇总图已保存: {save_path}")


# ==================== 评估函数 ====================

def evaluate_single_task_with_eef_tracking(
    task_id,
    policy,
    device,
    benchmark_dict,
    args,
    checkpoint_identifier
):
    """
    评估单个任务，同时记录 End Effector 轨迹
    返回：(success_rate, num_success, task_name, instruction, eef_data)
    """
    print(f"\n{'─'*80}")
    print(f"正在评估 Task {task_id} (带 EEF 追踪)")
    print(f"{'─'*80}")
    print(f"  ℹ 执行策略: Horizon={args.exec_horizon} (每次推理后执行{args.exec_horizon}步)")
    
    task_start_time = time.time()
    
    # 获取任务信息
    task_suite = benchmark_dict[args.dataset_name]()
    task = task_suite.get_task(task_id)
    
    bddl_file = os.path.join(
        get_libero_path("bddl_files"),
        task.problem_folder,
        task.bddl_file,
    )
    
    task_name = get_task_name_from_bddl(bddl_file)
    instruction = extract_instruction_from_task_name(task_name)
    
    print(f"  任务名称: {task_name}")
    print(f"  指令: {instruction}")
    
    # 加载语言嵌入
    text_embed = load_language_embedding(task_name, args.dataset_name, policy, device)
    
    # 获取初始状态
    init_states = task_suite.get_task_init_states(task_id)
    num_init_states = init_states.shape[0]
    
    # 创建并行环境
    env_num = args.num_traj
    env_args = dict(
        bddl_file_name=bddl_file,
        camera_heights=128,
        camera_widths=128,
    )
    
    env = SubprocVectorEnv(
        [lambda: OffScreenRenderEnv(**env_args) for _ in range(env_num)]
    )
    env.seed(args.seed)
    env.reset()
    
    # 分配初始状态
    indices = np.arange(env_num) % num_init_states
    init_states_batch = init_states[indices]
    obs = env.set_init_state(init_states_batch)
    
    # 准备图像历史和 proprio
    MAX_EPISODE_STEPS = 720
    EXEC_HORIZON = args.exec_horizon  # 从配置读取执行horizon
    dones = [False] * env_num
    global_steps = 0
    
    agentview_windows = [deque(maxlen=2) for _ in range(env_num)]
    eye_in_hand_windows = [deque(maxlen=2) for _ in range(env_num)]
    proprios = [None for _ in range(env_num)]
    
    # Action buffer：存储每个环境的动作序列和当前执行位置
    action_buffers = [None for _ in range(env_num)]  # 存储64步的action序列
    action_counters = [0 for _ in range(env_num)]  # 当前执行到第几步
    
    # ====== EEF 轨迹记录初始化 ======
    eef_trajectories = [[] for _ in range(env_num)]
    
    for i in range(env_num):
        agent_img = _get_obs_item(obs, "agentview_image", i)
        eye_img = _get_obs_item(obs, "robot0_eye_in_hand_image", i)
        
        for _ in range(2):
            agentview_windows[i].append(agent_img)
            eye_in_hand_windows[i].append(eye_img)
        
        joint_states = _get_obs_item(obs, "robot0_joint_pos", i)
        gripper_states = _get_obs_item(obs, "robot0_gripper_qpos", i)
        proprio_np = np.concatenate([joint_states, gripper_states], axis=-1).astype(np.float32)
        proprios[i] = torch.from_numpy(proprio_np).to(device=device, dtype=torch.bfloat16)
        
        # 记录初始 EEF pose
        eef_pos = _get_obs_item(obs, "robot0_eef_pos", i)
        eef_quat = _get_obs_item(obs, "robot0_eef_quat", i)
        eef_trajectories[i].append({
            "step": 0,
            "pos": eef_pos.tolist(),
            "quat": eef_quat.tolist()
        })
    
    # 物理预热
    for _ in range(5):
        env.step(np.zeros((env_num, 7), dtype=np.float32))
    
    # 决定是否保存视频
    save_videos = (args.video_save_interval > 0 and task_id % args.video_save_interval == 0)
    
    if save_videos:
        video_folder = os.path.join(
            args.video_root_dir,
            f"{args.dataset_name}_task{task_id}"
        )
        os.makedirs(video_folder, exist_ok=True)
        print(f"  📹 将保存视频到: {video_folder}")
    else:
        video_folder = "outs/videos"
    
    num_success = 0
    
    with VideoWriter(video_folder, save_video=save_videos, fps=30, single_video=True) as video_writer:
        while (global_steps < MAX_EPISODE_STEPS) and (not all(dones)):
            actions = np.zeros((env_num, 7), dtype=np.float32)
            
            # 推理
            with torch.inference_mode():
                for i in range(env_num):
                    if dones[i]:
                        continue
                    
                    # 检查是否需要重新推理（buffer为空或已用完前N步）
                    if action_buffers[i] is None or action_counters[i] >= EXEC_HORIZON:
                        # 准备图像
                        image_arrs = []
                        for t in range(2):
                            image_arrs.append(agentview_windows[i][t])
                            image_arrs.append(eye_in_hand_windows[i][t])
                            image_arrs.append(None)
                        
                        images = [
                            Image.fromarray(arr) if arr is not None else None
                            for arr in image_arrs
                        ]
                        
                        # RDT 推理：生成64步动作
                        action_seq = policy.step(proprios[i], images, text_embed).squeeze(0)
                        action_seq = action_seq.detach().cpu().numpy()
                        
                        if np.any(np.isnan(action_seq)) or np.any(np.isinf(action_seq)):
                            continue
                        
                        # 存储动作序列并重置计数器
                        action_buffers[i] = action_seq
                        action_counters[i] = 0
                    
                    # 从buffer中取出当前步的动作
                    actions[i] = action_buffers[i][action_counters[i]]
                    action_counters[i] += 1
            
            # 环境步进
            obs, reward, done, info = env.step(actions)
            global_steps += 1
            
            # 记录视频
            if save_videos:
                video_writer.append_vector_obs(
                    obs,
                    dones,
                    camera_name="agentview_image",
                )
            
            # 更新观测 + 记录 EEF pose
            for i in range(env_num):
                if not dones[i]:
                    agent_img = _get_obs_item(obs, "agentview_image", i)
                    eye_img = _get_obs_item(obs, "robot0_eye_in_hand_image", i)
                    
                    agentview_windows[i].append(agent_img)
                    eye_in_hand_windows[i].append(eye_img)
                    
                    joint_states = _get_obs_item(obs, "robot0_joint_pos", i)
                    gripper_states = _get_obs_item(obs, "robot0_gripper_qpos", i)
                    proprio_np = np.concatenate([joint_states, gripper_states], axis=-1).astype(np.float32)
                    proprios[i] = torch.from_numpy(proprio_np).to(device=device, dtype=torch.bfloat16)
                    
                    # ====== 记录 EEF pose ======
                    eef_pos = _get_obs_item(obs, "robot0_eef_pos", i)
                    eef_quat = _get_obs_item(obs, "robot0_eef_quat", i)
                    eef_trajectories[i].append({
                        "step": global_steps,
                        "pos": eef_pos.tolist(),
                        "quat": eef_quat.tolist()
                    })
                    
                    if done[i]:
                        dones[i] = True
        
        # 统计成功数
        for i in range(env_num):
            num_success += int(dones[i])
    
    env.close()
    
    # 计算成功率
    success_rate = num_success / float(env_num)
    task_time = time.time() - task_start_time
    
    print(f"  ✓ 成功率: {success_rate * 100:.2f}% ({num_success}/{env_num})")
    print(f"  ⏱ 耗时: {task_time:.1f}秒")
    
    # 构建 EEF 数据
    eef_data = {
        "task_id": task_id,
        "task_name": task_name,
        "instruction": instruction,
        "dataset_name": args.dataset_name,
        "num_trajectories": env_num,
        "success_rate": success_rate,
        "num_success": num_success,
        "trajectories": eef_trajectories,
        "success_flags": [dones[i] for i in range(env_num)],
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    # 写入 CSV
    write_task_result_to_csv(
        args.metrics_path,
        args.dataset_name,
        task_id,
        task_name,
        instruction,
        env_num,
        num_success,
        success_rate,
        checkpoint_identifier,
        video_folder if save_videos else ""
    )
    
    return success_rate, num_success, task_name, instruction, eef_data


def write_task_result_to_csv(
    metrics_path,
    dataset_name,
    task_id,
    task_name,
    instruction,
    num_traj,
    episode_done_count,
    success_rate,
    checkpoint_path,
    video_dir
):
    """将单个任务结果写入 CSV"""
    metrics_dir = os.path.dirname(metrics_path)
    if metrics_dir != "":
        os.makedirs(metrics_dir, exist_ok=True)
    
    file_exists = os.path.isfile(metrics_path) and os.path.getsize(metrics_path) > 0
    
    with open(metrics_path, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "dataset_name",
                "task_id",
                "task_name",
                "instruction",
                "num_traj",
                "episode_done_count",
                "success_rate",
                "checkpoint_path",
                "video_dir",
            ])
        
        writer.writerow([
            dataset_name,
            task_id,
            task_name,
            instruction,
            num_traj,
            episode_done_count,
            success_rate,
            checkpoint_path,
            video_dir,
        ])


def write_average_to_csv(metrics_path, dataset_name, checkpoint_path, random_seed, run_id, num_episodes):
    """计算并写入平均成功率"""
    success_rates = []
    episode_success_counts = []
    
    with open(metrics_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                success_rate = float(row['success_rate'])
                episode_done = int(row['episode_done_count'])
                success_rates.append(success_rate)
                episode_success_counts.append(episode_done)
            except (ValueError, KeyError):
                continue
    
    if len(success_rates) == 0:
        return
    
    total_tasks = len(success_rates)
    avg_success_rate = sum(success_rates) / total_tasks
    total_success_episodes = sum(episode_success_counts)
    total_episodes = total_tasks * num_episodes
    
    with open(metrics_path, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            dataset_name,
            "AVG",
            "AVERAGE",
            f"Average success rate across all tasks (seed={random_seed})",
            total_episodes,
            total_success_episodes,
            avg_success_rate,
            checkpoint_path,
            run_id
        ])


def main():
    args = parse_args()
    
    print("="*80)
    print("RDT-LIBERO 评估 + End Effector 轨迹追踪")
    print("="*80)
    print(f"数据集: {args.dataset_name}")
    print(f"每任务评估轮次: {args.num_traj}")
    print(f"随机种子: {args.seed}")
    print(f"执行 Horizon: {args.exec_horizon} (每{args.exec_horizon}步推理一次)")
    print(f"物理 GPU 编号: {args.gpu}")
    print(f"CUDA_VISIBLE_DEVICES: {os.environ.get('CUDA_VISIBLE_DEVICES', 'not set')}")
    print(f"EEF 轨迹保存目录: {args.eef_save_dir}")
    print("="*80)
    
    # 确定任务范围
    if args.task_ids:
        # 使用指定的任务ID
        task_range = [int(x.strip()) for x in args.task_ids.split(',')]
        print(f"指定评估任务: {task_range}")
    else:
        # 评估全部任务
        if args.dataset_name == "libero_10":
            task_range = list(range(0, 10))
        elif args.dataset_name == "libero_90":
            task_range = list(range(0, 90))
        elif args.dataset_name in ["libero_spatial", "libero_object", "libero_goal"]:
            task_range = list(range(0, 10))
        else:
            raise ValueError(f"不支持的数据集: {args.dataset_name}")
    
    # 设置随机种子
    set_global_seeds(args.seed)
    
    # 设置设备
    if torch.cuda.is_available():
        device = torch.device("cuda:0")
        print(f"\n使用设备: 物理 GPU {args.gpu} (映射为 cuda:0)")
    else:
        device = torch.device("cpu")
        print(f"\n使用设备: CPU (CUDA 不可用)")
    
    # ======== 一次性加载模型 ========
    print("\n" + "="*80)
    print("正在加载模型（只加载一次）...")
    print("="*80)
    
    model_start_time = time.time()
    
    config_path = 'configs/base.yaml'
    with open(config_path, "r") as fp:
        config = yaml.safe_load(fp)
    
    pretrained_text_encoder_name_or_path = "google/t5-v1_1-xxl"
    pretrained_vision_encoder_name_or_path = "google/siglip-so400m-patch14-384"
    
    policy = create_model(
        args=config, 
        dtype=torch.bfloat16,
        pretrained=args.pretrained_path,
        lora_adapter_path=args.lora_adapter,
        pretrained_text_encoder_name_or_path=pretrained_text_encoder_name_or_path,
        pretrained_vision_encoder_name_or_path=pretrained_vision_encoder_name_or_path,
    )
    
    model_load_time = time.time() - model_start_time
    print(f"✓ 模型加载完成！耗时: {model_load_time:.1f}秒")
    
    checkpoint_identifier = args.lora_adapter if args.lora_adapter else args.pretrained_path
    
    benchmark_dict = get_benchmark_dict()
    
    # 创建带时间戳的 EEF 保存目录
    # 目录结构: {eef_save_dir}/{dataset_name}/{timestamp}_{model_type}_{checkpoint_name}/
    eval_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 构建清晰的 checkpoint 标识
    if args.lora_adapter:
        # LoRA 模式：显示 base model 和 LoRA adapter
        base_name = os.path.basename(args.pretrained_path)
        lora_name = os.path.basename(args.lora_adapter)
        # 截断过长的名称
        if len(base_name) > 20:
            base_name = base_name[:20]
        if len(lora_name) > 30:
            lora_name = lora_name[:30]
        checkpoint_info = f"LoRA_{lora_name}_base_{base_name}"
    else:
        # 全参数模式
        checkpoint_short_name = os.path.basename(checkpoint_identifier)
        if len(checkpoint_short_name) > 40:
            checkpoint_short_name = checkpoint_short_name[:40]
        checkpoint_info = f"Full_{checkpoint_short_name}"
    
    run_folder_name = f"{eval_timestamp}_{checkpoint_info}_seed{args.seed}_eps{args.num_traj}"
    eef_save_dir = os.path.join(args.eef_save_dir, args.dataset_name, run_folder_name)
    os.makedirs(eef_save_dir, exist_ok=True)
    
    print(f"\n📁 本次评估输出目录: {eef_save_dir}")
    
    # ======== 循环评估所有任务 ========
    print("\n" + "="*80)
    print(f"开始评估 {len(task_range)} 个任务 (带 EEF 追踪)...")
    print("="*80)
    
    all_start_time = time.time()
    all_success_rates = []
    all_success_counts = []
    all_eef_data = []
    
    for task_id in task_range:
        success_rate, num_success, task_name, instruction, eef_data = evaluate_single_task_with_eef_tracking(
            task_id=task_id,
            policy=policy,
            device=device,
            benchmark_dict=benchmark_dict,
            args=args,
            checkpoint_identifier=checkpoint_identifier
        )
        
        all_success_rates.append(success_rate)
        all_success_counts.append(num_success)
        all_eef_data.append(eef_data)
        
        # 保存 EEF 轨迹数据
        eef_json_path = os.path.join(eef_save_dir, f"task{task_id}_eef_trajectories.json")
        with open(eef_json_path, 'w') as f:
            json.dump(eef_data, f, indent=2)
        print(f"  💾 EEF 轨迹已保存: {eef_json_path}")
    
    total_time = time.time() - all_start_time
    
    # ======== 生成汇总可视化（所有任务的所有轨迹）========
    # 确定 checkpoint 名称和是否使用 LoRA
    is_lora = args.lora_adapter is not None
    if is_lora:
        checkpoint_name = os.path.basename(args.lora_adapter)
    else:
        checkpoint_name = os.path.basename(args.pretrained_path)
    
    generate_summary_visualizations(
        all_eef_data, 
        eef_save_dir, 
        args.dataset_name,
        checkpoint_name=checkpoint_name,
        is_lora=is_lora,
        num_traj_per_task=args.num_traj
    )
    
    # ======== 计算并保存统计结果 ========
    print("\n" + "="*80)
    print("所有任务评估完成！正在计算统计结果...")
    print("="*80)
    
    run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    write_average_to_csv(
        args.metrics_path,
        args.dataset_name,
        checkpoint_identifier,
        args.seed,
        run_id,
        args.num_traj
    )
    
    # 打印汇总
    avg_success_rate = sum(all_success_rates) / len(all_success_rates)
    total_success = sum(all_success_counts)
    total_episodes = len(task_range) * args.num_traj
    
    print("\n" + "╔" + "═" * 78 + "╗")
    print("║" + " " * 28 + "评估结果汇总" + " " * 38 + "║")
    print("╠" + "═" * 78 + "╣")
    print(f"║ 数据集           : {args.dataset_name:<58} ║")
    print(f"║ Checkpoint       : {os.path.basename(checkpoint_identifier):<58} ║")
    print(f"║ 随机种子         : {args.seed:<58} ║")
    print("╠" + "═" * 78 + "╣")
    print(f"║ 评估任务总数     : {len(task_range):<58} ║")
    print(f"║ 每任务评估轮次   : {args.num_traj:<58} ║")
    print(f"║ 总评估轮次       : {total_episodes:<58} ║")
    print("╠" + "═" * 78 + "╣")
    print(f"║ ✓ 平均成功率     : {avg_success_rate * 100:>6.2f}%{' ' * 50} ║")
    print(f"║ ✓ 成功轮次       : {total_success}/{total_episodes}{' ' * (52 - len(str(total_success)) - len(str(total_episodes)))} ║")
    print("╠" + "═" * 78 + "╣")
    print(f"║ ⏱ 模型加载时间   : {model_load_time:>6.1f}秒{' ' * 48} ║")
    print(f"║ ⏱ 评估总时间     : {total_time:>6.1f}秒{' ' * 48} ║")
    print(f"║ ⏱ 平均每任务     : {total_time/len(task_range):>6.1f}秒{' ' * 48} ║")
    print("╚" + "═" * 78 + "╝")
    
    print(f"\n✅ 评估结果已保存到: {args.metrics_path}")
    print(f"📊 EEF 轨迹数据保存目录: {eef_save_dir}")
    print(f"🎨 可视化图表保存目录: {os.path.join(eef_save_dir, 'visualizations')}")
    print(f"⏱ 总耗时: {model_load_time + total_time:.1f}秒")


if __name__ == "__main__":
    main()

