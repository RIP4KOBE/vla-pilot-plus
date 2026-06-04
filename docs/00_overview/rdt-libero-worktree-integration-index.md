# RDT/LIBERO Worktree Integration Index

Date: 2026-06-03
Updated: 2026-06-04

This index records the main-branch integration of the historical RDT/LIBERO
worktrees. It keeps the provenance trail in `docs/` while leaving all
`.worktrees/*` directories intact.

## Branch And Worktree Status

| Worktree / branch | Status | Notes |
|---|---|---|
| `.worktrees/feat/rdt-libero-gt-rollout-integration` / `feat/rdt-libero-gt-rollout-reintegration` | Successful source | Source HEAD `360a6d052861`. Despite the directory name, its Git metadata points at `feat/rdt-libero-gt-rollout-reintegration`. This is the selected source for RDT+LIBERO GT rollout and RDT+VLS steering integration. |
| `.worktrees/feat/rdt-libero-dataset_finetune` / `feat/rdt-libero-object-ckpt` | Intermediate | Source HEAD `1be4afbf17ea`. Contains fine-tuning plans, dataset and GT-diff analysis. Useful for provenance, not used as the code source for main integration. |
| `.worktrees/feat/rdt-maniskill-ckpt-libero-integration` / `feat/rdt-integration` | Intermediate / failed path | Source HEAD `3835192744a4`. Early RDT/ManiSkill checkpoint-to-LIBERO integration attempt. Retained for historical analysis only. |
| `.worktrees/feat/rdt-libero-object-ckpt` | Checkpoint-related branch | Present in worktree registry; not selected as the source for this integration. |
| `.worktrees/debug-diffusion-baseline` | Unrelated baseline | Preserved, not integrated. |

## Current Main Capabilities

The integration branch keeps `policy.type=pi05` as the default to preserve the
original main-branch startup path. RDT is enabled as an explicit capability:

```bash
python main.py policy.type=rdt main.use_guidance=false
python main.py policy.type=rdt main.use_guidance=true
```

Main now includes:

- `RDTSteer` as a VLS-compatible policy wrapper for RDT-1B LIBERO checkpoints.
- A LIBERO GT observation processor that preserves raw agentview/wrist images,
  7 joint positions, 2 gripper qpos values, and task text for RDT.
- A direct 128D RDT action-slot decoder for LIBERO raw 7D actions.
- RDT guided denoising with translation-slot keypoint guidance, diversity
  guidance, FKD resampling, and particle selection.
- RDT-specific online observation sampling: RDT fetches one environment
  observation even when guided sampling uses multiple particles.
- LIBERO-PRO suite parsing fix: `libero_object` is a base suite with no
  perturbation; `libero_object_object` is the object perturbation suite.

## Key Documents

Specs:

- [RDT-LIBERO GT Rollout Re-Integration Design](../01_specs/2026-05-26-rdt-libero-gt-rollout-reintegration-design.md)
- [RDT-LIBERO VLS Steering Design](../01_specs/2026-06-02-rdt-libero-vls-steering-design.md)
- [RDT LIBERO-Finetuned Integration Design](../01_specs/2026-05-25-rdt-libero-finetuned-integration-design.md)

Analysis:

- [RDT-LIBERO Current Rollout System Path](../02_analysis/rdt_intergration/2026-06-01-rdt-libero-current-rollout-system-path.md)
- [RDT LIBERO 0/10 Success Debugging Summary](../02_analysis/rdt_intergration/libero/2026-05-26-rdt-libero-0-success-debugging-summary.md)
- [RDT VLS Steering Failure Analysis](../02_analysis/rdt_intergration/libero/rdt_vls_steering_failure_analysis.md)
- [RDT-1B LIBERO Integration Findings](../02_analysis/rdt_intergration/libero/rdt-libero-findings.md)
- [RDT Project Overview](../02_analysis/rdt_intergration/rdt_agent/rdt-project-overview.md)
- [RDT Fine-Tuning Analysis](../02_analysis/rdt_intergration/rdt_agent/rdt-finetune-analysis.md)
- [LIBERO Dataset Semantics Analysis](../02_analysis/rdt_intergration/rdt_agent/libero-dataset-semantics-analysis.md)

Evidence:

- [RDT LIBERO VLS Steering Hyperparameter Validation Evidence](../03_evidence/2026-06-03-rdt-libero-vls-hparam-validation.md)
- [Round-3 RDT-LIBERO Obs Chain Audit Report](../03_evidence/rdt_intergration/round-3/20260511_ROUND3_AUDIT_REPORT.md)
- [Round-4 Action Chain Probe Report](../03_evidence/rdt_intergration/round-4/20260511_action_probes_report.md)

Plans and manifest:

- [RDT-LIBERO VLS Steering Implementation Plan](../04_plans/2026-06-02-rdt-libero-vls-steering.md)
- [Archived Documents Manifest](./rdt-libero-archived-documents-manifest.md)
- [2026-06-04 Worktree Agent Markdown Gap Integration Report](./2026-06-04-worktree-agent-md-gap-integration-report.md)

## Known Issues

- RDT checkpoint and encoder paths are local `/mnt/data/hf_cache/...` paths; RDT
  smoke runs depend on those files being present on the machine.
- Guided RDT+VLS smoke can require VLM credentials/configuration. No credential,
  endpoint override, or local environment-file content is tracked in this branch.
- Full LIBERO-PRO perturbation generation was not revalidated in this pass.
  The suite-name parsing bug is fixed, and guided/unguided default runs both
  use `libero_object` unless the user explicitly selects a perturbed suite.
- Historical docs still mention obsolete implementation names for provenance
  (`rdt_obs_processor`, `rdt_action_converter`). The current code and tests do
  not import those modules.
