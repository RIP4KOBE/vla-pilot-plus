"""
RDT Policy Wrapper for Isaac-GR00T Evaluation Framework

This module provides a policy wrapper that makes RDT models compatible with
the Isaac-GR00T evaluation framework's BasePolicy interface.
"""

import os
import sys
from typing import Any

import numpy as np
import torch
from PIL import Image

# Add parent directory to path for importing RDT modules
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from configs.state_vec import STATE_VEC_IDX_MAPPING
from models.multimodal_encoder.siglip_encoder import SiglipVisionTower
from models.multimodal_encoder.t5_encoder import T5Embedder
from models.rdt_runner import RDTRunner


# State indices for LIBERO (7 arm joints + 2 gripper joints)
LIBERO_STATE_INDICES = [
    STATE_VEC_IDX_MAPPING[f"arm_joint_{i}_pos"] for i in range(7)
] + [
    STATE_VEC_IDX_MAPPING[f"gripper_joint_{i}_pos"] for i in range(2)
]

# Action indices for LIBERO (6D EEF velocity + gripper)
LIBERO_ACTION_INDICES = [
    STATE_VEC_IDX_MAPPING["eef_vel_x"],
    STATE_VEC_IDX_MAPPING["eef_vel_y"],
    STATE_VEC_IDX_MAPPING["eef_vel_z"],
    STATE_VEC_IDX_MAPPING["eef_angular_vel_roll"],
    STATE_VEC_IDX_MAPPING["eef_angular_vel_pitch"],
    STATE_VEC_IDX_MAPPING["eef_angular_vel_yaw"],
    STATE_VEC_IDX_MAPPING["gripper_open"],
]


