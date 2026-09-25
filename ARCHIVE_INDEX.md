# Experiment archive

The current Arbor RDT + QD + ED study is under
`research_sessions/rdt-qd-ed-final-20260921T093925Z/`. Its
`study_worktree/` holds the active code, state and ledger; `variants/`
separates N2, N3, N4, N5, N6, N7 and support worktrees; `artifacts/` exposes every
frozen plan, run output and diagnostic. The exact worktree heads and old-path
aliases are recorded in `archive-layout-v1.json` there.

Earlier `eds-*` experiments are grouped under `historical_variants/`, with
the exact source/target mapping and Git heads in
`historical_variants/historical-layout-v1.json`. This existing
`eds-qd-autoresearch-libero-swap-ood` worktree remains the archive root;
its historical tracked contents and protected untracked specification have
not been changed by relocation.

N5, N6 and N7 protocol, source, Dev plans and results are grouped in the
current session's `variants/n5_grasp_timing/` and `variants/n6_height_aware/`
and `variants/n7_direction_height/` folders. N7's validation runner is a
separate worktree inside its variant folder. `research_sessions/rdt-qd-ed-final-20260921T093925Z/archive-overview-v11.json`
records the current source heads, Dev decision, validation releases and GPU3 continuation status.

The owner confirmed the separate GPU2/N1V session had stopped. Its Git
worktree, unchanged dirty state, variant links and external artifact link are
under `research_sessions/rdt-qd-ed-gpu6-20260922T063626Z/`; see its
`archive-layout-v1.json`. The old `.worktrees/exp` path is a compatibility
symlink so historical absolute references still resolve.

Old `.worktrees/exp/*` names are compatibility symlinks to the grouped
worktrees. They preserve frozen absolute paths without retaining scattered
data copies. Large current-study artifacts stay physically on `/mnt/data`
and are exposed by the `artifacts/` link because the workspace disk has
insufficient free space for a second 28 GB copy. Historical `outputs`
links retain their original storage locations for the same provenance reason.
