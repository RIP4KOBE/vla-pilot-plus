# Current Status — run_010 Stage-A PASS

- Phase: inner-loop QD-1 offline PASS, online manifest pending; execution remains active and interruptible through `.autoresearch/PAUSE`.
- Primary objective: valid formal LIBERO-PRO `libero_object_swap >=5/10`; historical EDS-QD best is `2/10`, gap 3.
- Active experiment: `run_010_causal_envelope_candidate`, status `OFFLINE_PASS_MANIFEST_PENDING`.
- Protocol commit: `1017bf0212780b2e386764517661cf9970090f8d`; implementation commit: `930cdb5295b8f9b4ee099298764c3af3c078d6b7`.
- Candidate: sparse EDS-QD plus the single `causal_envelope_v1` partition/rebin change; all other EDS/QD and non-EDS-QD semantics are frozen by protocol.
- Verification: TDD completed; frozen nine-file suite `781 passed in 71.32s`.
- Offline evidence: v1 schema failure `16545749…9a61` preserved; protocol-first v2 PASS `3097afad…f7a9`. V2 passed 781 tests, checkpoint/LIBERO/source fingerprints, 176/11 accounting, overflow, visit/global-best, RNG, and resolution gates.
- Online budget consumed: attempts `0/143`, GPU-hours `0/48`, formal uses 0. No online success claim exists yet.
- Next gate: freeze an immutable manifest from v2 PASS, then execute the six-cell mechanism preflight with dynamically admitted idle GPUs 0–7.
- Dev-A remains gated behind mechanism PASS and requires candidate success `>= paired control +1` with zero loss of any control-success task.
- Dev-B, validation, and formal evaluation are not authorized by the current protocol.
- All new artifacts are confined to `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_010_causal_envelope_candidate`; other worktrees and historical artifacts remain read-only.
- User-owned untracked `docs/01_specs/2026-08-10-eds-qd-stage-guidance-transition-design.md` remains untouched and excluded from every commit.
