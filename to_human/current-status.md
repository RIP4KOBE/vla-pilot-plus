# Current Status — run_010 Implementation Complete

- Phase: inner-loop QD-1 sole offline schema repair; execution remains active and interruptible through `.autoresearch/PAUSE`.
- Primary objective: valid formal LIBERO-PRO `libero_object_swap >=5/10`; historical EDS-QD best is `2/10`, gap 3.
- Active experiment: `run_010_causal_envelope_candidate`, status `OFFLINE_V1_INVALID_SCHEMA_REPAIR_PROTOCOL_LOCKED`.
- Protocol commit: `1017bf0212780b2e386764517661cf9970090f8d`; implementation commit: `930cdb5295b8f9b4ee099298764c3af3c078d6b7`.
- Candidate: sparse EDS-QD plus the single `causal_envelope_v1` partition/rebin change; all other EDS/QD and non-EDS-QD semantics are frozen by protocol.
- Verification: TDD completed; frozen nine-file suite `781 passed in 71.32s`.
- Offline v1: immutable failure SHA `16545749…9a61`; all gates passed except an unregistered all-iterations resolution quantifier at one valid zero-SSE denominator. Iterations 1–9 were 1.0. The sole schema/fixture repair is protocol-locked before code changes.
- Online budget consumed: attempts `0/143`, GPU-hours `0/48`, formal uses 0. No online success claim exists yet.
- Next gate: implement only the v2 finite-median audit repair, rerun immutable CPU offline preflight, and freeze a manifest only on PASS. Then execute the six-cell mechanism preflight with dynamically admitted idle GPUs 0–7.
- Dev-A remains gated behind mechanism PASS and requires candidate success `>= paired control +1` with zero loss of any control-success task.
- Dev-B, validation, and formal evaluation are not authorized by the current protocol.
- All new artifacts are confined to `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_010_causal_envelope_candidate`; other worktrees and historical artifacts remain read-only.
- User-owned untracked `docs/01_specs/2026-08-10-eds-qd-stage-guidance-transition-design.md` remains untouched and excluded from every commit.
