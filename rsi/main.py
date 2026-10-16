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
import warnings

# hgpu1 resolves to host ``lhy-1``.  Its eight NVIDIA EGL devices are exposed
# to the container but cannot create a display; the ninth EGL device is the
# working headless renderer.  Configure this before importing MuJoCo,
# Robosuite, or LIBERO.  The check intentionally keeps other hosts unchanged.
if hasattr(os, "uname") and os.uname().nodename == "lhy-1":
    os.environ["PYOPENGL_PLATFORM"] = "egl"
    os.environ["MUJOCO_GL"] = "egl"
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

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
from omegaconf import DictConfig, OmegaConf

warnings.filterwarnings('ignore', category=FutureWarning, message='.*pynvml.*')
warnings.filterwarnings('ignore', category=UserWarning, message='.*pkg_resources.*')
warnings.filterwarnings('ignore', category=UserWarning, message='.*xFormers.*')
warnings.filterwarnings('ignore', category=UserWarning, message='.*env.get_obs.*')

# Add project root to path (for local modules like steer_utils, utils, etc.)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Monkey-patch calvin_env Light class with our modified version (supports initial_state config)
from patches.light import Light as PatchedLight, LightState as PatchedLightState
sys.modules['calvin_env.scene.objects.light'] = type(sys)('calvin_env.scene.objects.light')
sys.modules['calvin_env.scene.objects.light'].Light = PatchedLight
sys.modules['calvin_env.scene.objects.light'].LightState = PatchedLightState

# Import adapters
from rsi.core.env_adapters import create_adapter, BaseEnvAdapter
from rsi.core.keypoint_tracker import KeypointTracker
from rsi.core.keypoint_detector import KeypointDetector
from core.sam3_segmenter import create_segmenter as create_sam3_segmenter
from rsi.core.gemini_grounder import create_gemini_grounder, create_gemini_stage_recognizer
from rsi.vlm_query.vlm_agent import VLMAgent
from utils.vis_utils import TrajectoryVideoRecorder, add_text_to_image
from mode_gate.experiment_contract import label_contract_payload
from mode_gate.formal_protocol import prepare_requested_coordinators

# Only an explicit PID/hash-checked warm migration can refresh coordinators.
prepare_requested_coordinators()

from core.policy_observation_sampling import policy_observation_sample_num

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


def _active_deployment_is_loaded_theta0(
    registry: Any,
    active: Any,
    *,
    base_pretrained_path: str,
    loaded_checkpoint_digest: str,
) -> bool:
    """Prove that the active immutable policy is the theta0 already in memory.

    A rollout starts from ``policy.pretrained_path`` and then checks
    the active registry at the first episode boundary.  Reloading the same
    bootstrap artifact there wastes another full checkpoint read and briefly
    occupies two GPUs.  Skip that reload only when the immutable theta0
    reference and every committed deployment transaction back to
    ``bootstrap_theta0`` agree on the same policy.
    """

    from pathlib import Path

    try:
        reference_path = Path(registry.root) / "base/theta_0/ref.json"
        reference = json.loads(reference_path.read_text(encoding="utf-8"))
        if reference.get("schema_version") != "theta0-reference-v1":
            return False
        if (
            Path(str(reference["checkpoint_path"])).resolve()
            != Path(base_pretrained_path).resolve()
            or str(reference["checkpoint_digest"]) != str(loaded_checkpoint_digest)
        ):
            return False
        expected = {
            "deployment_revision": int(active.deployment_revision),
            "policy_id": str(active.policy_id),
            "controller_mode": str(active.controller_mode),
            "verifier_id": active.verifier_id,
            "manifest_hash": str(active.manifest_hash),
            "transaction_id": str(active.transaction_id),
        }
        seen: set[str] = set()
        while expected:
            transaction_id = str(expected["transaction_id"])
            if transaction_id in seen:
                return False
            seen.add(transaction_id)
            transaction_path = (
                Path(registry.root)
                / "attempts"
                / f"transaction_{transaction_id}.json"
            )
            transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
            if transaction.get("status") != "COMMITTED":
                return False
            next_value = dict(transaction.get("next") or {})
            if any(next_value.get(key) != value for key, value in expected.items()):
                return False
            # Installing/retraining a verifier does not change immutable
            # policy weights. The verifier has already been loaded above.
            if str(next_value.get("policy_id")) != str(active.policy_id):
                return False
            previous = transaction.get("previous")
            if transaction.get("reason") == "bootstrap_theta0":
                return previous is None and int(next_value["deployment_revision"]) == 1
            if not isinstance(previous, dict):
                return False
            expected = {
                key: previous.get(key)
                for key in (
                    "deployment_revision",
                    "policy_id",
                    "controller_mode",
                    "verifier_id",
                    "manifest_hash",
                    "transaction_id",
                )
            }
        return False
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        log.warning(f"Cannot prove active policy is loaded theta0: {exc}")
        return False


