# Available GPU queue executor scope

Authorized task continuation: use any usable GPU on the current server with existing Codex login. Implement only persistent CPU waiting/selection/orchestration around the existing audited runner and accounted GPU probe. GPU5/7-only restrictions superseded; one exclusive worker, no external sharing/preemption,240 attempts48GPUhours unchanged.

Worktree is this isolated exp/rdt-qd-ed-final-20260921T093925Z branch; root owns scientific gates, freeze and actual launch. Executor owns only scripts/qd_ed_available_gpu_queue.py and meaningful CPU tests. Do not run GPU, network, modify runtime/state, or commit. No target-success score exists.

Input is a frozen31-row plan for30 unique N1 Dev cells, including the explicitly linked infrastructure recovery n1_dev_t00_q0_r1 of attempt2b5e035fd6bb. Selected keys are that recovery and n1_dev_t00_c0. Preserve the separate originalbaseline invalid attempt. Every retry remains linked and budgeted. The queue itself never repeats a dispatched failure automatically.

Select only authorized server candidates without externalcompute processes and<1024MiB used. Waiting uses CPUmetadata only, no GPU allocation or fabricated attempt. Keep queue singleton lock; avoid nested runnerlocks when calling run_probe/run_plan. Hardware selection updates singleton state and a new immutable hardware-only runtime/plan; provider, scientificinput andsource remainidentical. Actual newCUDA/EGL probes count and failures stop. Sameprocess fullinputhash cache avoids repeated47GB reads.

Durable status must distinguishwaiting,selection,probing,running,completed,failed andlist completedkeys. Only predispatch GPU admissionraces can loop. Postdispatcherrors, source/input/auth drift, unclosedjobs and exhaustedbudgets stopforrootreview. Never exposecredentials or modifyhistorical files. Tests simulateGPUqueries/processes without importingCUDA.
