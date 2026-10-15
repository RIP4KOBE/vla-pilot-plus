# Latest user directive: independent GPU3/GPU2 studies

At 2026-09-24T07:25:56.413748+00:00, the user explicitly authorized two simultaneous experiment workers, one per study/GPU, and independent budgets: GPU3 N4 240 attempts/48 GPUh; GPU2 current branch 250 attempts/48 GPUh. Historical costs remain attributed to their owning study.

Authority: /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/resource-isolation-20260924-v1/authorization.json SHA256 4026c141ff9bd06f31734c0a43122327b359c35bd847670f641961df9ce81f47.

Migration is currently DRAINING: finish the currently active episode, then allow the one-time coordinator migration under the old shared lease. Do not start a new competing supervisor while migration is pending. No active episode is to be interrupted.

After migration each study owns its local state, journals and runner/state locks. Never rewrite the other study's budget, set an external hold, or terminate the other study's processes based on any older GPU priority notice. Prior GPU2/GPU3 priority records are historical and superseded for cross-study resource control. Each study still has one worker, its fixed physical GPU and its own scientific/phase gates. The GPU2 branch's currently frozen N1W plan remains its owner session's scientific authority.
