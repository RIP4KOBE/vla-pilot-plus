# RDT + QD + ED current-session archive

This is the single navigation root for the explicitly invoked Arbor study
`rdt-qd-ed-final-20260921T093925Z`. The machine-readable relocation list,
original paths and exact Git heads are in `archive-layout-v1.json`.

- `study_worktree/`: the active research state, unified attempt ledger,
  exposure registry, source, protocols and Arbor session report.
- `variants/support/decision_evidence/`: native decision evidence plumbing.
- `variants/n2_executed_quality/`: N2 implementation and runner.
- `variants/n3_executed_feedback/`: N3 runner.
- `variants/n4_terminal_population/`: N4 implementation, audits, evaluation
  runners, E1 transport runner and Stage lifecycle worktree.
- `variants/n5_grasp_timing/`: N5 frozen protocol, implementation and audits;
  this is a new branch inside the archive rather than a new top-level `exp`
  directory.
- `variants/n6_height_aware/`: N6 height-aware QD descriptor, native audit,
  matched Dev plan, GPU3 supervisor and rejected 1/4 Dev result.
- `variants/n7_direction_height/`: N7 coarse XY direction plus signed-height
  descriptor, native audit, frozen Dev plan and result, independent validation
  runner, GPU3 supervisors and read-only prerequisite replay. Its
  `formal_runner/` worktree holds a conditional, CPU-tested fixed-set protocol
  and runner; it is not released unless full C1 validation passes.
- `variants/n8_direction_radius_height/`: a read-only N7 Dev partition replay
  and negative screen. No N8 simulator run or executable candidate was made.
- `variants/n5_grasp_timing/dev_artifacts` and
  `variants/n6_height_aware/dev_artifacts`: links to each variant's frozen
  plans, attempt outputs and reports inside the unified `artifacts/` entry.
- `artifacts/`: all large run outputs, frozen plans, reports, videos, decision
  bundles and the September 25 same-state diagnostic.

Each variant remains an independent Git worktree with its original commit and
branch. Legacy paths under `.worktrees/exp/rdt-qd-ed-*` are compatibility
symlinks, because frozen plans and evidence reference those absolute paths.
The `artifacts/` entry points to the original 28 GB `/mnt/data` artifact tree:
the workspace disk cannot hold a duplicate, and relocating its underlying
absolute path would invalidate frozen input identities. No experiment data was
copied, deleted, merged across candidates or reclassified by this archive.

The pre-existing historical `eds-*` worktrees are grouped separately at
`../../historical_variants/`. After the owner confirmed it had stopped, the
other session was moved to `../rdt-qd-ed-gpu6-20260922T063626Z/` with its
dirty state and artifact link preserved. The older autoresearch worktree's
protected untracked specification was left untouched. The latest archive
status is in `archive-overview-v11.json`.
