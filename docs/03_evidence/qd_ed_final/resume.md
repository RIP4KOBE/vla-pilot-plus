# Research continuation

Updated 2026-09-22T10:45:05.150545+00:00. Physical GPU3 only; wait if unavailable; no automatic fallback.

Dedicated render thread still faults after model load before inference. Prepare one GPU3 diagnostic with a fresh spawned renderer process and model parent, synchronously on the same physical GPU3; scientific gates remain closed.

Budget: 0.938215221/48 GPU-hours, 11/240 scientific attempts, 0 valid. Target unmet; candidate N1 unmeasured; validation/formal closed.

Latest evidence: /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/gpu3-render-thread-diagnostic/rdt-qd-ed-final-20260921T093925Z__gpu3_render_thread__be460ba14398/healthcheck-result.json. No owned GPU worker remains. Authoritative state: research-state.yaml and docs/03_evidence/qd_ed_final/iteration-ledger.md.
