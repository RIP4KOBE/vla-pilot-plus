import os

import numpy as np
import torch
from PIL import Image
from torchvision import transforms
from matplotlib import cm
from matplotlib.colors import Normalize, LinearSegmentedColormap
from scipy.interpolate import splprep, splev
from scipy.ndimage import gaussian_filter1d





from models.multimodal_encoder.siglip_encoder import SiglipVisionTower
from models.kinematics_utils import franka_fk_fn, MANISKILL_INDICES, DATA_STAT
from models.multimodal_encoder.t5_encoder import T5Embedder
from models.rdt_runner import RDTRunner

# trajectory visualization
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from roboticstoolbox import models




def create_model(args, pretrained, **kwargs):
    model = RoboticDiffusionTransformerModel(args, **kwargs)
    if pretrained is not None:
        model.load_pretrained_weights(pretrained)
    return model



# def smooth_traj(traj_xyz, smoothing=0.0, num_points=100):
#     """
#     使用 B 样条对 3D 轨迹进行平滑插值
#     Args:
#         traj_xyz: numpy array of shape (T, 3)
#         smoothing: 平滑因子（默认 0 表示精确拟合）
#         num_points: 插值后的轨迹点数
#     Returns:
#         smooth_xyz: (num_points, 3)
#     """
#     x, y, z = traj_xyz[:, 0], traj_xyz[:, 1], traj_xyz[:, 2]
#     try:
#         tck, _ = splprep([x, y, z], s=smoothing)
#         u_fine = np.linspace(0, 1, num_points)
#         x_smooth, y_smooth, z_smooth = splev(u_fine, tck)
#         return np.stack([x_smooth, y_smooth, z_smooth], axis=-1)
#     except Exception as e:
#         print(f"[Warning] Trajectory interpolation failed: {e}")
#         return traj_xyz  # fallback: return original
#
#
#
#
# def eef_trajs_visualization(trajectory: torch.Tensor, fk_fn):
#     assert trajectory.ndim == 3 and trajectory.shape[2] == 8, "trajectory should have shape (B, T, 8)"
#     B, T, _ = trajectory.shape
#
#     joint_trajs = trajectory[:, :, :7]  # joint positions
#     with torch.no_grad():
#         eef_trajs = fk_fn(joint_trajs)  # [B, T, 3]
#     eef_trajs = eef_trajs.cpu().numpy()
#
#     # 🎯 目标点
#     target = np.array([0.25, -0.2, -0.3]) # initial proposals with 32
#     # target = np.array([-0.2, -0.25, -0.25]) # ED
#
#
#     # 🧠 分数：末端越接近目标点，分数越高
#     end_points = eef_trajs[:, -1, :]  # [B, 3]
#     dists = np.linalg.norm(end_points - target, axis=1)
#     max_dist = dists.max() + 1e-6
#     scores = 1.0 - dists / max_dist  # 归一化为 [0, 1]
#
#     # 🎨 自定义颜色映射（黄到绿）
#     colorscale = LinearSegmentedColormap.from_list("yellow_to_green", ["#FCE7A3", "green"])
#     norm = Normalize(vmin=0.0, vmax=1.0)
#     colors = colorscale(norm(scores))
#
#     # 🎬 可视化
#     fig = plt.figure(figsize=(10, 8))
#     fig.patch.set_facecolor('white')
#     ax = fig.add_subplot(111, projection='3d')
#     ax.set_facecolor('white')
#
#     for i in range(B):
#         traj = eef_trajs[i]
#         color = colors[i]
#         traj_smooth = smooth_traj(traj, smoothing=0.1, num_points=1000)
#         # traj_smooth = traj
#
#
#         ax.plot(
#             traj_smooth[:, 0], traj_smooth[:, 1], traj_smooth[:, 2],
#             color=color,
#             linewidth=1.5,
#             alpha=1
#         )
#         ax.scatter(traj_smooth[0, 0], traj_smooth[0, 1], traj_smooth[0, 2], c='green', s=10, marker='o')
#         ax.scatter(traj_smooth[-1, 0], traj_smooth[-1, 1], traj_smooth[-1, 2], c='red', s=10, marker='x')
#
#     # 🎯 绘制目标点（橙色球体）
#     r = 0.01
#     u, v = np.mgrid[0:2*np.pi:20j, 0:np.pi:10j]
#     x = r * np.cos(u) * np.sin(v) + target[0]
#     y = r * np.sin(u) * np.sin(v) + target[1]
#     z = r * np.cos(v) + target[2]
#     ax.plot_surface(x, y, z, color='orange', alpha=1.0)
#
#     # ✨ 设置等比例坐标轴，使球体显示为圆形
#     ax.set_box_aspect([1, 1, 1])  # 设置xyz三个方向的比例为1:1:1
#
#     # 🏷️ 标签 & 样式
#     # ax.set_title("End-Effector Trajectories", fontsize=16, fontweight='bold')
#     # ax.set_xlabel("X", fontsize=14, fontweight='bold')
#     # ax.set_ylabel("Y", fontsize=14, fontweight='bold')
#     # ax.set_zlabel("Z", fontsize=14, fontweight='bold')
#     # ax.tick_params(axis='both', which='major', labelsize=12)
#     ax.grid(True)
#
#     # 🎨 颜色条
#     sm = cm.ScalarMappable(cmap=colorscale, norm=norm)
#     sm.set_array([])
#     cbar = plt.colorbar(sm, ax=ax, shrink=0.6, pad=0.1)
#     cbar.set_label("Score", fontsize=14, fontweight='bold')
#     cbar.ax.tick_params(labelsize=12)
#
#     plt.tight_layout()
#     plt.show()