class RDTPolicy:
    """
    RDT Policy wrapper compatible with Isaac-GR00T's BasePolicy interface.
    
    This class wraps the RDT model to work with the gymnasium-based 
    LIBERO evaluation framework from Isaac-GR00T.
    """
    
    def __init__(
        self,
        config_path: str,
        pretrained_path: str,
        lora_adapter_path: str | None = None,
        device: str | int = "cuda",
        dtype: torch.dtype = torch.bfloat16,
        n_action_steps: int = 8,
        pretrained_text_encoder: str = "google/t5-v1_1-xxl",
        pretrained_vision_encoder: str = "google/siglip-so400m-patch14-384",
    ):
        """
        Initialize the RDT Policy.
        
        Args:
            config_path: Path to the RDT config YAML file
            pretrained_path: Path to the pretrained RDT checkpoint
            lora_adapter_path: Optional path to LoRA adapter
            device: Device to run inference on
            dtype: Data type for model weights
            n_action_steps: Number of action steps to execute before re-inference
            pretrained_text_encoder: Path or name of the text encoder
            pretrained_vision_encoder: Path or name of the vision encoder
        """
        import yaml
        
        self.device = device if isinstance(device, str) else f"cuda:{device}"
        self.dtype = dtype
        self.n_action_steps = n_action_steps
        
        # Load config
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
        
        # Initialize encoders
        # Note: Use model names, not full paths (the code will load from local dirs via symlinks)
        text_encoder_name = pretrained_text_encoder
        vision_encoder_name = pretrained_vision_encoder
        
        # Extract model name if full path is provided
        if "/" in text_encoder_name and not text_encoder_name.startswith("google/"):
            text_encoder_name = "google/t5-v1_1-xxl"
        if "/" in vision_encoder_name and not vision_encoder_name.startswith("google/"):
            vision_encoder_name = "google/siglip-so400m-patch14-384"
        
        print(f"[RDTPolicy] Loading text encoder: {text_encoder_name}")
        self.text_embedder = T5Embedder(
            from_pretrained=text_encoder_name,
            model_max_length=self.config["dataset"]["tokenizer_max_length"],
            device=self.device
        )
        self.text_tokenizer = self.text_embedder.tokenizer
        self.text_model = self.text_embedder.model
        
        print(f"[RDTPolicy] Loading vision encoder: {vision_encoder_name}")
        self.vision_encoder = SiglipVisionTower(
            vision_tower=vision_encoder_name, 
            args=None
        )
        self.image_processor = self.vision_encoder.image_processor
        
        # Initialize RDT policy
        print("[RDTPolicy] Initializing RDT model...")
        img_cond_len = (
            self.config["common"]["img_history_size"] 
            * self.config["common"]["num_cameras"] 
            * self.vision_encoder.num_patches
        )
        
        self.policy = RDTRunner(
            action_dim=self.config["common"]["state_dim"],
            pred_horizon=self.config["common"]["action_chunk_size"],
            config=self.config["model"],
            lang_token_dim=self.config["model"]["lang_token_dim"],
            img_token_dim=self.config["model"]["img_token_dim"],
            state_token_dim=self.config["model"]["state_token_dim"],
            max_lang_cond_len=self.config["dataset"]["tokenizer_max_length"],
            img_cond_len=img_cond_len,
            img_pos_embed_config=[
                ("image", (
                    self.config["common"]["img_history_size"],
                    self.config["common"]["num_cameras"],
                    -self.vision_encoder.num_patches
                )),
            ],
            lang_pos_embed_config=[
                ("lang", -self.config["dataset"]["tokenizer_max_length"]),
            ],
            dtype=self.dtype,
        )
        
        # Load weights
        self._load_weights(pretrained_path, lora_adapter_path)
        
        # Move to device
        self._to_device()
        
        # Action buffer for multi-step execution
        self._action_buffer = None
        self._action_index = 0
        self._cached_lang_embed = None
        self._cached_task_description = None
        
        # Image history (RDT needs img_history_size frames, typically 2)
        self.img_history_size = self.config["common"]["img_history_size"]  # Usually 2
        self.num_cameras = self.config["common"]["num_cameras"]  # Usually 3
        self._agentview_history = []  # List of images (maxlen = img_history_size)
        self._wrist_history = []  # List of images (maxlen = img_history_size)
        
        print("[RDTPolicy] Initialization complete!")
    
    def _load_weights(self, pretrained_path: str, lora_adapter_path: str | None = None):
        """Load model weights."""
        if lora_adapter_path is not None:
            # Load base model first
            print(f"[RDTPolicy] Loading base model: {pretrained_path}")
            self._load_checkpoint(pretrained_path)
            
            # Then load LoRA adapter
            print(f"[RDTPolicy] Loading LoRA adapter: {lora_adapter_path}")
            from peft import PeftModel
            self.policy = PeftModel.from_pretrained(
                self.policy,
                lora_adapter_path,
                is_trainable=False
            )
            print("[RDTPolicy] Merging LoRA weights...")
            self.policy = self.policy.merge_and_unload()
        else:
            print(f"[RDTPolicy] Loading checkpoint: {pretrained_path}")
            self._load_checkpoint(pretrained_path)
    
    def _load_checkpoint(self, path: str):
        """Load checkpoint from path."""
        def extract_state_dict(checkpoint):
            if isinstance(checkpoint, dict) and "module" in checkpoint:
                return checkpoint["module"]
            elif isinstance(checkpoint, dict) and "state_dict" in checkpoint:
                return checkpoint["state_dict"]
            return checkpoint
        
        if os.path.isdir(path):
            # Try EMA first
            ema_path = os.path.join(path, 'ema', 'pytorch_model.bin')
            if os.path.exists(ema_path):
                print(f"  -> Loading EMA weights: {ema_path}")
                ckpt = torch.load(ema_path, map_location='cpu')
                self.policy.load_state_dict(extract_state_dict(ckpt))
                return
            
            # Try pytorch_model.bin
            bin_path = os.path.join(path, 'pytorch_model.bin')
            if os.path.exists(bin_path):
                print(f"  -> Loading: {bin_path}")
                ckpt = torch.load(bin_path, map_location='cpu')
                self.policy.load_state_dict(extract_state_dict(ckpt))
                return
            
            # Try .pt files
            pt_files = [f for f in os.listdir(path) if f.endswith('.pt')]
            if pt_files:
                pt_path = os.path.join(path, pt_files[0])
                print(f"  -> Loading: {pt_path}")
                ckpt = torch.load(pt_path, map_location='cpu')
                self.policy.load_state_dict(extract_state_dict(ckpt))
                return
            
            raise FileNotFoundError(f"No checkpoint found in {path}")
        else:
            ckpt = torch.load(path, map_location='cpu')
            self.policy.load_state_dict(extract_state_dict(ckpt))
    
    def _to_device(self):
        """Move models to device."""
        self.policy.eval()
        self.text_model.eval()
        self.vision_encoder.eval()
        
        self.policy = self.policy.to(self.device, dtype=self.dtype)
        self.text_model = self.text_model.to(self.device, dtype=self.dtype)
        self.vision_encoder = self.vision_encoder.to(self.device, dtype=self.dtype)
    
    def reset(self, options: dict[str, Any] | None = None) -> dict[str, Any]:
        """Reset policy state."""
        self._action_buffer = None
        self._action_index = 0
        self._cached_lang_embed = None
        self._cached_task_description = None
        # Clear image history
        self._agentview_history = []
        self._wrist_history = []
        return {}
    
    def encode_instruction(self, instruction: str) -> torch.Tensor:
        """Encode text instruction to embeddings."""
        tokens = self.text_tokenizer(
            instruction,
            return_tensors="pt",
            padding="longest",
            truncation=True
        )["input_ids"].to(self.device)
        
        tokens = tokens.view(1, -1)
        with torch.no_grad():
            embeddings = self.text_model(tokens).last_hidden_state.detach()
        
        return embeddings.to(dtype=self.dtype)
    
    def _format_state(self, joints: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Format joint state to unified state vector."""
        # Normalize gripper state
        gripper_min, gripper_max = -0.04245, 0.05185
        joints = joints.clone()
        joints[..., -2:] = (joints[..., -2:] - gripper_min) / (gripper_max - gripper_min)
        
        B, N, _ = joints.shape
        state = torch.zeros(
            (B, N, self.config["model"]["state_token_dim"]),
            device=joints.device, dtype=joints.dtype
        )
        state[:, :, LIBERO_STATE_INDICES] = joints
        
        state_mask = torch.zeros(
            (B, self.config["model"]["state_token_dim"]),
            device=joints.device, dtype=joints.dtype
        )
        state_mask[:, LIBERO_STATE_INDICES] = 1
        
        return state, state_mask
    
    def _unformat_action(self, action: torch.Tensor) -> torch.Tensor:
        """Extract action from unified state vector."""
        joints = action[:, :, LIBERO_ACTION_INDICES]
        
        # Binarize gripper action
        joints[..., -1] = torch.where(
            joints[..., -1] < 0,
            torch.tensor(-1.0, device=joints.device),
            torch.tensor(1.0, device=joints.device)
        )
        
        return joints
    
    def _process_images(self, images: list[np.ndarray | None]) -> torch.Tensor:
        """Process images for the vision encoder."""
        background_color = np.array(
            [int(x * 255) for x in self.image_processor.image_mean],
            dtype=np.uint8
        ).reshape(1, 1, 3)
        background_image = np.ones((
            self.image_processor.size["height"],
            self.image_processor.size["width"], 3
        ), dtype=np.uint8) * background_color
        
        image_tensors = []
        for img in images:
            if img is None:
                pil_img = Image.fromarray(background_image)
            else:
                pil_img = Image.fromarray(img) if isinstance(img, np.ndarray) else img
            
            # Handle aspect ratio padding
            if self.config["dataset"].get("image_aspect_ratio", "pad") == 'pad':
                width, height = pil_img.size
                if width != height:
                    bg_color = tuple(int(x * 255) for x in self.image_processor.image_mean)
                    if width > height:
                        result = Image.new(pil_img.mode, (width, width), bg_color)
                        result.paste(pil_img, (0, (width - height) // 2))
                    else:
                        result = Image.new(pil_img.mode, (height, height), bg_color)
                        result.paste(pil_img, ((height - width) // 2, 0))
                    pil_img = result
            
            processed = self.image_processor.preprocess(pil_img, return_tensors='pt')['pixel_values'][0]
            image_tensors.append(processed)
        
        return torch.stack(image_tensors, dim=0).to(self.device, dtype=self.dtype)
    
    @torch.no_grad()
    def get_action(
        self, 
        observation: dict[str, Any],
        options: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Get action from observation.
        
        Compatible with Isaac-GR00T's LIBERO environment observation format:
        - video.image: (B, T, H, W, C) uint8
        - video.wrist_image: (B, T, H, W, C) uint8
        - state.x/y/z/roll/pitch/yaw/gripper: state values
        - annotation.human.action.task_description: task instruction
        
        Returns:
            Tuple of (action_dict, info_dict)
        """
        # Get batch size
        if "video.image" in observation:
            batch_size = observation["video.image"].shape[0]
        else:
            batch_size = 1
        
        # Check if we need to re-infer
        if self._action_buffer is None or self._action_index >= self.n_action_steps:
            # Update image history with current observation
            # Observations come as (B, T, H, W, C), we take the latest frame
            if "video.image" in observation:
                agentview = observation["video.image"]
                if agentview.ndim == 5:  # (B, T, H, W, C)
                    agentview = agentview[0, -1]  # Take latest frame from first batch
                elif agentview.ndim == 4:  # (B, H, W, C)
                    agentview = agentview[0]
                # agentview is now (H, W, C)
                self._agentview_history.append(agentview)
                if len(self._agentview_history) > self.img_history_size:
                    self._agentview_history.pop(0)
            
            if "video.wrist_image" in observation:
                wrist = observation["video.wrist_image"]
                if wrist.ndim == 5:  # (B, T, H, W, C)
                    wrist = wrist[0, -1]
                elif wrist.ndim == 4:  # (B, H, W, C)
                    wrist = wrist[0]
                self._wrist_history.append(wrist)
                if len(self._wrist_history) > self.img_history_size:
                    self._wrist_history.pop(0)
            
            # Build images list for RDT: (img_history_size * num_cameras) images
            # Order: [t0_cam0, t0_cam1, t0_cam2, t1_cam0, t1_cam1, t1_cam2, ...]
            # For LIBERO: cam0 = agentview, cam1 = wrist, cam2 = None
            images = []
            for b in range(batch_size):
                batch_images = []
                for t in range(self.img_history_size):
                    # Get image from history, pad with first frame if not enough history
                    if t < len(self._agentview_history):
                        batch_images.append(self._agentview_history[t])
                    elif len(self._agentview_history) > 0:
                        batch_images.append(self._agentview_history[0])  # Repeat first frame
                    else:
                        batch_images.append(None)
                    
                    if t < len(self._wrist_history):
                        batch_images.append(self._wrist_history[t])
                    elif len(self._wrist_history) > 0:
                        batch_images.append(self._wrist_history[0])
                    else:
                        batch_images.append(None)
                    
                    # Placeholder for third camera (RDT expects 3 cameras)
                    batch_images.append(None)
                images.append(batch_images)
            
            # Get task description
            if "annotation.human.action.task_description" in observation:
                task_desc = observation["annotation.human.action.task_description"]
                if isinstance(task_desc, (list, tuple)):
                    task_desc = task_desc[0]
            else:
                task_desc = ""
            
            # Encode language (with caching)
            if task_desc != self._cached_task_description:
                self._cached_lang_embed = self.encode_instruction(task_desc)
                self._cached_task_description = task_desc
            lang_embed = self._cached_lang_embed
            
            # Get state - use joint_pos (7) + gripper (2) = 9 dimensions
            # This matches the original RDT training data format
            if "state.joint_pos" in observation and "state.gripper" in observation:
                joint_pos = observation["state.joint_pos"]
                gripper = observation["state.gripper"]
                
                # Handle batched observations
                if isinstance(joint_pos, np.ndarray):
                    joint_pos = joint_pos.flatten()[:7]  # 7 arm joints
                else:
                    joint_pos = np.array(joint_pos).flatten()[:7]
                    
                if isinstance(gripper, np.ndarray):
                    gripper = gripper.flatten()[:2]  # 2 gripper joints
                else:
                    gripper = np.array(gripper).flatten()[:2]
                
                proprio = np.concatenate([joint_pos, gripper], axis=-1).astype(np.float32)
            else:
                # Fallback: use zeros
                proprio = np.zeros(9, dtype=np.float32)
                print("[WARN] Missing state.joint_pos or state.gripper, using zeros")
            
            proprio_tensor = torch.from_numpy(proprio).to(self.device, dtype=self.dtype)
            
            # Process images for each batch
            all_actions = []
            for b in range(batch_size):
                # Process images
                img_tensor = self._process_images(images[b])
                img_embeds = self.vision_encoder(img_tensor).detach()
                img_embeds = img_embeds.reshape(-1, self.vision_encoder.hidden_size).unsqueeze(0)
                
                # Format state
                joints = proprio_tensor.unsqueeze(0).unsqueeze(0)  # (1, 1, D)
                state, state_mask = self._format_state(joints)
                state = state[:, -1:, :]  # (1, 1, 128)
                
                # Create action mask
                action_mask = torch.zeros(
                    (1, self.config["model"]["state_token_dim"]),
                    device=self.device, dtype=self.dtype
                )
                action_mask[:, LIBERO_ACTION_INDICES] = 1
                
                # Control frequency
                ctrl_freq = torch.tensor([20.0]).to(self.device)
                
                # Run inference
                trajectory = self.policy.predict_action(
                    lang_tokens=lang_embed,
                    lang_attn_mask=torch.ones(
                        lang_embed.shape[:2], dtype=torch.bool, device=self.device
                    ),
                    img_tokens=img_embeds,
                    state_tokens=state,
                    action_mask=action_mask.unsqueeze(1),
                    ctrl_freqs=ctrl_freq
                )
                
                # Unformat action
                action = self._unformat_action(trajectory).to(torch.float32)
                all_actions.append(action)
            
            # Stack actions: (B, T, 7)
            self._action_buffer = torch.cat(all_actions, dim=0).cpu().numpy()
            self._action_index = 0
        
        # Get current action from buffer
        action = self._action_buffer[:, self._action_index, :]  # (B, 7)
        self._action_index += 1
        
        # Format output for Isaac-GR00T LIBERO env
        action_dict = {
            "action.x": action[:, 0:1],
            "action.y": action[:, 1:2],
            "action.z": action[:, 2:3],
            "action.roll": action[:, 3:4],
            "action.pitch": action[:, 4:5],
            "action.yaw": action[:, 5:6],
            "action.gripper": action[:, 6:7],
        }
        
        return action_dict, {"action_index": self._action_index}

