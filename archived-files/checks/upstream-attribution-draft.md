## 来源与引用

本仓库保留 VLS 上游方法的引用：[VLS: Steering Pretrained Robot Policies via Vision-Language Models](https://arxiv.org/abs/2602.03973)。该引用来自整合前 README，题名、作者与 arXiv 页面已核对。本次公共入口的 RDT、在线 Stage、任务初始化与 EDS/QD 设置由本仓库的配置和验收报告定义；本轮 VLS 成绩不冒充原论文结果。EDS 与 EDS+QD 的当前实现和本轮结果也不能归属于该论文。

```bibtex
@article{liu2026vls,
  title     = {VLS: Steering Pretrained Robot Policies via Vision-Language Models},
  author    = {Shuo Liu and Ishneet Sukhvinder Singh and Yiqing Xu and Jiafei Duan and Ranjay Krishna},
  journal   = {arXiv preprint arXiv:2602.03973},
  year      = {2026}
}
```

当前公共三模式验收范围为 RDT + LIBERO ObjectSwap OOD。仓库保留的其他 policy/backend 代码没有在本次验收中重新验证，不将旧 README 的其他基准和真实机器人结果计入本轮成绩。RDT、LeRobot、LIBERO 及外部模型的来源与许可分别见其子模块/资产准备说明。