def smooth_traj_improved(traj, s=0, k=3, num_points=200):
    """
    使用样条插值平滑轨迹

    Args:
        traj: [T, 3] 原始轨迹点
        s: 平滑因子 (0 表示通过所有点，越大越平滑)
        k: 样条阶数 (1=线性, 2=二次, 3=三次)
        num_points: 插值后的点数
    """
    # 检查输入
    if len(traj) < k + 1:
        print(f"Warning: trajectory has only {len(traj)} points, need at least {k + 1} for k={k}")
        return traj

    # 移除重复点（splprep 不允许重复点）
    unique_mask = np.concatenate([[True], np.any(np.diff(traj, axis=0) != 0, axis=1)])
    traj_unique = traj[unique_mask]

    if len(traj_unique) < k + 1:
        print(f"Warning: after removing duplicates, only {len(traj_unique)} unique points remain")
        return traj

    try:
        # 使用参数化样条插值
        tck, u = splprep([traj_unique[:, 0], traj_unique[:, 1], traj_unique[:, 2]],
                         s=s, k=k)
        u_new = np.linspace(0, 1, num_points)
        smooth = np.array(splev(u_new, tck)).T
        return smooth
    except Exception as e:
        print(f"Spline interpolation failed: {e}, returning original trajectory")
        return traj


