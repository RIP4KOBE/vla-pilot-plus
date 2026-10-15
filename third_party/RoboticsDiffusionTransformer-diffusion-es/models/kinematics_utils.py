import torch
from roboticstoolbox import models
from configs.state_vec import STATE_VEC_IDX_MAPPING


MANISKILL_INDICES = [
    STATE_VEC_IDX_MAPPING[f"right_arm_joint_{i}_pos"] for i in range(7)
] + [
    STATE_VEC_IDX_MAPPING[f"right_gripper_open"]
]

DATA_STAT = {'state_min': [-0.7463043928146362, -0.0801204964518547, -0.4976441562175751, -2.657780647277832, -0.5742632150650024, 1.8309762477874756, -2.2423808574676514, 0.0], 'state_max': [0.7645499110221863, 1.4967026710510254, 0.4650936424732208, -0.3866899907588959, 0.5505855679512024, 3.2900545597076416, 2.5737812519073486, 0.03999999910593033], 'action_min': [-0.7472005486488342, -0.08631071448326111, -0.4995281398296356, -2.658363103866577, -0.5751323103904724, 1.8290787935256958, -2.245187997817993, -1.0], 'action_max': [0.7654682397842407, 1.4984270334243774, 0.46786263585090637, -0.38181185722351074, 0.5517147779464722, 3.291581630706787, 2.575840711593628, 1.0]}


def franka_fk_fn(joint_trajs: torch.Tensor) -> torch.Tensor:
    """
    输入 shape [B, T, 7]，输出 shape [B, T, 3] 的 EEF 位置
    """
    B, T, _ = joint_trajs.shape
    eef_pos = torch.zeros((B, T, 3), dtype=joint_trajs.dtype)
    franka = models.URDF.Panda()

    for b in range(B):
        for t in range(T):
            q = joint_trajs[b, t].cpu().numpy()  # (7,)
            T_eef = franka.fkine(q)  # SE(3)
            pos = T_eef.t[:3]  # 取平移部分
            eef_pos[b, t] = torch.tensor(pos)

    return eef_pos
