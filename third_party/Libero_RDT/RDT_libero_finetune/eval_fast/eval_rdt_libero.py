#!/usr/bin/env python3
"""
RDT-LIBERO Evaluation Script using Isaac-GR00T Framework

This script evaluates RDT models on LIBERO benchmark tasks using the
gymnasium-based evaluation framework from Isaac-GR00T.

Usage:
    python eval_fast/eval_rdt_libero.py --config eval_fast/config/eval_config.yaml
    
Or with command line arguments:
    python eval_fast/eval_rdt_libero.py \
        --pretrained-path checkpoints/your_checkpoint \
        --dataset-name libero_10 \
        --num-episodes 20
"""

import argparse
import csv
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml

# Setup paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
GROOT_ROOT = os.path.join(PROJECT_ROOT, "..", "Isaac-GR00T")
LIBERO_ROOT = os.path.join(GROOT_ROOT, "external_dependencies", "LIBERO")

# Add paths
for path in [PROJECT_ROOT, GROOT_ROOT, LIBERO_ROOT]:
    if path not in sys.path:
        sys.path.insert(0, path)

# Set environment variables for rendering
os.environ.setdefault("MUJOCO_GL", "egl")
os.environ.setdefault("PYOPENGL_PLATFORM", "egl")


@dataclass
class EvalConfig:
    """Evaluation configuration."""
    # Model
    pretrained_path: str = ""
    lora_adapter: str | None = None
    config_path: str = "configs/base.yaml"
    
    # Encoders
    text_encoder: str = "google/t5-v1_1-xxl"
    vision_encoder: str = "google/siglip-so400m-patch14-384"
    
    # Dataset
    dataset_name: str = "libero_10"
    
    # Evaluation
    num_episodes: int = 20
    max_episode_steps: int = 720
    n_action_steps: int = 8
    n_envs: int = 1
    seed: int = 20241201
    gpu: int = 0
    
    # Output
    output_dir: str = "outs/eval_results"
    save_video: bool = False
    video_dir: str = "outs/eval_videos"


def parse_args() -> EvalConfig:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="RDT-LIBERO Evaluation")
    
    # Config file
    parser.add_argument("--config", type=str, default=None,
                        help="Path to YAML config file")
    
    # Model arguments
    parser.add_argument("--pretrained-path", type=str, default=None)
    parser.add_argument("--lora-adapter", type=str, default=None)
    parser.add_argument("--config-path", type=str, default="configs/base.yaml")
    parser.add_argument("--text-encoder", type=str, default="google/t5-v1_1-xxl")
    parser.add_argument("--vision-encoder", type=str, default="google/siglip-so400m-patch14-384")
    
    # Dataset arguments
    parser.add_argument("--dataset-name", type=str, default="libero_10",
                        choices=["libero_10", "libero_90", "libero_spatial", 
                                "libero_object", "libero_goal"])
    
    # Evaluation arguments
    parser.add_argument("--num-episodes", type=int, default=20)
    parser.add_argument("--max-episode-steps", type=int, default=720)
    parser.add_argument("--n-action-steps", type=int, default=8)
    parser.add_argument("--n-envs", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20241201)
    parser.add_argument("--gpu", type=int, default=0)
    
    # Output arguments
    parser.add_argument("--output-dir", type=str, default="outs/eval_results")
    parser.add_argument("--save-video", action="store_true")
    parser.add_argument("--video-dir", type=str, default="outs/eval_videos")
    
    args = parser.parse_args()
    
    # Load config file if provided
    config = EvalConfig()
    if args.config:
        with open(args.config, 'r') as f:
            yaml_config = yaml.safe_load(f)
        
        # Map YAML config to EvalConfig
        if 'model' in yaml_config:
            config.pretrained_path = yaml_config['model'].get('pretrained_path', config.pretrained_path)
            config.lora_adapter = yaml_config['model'].get('lora_adapter')
        if 'dataset' in yaml_config:
            config.dataset_name = yaml_config['dataset'].get('name', config.dataset_name)
        if 'evaluation' in yaml_config:
            eval_cfg = yaml_config['evaluation']
            config.num_episodes = eval_cfg.get('num_traj', config.num_episodes)
            config.seed = eval_cfg.get('seed', config.seed)
            config.gpu = eval_cfg.get('gpu', config.gpu)
            config.n_action_steps = eval_cfg.get('exec_horizon', config.n_action_steps)
            if 'video' in eval_cfg:
                config.save_video = eval_cfg['video'].get('save_interval', 0) > 0
                config.video_dir = eval_cfg['video'].get('root_dir', config.video_dir)
        if 'output' in yaml_config:
            config.output_dir = yaml_config['output'].get('metrics_dir', config.output_dir)
    
    # Override with command line arguments
    if args.pretrained_path:
        config.pretrained_path = args.pretrained_path
    if args.lora_adapter:
        config.lora_adapter = args.lora_adapter
    if args.config_path:
        config.config_path = args.config_path
    if args.text_encoder:
        config.text_encoder = args.text_encoder
    if args.vision_encoder:
        config.vision_encoder = args.vision_encoder
    if args.dataset_name:
        config.dataset_name = args.dataset_name
    if args.num_episodes:
        config.num_episodes = args.num_episodes
    if args.max_episode_steps:
        config.max_episode_steps = args.max_episode_steps
    if args.n_action_steps:
        config.n_action_steps = args.n_action_steps
    if args.n_envs:
        config.n_envs = args.n_envs
    if args.seed:
        config.seed = args.seed
    if args.gpu is not None:
        config.gpu = args.gpu
    if args.output_dir:
        config.output_dir = args.output_dir
    if args.save_video:
        config.save_video = args.save_video
    if args.video_dir:
        config.video_dir = args.video_dir
    
    # Validate
    if not config.pretrained_path:
        parser.error("--pretrained-path is required")
    
    return config