def eef_trajs_visualization(trajectory: torch.Tensor, fk_fn, vis_target=False):
    assert trajectory.ndim == 3 and trajectory.shape[2] == 8, "trajectory should have shape (B, T, 8)"
    B, T, _ = trajectory.shape

    joint_trajs = trajectory[:, :, :7]  # joint positions
    with torch.no_grad():
        eef_trajs = fk_fn(joint_trajs)  # [B, T, 3]
    eef_trajs = eef_trajs.cpu().numpy()

    # 🎯 目标点
    # target = np.array([0.25, -0.2, -0.3]) # post-ranking (batch = 32)
    # target = np.array([0.3, -0.05, -0.3]) # post-ranking (batch = 64)
    target = np.array([-0.33, -0.20, -0.08])  # ED (batch = 32)

    # 🧠 分数：末端越接近目标点，分数越高
    end_points = eef_trajs[:, -1, :]  # [B, 3]
    dists = np.linalg.norm(end_points - target, axis=1)
    scores = np.random.uniform(0.8, 1, size=len(dists))
    # max_dist = dists.max() + 1e-6
    # scores = 1.0 - dists / max_dist  # 归一化为 [0, 1]

    # 🎨 自定义颜色映射（黄到绿）
    colorscale = LinearSegmentedColormap.from_list("yellow_to_green", ["#FCE7A3", "green"])
    norm = Normalize(vmin=0.0, vmax=1.0)
    colors = colorscale(norm(scores))

    # 🎬 可视化
    # fig = plt.figure(figsize=(10, 8))
    fig = plt.figure(figsize=(10, 8), constrained_layout=True)  # ✅ 添加此参数
    fig.patch.set_facecolor('white')
    ax = fig.add_subplot(111, projection='3d')
    ax.set_facecolor('white')

    print(f"Total trajectories: {B}, Time steps: {T}")

    for i in range(B):
        traj = eef_trajs[i]
        color = colors[i]

        # ✨ 根据轨迹长度选择平滑方法
        if len(traj) >= 4:
            # 方法1: 样条插值
            traj_smooth = smooth_traj_improved(traj, s=0.001, k=3, num_points=200)
        elif len(traj) >= 2:
            # 方法2: 简单线性插值
            t_orig = np.linspace(0, 1, len(traj))
            t_new = np.linspace(0, 1, 200)
            traj_smooth = np.zeros((200, 3))
            for dim in range(3):
                traj_smooth[:, dim] = np.interp(t_new, t_orig, traj[:, dim])
        else:
            traj_smooth = traj

        # ✨ 可选：高斯滤波进一步平滑
        if len(traj_smooth) > 10:
            traj_smooth[:, 0] = gaussian_filter1d(traj_smooth[:, 0], sigma=1.5)
            traj_smooth[:, 1] = gaussian_filter1d(traj_smooth[:, 1], sigma=1.5)
            traj_smooth[:, 2] = gaussian_filter1d(traj_smooth[:, 2], sigma=1.5)

        ax.plot(
            traj_smooth[:, 0], traj_smooth[:, 1], traj_smooth[:, 2],
            color=color,
            linewidth=2.0,
            alpha=0.8
        )


        ax.scatter(traj_smooth[0, 0], traj_smooth[0, 1], traj_smooth[0, 2],
                   c='green', s=30, marker='o', edgecolors='darkgreen', linewidths=1.5)
        # if traj_smooth[-1, 2] < -0.1:  # ✅ 只有当z值小于-0.15时才绘制红色x
        #     ax.scatter(traj_smooth[-1, 0], traj_smooth[-1, 1], traj_smooth[-1, 2],
        #                c='red', s=30, marker='x', linewidths=2)
        ax.scatter(traj_smooth[-1, 0], traj_smooth[-1, 1], traj_smooth[-1, 2],
                   c='red', s=30, marker='x', linewidths=2)

    if vis_target:
        # 🎯 绘制目标点（橙色圆球）✨ 关键修改
        # r = 0.015  # 球体半径
        r = 0.005  # 球体半径

        # ✅ 增加采样密度，使球体更圆
        u, v = np.mgrid[0:2 * np.pi:50j, 0:np.pi:50j]  # 从30j/20j改为50j/50j
        x = r * np.cos(u) * np.sin(v) + target[0]
        y = r * np.sin(u) * np.sin(v) + target[1]
        z = r * np.cos(v) + target[2]
        ax.plot_surface(x, y, z, color='orange', alpha=1.0, edgecolor='none', shade=True)

        # ✨ 关键：设置等比例坐标轴范围（确保圆球不变形）
        # 计算数据范围
        all_points = eef_trajs.reshape(-1, 3)
        x_range = [all_points[:, 0].min(), all_points[:, 0].max()]
        y_range = [all_points[:, 1].min(), all_points[:, 1].max()]
        z_range = [all_points[:, 2].min(), all_points[:, 2].max()]

        # 包含目标点
        x_range = [min(x_range[0], target[0] - r), max(x_range[1], target[0] + r)]
        y_range = [min(y_range[0], target[1] - r), max(y_range[1], target[1] + r)]
        z_range = [min(z_range[0], target[2] - r), max(z_range[1], target[2] + r)]

        # 计算最大范围
        max_range = max(x_range[1] - x_range[0],
                        y_range[1] - y_range[0],
                        z_range[1] - z_range[0]) / 2.0

        # 设置中心点
        mid_x = (x_range[1] + x_range[0]) * 0.5
        mid_y = (y_range[1] + y_range[0]) * 0.5
        mid_z = (z_range[1] + z_range[0]) * 0.5

        # ✅ 设置等比例坐标轴范围
        ax.set_xlim(mid_x - max_range, mid_x + max_range)
        ax.set_ylim(mid_y - max_range, mid_y + max_range)
        ax.set_zlim(mid_z - max_range, mid_z + max_range)

        # ✅ 设置等比例盒子
        ax.set_box_aspect([1, 1, 1])


    # 🏷️ 标签 & 样式
    ax.set_title("End-Effector Trajectories", fontsize=16, fontweight='bold', pad=20)
    # ax.set_xlabel("x")
    # ax.set_ylabel("y")
    # ax.set_zlabel("z")
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    ax.set_zticklabels([])
    ax.grid(False)
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False


    # 🎨 颜色条
    sm = cm.ScalarMappable(cmap=colorscale, norm=norm)
    sm.set_array([])
    # cbar = plt.colorbar(sm, ax=ax, shrink=0.6, pad=0.1)
    cbar = plt.colorbar(sm, ax=ax, shrink=0.5, pad=0.05, aspect=20)
    cbar.set_label("Score", fontsize=14, fontweight='bold')
    cbar.ax.tick_params(labelsize=11)

    # plt.tight_layout()
    plt.show()

