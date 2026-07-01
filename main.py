"""
VLS Main Entry Point - Supports multiple backends (CALVIN, LIBERO, RealWorld)

Uses Hydra for configuration management and EnvAdapter abstraction layer.

Usage:
    python main.py                                    # Default: libero backend
    python main.py env=calvin task=drawer_open        # CALVIN + drawer_open task
    python main.py env=calvin task=door_left          # CALVIN + other tasks
    python main.py env=libero                         # LIBERO backend (explicit)
    python main.py main.episode_num=50                # Override parameters
"""

import os
import inspect
import warnings
from pathlib import Path
# Suppress pydantic v2 Field attribute warnings from third-party PI05 config classes
warnings.filterwarnings("ignore", category=UserWarning, message=".*'repr'.*Field.*")
warnings.filterwarnings("ignore", category=UserWarning, message=".*'frozen'.*Field.*")
# Load .env before anything else
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass
# Set tokenizers parallelism to false to avoid fork warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"
# Disable torch inductor/Triton compilation — PyTorch 2.7+cu118 generates invalid
# chained broadcast_to() calls in its SDPA fallback kernel, causing CompilationError.
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")

from typing import Any, Callable, List, Optional
import gymnasium as gym
import numpy as np
import torch
from collections import deque
from PIL import Image
import cv2
import imageio
from functools import partial
import matplotlib.pyplot as plt
import h5py
import random
from dataclasses import dataclass, field
import tqdm
import time
import sys
import json
import warnings

# Hydra imports
import hydra
from omegaconf import DictConfig, ListConfig, OmegaConf

warnings.filterwarnings('ignore', category=FutureWarning, message='.*pynvml.*')
warnings.filterwarnings('ignore', category=UserWarning, message='.*pkg_resources.*')
warnings.filterwarnings('ignore', category=UserWarning, message='.*xFormers.*')
warnings.filterwarnings('ignore', category=UserWarning, message='.*env.get_obs.*')


def _config_section_to_dict(section: Any, section_name: str) -> dict:
    """Return a fresh plain dict for optional grouped config sections."""
    if section is None:
        return {}
    if isinstance(section, dict):
        return dict(section)
    if isinstance(section, (DictConfig, ListConfig)):
        section = OmegaConf.to_container(section, resolve=True)
        if section is None:
            return {}
        if isinstance(section, dict):
            return dict(section)
        raise TypeError(f"{section_name} must be a mapping, got {type(section).__name__}")
    raise TypeError(f"{section_name} must be a mapping, got {type(section).__name__}")


def _adapter_actual_task_id(adapter: Any) -> int | None:
    """Return the dataset task id, preserving filtered LIBERO task ids."""
    current_task_idx = getattr(adapter, "current_task_idx", None)
    envs = getattr(adapter, "_env", None)
    if current_task_idx is not None and envs is not None:
        try:
            current_env = envs[int(current_task_idx)]
            task_id = getattr(current_env, "task_id", None)
            if task_id is not None:
                return int(task_id)
        except (IndexError, KeyError, TypeError, ValueError):
            pass

    task_id = getattr(adapter, "task_id", None)
    if task_id is not None:
        try:
            return int(task_id)
        except (TypeError, ValueError):
            pass

    if current_task_idx is not None:
        try:
            return int(current_task_idx)
        except (TypeError, ValueError):
            return None
    return None

# Add project root to path (for local modules like steer_utils, utils, etc.)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Monkey-patch calvin_env Light class with our modified version (supports initial_state config)
from patches.light import Light as PatchedLight, LightState as PatchedLightState
sys.modules['calvin_env.scene.objects.light'] = type(sys)('calvin_env.scene.objects.light')
sys.modules['calvin_env.scene.objects.light'].Light = PatchedLight
sys.modules['calvin_env.scene.objects.light'].LightState = PatchedLightState

# Import adapters
from core.env_adapters import create_adapter, BaseEnvAdapter
from core.keypoint_tracker import KeypointTracker
from core.keypoint_detector import KeypointDetector
from core.sam3_segmenter import create_segmenter as create_sam3_segmenter
from core.gemini_grounder import create_gemini_grounder, create_gemini_stage_recognizer
from vlm_query.vlm_agent import VLMAgent
from utils.vis_utils import TrajectoryVideoRecorder, add_text_to_image
from utils.eds_eval_vis import save_eds_qualitative_artifacts
from utils.eds_mechanism_pretest_vis import save_eds_mechanism_pretest_artifacts

from core.policy_observation_sampling import policy_observation_sample_num
from core.eds_eval_metrics import append_jsonl
from core.eds_mechanism_trace import build_run_id, save_mechanism_trace

# Import logging utility
from utils.logging_utils import SteerLogger

# Create logger instance
log = SteerLogger("Main")


def _get_visualization_action_chunk(policy: Any, adapter: Any, action_chunk: torch.Tensor) -> torch.Tensor:
    get_candidates = getattr(policy, "get_last_visualization_action_candidates", None)
    if not callable(get_candidates):
        return action_chunk

    candidates = get_candidates()
    if candidates is None:
        return action_chunk

    if hasattr(adapter, "env_postprocessor"):
        transition = adapter.env_postprocessor({"action": candidates})
        return transition["action"]
    return candidates


