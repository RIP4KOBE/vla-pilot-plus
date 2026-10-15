# E2 implementation readiness (CPU only)

The owning worktree contains dormant opt-in Stage transport commit `f552638`.
The isolated branch `exp/rdt-qd-ed-stage-e2-20260928` under this variant is at
`42f1907` and additionally prepares the exact GPU3 393-attempt/100-hour
budget admission, 32/12-hour protected reserves, explicit E2 runtime binding,
a four-cell serial supervisor, a fail-closed plan freezer, and the default-off Hydra config key. The guard is bound to proposal SHA-256
`25f7df614f8e8e476cdef7403756081156b192db8ab016e1afa1b2d01f3ffe0b`.

CPU-only checks: 132 tests passed across Codex Stage transport/lifecycle,
runner accounting and E2 supervisor scope/release. `git diff --check` is
clean. Old E1 behavior remains the default; E2 requires an explicit runtime
condition and plan marker. The isolated budget/supervisor code has **not** been
integrated into the owning worktree, the state still says 240/48, and no E2
GPU or live Codex call has occurred.

After approval, recheck the proposal SHA and branch HEAD, integrate the
isolated code, write an append-only approval/reservation event, update only
this study's state/resource notice, freeze a fresh E2 runtime manifest and
four-cell plan, then rerun CPU and physical GPU3 preflight before one-cell-at-
a-time dispatch. Any failure before dispatch leaves all old evidence intact.