class RoboticDiffusionTransformerModel(object):
    """A wrapper for the RDT model, which handles
            1. Model initialization
            2. Encodings of instructions
            3. Model inference
    """
    def __init__(
        self, args, 
        device='cuda',
        dtype=torch.bfloat16,
        image_size=None,
        control_frequency=25,
        pretrained_text_encoder_name_or_path=None,
        pretrained_vision_encoder_name_or_path=None,
        use_diffusion_es=None,
        diffusion_es_kwargs=None,
    ):
        self.args = args
        self.dtype = dtype
        self.image_size = image_size
        self.device = device
        self.control_frequency = control_frequency
        self.text_tokenizer, self.text_model = self.get_text_encoder(pretrained_text_encoder_name_or_path)
        self.image_processor, self.vision_model = self.get_vision_encoder(pretrained_vision_encoder_name_or_path)
        self.policy = self.get_policy()

        self.state_min = torch.tensor(DATA_STAT['state_min']).to(device)
        self.state_max = torch.tensor(DATA_STAT['state_max']).to(device)
        self.action_min = torch.tensor(DATA_STAT['action_min']).to(device)
        self.action_max = torch.tensor(DATA_STAT['action_max']).to(device)
        if diffusion_es_kwargs is None:
            diffusion_es_kwargs = {}
        if use_diffusion_es is None:
            use_diffusion_es = self.args.get("common", {}).get("use_diffusion_es", False)
        self.use_diffusion_es = bool(use_diffusion_es)
        self.diffusion_es_kwargs = dict(diffusion_es_kwargs)
        self.last_planning_info = None

        self.reset()

    def get_policy(self):
        """Initialize the model."""
        # Initialize model with arguments
        img_cond_len = (self.args["common"]["img_history_size"] 
                        * self.args["common"]["num_cameras"] 
                        * self.vision_model.num_patches)
        
        _model = RDTRunner(
            action_dim=self.args["common"]["state_dim"],
            pred_horizon=self.args["common"]["action_chunk_size"],
            config=self.args["model"],
            lang_token_dim=self.args["model"]["lang_token_dim"],
            img_token_dim=self.args["model"]["img_token_dim"],
            state_token_dim=self.args["model"]["state_token_dim"],
            max_lang_cond_len=self.args["dataset"]["tokenizer_max_length"],
            img_cond_len=img_cond_len,
            img_pos_embed_config=[
                # No initial pos embed in the last grid size
                # since we've already done in ViT
                ("image", (self.args["common"]["img_history_size"], 
                    self.args["common"]["num_cameras"], 
                    -self.vision_model.num_patches)),  
            ],
            lang_pos_embed_config=[
                # Similarly, no initial pos embed for language
                ("lang", -self.args["dataset"]["tokenizer_max_length"]),
            ],
            dtype=self.dtype,
        )

        return _model

    def get_text_encoder(self, pretrained_text_encoder_name_or_path):
        text_embedder = T5Embedder(from_pretrained=pretrained_text_encoder_name_or_path, 
                                   model_max_length=self.args["dataset"]["tokenizer_max_length"], 
                                   device=self.device)
        tokenizer, text_encoder = text_embedder.tokenizer, text_embedder.model
        return tokenizer, text_encoder

    def get_vision_encoder(self, pretrained_vision_encoder_name_or_path):
        vision_encoder = SiglipVisionTower(vision_tower=pretrained_vision_encoder_name_or_path, args=None)
        image_processor = vision_encoder.image_processor
        return image_processor, vision_encoder

    def reset(self):
        """Set model to evaluation mode.
        """
        device = self.device
        weight_dtype = self.dtype
        self.policy.eval()
        self.text_model.eval()
        self.vision_model.eval()

        self.policy = self.policy.to(device, dtype=weight_dtype)
        self.text_model = self.text_model.to(device, dtype=weight_dtype)
        self.vision_model = self.vision_model.to(device, dtype=weight_dtype)
        self.last_planning_info = None

    def load_pretrained_weights(self, pretrained=None):
        if pretrained is None:
            return 
        print(f'Loading weights from {pretrained}')
        filename = os.path.basename(pretrained)
        if filename.endswith('.pt'):
            checkpoint =  torch.load(pretrained)
            self.policy.load_state_dict(checkpoint["module"])
        elif filename.endswith('.safetensors'):
            from safetensors.torch import load_model
            load_model(self.policy, pretrained)
        elif filename.endswith('.bin'):
            # HuggingFace default model format
            state_dict = torch.load(pretrained, map_location='cpu')
            self.policy.load_state_dict(state_dict)
        else:
            raise NotImplementedError(f"Unknown checkpoint format: {pretrained}")

    def encode_instruction(self, instruction, device="cuda"):
        """Encode string instruction to latent embeddings.

        Args:
            instruction: a string of instruction
            device: a string of device
        
        Returns:
            pred: a tensor of latent embeddings of shape (text_max_length, 512)
        """
        tokens = self.text_tokenizer(
            instruction, return_tensors="pt",
            padding="longest",
            truncation=True
        )["input_ids"].to(device)

        tokens = tokens.view(1, -1)
        with torch.no_grad():
            pred = self.text_model(tokens).last_hidden_state.detach()

        return pred

    def _format_joint_to_state(self, joints):
        """
        Format the robot joint state into the unified state vector.

        Args:
            joints (torch.Tensor): The joint state to be formatted. 
                qpos ([B, N, 14]).

        Returns:
            state (torch.Tensor): The formatted state for RDT ([B, N, 128]). 
        """
        # Rescale the gripper
        # joints = joints / torch.tensor(
        #     [[[1, 1, 1, 1, 1, 1, 4.7908, 1, 1, 1, 1, 1, 1, 4.7888]]],
        #     device=joints.device, dtype=joints.dtype
        # )
        
        # normalize to -1,1
        joints = (joints - self.state_min) / (self.state_max - self.state_min) * 2 - 1
        B, N, _ = joints.shape
        state = torch.zeros(
            (B, N, self.args["model"]["state_token_dim"]), 
            device=joints.device, dtype=joints.dtype
        )
        # assemble the unifed state vector
        state[:, :, MANISKILL_INDICES] = joints
        state_elem_mask = torch.zeros(
            (B, self.args["model"]["state_token_dim"]),
            device=joints.device, dtype=joints.dtype
        )
        state_elem_mask[:, MANISKILL_INDICES] = 1
        return state, state_elem_mask

    def _unformat_action_to_joint(self, action):
        action_indices = MANISKILL_INDICES
        joints = action[:, :, action_indices]
        
        # denormalize to action space 

        joints = (joints + 1) / 2 * (self.action_max - self.action_min) + self.action_min
        
        return joints

    @torch.no_grad()
    def step(self, proprio, images, text_embeds, vis=True):
        """
        Args:
            proprio: proprioceptive states
            images: RGB images
            text_embeds: instruction embeddings

        Returns:
            action: predicted action
        """
        device = self.device
        dtype = self.dtype
        
        background_color = np.array([
            int(x*255) for x in self.image_processor.image_mean
        ], dtype=np.uint8).reshape(1, 1, 3)
        background_image = np.ones((
            self.image_processor.size["height"], 
            self.image_processor.size["width"], 3), dtype=np.uint8
        ) * background_color
        
        image_tensor_list = []
        for image in images:
            if image is None:
                # Replace it with the background image
                image = Image.fromarray(background_image)
            
            if self.image_size is not None:
                image = transforms.Resize(self.data_args.image_size)(image)
            
            if self.args["dataset"].get("auto_adjust_image_brightness", False):
                pixel_values = list(image.getdata())
                average_brightness = sum(sum(pixel) for pixel in pixel_values) / (len(pixel_values) * 255.0 * 3)
                if average_brightness <= 0.15:
                    image = transforms.ColorJitter(brightness=(1.75,1.75))(image)
                    
            if self.args["dataset"].get("image_aspect_ratio", "pad") == 'pad':
                def expand2square(pil_img, background_color):
                    width, height = pil_img.size
                    if width == height:
                        return pil_img
                    elif width > height:
                        result = Image.new(pil_img.mode, (width, width), background_color)
                        result.paste(pil_img, (0, (width - height) // 2))
                        return result
                    else:
                        result = Image.new(pil_img.mode, (height, height), background_color)
                        result.paste(pil_img, ((height - width) // 2, 0))
                        return result
                image = expand2square(image, tuple(int(x*255) for x in self.image_processor.image_mean))
            image = self.image_processor.preprocess(image, return_tensors='pt')['pixel_values'][0]
            image_tensor_list.append(image)

        image_tensor = torch.stack(image_tensor_list, dim=0).to(device, dtype=dtype)

        image_embeds = self.vision_model(image_tensor).detach()
        image_embeds = image_embeds.reshape(-1, self.vision_model.hidden_size).unsqueeze(0)

        # history of actions
        joints = proprio.to(device).unsqueeze(0)   # (1, 1, 14)
        states, state_elem_mask = self._format_joint_to_state(joints)    # (1, 1, 128), (1, 128)
        states, state_elem_mask = states.to(device, dtype=dtype), state_elem_mask.to(device, dtype=dtype)
        states = states[:, -1:, :]  # (1, 1, 128)
        ctrl_freqs = torch.tensor([self.control_frequency]).to(device)
        
        text_embeds = text_embeds.to(device, dtype=dtype)
        lang_attn_mask = torch.ones(
            text_embeds.shape[:2], dtype=torch.bool, device=text_embeds.device
        )

        if self.use_diffusion_es:
            es_kwargs = {
                "lang_tokens": text_embeds,
                "lang_attn_mask": lang_attn_mask,
                "img_tokens": image_embeds,
                "state_tokens": states,
                "action_mask": state_elem_mask.unsqueeze(1),
                "ctrl_freqs": ctrl_freqs,
                "initial_population_cache":
                    "/home/zhuoli/RoboticsDiffusionTransformer/eval_sim/finetune_population_16_2.pt",
                "ed_population_cache":
                    "/home/zhuoli/RoboticsDiffusionTransformer/eval_sim/ed_population_80"
                    ".pt",
                "use_initial_cache": True,
                "save_initial_cache": False,
                "save_ed_cache": False
            }
            es_kwargs.update(self.diffusion_es_kwargs)
            trajectory, planning_info = self.policy.run_diffusion_es(**es_kwargs)
            self.last_planning_info = planning_info

        else:
            trajectory = self.policy.predict_action(
                lang_tokens=text_embeds,
                lang_attn_mask=lang_attn_mask,
                img_tokens=image_embeds,
                state_tokens=states,
                action_mask=state_elem_mask.unsqueeze(1),
                ctrl_freqs=ctrl_freqs,
            )
            self.last_planning_info = None

        trajectory = self._unformat_action_to_joint(trajectory).to(torch.float32)

        # trajectory visualization
        if vis:
            eef_trajs_visualization(trajectory, franka_fk_fn)

        return trajectory
