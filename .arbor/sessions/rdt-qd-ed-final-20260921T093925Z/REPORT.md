# Interim research checkpoint

Status: native diagnostic queue preparation for GPU7 only. No owned GPU worker or queue is running at this checkpoint; later runtime process/status records take precedence. The latest user instruction restricts all subsequent work to physical GPU7, with one exclusive worker and no fallback to other cards.

The previous GPU6 recovery ran for 1201.38 seconds and completed one actual Codex Stage query at step24 (19.772 seconds, 10800 input / 42 output tokens). Shortly after guidance switched off, the native process exited with SIGABRT (-6). The cause remains unknown; the sample is invalid and nonretryable.

Current totals: 5 dispatched episodes, 3 infrastructure aborts, 2 invalid task failures, 0 scientifically valid outcomes, 0 running episodes, and 0.4306699061807659 closed GPU-hours including healthchecks. No candidate, validation or formal score exists. The project target is not achieved.

The isolated B1 diagnostic passed 37 CPU tests. It uses frozen real RDT/T5/SigLIP models and deterministic synthetic inputs, with no simulator, action execution, Stage call or scientific episode. It charges GPU-process wall time separately and cannot establish guided-transition or EGL causality by itself. The diagnostic queue will execute it once after GPU7 is continuously idle for 120 seconds, then stop for review. All scientific phase gates remain closed.

Codex saved-login transport is verified. Poe credentials remain unchanged. The prospective main phase-timing patch is still unapplied. Preserve all historical failures, immutable plans and resource costs.

Authority: research-state.yaml and docs/03_evidence/qd_ed_final/iteration-ledger.md. Resume: docs/03_evidence/qd_ed_final/resume.md.