def get_task_list(dataset_name: str) -> list[str]:
    """Get list of task names for a dataset."""
    from libero.libero import benchmark
    
    benchmark_dict = benchmark.get_benchmark_dict()
    task_suite = benchmark_dict[dataset_name]()
    return [task_suite.get_task(i).name for i in range(task_suite.get_num_tasks())]


def create_env(task_name: str, max_episode_steps: int = 720):
    """Create a LIBERO environment for a specific task."""
    import gymnasium as gym
    from gr00t.eval.sim.LIBERO.libero_env import register_libero_envs
    
    # Register all LIBERO environments
    register_libero_envs()
    
    # Create environment
    env_id = f"libero_sim/{task_name}"
    env = gym.make(env_id)
    
    return env


def run_single_task_evaluation(
    task_name: str,
    policy,
    config: EvalConfig,
) -> dict[str, Any]:
    """
    Run evaluation on a single task.
    
    Returns:
        Dictionary with evaluation results
    """
    import gymnasium as gym
    
    print(f"\n{'='*60}")
    print(f"Evaluating: {task_name}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    # Create environment
    env = create_env(task_name, config.max_episode_steps)
    
    # Set seed
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    
    # Run episodes
    successes = []
    episode_lengths = []
    
    for ep in range(config.num_episodes):
        obs, info = env.reset(seed=config.seed + ep)
        policy.reset()
        
        done = False
        step = 0
        episode_success = False
        
        while not done and step < config.max_episode_steps:
            # Prepare batched observation
            batched_obs = {}
            for key, value in obs.items():
                if isinstance(value, np.ndarray):
                    # Add batch and temporal dimensions
                    if value.ndim == 3:  # Image (H, W, C)
                        batched_obs[key] = value[np.newaxis, np.newaxis, ...]  # (1, 1, H, W, C)
                    elif value.ndim == 1:  # State
                        batched_obs[key] = value[np.newaxis, np.newaxis, ...]  # (1, 1, D)
                    else:
                        batched_obs[key] = value[np.newaxis, ...]
                elif isinstance(value, str):
                    batched_obs[key] = (value,)
                else:
                    batched_obs[key] = value
            
            # Get action
            action_dict, _ = policy.get_action(batched_obs)
            
            # Unbatch action
            action = {k: v[0] for k, v in action_dict.items()}
            
            # Step environment
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            step += 1
            
            # Check success
            if info.get("success", False):
                episode_success = True
        
        successes.append(episode_success)
        episode_lengths.append(step)
        
        status = "✓" if episode_success else "✗"
        print(f"  Episode {ep+1}/{config.num_episodes}: {status} (steps: {step})")
    
    env.close()
    
    elapsed = time.time() - start_time
    success_rate = np.mean(successes)
    
    print(f"\nTask Summary:")
    print(f"  Success Rate: {success_rate*100:.1f}% ({sum(successes)}/{len(successes)})")
    print(f"  Avg Episode Length: {np.mean(episode_lengths):.1f}")
    print(f"  Time: {elapsed:.1f}s")
    
    return {
        "task_name": task_name,
        "success_rate": success_rate,
        "num_successes": sum(successes),
        "num_episodes": len(successes),
        "avg_episode_length": np.mean(episode_lengths),
        "time": elapsed,
    }


def save_results(results: list[dict], config: EvalConfig):
    """Save evaluation results to CSV."""
    os.makedirs(config.output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ckpt_name = os.path.basename(config.pretrained_path)
    filename = f"{config.dataset_name}_{ckpt_name}_seed{config.seed}_{timestamp}.csv"
    filepath = os.path.join(config.output_dir, filename)
    
    with open(filepath, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            "task_name", "success_rate", "num_successes", 
            "num_episodes", "avg_episode_length", "time"
        ])
        writer.writeheader()
        writer.writerows(results)
        
        # Add summary row
        avg_success = np.mean([r["success_rate"] for r in results])
        total_success = sum(r["num_successes"] for r in results)
        total_episodes = sum(r["num_episodes"] for r in results)
        total_time = sum(r["time"] for r in results)
        
        writer.writerow({
            "task_name": "AVERAGE",
            "success_rate": avg_success,
            "num_successes": total_success,
            "num_episodes": total_episodes,
            "avg_episode_length": np.mean([r["avg_episode_length"] for r in results]),
            "time": total_time,
        })
    
    print(f"\nResults saved to: {filepath}")
    return filepath


def main():
    """Main evaluation function."""
    config = parse_args()
    
    # Set GPU
    os.environ["CUDA_VISIBLE_DEVICES"] = str(config.gpu)
    
    print("="*60)
    print("RDT-LIBERO Evaluation")
    print("="*60)
    print(f"Dataset: {config.dataset_name}")
    print(f"Checkpoint: {config.pretrained_path}")
    if config.lora_adapter:
        print(f"LoRA Adapter: {config.lora_adapter}")
    print(f"Episodes per task: {config.num_episodes}")
    print(f"Action steps: {config.n_action_steps}")
    print(f"GPU: {config.gpu}")
    print(f"Seed: {config.seed}")
    print("="*60)
    
    # Get task list
    tasks = get_task_list(config.dataset_name)
    print(f"\nFound {len(tasks)} tasks in {config.dataset_name}")
    
    # Initialize policy
    print("\n" + "="*60)
    print("Loading RDT Policy...")
    print("="*60)
    
    from rdt_policy import RDTPolicy
    
    policy = RDTPolicy(
        config_path=os.path.join(PROJECT_ROOT, config.config_path),
        pretrained_path=config.pretrained_path,
        lora_adapter_path=config.lora_adapter,
        device="cuda:0",
        n_action_steps=config.n_action_steps,
        pretrained_text_encoder=os.path.join(PROJECT_ROOT, config.text_encoder),
        pretrained_vision_encoder=os.path.join(PROJECT_ROOT, config.vision_encoder),
    )
    
    print("Policy loaded successfully!")
    
    # Run evaluation
    print("\n" + "="*60)
    print(f"Starting evaluation on {len(tasks)} tasks...")
    print("="*60)
    
    results = []
    total_start = time.time()
    
    for i, task_name in enumerate(tasks):
        print(f"\n[{i+1}/{len(tasks)}]", end="")
        result = run_single_task_evaluation(task_name, policy, config)
        results.append(result)
    
    total_time = time.time() - total_start
    
    # Print summary
    avg_success = np.mean([r["success_rate"] for r in results])
    total_successes = sum(r["num_successes"] for r in results)
    total_episodes = sum(r["num_episodes"] for r in results)
    
    print("\n" + "="*60)
    print("EVALUATION COMPLETE")
    print("="*60)
    print(f"Dataset: {config.dataset_name}")
    print(f"Total Tasks: {len(tasks)}")
    print(f"Episodes per Task: {config.num_episodes}")
    print(f"Total Episodes: {total_episodes}")
    print("-"*60)
    print(f"Average Success Rate: {avg_success*100:.2f}%")
    print(f"Total Successes: {total_successes}/{total_episodes}")
    print(f"Total Time: {total_time:.1f}s ({total_time/60:.1f}min)")
    print("="*60)
    
    # Save results
    save_results(results, config)


if __name__ == "__main__":
    main()