class Main:
    def __init__(self, cfg: DictConfig):
        """
        Initialize with Hydra DictConfig.

        Args:
            cfg: Hydra configuration (OmegaConf DictConfig)
        """
        self.cfg = cfg
        self.config = cfg.main  # Shortcut to main config section

        # Log the resolved configuration
        log.info(f"Configuration:\n{OmegaConf.to_yaml(cfg, resolve=True)[:500]}...")

        # Set random seed
        seed = cfg.get('seed', 0)
        np.random.seed(seed)
        torch.manual_seed(seed)
        torch.cuda.manual_seed(seed)

        # Get backend from config
        self.backend = cfg.backend.get('backend', 'calvin')
        log.info(f"Using backend: {self.backend}")

        # Get backend-specific config
        env_config = OmegaConf.to_container(cfg.backend.get(self.backend, {}), resolve=True)

        # Add main.episode_num to env_config for adapters that need it (e.g., LiberoAdapter)
        env_config['episode_num'] = self.config.get('episode_num', 10)
        # Pass task instruction from cfg.main (set by task config) so adapter can surface it
        if self.config.get('instruction', ''):
            env_config['instruction'] = self.config.get('instruction')

        # Create adapter
        self.adapter = create_adapter(self.backend, env_config)

        # Get task info from adapter for guidance adjustment
        task_info = self.adapter.get_task_info()
        instruction = task_info.get('instruction', '')
        recommended_scale = task_info.get('recommended_guide_scale')
        vls_config = _config_section_to_dict(self.config.get('vls_config'), "main.vls_config")
        base_guide_scale = vls_config.get('guide_scale', 80.0)

        # Override with recommended scale if available
        if recommended_scale is not None:
            self.current_guide_scale = recommended_scale
            if recommended_scale != base_guide_scale:
                log.info(f"Task '{instruction}' uses custom guide_scale={recommended_scale} (base: {base_guide_scale})")
            else:
                log.info(f"Using guide_scale: {recommended_scale} for task: '{instruction}'")
        else:
            self.current_guide_scale = base_guide_scale
            log.info(f"Using default guide_scale: {base_guide_scale}")

        # Initialize policy
        policy_config = cfg.get('policy', {})
        policy_type = policy_config.get('type', 'diffusion')
        self.policy_type = policy_type
        log.info(f"Policy config type: {policy_type}")

        # Get pretrained_path from the specific policy type config
        type_config = policy_config.get(policy_type, {})
        pretrained_path = type_config.get('pretrained_path', 'Vision-Language-Steering/vls_calvin_base')
        log.info(f"Loading {policy_type} from: {pretrained_path}")

        if policy_type == 'diffusion':
            from core.diffusion_policy_steer import DiffusionPolicySteer

            self.policy = DiffusionPolicySteer.from_pretrained(pretrained_path)
        elif policy_type == 'pi05':
            from core.pi05_steer import PI05PolicySteer

            self.policy = PI05PolicySteer.from_pretrained(pretrained_path)
        elif policy_type == 'rdt':
            from core.rdt_policy_steer import RDTSteer

            raw_num_steps = type_config.get('num_inference_steps', None)
            num_steps = None if raw_num_steps is None else int(raw_num_steps)
            self.policy = RDTSteer.from_pretrained(
                pretrained_path,
                num_inference_steps=num_steps,
                vision_encoder=type_config.get(
                    'vision_encoder',
                    '/mnt/data/hf_cache/hub/models--google--siglip-so400m-patch14-384',
                ),
                text_encoder=type_config.get(
                    'text_encoder',
                    '/mnt/data/hf_cache/hub/models--google--t5-v1_1-xxl',
                ),
                weight_variant=type_config.get('weight_variant', 'ema'),
                control_frequency=int(type_config.get('control_frequency', 20)),
            )
        else:
            raise ValueError(f"Unknown policy type: {policy_type}")

        self.device = cfg.get('device', 'cuda')
        self.policy.to(self.device)

        if policy_type == 'rdt':
            # RDTSteer handles all obs/action processing internally.
            self.policy_preprocessor = lambda x: x
            self.policy_postprocessor = lambda x: x
        else:
            from lerobot.policies.factory import make_pre_post_processors

            preprocessor_overrides = {
                "device_processor": {"device": str(self.policy.config.device)},
            }
            self.policy_preprocessor, self.policy_postprocessor = make_pre_post_processors(
                policy_cfg=self.policy.config,
                pretrained_path=pretrained_path,
                preprocessor_overrides=preprocessor_overrides,
            )

        self.policy.post_init(
            adapter=self.adapter,
            postprocessor=self.policy_postprocessor,
            sample_batch_size=_config_section_to_dict(
                self.config.get('vls_config'),
                "main.vls_config",
            ).get('sample_batch_size', 1),
            policy_config=policy_config.get(policy_type, {}),
        )

        self.policy.eval()
        log.info(f"Loaded {policy_type} policy from {pretrained_path}")

        # Output directory (use Hydra's output directory directly)
        self.output_dir = self.config.get('output_dir', 'results/')
        # Ensure it ends with /
        if not self.output_dir.endswith('/'):
            self.output_dir += '/'
        os.makedirs(self.output_dir, exist_ok=True)

        # Initialize components
        self._init_components(cfg)

        # Reset environment and policy
        # self.adapter.reset()
        self.policy.reset()

    def _init_components(self, cfg: DictConfig):
        """Initialize components."""
        if not self.config.get("use_guidance", True):
            self.keypoint_detector = None
            self.sam3_segmenter = None
            self.use_sam3 = False
            self.gemini_grounder = None
            self.gemini_default_objects = []
            self.use_gemini = False
            self.keypoint_tracker = None
            self.vlm_agent = None
            self.gemini_stage_recognizer = None
            self.video_recorder = TrajectoryVideoRecorder(output_dir=self.output_dir)
            self.cached_functions_dir = self.config.get('cached_functions_dir', None)
            return

        # Get perception config (loaded from perception.yaml with @package perception)
        perception_cfg = cfg.get('perception', {})

        # Initialize keypoint detector
        kp_config = OmegaConf.to_container(perception_cfg.get('keypoint_detector', {}), resolve=True)
        self.keypoint_detector = KeypointDetector(config=kp_config)

        # Initialize SAM3 segmenter if enabled
        sam3_config = perception_cfg.get('sam3', {})
        self.use_sam3 = sam3_config.get('enabled', False) if sam3_config else False
        if self.use_sam3:
            log.info("Initializing SAM3 segmenter for text-prompted segmentation")
            sam3_dict = OmegaConf.to_container(sam3_config, resolve=True)
            self.sam3_segmenter = create_sam3_segmenter(sam3_dict)
            self.sam3_default_objects = sam3_config.get('default_objects', [])
        else:
            self.sam3_segmenter = None

        # Initialize Gemini grounder if enabled
        gemini_config = perception_cfg.get('gemini_grounding', {})
        self.use_gemini = gemini_config.get('enabled', False) if gemini_config else False
        if self.use_gemini:
            api_key = gemini_config.get('api_key') or os.environ.get('GOOGLE_API_KEY')
            if api_key:
                gemini_dict = OmegaConf.to_container(gemini_config, resolve=True)
                gemini_dict['api_key'] = api_key
                log.info("Initializing Gemini grounder for visual grounding")
                self.gemini_grounder = create_gemini_grounder(gemini_dict)
                self.gemini_default_objects = list(gemini_config.get('default_objects', []))
            else:
                log.warning("Gemini API key not found - disabling Gemini grounding")
                self.use_gemini = False
                self.gemini_grounder = None
        else:
            self.gemini_grounder = None

        # Initialize keypoint tracker
        self.keypoint_tracker = KeypointTracker(self.adapter)

        # Initialize VLM agent (OpenAI - for generating guidance functions)
        vlm_config = OmegaConf.to_container(perception_cfg.get('vlm_agent', {}), resolve=True)
        # Ensure query_template_dir is absolute path
        if vlm_config.get('query_template_dir') and not os.path.isabs(vlm_config['query_template_dir']):
            vlm_config['query_template_dir'] = os.path.join(PROJECT_ROOT, vlm_config['query_template_dir'])
        self.vlm_agent = VLMAgent(
            config=vlm_config,
            base_dir=self.output_dir,
            env_type=self.backend,
        )

        # Initialize Gemini stage recognizer (for real-time stage recognition)
        gemini_config = OmegaConf.to_container(perception_cfg.get('gemini', {}), resolve=True)
        if self.config.get("use_vlm_stage_recognition", True):
            try:
                self.gemini_stage_recognizer = create_gemini_stage_recognizer(gemini_config)
                log.info("Gemini stage recognizer initialized")
            except Exception as e:
                log.warning(f"Failed to initialize Gemini stage recognizer: {e}")
                self.gemini_stage_recognizer = None
        else:
            self.gemini_stage_recognizer = None

        # Initialize video recorder
        self.video_recorder = TrajectoryVideoRecorder(output_dir=self.output_dir)

        self.cached_functions_dir = self.config.get('cached_functions_dir', None)

    def _get_policy_observation(self) -> dict:
        """Get observation in policy expected format (backend-agnostic)."""
        sample_num = policy_observation_sample_num(
            self.policy_type,
            _config_section_to_dict(
                self.config.get('vls_config'),
                "main.vls_config",
            ).get('sample_batch_size', None),
        )
        observation = self.adapter.get_policy_observation(sample_num=sample_num)

        processed_observation = self.policy_preprocessor(observation)
        return processed_observation

    def perform_task_for_episode(self, episode_dir: str):
        """Prepare for each episode (keypoint detection, guidance generation, etc.)"""
        from utils.guidance_utils import load_functions_from_txt

        # Get keypoint detection inputs from adapter (includes segmentation if available)
        rgb, depth, points, segmentation, segment_id_to_name = self.adapter.get_keypoint_detection_inputs()

        # Get instruction from adapter (backend-specific)
        instruction = self.adapter.get_instruction()
        log.info(f"Task instruction: {instruction}")

        # segmentation = None

        # Check if adapter provided valid segmentation
        has_valid_segmentation = (
            segmentation is not None and
            segment_id_to_name is not None and
            len(segment_id_to_name) > 0
        )

        if has_valid_segmentation:
            log.info(f"Using adapter-provided segmentation with {len(segment_id_to_name)} objects: {list(segment_id_to_name.values())}")
        else:
            log.warning("No valid segmentation from adapter, will use Gemini/SAM3")

            # Get interactable objects from adapter for grounding
            interactable_objects = self.adapter.get_interactable_objects()
            object_names = [obj.name for obj in interactable_objects]
            log.info(f"Interactable objects from adapter: {object_names}")

            # Use Gemini grounding for segmentation (preferred)
            if self.use_gemini and self.gemini_grounder is not None and len(object_names) > 0:
                log.info("Using Gemini for visual grounding")
                log.info(f"Gemini detecting: {object_names}")
                segmentation, segment_id_to_name = self.gemini_grounder.detect_to_segmentation(
                    rgb, object_names
                )

            # Fallback to SAM3
            elif self.use_sam3 and self.sam3_segmenter is not None:
                log.info("Using SAM3 for text-prompted segmentation")

                # Use VLM to plan which objects to segment based on instruction
                planned_objects = self.vlm_agent.plan_segmentation(rgb, instruction)

                if planned_objects and len(planned_objects) > 0:
                    object_names = planned_objects
                    log.info(f"VLM planned segmentation: {object_names}")
                elif len(object_names) == 0:
                    # Last resort: use default objects from config
                    object_names = self.sam3_default_objects
                    log.info(f"Using config default objects: {object_names}")

                segmentation, segment_id_to_name = self.sam3_segmenter.segment(
                    rgb, object_names, return_all_masks=False
                )
            else:
                log.error("No segmentation method available and adapter didn't provide segmentation!")
                raise RuntimeError("Cannot proceed without segmentation")

        # Detect keypoints
        key_points, projected_img, mask_ids = self.keypoint_detector.get_keypoints(
            rgb=rgb,
            points=points,
            segmentation=segmentation,
            segment_id_to_name=segment_id_to_name
        )

        # Register keypoints
        key_points_objects_map = self.keypoint_tracker.register_keypoints(
            key_points,
            mask_ids=mask_ids,
            segment_id_to_name=segment_id_to_name
        )

        # Save for stage recognition (used by Gemini)
        self.init_img_with_keypoints = projected_img  # Initial image with keypoint annotations
        self.keypoint_id_to_object = key_points_objects_map  # Keypoint ID -> object name mapping

        self.vlm_agent.task_dir = os.path.join(episode_dir, 'vlm_agent')
        os.makedirs(self.vlm_agent.task_dir, exist_ok=True)

        # Load or generate guidance functions
        if self.cached_functions_dir is not None:
            guidance_functions_dir = self.cached_functions_dir
            if not os.path.exists(guidance_functions_dir):
                raise ValueError(f"cached_functions_dir does not exist: {guidance_functions_dir}")
            log.info(f"Using cached guidance functions from: {guidance_functions_dir}")
        else:
            # Use instruction from adapter (already retrieved above)
            metadata = {
                'init_keypoint_positions': key_points,
                'num_keypoints': len(key_points),
                'key_points_objects_map': key_points_objects_map
            }
            guidance_functions_dir = self.vlm_agent.generate_guidance(
                projected_img, instruction, metadata
            )

        # Load guidance functions
        with open(os.path.join(guidance_functions_dir, 'metadata.json'), 'r') as f:
            self.program_info = json.load(f)

        self.guidance_fns = dict()
        for stage in range(1, self.program_info['num_stages'] + 1):
            load_path = os.path.join(guidance_functions_dir, f'stage{stage}_guidance.txt')
            self.guidance_fns[stage] = load_functions_from_txt(load_path) if os.path.exists(load_path) else []

        output_raw_path = os.path.join(guidance_functions_dir, 'output_raw.txt')
        self.stage_descriptions = self.vlm_agent._extract_stage_descriptions_from_output(output_raw_path)

        for stage, fns in self.guidance_fns.items():
            log.info(f"Stage {stage}: {len(fns)} guidance functions loaded")
        log.info(f"Loaded {len(self.guidance_fns)} stages total")
        log.debug(f"Stage descriptions:\n{self.stage_descriptions}")

    def _get_gripper_value(self, action_chunk, action_idx: int) -> Optional[float]:
        """Extract gripper value from action chunk."""
        if action_chunk is None:
            return None
        val = action_chunk[0][action_idx][-1]
        return val.item() if hasattr(val, 'item') else val

    def _update_stage(self, state: dict, gripper_val: Optional[float],
                      upper_th: float, lower_th: float) -> dict:
        """
        Update stage recognition state based on reward and gripper triggers.
        Returns updated state dict.
        """
        curr_reward = self.policy.get_normalized_reward()
        prev_reward = state['prev_norm_reward']
        prev_gripper = state['prev_gripper_open']

        # Detect gripper change (action < 0 = OPEN, action > 0 = CLOSE)
        curr_gripper_open = (gripper_val < 0) if gripper_val is not None else None
        gripper_changed = (prev_gripper is not None and curr_gripper_open is not None
                          and curr_gripper_open != prev_gripper)

        # Detect gripper state changes
        gripper_just_closed = gripper_changed and not curr_gripper_open
        gripper_just_opened = gripper_changed and curr_gripper_open

        # Schmitt trigger on reward (only relevant when guidance is active)
        reward_rising = state['use_guidance'] and (prev_reward < upper_th and curr_reward >= upper_th)
        reward_falling = state['use_guidance'] and (prev_reward > lower_th and curr_reward <= lower_th)

        # Build trigger reason (priority: gripper > reward > chunk interval > periodic)
        trigger_reason = None
        if gripper_just_closed:
            trigger_reason = "gripper closed"
        elif gripper_just_opened:
            trigger_reason = "gripper opened"
        elif reward_rising:
            trigger_reason = f"reward rose above {upper_th:.0%}"
        elif reward_falling:
            trigger_reason = f"reward dropped below {lower_th:.0%}"

        # Query VLM if triggered (with limit check)
        vlm_query_limit = self.config.get("vlm_query_limit", 10)
        vlm_query_count = state.get('vlm_query_count', 0)

        if trigger_reason and self.gemini_stage_recognizer is not None and vlm_query_count < vlm_query_limit:
            log.info(f"[Trigger] {trigger_reason} (query {vlm_query_count + 1}/{vlm_query_limit})")

            new_stage, need_guidance = self.gemini_stage_recognizer.identify_stage_and_guidance(
                current_rgb=np.array(self.adapter.get_vlm_image()),
                instruction=self.adapter.get_task_description(),
                stage_descriptions=self.stage_descriptions,
                init_img_with_keypoints=self.init_img_with_keypoints,
                keypoint_id_to_object=self.keypoint_id_to_object,
                num_stages=len(self.guidance_fns),
                trigger_reason=trigger_reason,
            )

            state['vlm_query_count'] = vlm_query_count + 1

            if new_stage != state['current_stage'] or need_guidance != state['use_guidance']:
                log.info(f"[VLM] Stage: {state['current_stage']} → {new_stage}, Guidance: {state['use_guidance']} → {need_guidance}")
                if new_stage != state['current_stage']:
                    self.policy.reset_stage()
                    curr_reward = 0.0  # Reset for new stage

            state.update({
                'current_stage': new_stage,
                'use_guidance': need_guidance,
            })
        elif trigger_reason and vlm_query_count >= vlm_query_limit:
            log.debug(f"[Trigger] {trigger_reason} (skipped, limit {vlm_query_limit} reached)")

        # Update tracking state
        state['prev_norm_reward'] = curr_reward
        state['prev_gripper_open'] = curr_gripper_open
        return state

    def run(self):
        """Main running loop."""
        self.success_count = 0
        base_output_dir = self.output_dir
        episode_num = self.config.get('episode_num', 10)

        for episode in range(episode_num):
            episode_seed = torch.randint(0, 1000, (1,)).item()
            self.policy.reset()
            self.video_recorder.clear()
            episode_dir = os.path.join(base_output_dir, f'episode_{episode+1}')
            os.makedirs(episode_dir, exist_ok=True)

            # Reset environment
            self.adapter.reset(seed=episode_seed)

            # Update guide_scale for current task (may change when switching tasks)
            task_info = self.adapter.get_task_info()
            recommended_scale = task_info.get('recommended_guide_scale')
            if recommended_scale is not None:
                self.current_guide_scale = recommended_scale
            log.info(f"Task {task_info.get('task_id', '?')}: guide_scale={self.current_guide_scale}")

            # Perform task preparation with error handling
            episode_error = False
            if self.config.get("use_guidance", True):
                try:
                    self.perform_task_for_episode(episode_dir)
                except Exception as e:
                    log.error(f"Episode {episode+1} preparation failed: {e}")
                    episode_error = True
                    # Save error info
                    error_file = os.path.join(episode_dir, 'error.txt')
                    with open(error_file, 'w') as f:
                        import traceback
                        f.write(f"Error during episode preparation:\n{traceback.format_exc()}")
                # Reset stage manager

            # Skip this episode if preparation failed
            if episode_error:
                log.warning(f"Skipping episode {episode+1} due to preparation error")
                # Save a placeholder fail video/marker
                fail_marker = os.path.join(episode_dir, f'episode_{episode+1}_fail_error.txt')
                with open(fail_marker, 'w') as f:
                    f.write("Episode failed due to guidance function error\n")
                continue

            # Wrap entire episode execution in try-except
            try:
                self._run_episode(episode, episode_dir)
            except Exception as e:
                log.error(f"Episode {episode+1} execution failed: {e}")
                import traceback
                error_file = os.path.join(episode_dir, 'error.txt')
                with open(error_file, 'w') as f:
                    f.write(f"Error during episode execution:\n{traceback.format_exc()}")
                # Save a placeholder fail marker
                fail_marker = os.path.join(episode_dir, f'episode_{episode+1}_fail_error.txt')
                with open(fail_marker, 'w') as f:
                    f.write(f"Episode failed due to execution error: {e}\n")
                log.warning(f"Skipping episode {episode+1} due to execution error")
                continue

        # Final statistics
        success_rate = self.success_count / episode_num * 100
        log.info(f"Tested {episode_num} episodes, success rate: {success_rate:.2f}%")

        # Save results
        log_file = os.path.join(self.output_dir, 'results.txt')
        with open(log_file, 'a') as f:
            f.write(f"Backend: {self.backend}\n")
            f.write(f"Success count: {self.success_count}/{episode_num}\n")
            f.write(f"Success rate: {success_rate:.2f}%\n")

    def _run_episode(self, episode: int, episode_dir: str):
        """Run a single episode with the current configuration."""
        observation = self._get_policy_observation()

        # Evaluation loop
        done = False
        global_steps = 0
        keypoints = None
        mask_ids = None
        generate_new_chunk = False
        action_executed = 0
        use_guidance = False
        action_horizon = self.policy._action_chunk_horizon
        current_stage = 1
        current_guidance_fns = None

        # Stage recognition thresholds
        UPPER_THRESHOLD = self.config.get("schmitt_upper", 0.8)
        LOWER_THRESHOLD = self.config.get("schmitt_lower", 0.6)
        action_chunk = None
        qualitative_chunks_saved = 0
        pretest_chunks_saved = 0

        log.info(f"Task description: {self.adapter.get_task_description()}")

        # Default: start with stage 1 and guidance ON
        current_stage = 1
        use_guidance = self.config.get("use_guidance", True) and hasattr(self, 'guidance_fns')
        current_guidance_fns = self.guidance_fns.get(current_stage, []) if use_guidance else None

        # Check if guidance functions are available
        if use_guidance and not current_guidance_fns:
            log.warning(f"No guidance functions for initial stage {current_stage}")
        else:
            log.info(f"Initial guidance: stage={current_stage}, use_guidance={use_guidance}, "
                    f"num_fns={len(current_guidance_fns) if current_guidance_fns else 0}")

        # Stage recognition state
        stage_state = {
            'prev_norm_reward': 0.0,
            'prev_gripper_open': None,
            'current_stage': current_stage,
            'use_guidance': use_guidance,
            'vlm_query_count': 0,
        }

        while not done:
            generate_new_chunk = (action_executed == 0)

            if generate_new_chunk and self.config.get("use_guidance", True) and hasattr(self, 'guidance_fns'):
                keypoints = self.keypoint_tracker.get_keypoint_positions()
                mask_ids = self.keypoint_tracker.get_mask_ids()

                # Update stage recognition
                gripper_val = self._get_gripper_value(action_chunk, action_executed)
                stage_state = self._update_stage(stage_state, gripper_val, UPPER_THRESHOLD, LOWER_THRESHOLD)

                current_stage = stage_state['current_stage']
                use_guidance = stage_state['use_guidance']
                current_guidance_fns = self.guidance_fns.get(current_stage, []) if use_guidance else None

                if use_guidance and not current_guidance_fns:
                    log.warning(f"No guidance functions for stage {current_stage}, disabling")
                    use_guidance = False
                    current_guidance_fns = None
            elif generate_new_chunk:
                use_guidance = False
                keypoints = None
                current_guidance_fns = None

            guidance_type = str(self.config.get("guidance_type", "vls")).lower()
            if guidance_type not in {"vls", "eds"}:
                raise ValueError(
                    f"Unsupported main.guidance_type={guidance_type!r}; "
                    "expected one of {'vls', 'eds'}"
                )

            vls_config = _config_section_to_dict(self.config.get("vls_config"), "main.vls_config")
            eds_config = _config_section_to_dict(self.config.get("eds_config"), "main.eds_config")
            eds_eval_config = _config_section_to_dict(self.config.get("eds_eval"), "main.eds_eval")
            eds_pretest_config = _config_section_to_dict(
                self.config.get("eds_mechanism_pretest"),
                "main.eds_mechanism_pretest",
            )
            if eds_eval_config:
                eds_config["reward_mode"] = eds_eval_config.get(
                    "reward_mode",
                    eds_config.get("reward_mode", "normal"),
                )
                eds_config["shuffle_seed"] = eds_eval_config.get(
                    "shuffle_seed",
                    eds_config.get("shuffle_seed", 0),
                )
            if eds_pretest_config:
                eds_config["mechanism_pretest"] = eds_pretest_config
            vls_config["guide_scale"] = getattr(
                self,
                "current_guide_scale",
                vls_config.get("guide_scale", 80.0),
            )
            select_params = inspect.signature(self.policy.select_action).parameters
            supports_grouped_guidance = "guidance_type" in select_params

            select_kwargs = {
                "batch": observation,
                "generate_new_chunk": generate_new_chunk,
                "use_guidance": use_guidance,
                "keypoints": keypoints,
                "guidance_fns": current_guidance_fns,
                "verbose": True,
                "global_step": global_steps,
                "current_stage": current_stage,
            }

            legacy_vls_kwargs = {
                "guide_scale": vls_config.get("guide_scale", 80.0),
                "sigmoid_k": vls_config.get("sigmoid_k", 12.0),
                "sigmoid_x0": vls_config.get("sigmoid_x0", 0.7),
                "start_ratio": vls_config.get("start_ratio", None),
                "use_diversity": vls_config.get("use_diversity", True),
                "diversity_scale": vls_config.get("diversity_scale", 10.0),
                "MCMC_steps": vls_config.get("MCMC_steps", 4),
                "use_fkd": vls_config.get("use_fkd", False),
                "fkd_config": (
                    _config_section_to_dict(vls_config.get("fkd"), "main.vls_config.fkd")
                    if vls_config.get("fkd") is not None
                    else None
                ),
            }

            if self.policy_type == "rdt" and supports_grouped_guidance:
                select_kwargs.update(
                    {
                        "guidance_type": guidance_type,
                        "vls_config": vls_config,
                        "eds_config": eds_config,
                    }
                )
            else:
                if guidance_type == "eds":
                    raise ValueError(
                        "main.guidance_type=eds is currently implemented only for an RDT policy "
                        "that supports grouped EDS guidance"
                    )
                select_kwargs.update(legacy_vls_kwargs)

            select_action_start_s = time.perf_counter()
            action_chunk = self.policy.select_action(**select_kwargs)
            select_action_latency_s = float(time.perf_counter() - select_action_start_s)
            actual_task_id = _adapter_actual_task_id(self.adapter)

            if (
                generate_new_chunk
                and use_guidance
                and guidance_type == "eds"
                and eds_eval_config.get("enabled", False)
                and eds_eval_config.get("write_metrics", True)
                and hasattr(self.policy, "get_last_eds_metrics")
            ):
                eds_metrics = self.policy.get_last_eds_metrics()
                if eds_metrics is not None:
                    eds_metrics.update(
                        {
                            "episode": int(episode),
                            "global_step": int(global_steps),
                            "suite": getattr(self.adapter, "suite_name", None),
                            "task_id": actual_task_id,
                            "method_label": eds_eval_config.get("method_label"),
                            "job_id": eds_eval_config.get("job_id"),
                            "num_elites": eds_config.get("num_elites"),
                            "renoise_t_max": eds_config.get("renoise_t_max"),
                            "renoise_t_min": eds_config.get("renoise_t_min"),
                            "select_action_latency_s": select_action_latency_s,
                        }
                    )
                    if (
                        eds_eval_config.get("save_qualitative", False)
                        and qualitative_chunks_saved
                        < int(eds_eval_config.get("max_visual_chunks_per_episode", 2))
                        and hasattr(self.policy, "get_last_eds_artifacts")
                    ):
                        artifacts = self.policy.get_last_eds_artifacts()
                        if artifacts is not None:
                            visual_root = Path(
                                eds_eval_config.get("output_dir", self.output_dir)
                            ) / "qualitative"
                            saved_artifacts = save_eds_qualitative_artifacts(
                                output_dir=visual_root,
                                adapter=self.adapter,
                                keypoints=keypoints,
                                mask_ids=mask_ids,
                                artifacts=artifacts,
                                episode=int(episode),
                                global_step=int(global_steps),
                                max_iters=int(
                                    eds_config.get("cem_iters", 10)
                                    if eds_eval_config.get("save_per_iter_best", True)
                                    else 0
                                ),
                            )
                            if saved_artifacts:
                                eds_metrics["qualitative_artifacts"] = saved_artifacts
                                qualitative_chunks_saved += 1
                    metrics_path = (
                        Path(eds_eval_config.get("output_dir", self.output_dir))
                        / "eds_metrics.jsonl"
                    )
                    append_jsonl(metrics_path, eds_metrics)

            if (
                generate_new_chunk
                and use_guidance
                and guidance_type == "eds"
                and eds_pretest_config.get("enabled", False)
                and pretest_chunks_saved < int(eds_pretest_config.get("max_chunks", 1))
                and hasattr(self.policy, "get_last_eds_mechanism_trace")
            ):
                trace = self.policy.get_last_eds_mechanism_trace()
                if trace is not None:
                    trace.suite = getattr(self.adapter, "suite_name", None)
                    trace.task_id = actual_task_id
                    trace.episode = int(episode)
                    seed = int(eds_pretest_config.get("seed", 0))
                    run_id = eds_pretest_config.get("run_id") or build_run_id(
                        suite=str(trace.suite or "unknown_suite"),
                        task_id=int(trace.task_id if trace.task_id is not None else -1),
                        seed=seed,
                        reward_mode=str(trace.reward_mode),
                        population_size=int(trace.population_size),
                        cem_iters=int(trace.cem_iters),
                    )
                    pretest_root = (
                        Path(
                            eds_pretest_config.get(
                                "output_dir",
                                "outputs/rdt_eds_mechanism_pretest",
                            )
                        )
                        / run_id
                    )
                    saved_trace_paths = save_mechanism_trace(
                        pretest_root,
                        trace,
                        save_tensors=bool(eds_pretest_config.get("save_tensors", True)),
                    )
                    saved_plot_paths = []
                    if bool(eds_pretest_config.get("plot_3d", True)):
                        saved_plot_paths = save_eds_mechanism_pretest_artifacts(
                            pretest_root,
                            trace,
                        )
                    log.info(
                        f"[EDS_PRETEST] saved {len(saved_trace_paths)} trace artifacts "
                        f"and {len(saved_plot_paths)} plot artifacts to {pretest_root}"
                    )
                    pretest_chunks_saved += 1

            if hasattr(self.adapter, 'env_postprocessor'):
                action_transition = {"action": action_chunk}
                action_transition = self.adapter.env_postprocessor(action_transition)
                action_chunk = action_transition["action"]

            # Get image and add status overlay
            if self.config.get("debug_draw_trajectory", False):
                from utils.vis_utils import draw_action_trajectory_on_vlm_image
                visualization_action_chunk = _get_visualization_action_chunk(
                    self.policy,
                    self.adapter,
                    action_chunk,
                )
                image = draw_action_trajectory_on_vlm_image(
                    adapter=self.adapter,
                    action_chunk=visualization_action_chunk[:, action_executed:],
                    num_steps=action_horizon,
                    global_step=global_steps,
                    action_executed=action_executed,
                )
            else:
                image = np.array(self.adapter.get_vlm_image())

            # Draw keypoints on image for debugging (disabled by default)
            if self.config.get("debug_draw_keypoints", False) and keypoints is not None:
                from utils.vis_utils import draw_keypoints_on_image
                image = draw_keypoints_on_image(
                    adapter=self.adapter,
                    image=image,
                    keypoints=keypoints,
                    mask_ids=mask_ids
                )

            # Add guidance status overlay
            gripper_val = self._get_gripper_value(action_chunk, action_executed)
            gripper_str = f"Grip:{'O' if gripper_val and gripper_val < 0 else 'C'}({gripper_val:.2f})" if gripper_val else "Grip:-"

            status_text = [
                f"Step:{global_steps} Stage:{current_stage}",
                f"Guide:{'ON' if use_guidance else 'OFF'} {gripper_str}",
            ]

            # Add reward-based guidance info
            if hasattr(self.policy, 'get_normalized_reward') and use_guidance:
                norm_r = self.policy.get_normalized_reward()
                scale = self.policy.get_last_scale()

                # Use config values for consistent display
                vls_config = _config_section_to_dict(
                    self.config.get("vls_config"),
                    "main.vls_config",
                )
                k = vls_config.get("sigmoid_k", 12.0)
                x0 = vls_config.get("sigmoid_x0", 0.8)
                sig_strength = 1.0 / (1.0 + np.exp(k * (norm_r - x0)))

                # Show scale as "-" if not yet computed (first chunk before guidance runs)
                scale_str = f"{scale:.1f}" if scale > 0 else "-"
                status_text.extend([
                    f"Norm_R: {norm_r:.2f}",
                    f"Sig_Str: {sig_strength:.1%}",
                    f"Scale: {scale_str}",
                ])

            image_with_status = add_text_to_image(image, status_text)
            self.video_recorder.add_frame(self.adapter.vlm_camera, image_with_status)
            obs, reward, terminated, truncated, info = self.adapter.step(action_chunk[0][action_executed])

            action_executed += 1
            if action_executed == action_horizon:
                action_executed = 0

            observation = self._get_policy_observation()
            global_steps += 1

            if terminated or truncated:
                is_success = info.get('success', False)
                if is_success:
                    done = True
                    self.success_count += 1

                behavior_name = info.get("behavior_name", "unknown")
                video_path = os.path.join(episode_dir, f'episode_{episode+1}_{"success" if is_success else "fail"}')
                self.video_recorder.save_video(save_path=video_path, success=is_success, behavior_name=behavior_name)
                break

        log.info(f"Episode {episode+1} finished, success: {info.get('success', False)}, steps: {global_steps}")

    def _plot_behavior_stats(self):
        """Draw behavior statistics plot."""
        behavior_data = self.adapter.get_behavior_static()
        labels = list(behavior_data.keys())
        values = list(behavior_data.values())

        fig, ax = plt.subplots(figsize=(12, 6))
        bars = ax.bar(labels, values, color='steelblue', edgecolor='black')

        for bar, val in zip(bars, values):
            height = bar.get_height()
            ax.annotate(f'{val}',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom',
                       fontsize=10, fontweight='bold')

        ax.set_ylabel('Count', fontsize=12)
        ax.set_title('Behavior Statistics', fontsize=14)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, 'behavior_static.png'), dpi=150)
        plt.close()

    def run_test(self):
        """Test segmentation and keypoint detection."""
        self.adapter.reset()
        rgb, depth, points, segmentation, segment_id_to_name = self.adapter.get_keypoint_detection_inputs()

        # Save images
        rgb_path = os.path.join(self.output_dir, 'rgb_static.png')
        cv2.imwrite(rgb_path, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        log.debug(f"Saved RGB image to: {rgb_path}")

        # Visualize segmentation
        unique_ids = np.unique(segmentation)
        seg_colored = np.zeros((*segmentation.shape, 3), dtype=np.uint8)
        np.random.seed(42)
        for seg_idx in unique_ids:
            if seg_idx == 0:
                continue
            color = np.random.randint(50, 255, 3).tolist()
            seg_colored[segmentation == seg_idx] = color

        seg_path = os.path.join(self.output_dir, 'segmentation.png')
        cv2.imwrite(seg_path, seg_colored)
        log.debug(f"Saved segmentation image to: {seg_path}")

        log.info("Interactable objects:")
        for seg_idx, name in segment_id_to_name.items():
            if seg_idx > 0:
                pixel_count = np.sum(segmentation == seg_idx)
                if pixel_count > 0:
                    log.debug(f"  [{seg_idx}] {name}: {pixel_count} pixels")

        # Detect keypoints
        log.info("Detecting keypoints...")
        keypoints, projected_img, mask_ids, dino_vis = self.keypoint_detector.get_keypoints_with_visualization(
            rgb=rgb,
            points=points,
            segmentation=segmentation,
            segment_id_to_name=segment_id_to_name,
            save_dir=self.output_dir
        )

        projected_path = os.path.join(self.output_dir, 'keypoints_projected.png')
        cv2.imwrite(projected_path, cv2.cvtColor(projected_img, cv2.COLOR_RGB2BGR))
        log.info(f"Saved keypoint projection to: {projected_path}")

        log.info(f"Detected {len(keypoints)} keypoints:")
        for i, (kp, mid) in enumerate(zip(keypoints, mask_ids)):
            obj_name = segment_id_to_name.get(mid, f"unknown_{mid}")
            log.info(f"  [{i}] {obj_name}: position=[{kp[0]:.4f}, {kp[1]:.4f}, {kp[2]:.4f}]")


@hydra.main(version_base=None, config_path="configs", config_name="config")
def main(cfg: DictConfig) -> None:
    """
    Main entry point with Hydra configuration.

    Usage:
        # CALVIN (uses task configs)
        python main.py env=calvin task=drawer_open
        python main.py env=calvin task=button_on

        # LIBERO (uses suite_name directly, no task configs)
        python main.py env=libero backend.libero.suite_name=libero_goal
        python main.py env=libero env.libero.suite_name=libero_spatial

        # Override parameters
        python main.py main.episode_num=50 main.vls_config.guide_scale=120
    """
    # Print resolved config
    log.info(f"Working directory: {os.getcwd()}")
    log.info(f"Output directory: {hydra.core.hydra_config.HydraConfig.get().runtime.output_dir}")

    env_backend = cfg.backend.backend
    log.info(f"Using environment: {env_backend}")

    # Backend-specific logging
    if env_backend == "calvin":
        target_behavior = cfg.backend.calvin.get("target_behavior")
        log.info(f"Target behavior: {target_behavior or 'any'}")
    elif env_backend == "libero":
        log.info(f"Suite: {cfg.backend.libero.suite_name}")

    # Initialize and run
    runner = Main(cfg)
    runner.run()


if __name__ == "__main__":
    main()
