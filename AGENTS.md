# Resource ownership for this research worktree

These instructions implement the user's explicit 2026-09-24 authorization for two independent studies. Read RESOURCE_ISOLATION_USER_20260924.md and the resource_isolation field of this worktree's research-state.yaml before GPU dispatch or any resource-state change.

- This worktree owns only its own research-state.yaml, local data journals, locks, attempts and output artifacts. After migration, do not write another study's state/budget, create holds on it, or signal its processes.
- The one-time resource migration is authorized to coordinate both worktrees while draining; do not start a new supervisor until resource_isolation.status is ACTIVE and validation is PASS. Let any active episode finish.
- Keep one GPU worker within this study, with its assigned physical GPU/UUID. Independent other-study execution on its own GPU is authorized and is not a conflict.
- The GPU3 study has a user-approved private 393-attempt/100-GPU-hour cumulative budget, with baseline 28, development 125, validation 180, formal 40, recovery 20, and protected validation/formal GPU-hour reserves 32/12. Approval: `../budget-extension-proposal-20260928.md` SHA-256 `25f7df614f8e8e476cdef7403756081156b192db8ab016e1afa1b2d01f3ffe0b`; protocol: `../variants/n10_lineage_survival/e2-prospective-measurement-protocol-v1.md` SHA-256 `c9a66bfdd8dd0848a8f32a565ee2800759941f4865a6ed6c001ee87efb09c62e`. The GPU2 study remains on its private 250-attempt/48-GPU-hour budget. These are separate, including retained owner-attributed history. Preserve each study's protected reserves and scientific gates.
- Older RESOURCE_PRIORITY_* notices or historical shared-budget authorizations do not authorize cross-study preemption or state writes.
- Preserve frozen scientific code/plans and all recorded results; resource isolation alone does not authorize algorithm changes or protected-phase evaluation.
- Existing global policy remains: Superpowers is disabled; Arbor and Orchestra autoresearch remain explicit-invocation-only. This ongoing Arbor task was explicitly invoked.
