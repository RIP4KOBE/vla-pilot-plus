```mermaid
flowchart TD
    Init[每任务：环境与 RNG 初始化] --> Generate[Codex 在线生成身份、阶段与 reward 内容]
    Generate --> Obs[当前图像、机器人状态与目标几何]
    Generate --> Reward[本地 reward 函数]
    Obs --> Stage[共享 Stage 控制器：按触发条件在线查询]
    Stage --> Gate{是否开启引导}
    Gate -->|否| Plain[RDT 单候选去噪]
    Gate -->|是| Method{steering 模式}
    Method -->|vls| VLS[VLS：reward 梯度、RBF、条件 FKD]
    Method -->|eds / eds_qd| EDS[共享 EDS：采样、评分、父代选择、截断去噪]
    EDS <-->|仅 eds_qd| Archive[动作块内 QD 档案：精英维护与稀疏父代]
    Reward --> VLS
    Reward --> EDS
    VLS --> Choose[选择动作候选]
    EDS --> Choose
    Choose -.选中候选的外层 reward 进度.-> Stage
    Plain --> Execute[统一转换与执行前 8 个动作]
    Choose --> Execute
    Execute --> Obs
    Execute --> Evidence[环境成功判定、日志、视频与独立审计]
```

Figure scope: loop ends on environment success or step limit; provider queries occur when scheduled, not for every action. Generated reward is local numeric computation. QD archive is fresh for each guided action chunk. Node order is conceptual; exact prepare/rollout RNG restore boundaries remain defined by the recorded hooks.
