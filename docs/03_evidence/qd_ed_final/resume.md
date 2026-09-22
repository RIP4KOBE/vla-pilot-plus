# Research continuation

Updated 2026-09-22T11:05:46.678717+00:00. Physical GPU3 only; wait if unavailable; no automatic fallback.

Process-isolated renderer still faults on GPU3 after model loading, before any B1. Prepare a no-model static-scene control with a fixed75-second idle interval to distinguish elapsed-time effects. All task GPU work remains physical3; no fallback.

Budget: 0.958362134/48 GPU-hours, 11/240 scientific attempts, 0 valid. Target unmet; candidate N1 unmeasured; validation/formal closed.

Latest evidence: /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/gpu3-render-process-diagnostic/rdt-qd-ed-final-20260921T093925Z__gpu3_render_process__7a179aced1de/healthcheck-result.json. Both owned GPU processes cleaned up; no owned GPU worker remains. Authoritative state: research-state.yaml and docs/03_evidence/qd_ed_final/iteration-ledger.md.
