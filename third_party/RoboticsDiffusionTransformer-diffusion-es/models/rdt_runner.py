import re
import time
from pathlib import Path

from typing import Optional, Union

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from torch.cuda import device

from models.kinematics_utils import franka_fk_fn, MANISKILL_INDICES, DATA_STAT
# from scripts.maniskill_model import MANISKILL_INDICES
from diffusers.schedulers.scheduling_ddim import DDIMScheduler
from diffusers.schedulers.scheduling_ddpm import DDPMScheduler
from diffusers.schedulers.scheduling_dpmsolver_multistep import \
    DPMSolverMultistepScheduler

from models.hub_mixin import CompatiblePyTorchModelHubMixin
from models.rdt.model import RDT




class RDTRunner(
        nn.Module, 
        CompatiblePyTorchModelHubMixin, 
        repo_url="https://huggingface.co/robotics-diffusion-transformer/rdt-1b"
    ):
    def __init__(self, *, action_dim, pred_horizon, config, 
                 lang_token_dim, img_token_dim, state_token_dim, 
                 max_lang_cond_len, img_cond_len, lang_pos_embed_config=None, 
                 img_pos_embed_config=None, dtype=torch.bfloat16):
        super(RDTRunner, self).__init__()
        # Create diffusion model
        hidden_size = config['rdt']['hidden_size']
        self.model = RDT(
            output_dim=action_dim,
            horizon=pred_horizon,
            hidden_size=hidden_size,
            depth=config['rdt']['depth'],
            num_heads=config['rdt']['num_heads'],
            max_lang_cond_len=max_lang_cond_len,
            img_cond_len=img_cond_len,
            lang_pos_embed_config=lang_pos_embed_config,
            img_pos_embed_config=img_pos_embed_config,
            dtype=dtype,
        )

        # Create adpators for various conditional inputs
        self.lang_adaptor = self.build_condition_adapter(
            config['lang_adaptor'], 
            in_features=lang_token_dim, 
            out_features=hidden_size
        )
        self.img_adaptor = self.build_condition_adapter(
            config['img_adaptor'], 
            in_features=img_token_dim, 
            out_features=hidden_size
        )
        # A `state` refers to an action or a proprioception vector
        self.state_adaptor = self.build_condition_adapter(
            config['state_adaptor'], 
            in_features=state_token_dim * 2,    # state + state mask (indicator)
            out_features=hidden_size
        )
        
        # Create the noise scheduler
        noise_scheduler_config = config['noise_scheduler']
        self.noise_scheduler = DDPMScheduler(
            num_train_timesteps=noise_scheduler_config['num_train_timesteps'],
            beta_schedule=noise_scheduler_config['beta_schedule'],
            prediction_type=noise_scheduler_config['prediction_type'],
            clip_sample=noise_scheduler_config['clip_sample'],
        )
        self.noise_scheduler_sample = DPMSolverMultistepScheduler(
            num_train_timesteps=noise_scheduler_config['num_train_timesteps'],
            beta_schedule=noise_scheduler_config['beta_schedule'],
            prediction_type=noise_scheduler_config['prediction_type'],
        )
        self.diffusion_es_scheduler = DDIMScheduler(
            num_train_timesteps=noise_scheduler_config['num_train_timesteps'],
            beta_schedule=noise_scheduler_config['beta_schedule'],
            prediction_type=noise_scheduler_config['prediction_type'],
            clip_sample=noise_scheduler_config['clip_sample'],
        )

        self.num_train_timesteps = noise_scheduler_config['num_train_timesteps']
        self.num_inference_timesteps = noise_scheduler_config['num_inference_timesteps']
        self.prediction_type = noise_scheduler_config['prediction_type']
        self.diffusion_es_default_steps = noise_scheduler_config.get(
            'diffusion_es_timesteps', self.num_inference_timesteps
        )

        self.pred_horizon = pred_horizon
        self.action_dim = action_dim

        print("Diffusion params: %e" % sum(
            [p.numel() for p in self.model.parameters()] + 
            [p.numel() for p in self.lang_adaptor.parameters()] + 
            [p.numel() for p in self.img_adaptor.parameters()] + 
            [p.numel() for p in self.state_adaptor.parameters()]))
    
    def build_condition_adapter(
        self, projector_type, in_features, out_features):
        projector = None
        if projector_type == 'linear':
            projector = nn.Linear(in_features, out_features)
        else:
            mlp_gelu_match = re.match(r'^mlp(\d+)x_gelu$', projector_type)
            if mlp_gelu_match:
                mlp_depth = int(mlp_gelu_match.group(1))
                modules = [nn.Linear(in_features, out_features)]
                for _ in range(1, mlp_depth):
                    modules.append(nn.GELU(approximate="tanh"))
                    modules.append(nn.Linear(out_features, out_features))
                projector = nn.Sequential(*modules)

        if projector is None:
            raise ValueError(f'Unknown projector type: {projector_type}')

        return projector
    
    def adapt_conditions(self, lang_tokens, img_tokens, state_tokens):
        '''
        lang_tokens: (batch_size, lang_len, lang_token_dim)
        img_tokens: (batch_size, img_len, img_token_dim)
        state_tokens: (batch_size, state_len, state_token_dim)
        
        return: adpated (..., hidden_size) for all input tokens
        '''
        adpated_lang = self.lang_adaptor(lang_tokens)
        adpated_img = self.img_adaptor(img_tokens)
        adpated_state = self.state_adaptor(state_tokens)

        return adpated_lang, adpated_img, adpated_state

    def conditional_sample(self, lang_cond, lang_attn_mask, img_cond, 
                           state_traj, action_mask, ctrl_freqs):
        '''
        lang_cond: language conditional data, (batch_size, lang_len, hidden_size).
        lang_attn_mask: (batch_size, lang_len), a mask for valid language tokens,
            which should be True-False bool tensor.
        img_cond: image conditional data, (batch_size, img_len, hidden_size).
        state_traj: (batch_size, 1, hidden_size), state trajectory.
        action_mask: (batch_size, 1, action_dim), a 0-1 **float** tensor
            indicating the valid action dimensions.
        ctrl_freqs: (batch_size,), control frequency for each sample.
        
        return: (batch_size, horizon, action_dim)
        '''
        device = state_traj.device
        dtype = state_traj.dtype
        noisy_action = torch.randn(
            size=(state_traj.shape[0], self.pred_horizon, self.action_dim), 
            dtype=dtype, device=device)
        action_mask = action_mask.expand(-1, self.pred_horizon, -1)
    
        # Set step values
        self.noise_scheduler_sample.set_timesteps(self.num_inference_timesteps)
        
        for t in self.noise_scheduler_sample.timesteps:
            # Prepare state-action trajectory
            action_traj = torch.cat([noisy_action, action_mask], dim=2)
            action_traj = self.state_adaptor(action_traj)
            state_action_traj = torch.cat([state_traj, action_traj], dim=1)
            
            # Predict the model output
            model_output = self.model(state_action_traj, ctrl_freqs,
                                    t.unsqueeze(-1).to(device),
                                    lang_cond, img_cond, lang_mask=lang_attn_mask)
            
            # Compute previous actions: x_t -> x_t-1
            noisy_action = self.noise_scheduler_sample.step(
                model_output, t, noisy_action).prev_sample
            noisy_action = noisy_action.to(state_traj.dtype)
        
        # Finally apply the action mask to mask invalid action dimensions
        noisy_action = noisy_action * action_mask

        return noisy_action
    
    # ========= Train  ============
    def compute_loss(self, lang_tokens, lang_attn_mask, img_tokens, 
                     state_tokens, action_gt, action_mask, ctrl_freqs
                    ) -> torch.Tensor:
        '''
        lang_tokens: (batch_size, lang_len, lang_token_dim)
        lang_attn_mask: (batch_size, lang_len), a mask for valid language tokens,
            which should be True-False bool tensor.
        img_tokens: (batch_size, img_len, img_token_dim)
        state_tokens: (batch_size, 1, state_token_dim)
        action_gt: (batch_size, horizon, state_token_dim), ground-truth actions for supervision
        action_mask: (batch_size, 1, state_token_dim), a 0-1 **float** tensor.
        ctrl_freqs: (batch_size,), control frequency for each sample.
        
        return: loss_value, a scalar tensor
        '''
        batch_size = lang_tokens.shape[0]
        device = lang_tokens.device  

        # Sample noise that we'll add to the actions
        noise = torch.randn(
            action_gt.shape, dtype=action_gt.dtype, device=device
        )
        # Sample random diffusion timesteps
        timesteps = torch.randint(
            0, self.num_train_timesteps, 
            (batch_size,), device=device
        ).long()
        # Add noise to the clean actions according to the noise magnitude at each timestep
        # (this is the forward diffusion process)
        noisy_action = self.noise_scheduler.add_noise(
            action_gt, noise, timesteps)
        
        # Concatenate the state and action tokens to form the input sequence
        state_action_traj = torch.cat([state_tokens, noisy_action], dim=1)
        # Append the action mask to the input sequence
        action_mask = action_mask.expand(-1, state_action_traj.shape[1], -1)
        state_action_traj = torch.cat([state_action_traj, action_mask], dim=2)
        # Align the dimension with the hidden size
        lang_cond, img_cond, state_action_traj = self.adapt_conditions(
            lang_tokens, img_tokens, state_action_traj)
        # Predict the denoised result
        pred = self.model(state_action_traj, ctrl_freqs, 
                          timesteps, lang_cond, img_cond, 
                          lang_mask=lang_attn_mask)

        pred_type = self.prediction_type 
        if pred_type == 'epsilon':
            target = noise
        elif pred_type == 'sample':
            target = action_gt
        else:
            raise ValueError(f"Unsupported prediction type {pred_type}")

        loss = F.mse_loss(pred, target)
        return loss
    
    # ========= Inference  ============
    def predict_action(self, lang_tokens, lang_attn_mask, img_tokens, state_tokens,
                       action_mask, ctrl_freqs):
        '''
        lang_tokens: (batch_size, lang_len, lang_token_dim)
        lang_attn_mask: (batch_size, lang_len), a mask for valid language tokens,
            which should be True-False bool tensor.
        img_tokens: (batch_size, img_len, img_token_dim)
        state_tokens: (batch_size, 1, state_token_dim)
        action_mask: (batch_size, 1, action_dim),
            which should be a 0-1 **float** tensor.
        ctrl_freqs: (batch_size,), control frequency for each sample.
        
        return: (batch_size, horizon, action_dim), predicted action sequence
        '''
        # Prepare the state and conditions
        state_tokens = torch.cat([state_tokens, action_mask], dim=2)
        lang_cond, img_cond, state_traj = self.adapt_conditions(
            lang_tokens, img_tokens, state_tokens)

        # batch sampling
        sampling_batch_size = 32
        lang_cond = lang_cond.repeat(sampling_batch_size, 1, 1)
        lang_attn_mask = lang_attn_mask.repeat(sampling_batch_size, 1, 1)
        img_cond = img_cond.repeat(sampling_batch_size, 1, 1)
        state_traj = state_traj.repeat(sampling_batch_size, 1, 1)
        action_mask = action_mask.repeat(sampling_batch_size, 1, 1)
        ctrl_freqs = ctrl_freqs.repeat(sampling_batch_size)
        
        # Run sampling
        action_pred = self.conditional_sample(
            lang_cond, lang_attn_mask, img_cond, 
            state_traj, action_mask, ctrl_freqs,
        )
        
        return action_pred

    def run_diffusion_es(
        self,
        lang_tokens,
        lang_attn_mask,
        img_tokens,
        state_tokens,
        action_mask,
        ctrl_freqs,
        *,
        constraints=None,
        population_size=16,
        use_cem=False,
        cem_iters=20,
        num_elites=32,
        temperature=0.1,
        initial_population_cache: Optional[Union[str, Path]] = None,
        ed_population_cache: Optional[Union[str, Path]] = None,
        use_initial_cache: bool = False,
        save_initial_cache: bool = False,
        save_ed_cache: bool = True,
    ):
        '''
        Run diffusion-es planning with RDT-1B proposals as warm starts.

        Args:
            lang_tokens: (B, L, D_lang) language tokens.
            lang_attn_mask: (B, L) boolean attention mask.
            img_tokens: (B, V, D_img) image features.
            state_tokens: (B, 1, D_state) proprioceptive tokens.
            action_mask: (B, 1, action_dim) float validity mask.
            ctrl_freqs: (B,) control frequencies.
            constraints: callable taking trajectories -> (cost, info).
            population_size: number of candidates per batch item.
            use_cem / cem_iters / num_elites / temperature: ES hyper-parameters.

        Returns:
            action_pred: (B, pred_horizon, action_dim) torch.Tensor.
            extras: dict with population trajectories, scores, metadata.
        '''

        base_batch = state_tokens.shape[0]
        if base_batch != 1:
            raise NotImplementedError(
                "run_diffusion_es currently supports a single context sample per call."
            )
        if population_size <= 0:
            raise ValueError("population_size must be positive.")

        self.sampling_batch_size = population_size

        if constraints is None:
            constraints = self.generate_constraints()

        with torch.no_grad():
            # Prepare conditional encodings
            state_tokens_with_mask = torch.cat([state_tokens, action_mask], dim=2)
            lang_cond, img_cond, state_traj = self.adapt_conditions(
                lang_tokens, img_tokens, state_tokens_with_mask
            )

            lang_cond = lang_cond.repeat(population_size, 1, 1)
            img_cond = img_cond.repeat(population_size, 1, 1)
            state_traj = state_traj.repeat(population_size, 1, 1)
            action_mask = action_mask.repeat(population_size, 1, 1)
            lang_mask = lang_attn_mask.repeat(population_size, 1, 1)
            ctrl_freqs = ctrl_freqs.repeat(population_size)

            # initialize action proposals for Evolutionary Diffusion
            if use_initial_cache:
                cache_path = Path(initial_population_cache)
                if cache_path.exists():
                    try:
                        cached = torch.load(cache_path, map_location=state_traj.device)
                        if isinstance(cached, dict) and "initial_population" in cached:
                            cached = cached["initial_population"]
                        if not isinstance(cached, torch.Tensor):
                            raise TypeError("Cached initial_population must be a torch.Tensor.")
                        expected_shape = (population_size, self.pred_horizon, self.action_dim)
                        if cached.shape != expected_shape:
                            raise ValueError(
                                f"Cached population has shape {cached.shape}, expected {expected_shape}."
                            )
                        initial_population = cached.to(device=state_traj.device, dtype=state_traj.dtype)
                    except Exception as exc:  # noqa: BLE001
                        print(f"Failed to load cached initial_population: {exc}")
                        initial_population = None

            else:
                initial_population = self.conditional_sample(
                    lang_cond,
                    lang_mask,
                    img_cond,
                    state_traj,
                    action_mask,
                    ctrl_freqs,
                )

            # save initial population to cache
            if save_initial_cache and initial_population is not None:
                cache_path = Path(initial_population_cache)
                if cache_path is not None:
                    try:
                        cache_path.parent.mkdir(parents=True, exist_ok=True)
                        torch.save(
                            {"initial_population": initial_population.detach().cpu()}, cache_path
                        )
                    except Exception as exc:  # noqa: BLE001
                        print(f"Failed to cache initial_population: {exc}")


            initial_population = initial_population * action_mask
            # return initial_population, {}

            self.device = initial_population.device

            population_trajectories = initial_population
            population_scores, population_info = constraints(population_trajectories)
            population_scores = population_scores.detach()

            trunc_step_schedule = np.linspace(5, 1, cem_iters).astype(int)
            start_time = time.time()

            for i in range(cem_iters):
                n_trunc_steps = trunc_step_schedule[i]

                """
                Local MPPI update
                """
                # Compute reward-probabilities
                reward_probs = torch.exp(temperature * -population_scores)
                reward_probs = reward_probs / reward_probs.sum()
                probs = reward_probs

                """
                Resample and mutate (renoise-denoise)
                """
                if use_cem:
                    elites = torch.argsort(population_scores)[:num_elites]
                    indices = torch.randint(0, num_elites, (self.sampling_batch_size,), device=self.device)
                    population_trajectories = population_trajectories[elites[indices]]
                    population_trajectories = self.renoise(population_trajectories, n_trunc_steps)
                else:
                    indices = torch.multinomial(probs, self.sampling_batch_size,
                                                replacement=True)  # torch.multinomial(probs, 1).squeeze(1)
                    population_trajectories = population_trajectories[indices]
                    population_trajectories = self.renoise(population_trajectories, n_trunc_steps)

                # Denoise
                population_trajectories, population_scores, population_info = self.rollout(
                    lang_cond,
                    lang_mask,
                    img_cond,
                    state_traj,
                    action_mask,
                    ctrl_freqs,
                    population_trajectories,
                    constraints,
                    n_trunc_steps,
                )

            # for i in range(cem_iters):
            #     n_trunc_steps = max(int(trunc_step_schedule[i]), 1)
            #
            #     # Convert scores to sampling probabilities
            #     shifted = population_scores - population_scores.min()
            #     scaled = torch.exp(-shifted / max(temperature, 1e-6))
            #     probs = scaled / torch.clamp(scaled.sum(), min=1e-6)
            #
            #     if use_cem:
            #         topk = torch.topk(population_scores, k=min(num_elites, total_population), largest=False)
            #         elite_indices = topk.indices
            #         selection_indices = elite_indices[
            #             torch.randint(0, elite_indices.shape[0], (total_population,), device=device)
            #         ]
            #     else:
            #         selection_indices = torch.multinomial(probs, total_population, replacement=True)
            #
            #     selected = population_trajectories[selection_indices]
            #     batch_ids = batch_ids[selection_indices]
            #     lang_cond = lang_cond_base[batch_ids]
            #     img_cond = img_cond_base[batch_ids]
            #     state_traj = state_traj_base[batch_ids]
            #     expanded_mask = action_mask_base[batch_ids]
            #     lang_mask = lang_mask_base[batch_ids]
            #     ctrl_freqs_expanded = ctrl_freqs_base[batch_ids]
            #     renoised = self.renoise(selected, n_trunc_steps, noise_scale=noise_scale)
            #
            #     population_trajectories, population_scores, population_info = self.rollout(
            #         lang_cond,
            #         lang_mask,
            #         img_cond,
            #         state_traj,
            #         expanded_mask,
            #         ctrl_freqs_expanded,
            #         renoised,
            #         constraints,
            #         initial_rollout=False,
            #         n_trunc_steps=n_trunc_steps,
            #         noise_scale=noise_scale,
            #     )
            #     population_scores = population_scores.detach()

            end_time = time.time()
            print("Diffusion-ES planning time", end_time - start_time)
            print("population_scores", population_scores)
            print("best score", population_scores.min())

            # save ED population to cache
            if save_ed_cache and population_trajectories is not None:
                cache_path = Path(ed_population_cache)
                if cache_path is not None:
                    try:
                        cache_path.parent.mkdir(parents=True, exist_ok=True)
                        torch.save(
                            {"initial_population": population_trajectories.detach().cpu()}, cache_path
                        )
                    except Exception as exc:  # noqa: BLE001
                        print(f"Failed to cache initial_population: {exc}")

            extras = {
                "population": population_trajectories,
                "scores": population_scores,
                "best_scores": population_scores.min(),
                "elapsed_time": start_time - end_time,
            }

        return population_trajectories, extras

    
    def forward(self, *args, **kwargs) -> torch.Tensor:
        return self.compute_loss(*args, **kwargs)


    def rollout(
        self,
        lang_cond,
        lang_attn_mask,
        img_cond,
        state_traj,
        action_mask,
        ctrl_freqs,
        noisy_action,
        constraints,
        n_trunc_steps=5,
    ):
        device = state_traj.device
        dtype = state_traj.dtype
        scheduler = self.noise_scheduler
        noisy_action = noisy_action.to(device=device, dtype=dtype)
        action_mask = action_mask.expand(-1, self.pred_horizon, -1)

        timesteps = scheduler.timesteps[-n_trunc_steps:]

        for k in timesteps:
            action_traj = torch.cat([noisy_action, action_mask], dim=-1)
            action_traj = self.state_adaptor(action_traj)
            state_action_traj = torch.cat([state_traj, action_traj], dim=1)

            model_output = self.model(
                state_action_traj,
                ctrl_freqs,
                k.unsqueeze(-1).to(device),
                lang_cond,
                img_cond,
                lang_mask=lang_attn_mask,
            )

            noisy_action = scheduler.step(
                model_output=model_output,
                timestep=k,
                sample=noisy_action,
            ).prev_sample

            noisy_action = noisy_action.to(dtype)

        # denoised = noisy_action * action_mask_expanded
        # Finally apply the action mask to mask invalid action dimensions
        noisy_action = noisy_action * action_mask
        scores, info = constraints(noisy_action)

        return noisy_action, scores, info

    # def renoise(self, population_trajectories, n_steps, noise_scale=0.1):
    #     if n_steps <= 0:
    #         return population_trajectories
    #     scheduler = self.diffusion_es_scheduler
    #     timesteps = scheduler.timesteps
    #     target_index = max(len(timesteps) - n_steps, 0)
    #     timestep = timesteps[target_index]
    #     noise = torch.randn_like(population_trajectories) * noise_scale
    #     return scheduler.add_noise(population_trajectories, noise, timestep)

    def renoise(self, population_trajectories, t):
        noise = torch.randn(population_trajectories.shape, device=self.device)
        population_trajectories = self.noise_scheduler.add_noise(population_trajectories, noise, self.noise_scheduler.timesteps[-t])
        return population_trajectories

    def process_trajectory(self, trajectories: torch.Tensor, fk_fn) -> np.ndarray:
        """
        Visualize a batch of Franka robot trajectories in end-effector (EEF) space.

        Args:
            trajectory (Tensor): shape = [B, T, 8], robot trajectories (joint positions + gripper)
            fk_fn (callable): Forward kinematics function, input [B, T, 7] -> output [B, T, 3] (EEF positions)
        """
        assert trajectories.ndim == 3 and trajectories.shape[2] == 128, "trajectory should have shape (B, T, 128)"

        B, T, _ = trajectories.shape
        device = trajectories.device

        # denormalize to action space
        action_indices = MANISKILL_INDICES
        joints = trajectories[:, :, action_indices]

        action_max = torch.tensor(DATA_STAT['action_max']).to(device)
        action_min = torch.tensor(DATA_STAT['action_min']).to(device)

        joints = (joints + 1) / 2 * (action_max - action_min) + action_min

        # Take the first 7 dimensions (joint positions) for FK
        joints = joints[:, :, :7]  # shape = [B, T, 7]

        # Run forward kinematics to get EEF trajectories
        with torch.no_grad():
            eef_trajs = fk_fn(joints)  # shape = [B, T, 3]

        # Convert to numpy for plotting
        eef_trajs = eef_trajs.cpu().numpy()

        return eef_trajs

    def generate_constraints(self):
        """
        Build a default constraint function that penalizes invalid actions,
        large deviations from a reference trajectory, and optional range limits.
        """

        def constraint_fn_point(trajectories):
            """
            Compute the reward for "raising the left arm slightly" based on joint angles.

            :param trajectory: Tensor of shape (batch, 16, 14), representing bimanual motion trajectories.
                               Each trajectory consists of 16 timesteps, and each timestep has 14 joint angles
                               (7 for the left arm, 7 for the right arm).
            :return: Tensor of shape (batch,), representing the reward scores for each trajectory.
            """
            device = trajectories.device
            eef_traj = self.process_trajectory(trajectories, franka_fk_fn)

            # Extract predicted left arm ee positions
            ee_position = eef_traj[:, :, :3]
            plate_position = [0.25, -0.2, -0.3]  # Example plate position
            safe_distance = 0.001  # Minimum distance to the bottle
            scores = np.zeros(self.sampling_batch_size)

            # Iterate scoring each trajectory in the batch
            for i in range(self.sampling_batch_size):
                final_position = ee_position[i, -1, :3]  # Last timestep position
                distances = np.linalg.norm(final_position - plate_position)  # (16,)
                scores[i] = -np.mean((distances - safe_distance) ** 2)  # average deviation over trajectory
            scores = -torch.as_tensor(scores, device=device)
            return scores, {}

        def constraint_fn_lower(trajectory):
            # Convert trajectory to numpy and unnormalize
            device = trajectory.device
            eef_traj = self.process_trajectory(trajectory, franka_fk_fn)

            # Extract predicted left arm ee positions
            ee_position = eef_traj[:, :, :3]  # Shape: (batch, 16)
            scores = np.zeros(self.sampling_batch_size)
            # scores = -torch.as_tensor(scores, device=device)
            #
            # return scores, {}

            # Iterate scoring each trajectory in the batch
            for i in range(self.sampling_batch_size):
                initial_height = ee_position[i, 0, 2]  # First timestep
                final_height = ee_position[i, -1, 2]  # Last timestep

                # Compute reward as the height increase from the first to the last timestep
                # scores[i] = final_height - initial_height
                scores[i] = initial_height - final_height
            scores = -torch.as_tensor(scores, device=device)
            return scores, {}

        return constraint_fn_lower