class Main:
    def __init__(self, cfg: DictConfig):
        """
        Initialize with Hydra DictConfig.

        Args:
            cfg: Hydra configuration (OmegaConf DictConfig)
        """
        self.cfg = cfg
        self.config = cfg.main  # Shortcut to main config section
        from mode_gate.config import ModeGateConfig

        raw_mode_gate_config = OmegaConf.to_container(
            cfg.get("mode_gate", {}), resolve=True
        )
        self.mode_gate_config = ModeGateConfig.from_mapping(raw_mode_gate_config)

        # Some policy implementations construct tensors on bare ``cuda``
        # inside ``from_pretrained``.  Select the requested ordinal before any
        # adapter or model construction so ``device=cuda:6`` never stages a
        # multi-GB checkpoint on GPU0 first.  This is not process-level GPU
        # binding; all devices remain visible.
        self.device = str(cfg.get('device', 'cuda'))
        if torch.cuda.is_available() and self.device.startswith("cuda"):
            torch.cuda.set_device(torch.device(self.device))

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
        base_guide_scale = self.config.get('guide_scale', 80.0)

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
        self.policy_config = policy_config
        self.policy_type_config = type_config
        self.base_pretrained_path = pretrained_path
        log.info(f"Loading {policy_type} from: {pretrained_path}")

        if policy_type == 'diffusion':
            from rsi.core.diffusion_policy_steer import DiffusionPolicySteer

            self.policy = DiffusionPolicySteer.from_pretrained(pretrained_path)
        elif policy_type == 'pi05':
            from rsi.core.pi05_steer import PI05PolicySteer

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

        self.policy.to(self.device)
        # ``nn.Module.to`` moves parameters but does not update the LeRobot
        # policy config. PI05 and its observation processor consult this field
        # later, so keep it aligned when using a non-default GPU.
        if hasattr(self.policy, "config") and hasattr(self.policy.config, "device"):
            self.policy.config.device = str(self.device)

        if policy_type == 'rdt':
            # RDTSteer handles all obs/action processing internally.
            self.policy_preprocessor = lambda x: x
            self.policy_postprocessor = lambda x: x
        else:
            from lerobot.policies.factory import make_pre_post_processors

            preprocessor_overrides = {
                "device_processor": {"device": str(self.policy.config.device)},
            }
            local_tokenizer_path = type_config.get("tokenizer_path", None)
            if local_tokenizer_path:
                preprocessor_overrides["tokenizer_processor"] = {
                    "tokenizer_name": str(local_tokenizer_path),
                }
            self.policy_preprocessor, self.policy_postprocessor = make_pre_post_processors(
                policy_cfg=self.policy.config,
                pretrained_path=pretrained_path,
                preprocessor_overrides=preprocessor_overrides,
            )

        self.policy.post_init(
            adapter=self.adapter,
            postprocessor=self.policy_postprocessor,
            sample_batch_size=(
                self.mode_gate_config.sample_count
                if self.mode_gate_config.enabled
                else self.config.get('sample_batch_size', 1)
            ),
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
        self._init_mode_gate()

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

        # Keep the legacy configuration key, but use account planning without API credentials.
        gemini_config = perception_cfg.get('gemini_grounding', {})
        self.use_gemini = (bool(gemini_config.get('enabled', False))
                          and self.config.get('planner_steering_enabled', True)) if gemini_config else False
        if self.use_gemini:
            gemini_dict = OmegaConf.to_container(gemini_config, resolve=True)
            gemini_dict.pop('api_key', None)
            log.info("Initializing Codex account planner for visual grounding")
            self.gemini_grounder = create_gemini_grounder(gemini_dict)
            self.gemini_default_objects = list(gemini_config.get('default_objects', []))
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

        # Initialize account-based real-time stage recognition.
        gemini_config = OmegaConf.to_container(perception_cfg.get('gemini', {}), resolve=True)
        if (self.config.get("use_vlm_stage_recognition", True)
                and self.config.get('planner_steering_enabled', True)):
            try:
                self.gemini_stage_recognizer = create_gemini_stage_recognizer(gemini_config)
                log.info("Codex account stage recognizer initialized")
            except Exception as e:
                log.warning(f"Failed to initialize Codex account stage recognizer: {e}")
                self.gemini_stage_recognizer = None
        else:
            self.gemini_stage_recognizer = None

        # Initialize video recorder
        self.video_recorder = TrajectoryVideoRecorder(output_dir=self.output_dir)

        self.cached_functions_dir = self.config.get('cached_functions_dir', None)

    def _init_mode_gate(self) -> None:
        """Initialize the persistent v2 fast loop and its fail-closed providers."""
        self.mode_gate_controller = None
        self.mode_aware_runtime = None
        if not self.mode_gate_config.enabled:
            return

        from dataclasses import replace
        from pathlib import Path

        from mode_gate.cards import (
            CandidateCardRenderer,
            adapter_camera_projector,
        )
        from mode_gate.checkpoint_math import checkpoint_digest
        from mode_gate.gate import TrajectoryCandidateGate
        from mode_gate.geometry import adapter_geometry_scorer
        from mode_gate.incidents import IncidentMemory
        from mode_gate.projectors import (
            CalvinTrajectoryProjector,
            LiberoTrajectoryProjector,
        )
        from mode_gate.preflight import source_revision
        from mode_gate.registry import PolicyRegistry
        from mode_gate.runtime import CandidateRuntime
        from mode_gate.semantic_planner import (
            SemanticPlanner,
            preflight_with_network_recovery,
        )
        from mode_gate.slow_loop import SlowLoopStore
        from mode_gate.snapshots import DecisionSnapshotStore
        from mode_gate.verifier import DeployedVerifierPredictor
        from mode_gate.experiment_contract import fixed_budget_controller_mode

        if self.backend == "calvin":
            projector = CalvinTrajectoryProjector(self.adapter)
        elif self.backend == "libero":
            projector = LiberoTrajectoryProjector(self.adapter)
        else:
            raise ValueError(
                f"mode_gate supports only CALVIN and LIBERO, got {self.backend!r}"
            )

        camera_projector = adapter_camera_projector(self.adapter)
        registry = PolicyRegistry(Path(self.mode_gate_config.registry_root))
        self.mode_gate_source_revision = source_revision(Path(PROJECT_ROOT))
        self.active_policy_checkpoint_digest = checkpoint_digest(
            Path(self.base_pretrained_path)
        )
        if self.keypoint_tracker is None:
            self.keypoint_tracker = KeypointTracker(self.adapter)
        if self.policy_type == "pi05":
            self._initialize_theta0_scene_encoder(registry)
        active = registry.active()
        verifier = None
        effective_mode = fixed_budget_controller_mode(
            self.mode_gate_config.retry_budget
        )
        if (active is not None and active.controller_mode == "learned_verifier"
                and not self.config.get('initialization_posthoc_only', False)):
            verifier_path = Path(self.mode_gate_config.registry_root) / "verifiers" / str(active.verifier_id)
            try:
                verifier = DeployedVerifierPredictor(
                    verifier_path, device=str(self.device)
                )
            except ValueError as exc:
                if self.mode_gate_config.require_learned_verifier:
                    raise RuntimeError(
                        "Formal verifier could not load; fixed-budget fallback is disabled"
                    ) from exc
                log.warning(
                    "Legacy verifier is incompatible with the candidate architecture; "
                    f"fixed-budget bootstrap (50) remains active until the new head is trained: {exc}"
                )
                verifier = None
            # The theta0 scene encoder is attached by the deployment loader.
            # Without it, use the configured fixed-budget controller rather than
            # running a verifier on active-policy features.
            if (
                verifier is not None
                and getattr(self, "theta0_scene_encoder", None) is not None
            ):
                effective_mode = "learned_verifier"
        if self.mode_gate_config.require_learned_verifier and effective_mode != "learned_verifier":
            raise RuntimeError("Formal execution needs its initialized verifier and frozen v44 encoder")
        self.mode_gate_config = replace(
            self.mode_gate_config,
            controller_mode=effective_mode,
        )
        gate = TrajectoryCandidateGate(self.mode_gate_config, projector)
        planner = SemanticPlanner(
            model=self.mode_gate_config.planner_model,
            prompt_version=self.mode_gate_config.planner_prompt_version,
            timeout_seconds=self.mode_gate_config.planner_timeout_seconds,
            max_retries=self.mode_gate_config.planner_max_retries,
            thinking_level=self.mode_gate_config.planner_reasoning_effort,
            cache_dir=Path(self.mode_gate_config.incident_root) / "planner_cache",
            max_provider_calls=self.mode_gate_config.planner_max_provider_calls,
            call_ledger_path=(
                Path(self.mode_gate_config.planner_call_ledger)
                if self.mode_gate_config.planner_call_ledger
                else (
                    Path(self.mode_gate_config.incident_root)
                    / "gemini_provider_calls.jsonl"
                    if self.mode_gate_config.planner_max_provider_calls > 0
                    else None
                )
            ),
        )
        if (not self.config.get('initialization_posthoc_only', False)
                and self.config.get('planner_steering_enabled', True)):
            preflight_with_network_recovery(
                planner,
                recovery_label="online mode-aware runtime startup",
            )
        self.mode_gate_registry = registry
        self.mode_gate_incidents = IncidentMemory(Path(self.mode_gate_config.incident_root))
        self.mode_gate_snapshot_store = DecisionSnapshotStore(
            Path(self.mode_gate_config.snapshot_root)
        )
        self.mode_gate_slow_loop = SlowLoopStore(Path(self.mode_gate_config.slow_loop_root))
        self.mode_aware_runtime = CandidateRuntime(
            config=self.mode_gate_config,
            gate=gate,
            planner=planner,
            combined_renderer=CandidateCardRenderer(camera_projector),
            geometry_factory=lambda context: adapter_geometry_scorer(
                self.adapter, context.metadata
            ),
            incidents=self.mode_gate_incidents,
            verifier=verifier,
            backbone_id=(self.theta0_scene_encoder.theta0_checksum
                         if getattr(self, "theta0_scene_encoder", None) is not None else ""),
        )
        from mode_gate.deployment import EpisodeBoundaryDeploymentManager

        initial_deployment_revision = 0
        if active is not None and _active_deployment_is_loaded_theta0(
            registry,
            active,
            base_pretrained_path=str(self.base_pretrained_path),
            loaded_checkpoint_digest=str(self.active_policy_checkpoint_digest),
        ):
            initial_deployment_revision = int(active.deployment_revision)
            log.info(
                "Active registry policy is the already-loaded theta0; "
                f"starting at deployment revision {initial_deployment_revision}"
            )
        self.mode_gate_deployment_manager = EpisodeBoundaryDeploymentManager(
            registry=registry,
            policy_loader=self._fresh_load_registry_policy,
            verifier_loader=self._fresh_load_registry_verifier,
            canary=self._deployment_canary,
            initial_revision=initial_deployment_revision,
        )
        # Compatibility sentinel used by the existing rollout condition.
        self.mode_gate_controller = self.mode_aware_runtime
        log.info(
            f"Mode-aware v2 runtime initialized: controller_mode={effective_mode}, "
            f"baseline={self.mode_gate_config.baseline_kind or 'none'}"
        )

    def _launch_expansion_automation(self, slow_job) -> dict[str, Any]:
        """Detach the slow worker that will issue and serve the demo ticket."""

        from pathlib import Path

        from mode_gate.expansion_automation import launch_expansion_worker
        from mode_gate.io_utils import atomic_write_json

        if not bool(self.mode_gate_config.auto_start_expansion_worker):
            return {"launch_status": "disabled_by_config"}
        if self.mode_gate_config.baseline_kind:
            # Formal audit and baselines may emit EXPANSION outcomes for
            # measurement, but must never solicit human data.
            return {"launch_status": "disabled_for_baseline"}
        persistent_root = Path(self.mode_gate_config.slow_loop_root).resolve().parent
        try:
            launch = launch_expansion_worker(
                job_id=slow_job.job_id,
                repo_root=Path(PROJECT_ROOT),
                persistent_root=persistent_root,
                slow_loop_root=Path(self.mode_gate_config.slow_loop_root),
                registry_root=Path(self.mode_gate_config.registry_root),
                incident_root=Path(self.mode_gate_config.incident_root),
                snapshot_root=Path(self.mode_gate_config.snapshot_root),
                operator=self.mode_gate_config.teleop_operator,
                teleop_port=int(self.mode_gate_config.teleop_port),
                teleop_max_steps=int(self.mode_gate_config.teleop_max_steps),
                full_cycle=bool(getattr(self, "expansion_full_cycle", False)),
                gpu_index=int(str(self.device).split(":")[-1]),
            )
            log.warning(
                "Automatic expansion worker launched: "
                f"job={slow_job.job_id}, teleop={launch['teleop_url']}"
            )
            return launch
        except Exception as exc:
            failure = {
                "schema_version": "vls-expansion-worker-launch-failure-v1",
                "launch_status": "failed",
                "job_id": slow_job.job_id,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            atomic_write_json(
                persistent_root
                / "slow_worker_launches"
                / f"{slow_job.job_id}.failure.json",
                failure,
            )
            log.error(
                "Automatic expansion worker failed to launch; the persistent "
                f"job remains resumable: {failure}"
            )
            return failure

    def _initialize_theta0_scene_encoder(self, registry) -> None:
        """Bind a permanently frozen feature source to theta0 and its processor."""
        import json
        from pathlib import Path

        from mode_gate.checkpoint_math import checkpoint_digest
        from mode_gate.scene_encoder import (
            Pi05PrefixFeatureSource,
            Theta0SceneEncoder,
            processor_artifact_digest,
        )

        theta0_root = Path(self.mode_gate_config.theta0_checkpoint)
        reference = registry.root / "base/theta_0/ref.json"
        if reference.exists():
            theta0_checksum = json.loads(reference.read_text(encoding="utf-8"))[
                "checkpoint_digest"
            ]
        elif theta0_root.resolve() == Path(self.base_pretrained_path).resolve():
            # _init_mode_gate computed this exact digest immediately before
            # constructing the scene encoder.  Reuse it instead of rereading
            # a multi-GB checkpoint from shared storage during cold startup.
            theta0_checksum = self.active_policy_checkpoint_digest
        else:
            theta0_checksum = checkpoint_digest(theta0_root)
        tokenizer_path = self.policy_type_config.get("tokenizer_path", None)
        processor_digest = processor_artifact_digest(
            theta0_root,
            tokenizer_root=Path(tokenizer_path) if tokenizer_path else None,
        )
        existing_encoder = getattr(self, 'theta0_scene_encoder', None)
        if (existing_encoder is not None
                and existing_encoder.theta0_checksum == theta0_checksum
                and existing_encoder.processor_hash == processor_digest
                and existing_encoder.cache_dir == Path(self.mode_gate_config.incident_root) / 'scene_features'):
            return  # Controller/phase changes never need to reload the frozen VLM.
        theta0_preprocessor = self.policy_preprocessor
        if self.active_policy_checkpoint_digest != theta0_checksum:
            raise ValueError("scene encoder must be initialized from v44, not the current merged policy")

        def batch_factory(kind: str, _image: Any, instruction: str) -> dict[str, Any]:
            raw = self.adapter.get_policy_observation(sample_num=1)
            copied = {
                key: (value.clone() if isinstance(value, torch.Tensor) else value)
                for key, value in raw.items()
            }
            if kind == "goal":
                for key, value in copied.items():
                    if str(key).startswith("observation.images.") and isinstance(
                        value, torch.Tensor
                    ):
                        copied[key] = torch.zeros_like(value)
            copied["task"] = ["" if kind == "observation" else instruction]
            return theta0_preprocessor(copied)

        source = Pi05PrefixFeatureSource(self.policy, batch_factory)
        self.theta0_scene_encoder = Theta0SceneEncoder(
            source,
            theta0_checksum=theta0_checksum,
            processor_hash=processor_digest,
            cache_dir=Path(self.mode_gate_config.incident_root) / "scene_features",
        )

    def _fresh_load_registry_policy(self, deployment) -> dict[str, Any]:
        """Fresh-load a composed PI0.5 policy without mutating the live instance."""
        if self.policy_type != "pi05":
            raise RuntimeError("v2 registry deployment currently supports PI0.5 only")
        from pathlib import Path

        from lerobot.policies.factory import make_pre_post_processors

        from rsi.core.pi05_steer import PI05PolicySteer

        checkpoint = Path(self.mode_gate_config.registry_root) / "policies" / deployment.policy_id
        candidate = PI05PolicySteer.from_pretrained(str(checkpoint))
        candidate.to(self.device)
        candidate.config.device = str(self.device)
        overrides = {"device_processor": {"device": str(candidate.config.device)}}
        tokenizer_path = self.policy_type_config.get("tokenizer_path", None)
        if tokenizer_path:
            overrides["tokenizer_processor"] = {"tokenizer_name": str(tokenizer_path)}
        # The processor/statistics remain pinned to theta0 even when weights evolve.
        preprocessor, postprocessor = make_pre_post_processors(
            policy_cfg=candidate.config,
            pretrained_path=self.mode_gate_config.theta0_checkpoint,
            preprocessor_overrides=overrides,
        )
        candidate.post_init(
            adapter=self.adapter,
            postprocessor=postprocessor,
            sample_batch_size=self.mode_gate_config.sample_count,
            policy_config=self.policy_type_config,
        )
        candidate.eval()
        return {
            "policy": candidate,
            "preprocessor": preprocessor,
            "postprocessor": postprocessor,
            "checkpoint": str(checkpoint),
        }

    def _fresh_load_registry_verifier(self, deployment):
        if deployment.controller_mode.startswith("fixed_budget_"):
            if self.mode_gate_config.require_learned_verifier:
                raise RuntimeError("Formal execution cannot load a fixed-budget deployment")
            return None
        if getattr(self, "theta0_scene_encoder", None) is None:
            raise RuntimeError("learned verifier deployment requires the immutable theta0 encoder")
        from pathlib import Path

        from mode_gate.verifier import DeployedVerifierPredictor

        path = Path(self.mode_gate_config.registry_root) / "verifiers" / str(deployment.verifier_id)
        return DeployedVerifierPredictor(path, device=str(self.device))

    def _deployment_canary(self, policy_bundle, verifier, deployment) -> dict[str, Any]:
        policy = policy_bundle["policy"]
        finite = True
        checked = 0
        for parameter in policy.parameters():
            finite = finite and bool(torch.isfinite(parameter.detach()).all())
            checked += parameter.numel()
            if checked >= 1_000_000:
                break
        return {
            "passed": (
                finite
                and policy._action_chunk_horizon == self.mode_gate_config.chunk_horizon
                and (
                    deployment.controller_mode.startswith("fixed_budget_")
                    or verifier is not None
                )
            ),
            "finite_parameter_prefix": finite,
            "checked_parameters": checked,
            "action_chunk_horizon": policy._action_chunk_horizon,
        }

    def _reload_active_deployment(self) -> None:
        if self.mode_aware_runtime is None:
            return
        from pathlib import Path
        from mode_gate.runtime_settings import apply_runtime_steering_settings

        apply_runtime_steering_settings(
            self,
            request_path=Path(self.mode_gate_config.slow_loop_root).parent
            / "formal_experiment/runtime_steering_settings.json",
            at_episode_boundary=True,
        )
        bundle = self.mode_gate_deployment_manager.reload_if_changed(
            at_episode_boundary=True
        )
        if bundle is None:
            return
        from dataclasses import replace
        from pathlib import Path

        from mode_gate.checkpoint_math import checkpoint_digest
        from mode_gate.state_machine import EpisodeChunkController

        self.policy = bundle.policy["policy"]
        self.policy_preprocessor = bundle.policy["preprocessor"]
        self.policy_postprocessor = bundle.policy["postprocessor"]
        self.active_policy_checkpoint_digest = checkpoint_digest(
            Path(bundle.policy["checkpoint"])
        )
        deployment_mode = bundle.deployment.controller_mode
        if deployment_mode.startswith("fixed_budget_"):
            from mode_gate.experiment_contract import fixed_budget_controller_mode

            deployment_mode = fixed_budget_controller_mode(
                self.mode_gate_config.retry_budget
            )
        self.mode_gate_config = replace(
            self.mode_gate_config,
            controller_mode=deployment_mode,
        )
        self.mode_aware_runtime.config = self.mode_gate_config
        self.mode_aware_runtime.controller = EpisodeChunkController(
            self.mode_gate_config,
            retry_budget_override=(
                self.mode_gate_config.baseline_budget
                if self.mode_gate_config.baseline_kind == "fixed_budget"
                else None
            ),
        )
        self.mode_aware_runtime.verifier = bundle.verifier
        log.info(
            f"Loaded deployment revision {bundle.deployment.deployment_revision} "
            f"at episode boundary: policy={bundle.deployment.policy_id}, "
            f"controller={bundle.deployment.controller_mode}"
        )

    def _get_policy_observation(self) -> dict:
        """Get observation in policy expected format (backend-agnostic)."""
        configured_sample_count = (
            self.mode_gate_config.sample_count
            if self.mode_gate_config.enabled
            else self.config.get('sample_batch_size', None)
        )
        sample_num = policy_observation_sample_num(
            self.policy_type,
            configured_sample_count,
        )
        observation = self.adapter.get_policy_observation(sample_num=sample_num)

        processed_observation = self.policy_preprocessor(observation)
        return processed_observation

    def _build_mode_context_metadata(self, instruction: str) -> dict[str, Any]:
        """Collect deterministic task keypoints and ee-proxy scene geometry."""
        import re

        from mode_gate.features import select_task_keypoints

        result: dict[str, Any] = {}
        try:
            positions = self.keypoint_tracker.get_keypoint_positions()
            mask_ids = self.keypoint_tracker.get_mask_ids()
            if positions is not None:
                result["task_keypoints"] = select_task_keypoints(
                    positions,
                    instruction=instruction,
                    mask_ids=mask_ids,
                    keypoint_to_object=getattr(self, "keypoint_id_to_object", {}),
                )
        except Exception as exc:
            log.debug(f"Task keypoints unavailable for mode descriptor: {exc}")

        try:
            objects = sorted(self.adapter.get_scene_objects(), key=lambda item: item.name)
        except Exception as exc:
            log.debug(f"Scene objects unavailable for geometry proxy: {exc}")
            objects = []
        object_positions = {
            str(item.name): np.asarray(item.pose.position, dtype=np.float64).tolist()
            for item in objects
            if np.asarray(item.pose.position).shape == (3,)
            and np.isfinite(item.pose.position).all()
        }
        if object_positions:
            result["object_positions"] = object_positions
            normalized_instruction = set(
                re.findall(r"[a-z0-9]+", instruction.lower().replace("_", " "))
            )
            ranked_targets = []
            for name in object_positions:
                tokens = [
                    token
                    for token in re.findall(
                        r"[a-z0-9]+", name.lower().replace("_", " ")
                    )
                    if len(token) > 1
                ]
                if tokens and all(token in normalized_instruction for token in tokens):
                    ranked_targets.append((-len(tokens), name))
            target_name = min(ranked_targets)[1] if ranked_targets else None
            half_extent = float(self.config.get("geometry_proxy_half_extent_m", 0.04))

            def box(name: str) -> dict[str, Any]:
                center = np.asarray(object_positions[name], dtype=np.float64)
                return {
                    "minimum": (center - half_extent).tolist(),
                    "maximum": (center + half_extent).tolist(),
                    "object_id": name,
                    "exact": False,
                }

            if target_name is not None:
                result["target_aabb"] = box(target_name)
                result["target_object_id"] = target_name
            result["obstacle_aabbs"] = [
                box(name)
                for name in sorted(object_positions)
                if name != target_name
            ][:16]
        return result

    def _run_mode_gate(
        self,
        *,
        sample_policy: Callable[..., Any],
        episode: int,
        episode_dir: str,
        global_step: int,
        current_stage: int,
        use_guidance: bool,
    ) -> Any | None:
        """Sample/score modes and return only the selected real candidate chunk."""
        import hashlib
        from pathlib import Path

        from mode_gate.black_box import as_numpy_actions
        from mode_gate.io_utils import atomic_write_json, sha256_file
        from mode_gate.runtime import RuntimeStatus
        from mode_gate.signatures import (
            map_failure_text,
            signature_hash,
        )
        from mode_gate.types import ActionChunkBatch, GateContext

        # A checked, method-only warm update preserves this object's fields.
        # Refresh source provenance once before recording the first new decision.
        method_revision = getattr(type(self), '_planner_role_methods_sha256', None)
        if method_revision and getattr(self, '_planner_role_recorded_revision', None) != method_revision:
            from mode_gate.preflight import source_revision
            self.mode_gate_source_revision = source_revision(Path(PROJECT_ROOT))
            self._planner_role_recorded_revision = method_revision

        observation_image = np.asarray(self.adapter.get_vlm_image())
        instruction = self.adapter.get_task_description()
        stage_label = str(current_stage)
        stage_descriptions = getattr(self, "stage_descriptions", "")
        for line in str(stage_descriptions).splitlines():
            if line.lower().startswith(f"stage {current_stage}:"):
                stage_label = line
                break
        fingerprint = hashlib.sha256()
        fingerprint.update(observation_image.tobytes())
        fingerprint.update(str(instruction).encode("utf-8"))
        fingerprint.update(stage_label.encode("utf-8"))
        provenance_getter = getattr(self.adapter, "get_context_provenance", None)
        context_provenance = (
            dict(provenance_getter()) if callable(provenance_getter) else {}
        )
        context_id = (
            f"episode-{episode + 1:03d}-step-{global_step:05d}-"
            f"stage-{current_stage}-{fingerprint.hexdigest()[:10]}"
        )
        context = GateContext(
            context_id=context_id,
            observation_image=observation_image,
            task_instruction=instruction,
            task_stage=stage_label,
            metadata={
                "backend": self.backend,
                "episode": episode + 1,
                "global_step": global_step,
                "execution_horizon": int(self.policy._action_chunk_horizon),
                "initialization_posthoc_only": bool(self.config.get('initialization_posthoc_only', False)),
                "planner_steering_enabled": bool(self.config.get('planner_steering_enabled', True)),
                "online_stage_guidance_judgment": bool(
                    self.config.get('planner_steering_enabled', True)
                    and self.config.get('use_vlm_stage_recognition', True)
                    and not self.config.get('initialization_posthoc_only', False)),
                "code_revision": self.mode_gate_source_revision,
                **context_provenance,
                **self._build_mode_context_metadata(instruction),
                "progress_history": tuple(
                    self.mode_aware_runtime.progress_history[-8:]
                ),
                "workspace_bounds": self.config.get(
                    "workspace_bounds",
                    ((-1.0, -1.0, 0.0), (1.0, 1.0, 1.5)),
                ),
            },
        )
        action_info = self.adapter.get_action_space_info()
        active = self.mode_gate_registry.active()
        policy_id = active.policy_id if active is not None else "theta0-pi05-v044"
        snapshot = None
        scene_signature = None

        for sampling_attempt in range(2):
            if self.mode_aware_runtime.verification_due and snapshot is None:
                snapshot = self.mode_gate_snapshot_store.capture(
                    adapter=self.adapter,
                    policy=self.policy,
                    policy_id=policy_id,
                    controller_state={**self.mode_aware_runtime.controller.state.as_dict(),
                                      "executed_history": self.mode_aware_runtime.executed_history},
                    provenance={
                        "backend": self.backend,
                        "episode": episode + 1,
                        "global_step": global_step,
                        "task": instruction,
                        "task_stage": stage_label,
                        "context_id": context_id,
                        **context_provenance,
                        "progress_history": list(
                            self.mode_aware_runtime.progress_history[-8:]
                        ),
                        "planner_model": self.mode_gate_config.planner_model,
                        "planner_prompt_version": self.mode_gate_config.planner_prompt_version,
                        "gemini_thinking_level": self.mode_gate_config.verifier_thinking_level,
                        "label_version": self.mode_gate_config.label_version,
                        "label_config": label_contract_payload(
                            self.mode_gate_config.experiment_contract()
                        ),
                        "chunk_horizon": self.mode_gate_config.chunk_horizon,
                        "retry_budget": self.mode_gate_config.retry_budget,
                        "retry_schedule": [
                            list(level)
                            for level in self.mode_gate_config.retry_schedule
                        ],
                        "sample_count": self.mode_gate_config.sample_count,
                        "policy_checkpoint_digest": self.active_policy_checkpoint_digest,
                        "code_revision": self.mode_gate_source_revision,
                        "guidance": self._guidance_snapshot_provenance(
                            current_stage=current_stage,
                            use_guidance=use_guidance,
                        ),
                        "sampling_config": {
                            "guide_scale": float(
                                getattr(
                                    self,
                                    "current_guide_scale",
                                    self.config.get("guide_scale", 80.0),
                                )
                            ),
                            "diversity_scale": float(
                                self.config.get("diversity_scale", 10.0)
                            ),
                            "start_ratio": self.config.get("start_ratio", None),
                            "MCMC_steps": int(self.config.get("MCMC_steps", 4)),
                            "sigmoid_k": float(self.config.get("sigmoid_k", 12.0)),
                            "sigmoid_x0": float(self.config.get("sigmoid_x0", 0.7)),
                            "use_diversity": bool(
                                self.config.get("use_diversity", True)
                            ),
                            "use_fkd": bool(self.config.get("use_fkd", False)),
                            "fkd": (
                                OmegaConf.to_container(
                                    self.config.get("fkd", {}), resolve=True
                                )
                                if self.config.get("fkd")
                                else None
                            ),
                        },
                    },
                    observation_image=observation_image,
                    stateful_components={"keypoint_tracker": self.keypoint_tracker},
                )
            seed = (
                int(self.cfg.get("seed", 0)) * 1_000_003
                + (episode + 1) * 10_007
                + global_step * 101
                + sampling_attempt
            )
            condition = self.mode_aware_runtime.controller.sampling_condition(seed)
            torch.manual_seed(condition.seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(condition.seed)
            execution_action_chunk = sample_policy(condition)
            candidates = _get_visualization_action_chunk(
                self.policy,
                self.adapter,
                execution_action_chunk,
            )
            candidate_actions = as_numpy_actions(candidates)
            diagnostics_getter = getattr(
                self.policy, "get_last_sampling_diagnostics", None
            )
            metadata = {
                "sampling_condition": {
                    "seed": condition.seed,
                    "retry_index": condition.retry_index,
                    "guide_mult": condition.guide_mult,
                    "diversity_mult": condition.diversity_mult,
                },
            }
            if "task_keypoints" in context.metadata:
                metadata["task_keypoints"] = context.metadata["task_keypoints"]
            if callable(diagnostics_getter):
                diagnostics = diagnostics_getter()
                if diagnostics is not None:
                    metadata["sampling_diagnostics"] = diagnostics
            batch = ActionChunkBatch(
                actions=candidate_actions,
                sample_ids=tuple(
                    f"{context_id}-r{self.mode_aware_runtime.next_round_id:03d}-s{index:03d}"
                    for index in range(len(candidate_actions))
                ),
                context_id=context_id,
                round_id=self.mode_aware_runtime.next_round_id,
                checkpoint_id=policy_id,
                action_space=str(action_info.get("type", "environment_action")),
                coordinate_frame="world",
                metadata=metadata,
            )
            scene_features = None
            scene_path = None
            encoder = getattr(self, "theta0_scene_encoder", None)
            if encoder is not None and self.mode_aware_runtime.verification_due:
                encoded = encoder.encode(observation_image, instruction)
                scene_signature = encoded
                scene_features = encoded.joint_feature
                scene_path = encoded.cache_path
            from mode_gate.ticket_visuals import policy_camera_images
            result = self.mode_aware_runtime.process_batch(
                context=context,
                batch=batch,
                artifact_root=Path(episode_dir) / self.mode_gate_config.output_subdir,
                scene_feature=scene_features,
                scene_feature_path=scene_path,
                snapshot=snapshot,
                camera_images=policy_camera_images(self.adapter),
            )
            if result.status is RuntimeStatus.INTERNAL_RESAMPLE:
                continue
            if result.status in {RuntimeStatus.EXECUTE, RuntimeStatus.RESTEER}:
                selected_index = result.selected.sample_index
                if int(execution_action_chunk.shape[0]) <= selected_index:
                    raise RuntimeError(
                        "selected candidate index is not present in executable policy batch"
                    )
                return execution_action_chunk[selected_index : selected_index + 1]
            if result.status is RuntimeStatus.EXPAND:
                if snapshot is None or scene_signature is None:
                    raise RuntimeError(
                        "EXPANSION requires an exact decision snapshot and theta0 signature"
                    )
                failure_text = " ".join(
                    [
                        *result.semantic_failure_types,
                        result.required_trajectory_pattern,
                        result.route.reason if result.route else "",
                    ]
                )
                failure_mode = map_failure_text(failure_text)
                signature_id = signature_hash(
                    suite=str(
                        context_provenance.get(
                            "base_suite",
                            context_provenance.get("suite", self.backend),
                        )
                    ),
                    task_id=str(context_provenance.get("task_id", "UNKNOWN")),
                    perturbation_variant=str(
                        context_provenance.get("perturbation_variant", "base")
                    ),
                    failure_mode=failure_mode,
                    e_goal=scene_signature.e_goal,
                    e_obs=scene_signature.e_obs,
                )
                request_path = Path(episode_dir) / "mode_gate_expansion_request.json"
                baseline_kind = self.mode_gate_config.baseline_kind
                merge_method = (
                    "retain_uniform"
                    if baseline_kind == "always_expand_retain"
                    else "planner_uniform"
                )
                slow_job = self.mode_gate_slow_loop.create(
                    active_policy_id=policy_id,
                    input_hash=hashlib.sha256(
                        (
                            f"{snapshot.snapshot_hash}\0{signature_id}\0"
                            f"{baseline_kind}\0{merge_method}"
                        ).encode("utf-8")
                    ).hexdigest(),
                    metadata={
                        "context_id": context_id,
                        "record_id": result.record_id,
                        "snapshot_id": snapshot.snapshot_id,
                        "snapshot_hash": snapshot.snapshot_hash,
                        "signature_id": signature_id,
                        "signature_feature_id": scene_signature.feature_id,
                        "signature_feature_path": str(scene_signature.cache_path),
                        "failure_mode": failure_mode.value,
                        "semantic_failure_types": list(result.semantic_failure_types),
                        "required_trajectory_pattern": result.required_trajectory_pattern,
                        "round_analysis_path": result.analysis_path,
                        "multimodal_evidence_path": result.evidence_path,
                        "round_analysis_sha256": sha256_file(
                            Path(result.analysis_path)
                        ),
                        "round_metadata_path": str(
                            Path(result.analysis_path).with_suffix(".json")
                        ),
                        "round_metadata_sha256": sha256_file(
                            Path(result.analysis_path).with_suffix(".json")
                        ),
                        "reason": result.route.reason if result.route else "unknown",
                        "label_eligible": bool(
                            result.route.label_eligible if result.route else False
                        ),
                        "task_instruction": instruction,
                        "target_object_id": context.metadata.get("target_object_id"),
                        "baseline_kind": baseline_kind,
                        "lookup_enabled": baseline_kind
                        != "always_expand_retain",
                        "candidate_merge_method": merge_method,
                        "code_revision": self.mode_gate_source_revision,
                        **context_provenance,
                        "episode_id": self.mode_aware_runtime.episode_id,
                    },
                )
                expansion_automation = self._launch_expansion_automation(slow_job)
                atomic_write_json(
                    request_path,
                    {
                        "schema_version": "expansion-trigger-v2",
                        "context_id": context_id,
                        "policy_id": policy_id,
                        "record_id": result.record_id,
                        "snapshot_id": snapshot.snapshot_id,
                        "snapshot_hash": snapshot.snapshot_hash,
                        "signature_id": signature_id,
                        "failure_mode": failure_mode.value,
                        "code_revision": self.mode_gate_source_revision,
                        "round_analysis_path": result.analysis_path,
                        "multimodal_evidence_path": result.evidence_path,
                        "round_analysis_sha256": sha256_file(
                            Path(result.analysis_path)
                        ),
                        "round_metadata_path": str(
                            Path(result.analysis_path).with_suffix(".json")
                        ),
                        "round_metadata_sha256": sha256_file(
                            Path(result.analysis_path).with_suffix(".json")
                        ),
                        "reason": result.route.reason if result.route else "unknown",
                        "label_eligible": bool(
                            result.route.label_eligible if result.route else False
                        ),
                        "slow_loop_job_id": slow_job.job_id,
                        "automation": expansion_automation,
                    },
                )
                log.warning(f"Mode-aware runtime requested expansion: {request_path}")
                self._wait_for_expansion_demonstrations(slow_job, episode_dir)
                return None
            raise RuntimeError(f"mode-aware runtime aborted: {result.error}")
        raise RuntimeError("mode-aware runtime exceeded the one permitted internal fresh resample")

    def _wait_for_expansion_demonstrations(self, slow_job, episode_dir):
        """Keep the resident fast loop idle until this ticket has usable demos."""
        if (
            not self.mode_gate_config.auto_start_expansion_worker
            or self.mode_gate_config.baseline_kind
        ):
            return
        from pathlib import Path
        from mode_gate.expansion_automation import wait_for_expansion_demonstrations
        from mode_gate.io_utils import atomic_write_json

        def update(progress):
            atomic_write_json(
                Path(episode_dir) / "mode_gate_demonstration_wait.json", progress
            )
            callback = getattr(self, "expansion_wait_callback", None)
            if callback is not None:
                callback(progress)

        wait_for_expansion_demonstrations(
            store=self.mode_gate_slow_loop,
            job_id=slow_job.job_id,
            on_update=update,
            stop_requested=getattr(self, "expansion_stop_requested", None),
            wait_for_completion=bool(getattr(self, "expansion_full_cycle", False)),
        )

    def _guidance_snapshot_provenance(
        self, *, current_stage: int, use_guidance: bool
    ) -> dict[str, Any]:
        """Freeze the generated reward source required for exact replay."""

        from pathlib import Path

        from mode_gate.io_utils import sha256_file

        if not use_guidance:
            return {"enabled": False, "stage": int(current_stage), "files": []}
        root_value = getattr(self, "guidance_functions_dir", None)
        if not root_value:
            raise RuntimeError("guided snapshot has no persisted guidance source")
        root = Path(root_value).resolve()
        required = [root / f"stage{int(current_stage)}_guidance.txt"]
        metadata = root / "metadata.json"
        if metadata.is_file():
            required.append(metadata)
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                f"guided snapshot source files are missing: {missing}"
            )
        return {
            "enabled": True,
            "stage": int(current_stage),
            "root": str(root),
            "files": [
                {"path": str(path), "sha256": sha256_file(path)}
                for path in required
            ],
        }

    def perform_task_for_episode(self, episode_dir: str):
        """Prepare for each episode (keypoint detection, guidance generation, etc.)"""

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
            if (self.use_gemini and self.gemini_grounder is not None and len(object_names) > 0
                    and self.config.get('planner_steering_enabled', True)):
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

        metadata = {
            'init_keypoint_positions': key_points,
            'num_keypoints': len(key_points),
            'key_points_objects_map': key_points_objects_map,
        }
        guidance_functions_dir, program_info, guidance_fns = self._prepare_guidance_program(
            projected_img, instruction, metadata
        )
        self.guidance_functions_dir = os.path.abspath(guidance_functions_dir)
        self.program_info, self.guidance_fns = program_info, guidance_fns
        output_raw_path = os.path.join(guidance_functions_dir, 'output_raw.txt')
        self.stage_descriptions = self.vlm_agent._extract_stage_descriptions_from_output(output_raw_path)

        for stage, fns in self.guidance_fns.items():
            log.info(f"Stage {stage}: {len(fns)} guidance functions loaded")
        log.info(f"Loaded {len(self.guidance_fns)} stages total")
        log.debug(f"Stage descriptions:\n{self.stage_descriptions}")

    def _prepare_guidance_program(self, image, instruction, metadata):
        """Validate generated rewards and request bounded syntax repairs before motion.

        The same reward-code provider sees the same scene/instruction. Rejected
        programs stay in separate attempt directories; the AST sandbox is never
        weakened and cached programs are read-only, not silently rewritten.
        """
        from copy import deepcopy
        from pathlib import Path
        from mode_gate.io_utils import atomic_write_json
        from rsi.utils.guidance_utils import (
            _SAFE_BUILTINS, _SAFE_TENSOR_MEMBERS, _SAFE_TORCH_MEMBERS,
            load_functions_from_txt,
        )

        def load_program(directory):
            directory = Path(directory)
            try:
                info = json.loads((directory / 'metadata.json').read_text())
                count = int(info['num_stages'])
            except (OSError, KeyError, TypeError, ValueError) as error:
                raise ValueError(f'invalid guidance metadata: {error}') from error
            if count < 1:
                raise ValueError('guidance must describe at least one stage')
            functions = {}
            for stage in range(1, count + 1):
                path = directory / f'stage{stage}_guidance.txt'
                if not path.is_file():
                    raise ValueError(f'missing generated stage {stage} guidance file')
                functions[stage] = load_functions_from_txt(str(path))
                if not functions[stage]:
                    raise ValueError(f'empty generated stage {stage} guidance')
            return str(directory), info, functions

        if self.cached_functions_dir is not None:
            log.info(f"Using cached guidance functions from: {self.cached_functions_dir}")
            return load_program(self.cached_functions_dir)

        attempts = int(self.config.get('guidance_code_generation_attempts', 3))
        if not 1 <= attempts <= 5:
            raise ValueError('guidance code generation attempts must be between 1 and 5')
        original_template = self.vlm_agent.prompt_template
        base_dir = Path(self.vlm_agent.task_dir)
        constraints = (
            '\n\nRUNTIME EXECUTION CONTRACT (overrides any earlier suggestion to use arbitrary Python/PyTorch):\n'
            'Rewards must be side-effect-free tensor expressions. Assign only local variable names. '
            'Never assign or augment tensor elements/slices/attributes, including on a copy; '
            'do not call clone, detach, numpy, item, or in-place methods. '
            'Instead of copying and changing an element, form a new target by adding a '
            'torch.tensor offset with the source tensor device/dtype. '
            'Do not import modules, define helpers, use loops, branches, comprehensions, '
            'filesystem/network calls, or private attributes. '
            'Each stage file must stay within 500 AST nodes and 32 KiB. '
            'Provide a self-contained stageN_guidance(keypoints, action_sequence) for every declared stage.\n'
            f'Allowed builtins: {", ".join(sorted(_SAFE_BUILTINS))}.\n'
            f'Allowed torch members: {", ".join(sorted(_SAFE_TORCH_MEMBERS))}.\n'
            f'Allowed tensor members: {", ".join(sorted(_SAFE_TENSOR_MEMBERS))}.\n'
        )
        feedback = ''
        try:
            for attempt in range(1, attempts + 1):
                directory = base_dir if attempt == 1 else base_dir / f'generation_{attempt:03d}'
                directory.mkdir(parents=True, exist_ok=True)
                self.vlm_agent.task_dir = str(directory)
                self.vlm_agent.prompt_template = original_template + constraints + feedback
                try:
                    generated = self.vlm_agent.generate_guidance(image, instruction, deepcopy(metadata))
                    result = load_program(generated)
                except ValueError as error:
                    atomic_write_json(directory / 'validation_error.json', {
                        'generation_attempt': attempt, 'error': f'{type(error).__name__}: {error}',
                        'executed_steps': 0, 'native_failure_label_allowed': False,
                    })
                    if attempt == attempts:
                        raise
                    log.warning(f'Generated reward validation failed; repairing code in the same warm '
                                f'attempt ({attempt}/{attempts}), no robot motion: {error}')
                    raw = directory / 'output_raw.txt'
                    previous = raw.read_text()[:16000] if raw.is_file() else ''
                    feedback = ('\nPrevious output failed runtime validation. Keep the same scene, '
                                'task and intended reward; repair its unsupported syntax/operations.\n'
                                f'Validation error: {error}\nPrevious output:\n{previous}\n')
                    continue
                atomic_write_json(directory / 'validation_result.json', {
                    'accepted': True, 'generation_attempt': attempt,
                    'validator': 'unchanged_guidance_ast_and_dummy_inputs',
                })
                return result
        finally:
            self.vlm_agent.prompt_template = original_template

    def _record_preparation_failure(self, episode_dir, error):
        """A no-motion preparation failure is not the previous completed episode."""
        if self.mode_aware_runtime is not None:
            import hashlib
            identity = 'preparation-' + hashlib.sha256(os.path.abspath(episode_dir).encode()).hexdigest()
            self.mode_aware_runtime.episode_id = identity
            self.mode_gate_incidents.record_fact(
                episode_id=identity, context_id='', kind='episode_preparation_failure',
                payload={'output_dir':os.path.abspath(episode_dir),
                         'error':f'{type(error).__name__}: {error}',
                         'executed_steps':0, 'native_failure_label_allowed':False},
            )

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

        if (trigger_reason and self.gemini_stage_recognizer is not None
                and self.config.get('use_vlm_stage_recognition', True)
                and self.config.get('planner_steering_enabled', True)
                and not self.config.get('initialization_posthoc_only', False)
                and vlm_query_count < vlm_query_limit):
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
        from mode_gate.formal_protocol import apply_requested_warm_update
        apply_requested_warm_update(self)
        if getattr(getattr(self, 'mode_gate_config', None), 'enabled', False):
            from scripts.initialize_candidate_verifier import continue_driver_if_requested
            continue_driver_if_requested(self)
        self.success_count = 0
        base_output_dir = self.output_dir
        episode_num = self.config.get('episode_num', 10)

        for episode in range(episode_num):
            fixed_env_seed = self.config.get("env_seed", None)
            fixed_policy_seed = self.config.get("policy_seed", None)
            episode_seed = (
                int(fixed_env_seed)
                if fixed_env_seed is not None
                else torch.randint(0, 1000, (1,)).item()
            )
            if fixed_policy_seed is not None:
                np.random.seed(int(fixed_policy_seed) % (2**32))
                torch.manual_seed(int(fixed_policy_seed))
                if torch.cuda.is_available():
                    torch.cuda.manual_seed_all(int(fixed_policy_seed))
            self._reload_active_deployment()
            self.policy.reset()
            self.video_recorder.clear()
            episode_dir = os.path.join(base_output_dir, f'episode_{episode+1}')
            os.makedirs(episode_dir, exist_ok=True)

            # Reset environment
            init_state_id = self.config.get("init_state_id", None)
            if init_state_id is not None and self.backend != "libero":
                raise ValueError("main.init_state_id is supported only by LIBERO")
            reset_kwargs = {"seed": episode_seed}
            if init_state_id is not None:
                reset_kwargs["init_state_id"] = str(init_state_id)
            self.adapter.reset(**reset_kwargs)

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
                    self._record_preparation_failure(episode_dir, e)
                    episode_error = True
                    # Save error info
                    error_file = os.path.join(episode_dir, 'error.txt')
                    with open(error_file, 'w') as f:
                        import traceback
                        f.write(f"Error during episode preparation:\n{traceback.format_exc()}")
                    if self.config.get("fail_on_episode_error", False):
                        raise RuntimeError(
                            f"episode {episode + 1} preparation failed"
                        ) from e
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
                if self.config.get("fail_on_episode_error", False):
                    raise RuntimeError(
                        f"episode {episode + 1} execution failed"
                    ) from e
                log.warning(f"Skipping episode {episode+1} due to execution error")
                continue
            finally:
                if self.mode_aware_runtime is not None:
                    self.mode_gate_incidents.experiences.finish_video(self.mode_aware_runtime.episode_id, finalize=True)

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
        last_chunk_stage = current_stage
        last_chunk_reward = 0.0
        last_step_info = {}
        if self.mode_aware_runtime is not None:
            self.mode_aware_runtime.start_episode(stage_id=str(current_stage))
            from mode_gate.ticket_visuals import policy_camera_images
            self.mode_gate_incidents.record_video_frame(
                self.mode_aware_runtime.episode_id, policy_camera_images(self.adapter),
                context_id="initial", step=0)

        while not done:
            if getattr(self, "expansion_stop_requested", lambda: False)():
                raise InterruptedError("experiment park/stop requested at policy step boundary")
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

            if (
                generate_new_chunk
                and action_chunk is not None
                and self.mode_aware_runtime is not None
            ):
                from mode_gate.types import FailureTrigger

                current_reward = (
                    float(self.policy.get_normalized_reward())
                    if hasattr(self.policy, "get_normalized_reward")
                    else 0.0
                )
                stage_advanced = current_stage != last_chunk_stage
                predicate_getter = getattr(
                    self.adapter, "get_progress_predicate", None
                )
                predicate_raw = predicate_getter() if callable(predicate_getter) else None
                predicate = dict(predicate_raw or {})
                progress = self.mode_aware_runtime.assess_progress(
                    task_success=bool(last_step_info.get("success", False)),
                    predicate_stage_id=predicate.get("stage_id"),
                    predicate_advanced=predicate.get("advanced"),
                    gemini_stage_id=(str(current_stage) if stage_advanced else None),
                    gemini_confidence=(0.8 if stage_advanced else None),
                    normalized_reward=current_reward,
                    relation_improved=current_reward - last_chunk_reward >= 0.02,
                )
                contact_check = getattr(self.adapter, "has_forbidden_contact", None)
                trigger = (
                    FailureTrigger.CONTACT
                    if callable(contact_check) and contact_check()
                    else None
                )
                self.mode_aware_runtime.observe_chunk(
                    progress,
                    failure_trigger=trigger,
                )
                last_chunk_stage = current_stage
                last_chunk_reward = current_reward

            # Get parameters from config
            guide_scale = getattr(self, 'current_guide_scale', self.config.get("guide_scale", 80.0))
            sigmoid_k = self.config.get("sigmoid_k", 12.0)
            sigmoid_x0 = self.config.get("sigmoid_x0", 0.7)

            def sample_policy(sampling_condition=None) -> Any:
                condition_guide = (
                    float(sampling_condition.guide_mult)
                    if sampling_condition is not None
                    else 1.0
                )
                condition_diversity = (
                    float(sampling_condition.diversity_mult)
                    if sampling_condition is not None
                    else 1.0
                )
                sampled_chunk = self.policy.select_action(
                    observation,
                    generate_new_chunk=generate_new_chunk,
                    use_guidance=use_guidance,
                    keypoints=keypoints,
                    guidance_fns=current_guidance_fns,
                    guide_scale=guide_scale * condition_guide,
                    sigmoid_k=sigmoid_k,
                    sigmoid_x0=sigmoid_x0,
                    start_ratio=self.config.get("start_ratio", None),
                    use_diversity=self.config.get("use_diversity", True),
                    diversity_scale=(
                        self.config.get("diversity_scale", 10.0)
                        * condition_diversity
                    ),
                    MCMC_steps=self.config.get("MCMC_steps", 4),
                    verbose=True,
                    use_fkd=self.config.get("use_fkd", False),
                    fkd_config=(
                        OmegaConf.to_container(
                            self.config.get("fkd", {}), resolve=True
                        )
                        if self.config.get("fkd")
                        else None
                    ),
                    global_step=global_steps,
                    current_stage=current_stage,
                )
                if hasattr(self.adapter, 'env_postprocessor'):
                    transition = self.adapter.env_postprocessor(
                        {"action": sampled_chunk}
                    )
                    sampled_chunk = transition["action"]
                return sampled_chunk

            if (
                self.mode_gate_controller is not None
                and generate_new_chunk
            ):
                action_chunk = self._run_mode_gate(
                    sample_policy=sample_policy,
                    episode=episode,
                    episode_dir=episode_dir,
                    global_step=global_steps,
                    current_stage=current_stage,
                    use_guidance=use_guidance,
                )
                if action_chunk is None:
                    # Expansion execution is intentionally outside this change.
                    # Save the complete no-action episode before returning.
                    image = np.array(self.adapter.get_vlm_image())
                    image_with_status = add_text_to_image(
                        image,
                        [
                            f"Step:{global_steps} Stage:{current_stage}",
                            "Mode gate: REQUEST_EXPANSION",
                            "No candidate action executed",
                        ],
                    )
                    self.video_recorder.add_frame(
                        self.adapter.vlm_camera,
                        image_with_status,
                    )
                    video_path = os.path.join(
                        episode_dir,
                        f"episode_{episode + 1}_mode_gate_expansion",
                    )
                    self.video_recorder.save_video(
                        save_path=video_path,
                        success=False,
                        behavior_name="mode_gate_expansion",
                    )
                    return
            elif self.mode_gate_controller is None:
                action_chunk = sample_policy(None)
            # With the candidate controller, keep the selected executable
            # chunk between boundaries. The policy cache still contains all
            # candidates; rereading it would switch back to particle zero.

            # Get image and add status overlay
            if self.config.get("debug_draw_trajectory", False):
                from utils.vis_utils import draw_action_trajectory_on_vlm_image
                visualization_action_chunk = (
                    action_chunk
                    if self.mode_aware_runtime is not None
                    else _get_visualization_action_chunk(
                        self.policy,
                        self.adapter,
                        action_chunk,
                    )
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
                k = self.config.get("sigmoid_k", 12.0)
                x0 = self.config.get("sigmoid_x0", 0.8)
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
            last_step_info = info
            if self.mode_aware_runtime is not None:
                from mode_gate.ticket_visuals import policy_camera_images
                recorded_action = action_chunk[0][action_executed]
                if hasattr(recorded_action, "detach"):
                    recorded_action = recorded_action.detach().cpu().numpy()
                self.mode_aware_runtime.record_execution_step(
                    recorded_action, self.adapter.get_ee_pose_world(),
                    native_success=bool(info.get("success", False)),
                    images=policy_camera_images(self.adapter))
                if terminated or truncated or info.get("success", False):
                    self.mode_aware_runtime._close_factual_labels(
                        success=bool(info.get("success", False)),
                        censored=not bool(info.get("success", False)), reason="native_terminal")
                    self.mode_gate_incidents.experiences.finish_video(self.mode_aware_runtime.episode_id)

            action_executed += 1
            if action_executed == action_horizon:
                action_executed = 0

            observation = self._get_policy_observation()
            global_steps += 1

            if terminated or truncated or info.get('success', False):
                is_success = info.get('success', False)
                if self.mode_aware_runtime is not None:
                    self.mode_gate_incidents.record_fact(
                        episode_id=self.mode_aware_runtime.episode_id, context_id='',
                        kind='rollout_completed', payload={
                            'native_success': bool(is_success), 'steps': global_steps,
                            'terminated': bool(terminated), 'truncated': bool(truncated),
                            'success_authority': 'LIBERO-PRO native success only',
                            'complete_task_rollout': True,
                        })
                if (
                    not is_success
                    and self.mode_aware_runtime is not None
                ):
                    import hashlib
                    from pathlib import Path

                    from mode_gate.io_utils import atomic_write_json
                    from mode_gate.signatures import FailureMode, signature_hash
                    from mode_gate.types import ProgressEvidence

                    timeout_route = self.mode_aware_runtime.observe_chunk(
                        ProgressEvidence(
                            stage_id="UNKNOWN",
                            advanced=False,
                            confidence=0.0,
                            source="terminal_timeout",
                        ),
                        terminal_timeout=True,
                    )
                    active = self.mode_gate_registry.active()
                    policy_id = active.policy_id if active else "theta0-pi05-v044"
                    instruction = self.adapter.get_task_description()
                    image = np.asarray(self.adapter.get_vlm_image())
                    encoder = getattr(self, "theta0_scene_encoder", None)
                    if encoder is None:
                        raise RuntimeError(
                            "terminal EXPANSION requires the immutable theta0 signature encoder"
                        )
                    signature = encoder.encode(image, instruction)
                    provenance_getter = getattr(
                        self.adapter, "get_context_provenance", None
                    )
                    provenance = (
                        dict(provenance_getter())
                        if callable(provenance_getter)
                        else {}
                    )
                    timeout_context_id = (
                        f"timeout-episode-{episode + 1:03d}-step-{global_steps:05d}"
                    )
                    timeout_snapshot = self.mode_gate_snapshot_store.capture(
                        adapter=self.adapter,
                        policy=self.policy,
                        policy_id=policy_id,
                        controller_state={**self.mode_aware_runtime.controller.state.as_dict(),
                                      "executed_history": self.mode_aware_runtime.executed_history},
                        provenance={
                            "backend": self.backend,
                            "episode": episode + 1,
                            "global_step": global_steps,
                            "task": instruction,
                            "context_id": timeout_context_id,
                            "terminal_timeout": True,
                            **provenance,
                            "label_version": self.mode_gate_config.label_version,
                            "label_config": label_contract_payload(
                                self.mode_gate_config.experiment_contract()
                            ),
                        },
                        observation_image=image,
                        stateful_components={"keypoint_tracker": self.keypoint_tracker},
                    )
                    timeout_signature_id = signature_hash(
                        suite=str(
                            provenance.get(
                                "base_suite", provenance.get("suite", self.backend)
                            )
                        ),
                        task_id=str(provenance.get("task_id", "UNKNOWN")),
                        perturbation_variant=str(
                            provenance.get("perturbation_variant", "base")
                        ),
                        failure_mode=FailureMode.UNKNOWN,
                        e_goal=signature.e_goal,
                        e_obs=signature.e_obs,
                    )
                    from mode_gate.ticket_visuals import build_decision_evidence, policy_camera_images
                    from mode_gate.types import GateContext
                    timeout_evidence = build_decision_evidence(
                        directory=Path(episode_dir) / "timeout_evidence",
                        context=GateContext(timeout_context_id, image, instruction, str(current_stage),
                                            self._build_mode_context_metadata(instruction)),
                        analysis_path=self.mode_aware_runtime.last_analysis_path,
                        executed_history=self.mode_aware_runtime.executed_history,
                        images=policy_camera_images(self.adapter),
                        project_points=self.mode_aware_runtime.combined_renderer._project_points,
                        library=self.mode_gate_incidents.experiences,
                        episode_id=self.mode_aware_runtime.episode_id)
                    timeout_job = self.mode_gate_slow_loop.create(
                        active_policy_id=policy_id,
                        input_hash=hashlib.sha256(
                            (
                                f"{timeout_snapshot.snapshot_hash}\0"
                                f"{timeout_signature_id}\0"
                                f"{self.mode_gate_config.baseline_kind}\0"
                                f"{'retain_uniform' if self.mode_gate_config.baseline_kind == 'always_expand_retain' else 'planner_uniform'}"
                            ).encode("utf-8")
                        ).hexdigest(),
                        metadata={
                            "context_id": timeout_context_id,
                            "record_id": None,
                            "multimodal_evidence_path": str(timeout_evidence),
                            "snapshot_id": timeout_snapshot.snapshot_id,
                            "snapshot_hash": timeout_snapshot.snapshot_hash,
                            "signature_id": timeout_signature_id,
                            "signature_feature_id": signature.feature_id,
                            "signature_feature_path": str(signature.cache_path),
                            "failure_mode": FailureMode.UNKNOWN.value,
                            "semantic_failure_types": ["terminal timeout"],
                            "required_trajectory_pattern": "complete within episode horizon",
                            "task_instruction": instruction,
                            "reason": timeout_route.reason,
                            "label_eligible": False,
                            "baseline_kind": self.mode_gate_config.baseline_kind,
                            "lookup_enabled": self.mode_gate_config.baseline_kind
                            != "always_expand_retain",
                            "candidate_merge_method": (
                                "retain_uniform"
                                if self.mode_gate_config.baseline_kind
                                == "always_expand_retain"
                                else "planner_uniform"
                            ),
                            **provenance,
                            "episode_id": self.mode_aware_runtime.episode_id,
                            "complete_task_rollout": True,
                            "executed_steps": global_steps,
                            "native_terminal_reason": "truncated" if truncated else "terminated",
                        },
                    )
                    timeout_automation = self._launch_expansion_automation(
                        timeout_job
                    )
                    atomic_write_json(
                        Path(episode_dir) / "mode_gate_timeout_expansion.json",
                        {
                            "schema_version": "expansion-trigger-v2",
                            "reason": timeout_route.reason,
                            "label_eligible": False,
                            "snapshot_id": timeout_snapshot.snapshot_id,
                            "signature_id": timeout_signature_id,
                            "failure_mode": FailureMode.UNKNOWN.value,
                            "slow_loop_job_id": timeout_job.job_id,
                            "automation": timeout_automation,
                        },
                    )
                    self._wait_for_expansion_demonstrations(timeout_job, episode_dir)
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
        python main.py main.episode_num=50 main.guide_scale=120
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
