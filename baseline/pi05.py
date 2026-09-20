"""Differentiable, cached-prefix access to the exact installed LeRobot PI0.5.

The 50 x 32 internal flow state and 7 physical actions are never conflated.
Only the action expert is adapted; frozen prefix features contain both camera
tokens and the checkpoint's tokenized language/discretized-state input.
"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path

import torch
from torch import nn

from .io import digest, to_cpu


class Pi05Runtime:
    def __init__(self, cfg, *, hash_weights=True):
        from lerobot.configs.policies import PreTrainedConfig
        from lerobot.policies.pi05.modeling_pi05 import PI05Policy
        from lerobot.policies.factory import make_pre_post_processors
        self.cfg = cfg
        self.device = torch.device(cfg["device"])
        path = Path(cfg["checkpoint"])
        index = path / "model.safetensors.index.json"
        weights = [path / "model.safetensors"]
        if index.is_file():
            weights = [path / name for name in sorted(set(json.loads(index.read_text())["weight_map"].values()))]
            if any(not p.resolve().is_relative_to(path.resolve()) for p in weights):
                raise ValueError("checkpoint index points outside its directory")
        if not path.is_dir() or not weights or any(not p.is_file() for p in weights):
            raise FileNotFoundError(f"local v44 checkpoint missing: {path}")
        model_cfg = PreTrainedConfig.from_pretrained(str(path), local_files_only=True)
        model_cfg.device = str(self.device)
        model_cfg.compile_model = False
        model_cfg.gradient_checkpointing = cfg["gradient_checkpointing"]
        model_cfg.push_to_hub = False
        model_cfg.num_inference_steps = cfg["inference_steps"]
        if model_cfg.chunk_size != 50 or model_cfg.output_features["action"].shape[0] != 7:
            raise ValueError("checkpoint is not the v44 50-step, seven-action contract")
        self.policy = PI05Policy.from_pretrained(str(path), config=model_cfg, local_files_only=True).to(self.device)
        self.policy.eval().requires_grad_(False)
        self.model = self.policy.model
        self.pre, self.post = make_pre_post_processors(
            policy_cfg=model_cfg, pretrained_path=str(path),
            preprocessor_overrides={"device_processor": {"device": str(self.device)},
                                    "tokenizer_processor": {"tokenizer_name": cfg["tokenizer"]}})
        from transformers import AutoTokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(cfg["tokenizer"], local_files_only=True)
        self.action_dim = 7
        self.chunk_size = 50
        self.internal_dim = model_cfg.max_action_dim
        self.hidden_dim = self.model.action_out_proj.in_features
        self.prefix_dim = self.model.paligemma_with_expert.paligemma.config.text_config.hidden_size
        files = [p for p in path.iterdir() if p.name == "config.json" or p.name.startswith("policy_preprocessor") or p.name.startswith("policy_postprocessor")]
        checks = {p.name: digest(p) for p in sorted(files)}
        if hash_weights:
            checks.update({p.name: digest(p) for p in weights})
            if index.is_file():
                checks[index.name] = digest(index)
        token_files = {p.name: digest(p) for p in sorted(Path(cfg["tokenizer"]).iterdir())
                       if p.is_file() and p.suffix in (".json", ".model", ".txt", ".spm")}
        self.identity = {"checkpoint": str(path.resolve()), "files": checks,
                         "pretraining": "LIBERO-40 (user-provided provenance)",
                         "chunk_size": 50, "physical_action_dim": 7,
                         "normalization": "unchanged checkpoint processors"}
        self.identity["tokenizer_files"] = token_files
        material = {k: v for k, v in self.identity.items() if k != "checkpoint"}
        self.identity["sha256"] = hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()

    def autocast(self):
        return torch.autocast(device_type=self.device.type, dtype=torch.bfloat16, enabled=self.device.type == "cuda")

    def preprocess(self, batch):
        result = self.pre(dict(batch))
        result["_baseline_instruction"] = batch.get("task")
        return result

    @torch.no_grad()
    def embed(self, batch):
        images, image_masks = self.policy._preprocess_images(batch)
        tokens, mask = batch["observation.language.tokens"], batch["observation.language.attention_mask"]
        with self.autocast():
            embeddings, padding, attention = self.model.embed_prefix(images, image_masks, tokens, mask)
        ntext = tokens.shape[1]
        text_weights = padding[:, -ntext:].float().unsqueeze(-1)
        image_weights = padding[:, :-ntext].float().unsqueeze(-1)
        language = (embeddings[:, -ntext:].float() * text_weights).sum(1) / text_weights.sum(1).clamp_min(1)
        instruction = batch.get("_baseline_instruction")
        if instruction is not None:
            encoded = self.tokenizer(instruction, padding=True, truncation=True, max_length=200, return_tensors="pt").to(self.device)
            with self.autocast():
                text_embeddings = self.model.paligemma_with_expert.embed_language_tokens(encoded["input_ids"])
            weights = encoded["attention_mask"].float().unsqueeze(-1)
            language = (text_embeddings.float() * weights).sum(1) / weights.sum(1).clamp_min(1)
        visual = (embeddings[:, :-ntext].float() * image_weights).sum(1) / image_weights.sum(1).clamp_min(1)
        return {"embeddings": embeddings.detach(), "padding": padding, "attention": attention,
                "language": language, "visual": visual}

    @torch.no_grad()
    def prefix(self, embedded):
        from lerobot.policies.pi05.modeling_pi05 import make_att_2d_masks
        data = {k: v.to(self.device) for k, v in embedded.items()}
        padding = data["padding"]
        attention = make_att_2d_masks(padding, data["attention"])
        self.model.paligemma_with_expert.paligemma.language_model.config._attn_implementation = "eager"
        with self.autocast():
            _, cache = self.model.paligemma_with_expert.forward(
                attention_mask=self.model._prepare_attention_masks_4d(attention),
                position_ids=padding.long().cumsum(1) - 1,
                past_key_values=None, inputs_embeds=[data["embeddings"], None], use_cache=True)
        return {"padding": padding, "cache": cache}

    def encode(self, batch):
        return self.prefix(self.embed(batch))

    def velocity(self, prefix, x, time, *, features=False):
        def forward(point, timestep):
            captured = []
            handle = None
            if features:
                handle = self.model.action_out_proj.register_forward_pre_hook(
                    lambda _m, args: captured.append(args[0]))
            try:
                with self.autocast():
                    value = self.model.denoise_step(prefix["padding"], prefix["cache"], point, timestep)
                return (value, captured[-1].float().mean(1)) if features else value
            finally:
                if handle:
                    handle.remove()
        if torch.is_grad_enabled() and self.cfg["gradient_checkpointing"]:
            from torch.utils.checkpoint import checkpoint
            return checkpoint(forward, x, time, use_reentrant=False)
        return forward(x, time)

    def noise(self, batch_size):
        return torch.randn(batch_size, self.chunk_size, self.internal_dim, device=self.device)

    def flow_loss(self, prefix, actions, *, padding=None, return_features=False):
        actions = actions.to(self.device).float()
        if actions.shape[1:] != (50, 7):
            raise ValueError(f"training actions must be normalized [B,50,7], got {actions.shape}")
        actions = torch.nn.functional.pad(actions, (0, self.internal_dim - 7))
        noise = torch.randn_like(actions)
        time = self.model.sample_time(len(actions), self.device)
        x = time[:, None, None] * noise + (1 - time[:, None, None]) * actions
        prediction, features = self.velocity(prefix, x, time, features=True)
        loss = (prediction[..., :7] - (noise - actions)[..., :7]).square()
        mask = torch.ones(loss.shape[:2], device=self.device) if padding is None else (~padding.to(self.device).bool()).float()
        loss = (loss * mask[..., None]).sum() / (mask.sum().clamp_min(1) * 7)
        return (loss, features) if return_features else loss

    @torch.no_grad()
    def sample(self, prefix, noise=None, compose=None):
        x = self.noise(len(prefix["padding"])) if noise is None else noise.clone()
        dt = torch.tensor(-1.0 / self.cfg["inference_steps"], dtype=torch.float32, device=self.device)
        time = torch.tensor(1.0, dtype=torch.float32, device=self.device)
        for _ in range(self.cfg["inference_steps"]):
            t = time.expand(len(x))
            v = self.velocity(prefix, x, t)
            if compose is not None:
                v = compose(x, t, v)
            x = x + dt * v
            time = time + dt
        return x[..., :7]

    def physical(self, normalized):
        return self.post(normalized).float()

    @torch.no_grad()
    def latent(self, prefix):
        _, feature = self.velocity(prefix, self.noise(len(prefix["padding"])),
                                   torch.ones(len(prefix["padding"]), device=self.device), features=True)
        return feature

    def unfreeze_action_expert(self):
        self.policy.requires_grad_(False)
        # Keep trainable master weights/Adam states in fp32; a small update
        # would otherwise round away in checkpoint-loaded bf16 parameters.
        self.model.paligemma_with_expert.gemma_expert.float().requires_grad_(True)
        for module in (self.model.action_in_proj, self.model.action_out_proj,
                       self.model.time_mlp_in, self.model.time_mlp_out):
            module.float().requires_grad_(True)

    def trainable_state(self):
        return {k: p.detach().cpu() for k, p in self.policy.named_parameters() if p.requires_grad}

    def restore_partial(self, state):
        live = dict(self.policy.named_parameters())
        unknown = set(state) - set(live)
        if unknown:
            raise ValueError(f"unknown policy parameters: {sorted(unknown)[:5]}")
        with torch.no_grad():
            for key, value in state.items():
                if live[key].shape != value.shape:
                    raise ValueError(f"shape mismatch: {key}")
                live[key].copy_(value.to(live[key].device))
