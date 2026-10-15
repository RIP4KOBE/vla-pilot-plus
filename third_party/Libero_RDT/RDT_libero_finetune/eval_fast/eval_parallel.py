#!/usr/bin/env python3
"""
Fast Parallel RDT-LIBERO Evaluation

Uses SubprocVectorEnv for parallel episode execution, matching the original
RDT evaluation speed.

Usage:
    python eval_fast/eval_parallel.py \
        --checkpoint ./checkpoints/RDT-1B-Full-libero_10.../checkpoint-28000 \
        --dataset libero_10 \
        --num-episodes 20 \
        --num-envs 20
"""

import argparse
import os
import sys
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
from PIL import Image

# Setup paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
GROOT_ROOT = os.path.join(PROJECT_ROOT, "..", "Isaac-GR00T")
LIBERO_ROOT = os.path.join(GROOT_ROOT, "external_dependencies", "LIBERO")

for path in [PROJECT_ROOT, GROOT_ROOT, LIBERO_ROOT]:
    if path not in sys.path:
        sys.path.insert(0, path)

os.environ.setdefault("MUJOCO_GL", "egl")
os.environ.setdefault("PYOPENGL_PLATFORM", "egl")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=str, required=True, help="Checkpoint path")
    parser.add_argument("--lora-adapter", type=str, default=None, help="LoRA adapter path")
    parser.add_argument("--dataset", type=str, default="libero_10", 
                       choices=["libero_10", "libero_90", "libero_spatial", "libero_object", "libero_goal"])
    parser.add_argument("--num-episodes", type=int, default=20, help="Episodes per task")
    parser.add_argument("--num-envs", type=int, default=20, help="Parallel environments")
    parser.add_argument("--exec-horizon", type=int, default=8, help="Action chunk execution steps")
    parser.add_argument("--max-steps", type=int, default=720, help="Max steps per episode")
    parser.add_argument("--seed", type=int, default=20241201)
    parser.add_argument("--gpu", type=int, default=0)
    parser.add_argument("--output-dir", type=str, default="outs/results")
    return parser.parse_args()


def get_obs_item(obs, key, idx):
    """Extract observation item handling different formats from SubprocVectorEnv.
    
    SubprocVectorEnv can return:
    - numpy array of dicts: obs[idx][key]
    - dict of arrays: obs[key][idx]
    - list of dicts: obs[idx][key]
    """
    if isinstance(obs, np.ndarray) and obs.dtype == object:
        # numpy array of dicts (e.g., from set_init_state)
        return obs[idx][key]
    elif isinstance(obs, dict):
        # dict of arrays
        return obs[key][idx]
    elif isinstance(obs, (list, tuple)):
        # list of dicts
        return obs[idx][key]
    else:
        # Fallback
        try:
            return obs[idx][key]
        except:
            return obs[key][idx]


