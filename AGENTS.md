# Resource ownership for this research worktree

These instructions implement the user's explicit 2026-09-24 authorization for two independent studies. Read RESOURCE_ISOLATION_USER_20260924.md and the resource_isolation field of this worktree's research-state.yaml before GPU dispatch or any resource-state change.

- This worktree owns only its own research-state.yaml, local data journals, locks, attempts and output artifacts. After migration, do not write another study's state/budget, create holds on it, or signal its processes.
- The one-time resource migration is authorized to coordinate both worktrees while draining; do not start a new supervisor until resource_isolation.status is ACTIVE and validation is PASS. Let any active episode finish.
- Keep one GPU worker within this study, with its assigned physical GPU/UUID. Independent other-study execution on its own GPU is authorized and is not a conflict.
- The GPU3 study has a private 240-attempt/48-GPU-hour budget; the GPU2 study has a private 250-attempt/48-GPU-hour budget. These are separate, including retained owner-attributed history. Preserve each study's protected reserves and scientific gates.
- 2026-09-28 user amendment for this GPU2 study only: total attempt cap is 258 for one ten-task current-source C0 historical-Stage replay. The 48-GPU-hour cap and protected validation/formal 100 attempts/24 GPU hours are unchanged. See `artifacts/c0_trace_replay_20260925/current-budget-approval.json`; the preceding 250 figure remains historical.
- Later 2026-09-28 user instruction for the approved Codex Stage diagnostic: "不用管预算，只要完成任务就好". The former 258-attempt stop condition does not block this diagnostic. Record new episodes and GPU hours in this study; keep GPU2 ownership, one worker, frozen evidence and GPU3 isolation. The 298-attempt accounting version and diagnostic authorization are in `research-state.yaml` and `artifacts/c0_online_stage_diagnostic_20260928/authorization.json`.
- Older RESOURCE_PRIORITY_* notices or historical shared-budget authorizations do not authorize cross-study preemption or state writes.
- Preserve frozen scientific code/plans and all recorded results; resource isolation alone does not authorize algorithm changes or protected-phase evaluation.
- Existing global policy remains: Superpowers is disabled; Arbor and Orchestra autoresearch remain explicit-invocation-only. This ongoing Arbor task was explicitly invoked.
