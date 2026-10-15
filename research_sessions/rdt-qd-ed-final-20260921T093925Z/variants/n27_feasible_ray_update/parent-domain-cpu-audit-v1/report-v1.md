# 固定首 guided chunk 的 CPU 父代域检查

状态：**COMPLETE**。一次已授权容器读取；无模型/API/仿真；解码与张量计算均在CPU。CPU参考不能证明CUDA逐位结果、去噪后影响或任务收益。

输入读取1次／12060933 bytes；weights_only CPU解码1次；耗时1.931s，CPU2.108s，峰值RSS470488 KiB（进程设置8GiB RLIMIT_AS；未设置或声称单独的RSS上限）。

脚本SHA256 `23916c464483905f62e2c15b68a97f0fd6430d0a6678c864294b1ecfd481a15f`；协议SHA256 `90b6dcfc459048293bb9f2ee51e4e12629c91f2c1ebfaff0e6b9c9b422906fa0`。

| iter | full-action unique/16 | xyz unique/16 | clipped xyz unique/16 | interior/boundary/outside | CPU gradient zero | assigned changed components |
|---:|---:|---:|---:|---|---|---:|
| 0 | 6 | 6 | 6 | 384/0/0 | False | 384 |
| 1 | 6 | 6 | 6 | 384/0/0 | False | 380 |
| 2 | 7 | 7 | 7 | 378/6/0 | False | 355 |
| 3 | 8 | 8 | 8 | 374/10/0 | False | 356 |
| 4 | 8 | 8 | 8 | 370/14/0 | False | 361 |
| 5 | 8 | 8 | 8 | 371/13/0 | False | 371 |
| 6 | 8 | 8 | 8 | 371/13/0 | False | 371 |
| 7 | 8 | 8 | 8 | 368/16/0 | False | 365 |
| 8 | 8 | 8 | 8 | 368/16/0 | False | 365 |
| 9 | 8 | 8 | 8 | 368/16/0 | False | 350 |

origin沿用同一决策原rollout witness，显式假设搜索期间当前EEF固定；它不是新pre-renoise测量。未分析或导出共存quality/provider-return/selection数值。全部10轮为固定分母，不按活跃性挑选；重复组相对其他组可共同移动，不能以重复率单独判定零梯度。

原投影静态来源：/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree/core/env_adapters/libero_adapter.py:1631–1690，SHA256 22e8be88e1a68bcffdd72536b79e7f9e4d56efdc0b12b5a0c3fb1c7877930c64；policy:7695–7723。该纯CPU参考保留原origin cast→delta*.01→cumsum→加origin次序，未调用环境。

result SHA256 `16faabff91b8bed0a0337016de1231cc11958afb76973ec4ac38131da3153c74`；execution metadata SHA256 `83ec1bfadf829ddc06c0417c2eccca141ed7e648fc2b113f1e9dae9714ccdb67`。

## 聚合解释与运行时警告

10轮均完整关联：每轮完整动作、原xyz与clipped xyz独特数一致，为6、6、7、8、8、8、8、8、8、8；按每轮独特槽数相加为75/160（不能称跨轮75个全局unique候选）。严格内部3736/3840，边界104，外部0。全部160粒子都有支持且CPU假设赋值发生变化，10轮均非零梯度；operand非零3736分量，实际赋值变化3658分量，78分量被native赋值舍入吸收。没有新增越界，零operand字节保留；159/160粒子alpha<1。原生提议norm每轮20，实际CPU赋值delta L2范围3.279889–7.185870。

因此，在这个固定首guided父代域和已声明origin假设下，“重复/饱和使拟议变异全零”这一强反驳不符合CPU参考。它不证明重复副本被拆分，不证明方向覆盖改善，也不证明经过原renoise/模型后影响保留。没有运行模型对照或新物理分支，不能从局部非零推出任务收益、优先级或下一候选授权。

唯一执行的stderr包含以下原文警告（保留，不重跑）：

```text
/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/torch/autograd/graph.py:824: UserWarning: CUDA initialization: Unexpected error from cudaGetDeviceCount(). Did you run some cuda functions before calling NumCudaDevices() that might have already set an error? Error 2: out of memory (Triggered internally at /pytorch/c10/cuda/CUDAFunctions.cpp:109.)
```

这是Torch CPU autograd内部CUDA设备数探测路径产生的警告；CUDA_VISIBLE_DEVICES为空，所有解码与计算tensor均为CPU，末尾torch.cuda.is_initialized()仍False。不能把此次运行描述成“绝无CUDA运行时探测”；也没有证据把它当作成功初始化、CUDA数值证明或GPU实验。8GiB AS上限始终生效，错误2的具体内部成因未另查。该stderr已追加到execution metadata；原标量结果、脚本和单次执行计数均未修改。