def main():
    args = parse_args()
    
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16
    
    print("=" * 60)
    print("Fast Parallel RDT-LIBERO Evaluation")
    print("=" * 60)
    print(f"Checkpoint: {args.checkpoint}")
    print(f"Dataset: {args.dataset}")
    print(f"Episodes: {args.num_episodes}, Parallel Envs: {args.num_envs}")
    print(f"Exec Horizon: {args.exec_horizon}")
    print("=" * 60)
    
    # Import LIBERO components
    from libero.libero import benchmark
    from libero.libero.envs import OffScreenRenderEnv, SubprocVectorEnv
    
    # Import RDT model
    from libero_eval.libero_rdt_model import create_model
    import yaml
    
    # Load config
    config_path = os.path.join(PROJECT_ROOT, "configs/base.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Load model
    print("\nLoading RDT model...")
    policy = create_model(
        args=config,
        dtype=dtype,
        pretrained=args.checkpoint,
        lora_adapter_path=args.lora_adapter,
        pretrained_text_encoder_name_or_path="google/t5-v1_1-xxl",
        pretrained_vision_encoder_name_or_path="google/siglip-so400m-patch14-384",
    )
    policy.reset()
    print("Model loaded!")
    
    # Get tasks
    benchmark_dict = benchmark.get_benchmark_dict()
    task_suite = benchmark_dict[args.dataset]()
    num_tasks = task_suite.get_num_tasks()
    
    # Prepare output
    os.makedirs(args.output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ckpt_name = os.path.basename(args.checkpoint)
    results_file = os.path.join(
        args.output_dir, 
        f"{args.dataset}_{ckpt_name}_seed{args.seed}_{timestamp}.csv"
    )
    
    with open(results_file, "w") as f:
        f.write("task_id,task_name,success_rate,num_success,num_episodes,avg_steps\n")
    
    all_success_rates = []
    
    # Evaluate each task
    for task_id in range(num_tasks):
        task = task_suite.get_task(task_id)
        task_name = task.name
        bddl_file = os.path.join(
            benchmark.get_libero_path("bddl_files"),
            task.problem_folder,
            task.bddl_file,
        )
        instruction = task.language
        
        print(f"\n[{task_id+1}/{num_tasks}] {task_name}")
        
        # Pre-encode language
        text_embed = policy.encode_instruction(instruction)
        text_embed = text_embed.to(device=device, dtype=dtype)
        
        # Create parallel environments
        env_num = min(args.num_envs, args.num_episodes)
        env_args = dict(
            bddl_file_name=bddl_file,
            camera_heights=128,
            camera_widths=128,
        )
        
        env = SubprocVectorEnv(
            [lambda: OffScreenRenderEnv(**env_args) for _ in range(env_num)]
        )
        env.seed(args.seed)
        
        # Get initial states
        init_states = task_suite.get_task_init_states(task_id)
        
        total_success = 0
        total_steps = 0
        episodes_done = 0
        
        # Run episodes in batches
        while episodes_done < args.num_episodes:
            batch_size = min(env_num, args.num_episodes - episodes_done)
            
            # Reset environments
            env.reset()
            indices = np.arange(batch_size) % len(init_states)
            obs = env.set_init_state(init_states[indices])
            
            # Initialize tracking
            agentview_windows = [deque(maxlen=2) for _ in range(batch_size)]
            eye_in_hand_windows = [deque(maxlen=2) for _ in range(batch_size)]
            proprios = [None] * batch_size
            action_buffers = [None] * batch_size
            action_counters = [0] * batch_size
            dones = [False] * batch_size
            step_counts = [0] * batch_size
            
            # Initialize image history
            for i in range(batch_size):
                agent_img = get_obs_item(obs, "agentview_image", i)
                eye_img = get_obs_item(obs, "robot0_eye_in_hand_image", i)
                for _ in range(2):
                    agentview_windows[i].append(agent_img)
                    eye_in_hand_windows[i].append(eye_img)
                
                joint_pos = get_obs_item(obs, "robot0_joint_pos", i)
                gripper_qpos = get_obs_item(obs, "robot0_gripper_qpos", i)
                proprio = np.concatenate([joint_pos, gripper_qpos]).astype(np.float32)
                proprios[i] = torch.from_numpy(proprio).to(device, dtype)
            
            # Warm up physics
            for _ in range(5):
                env.step(np.zeros((batch_size, 7), dtype=np.float32))
            
            # Run episode
            global_step = 0
            while global_step < args.max_steps and not all(dones):
                actions = np.zeros((batch_size, 7), dtype=np.float32)
                
                with torch.inference_mode():
                    for i in range(batch_size):
                        if dones[i]:
                            continue
                        
                        # Check if need new inference
                        if action_buffers[i] is None or action_counters[i] >= args.exec_horizon:
                            # Prepare images
                            images = []
                            for t in range(2):
                                images.append(Image.fromarray(agentview_windows[i][t]))
                                images.append(Image.fromarray(eye_in_hand_windows[i][t]))
                                images.append(None)  # Third camera placeholder
                            
                            # Run inference
                            action_seq = policy.step(proprios[i], images, text_embed)
                            action_seq = action_seq.squeeze(0).cpu().numpy()
                            
                            if np.any(np.isnan(action_seq)) or np.any(np.isinf(action_seq)):
                                action_seq = np.zeros_like(action_seq)
                            
                            action_buffers[i] = action_seq
                            action_counters[i] = 0
                        
                        # Get action from buffer
                        actions[i] = action_buffers[i][action_counters[i]]
                        action_counters[i] += 1
                
                # Step all environments
                obs, rewards, done_flags, infos = env.step(actions)
                global_step += 1
                
                # Update state
                for i in range(batch_size):
                    if dones[i]:
                        continue
                    
                    step_counts[i] += 1
                    
                    # Check done
                    if done_flags[i] or infos[i].get("success", False):
                        dones[i] = True
                        if infos[i].get("success", False):
                            total_success += 1
                        total_steps += step_counts[i]
                        continue
                    
                    # Update observations
                    agent_img = get_obs_item(obs, "agentview_image", i)
                    eye_img = get_obs_item(obs, "robot0_eye_in_hand_image", i)
                    agentview_windows[i].append(agent_img)
                    eye_in_hand_windows[i].append(eye_img)
                    
                    joint_pos = get_obs_item(obs, "robot0_joint_pos", i)
                    gripper_qpos = get_obs_item(obs, "robot0_gripper_qpos", i)
                    proprio = np.concatenate([joint_pos, gripper_qpos]).astype(np.float32)
                    proprios[i] = torch.from_numpy(proprio).to(device, dtype)
            
            # Count completed episodes
            episodes_done += batch_size
        
        env.close()
        
        # Calculate stats
        success_rate = total_success / args.num_episodes
        avg_steps = total_steps / args.num_episodes if args.num_episodes > 0 else 0
        all_success_rates.append(success_rate)
        
        print(f"  Success: {total_success}/{args.num_episodes} ({success_rate*100:.1f}%)")
        
        # Save result
        with open(results_file, "a") as f:
            f.write(f"{task_id},{task_name},{success_rate:.4f},{total_success},{args.num_episodes},{avg_steps:.1f}\n")
    
    # Summary
    avg_success = np.mean(all_success_rates)
    print("\n" + "=" * 60)
    print(f"Overall Success Rate: {avg_success*100:.1f}%")
    print(f"Results saved to: {results_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()

