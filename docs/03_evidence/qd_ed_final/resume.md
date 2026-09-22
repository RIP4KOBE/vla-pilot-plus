# Research continuation

Updated 2026-09-22T10:31:01.328229+00:00. Physical GPU3 only; wait if unavailable; no automatic fallback.

Early CUDA initialization passes the identity/seed boundary but rendering corrupts after T5 loading before inference. Early-CUDA patch remains unapplied. Prepare a single dedicated-render-thread isolation healthcheck; physical GPU3 only, no scientific score.

Budget: 0.918117368/48 GPU-hours, 11/240 scientific attempts, 0 valid. Target unmet; candidate N1 remains unmeasured; validation/formal closed.

Latest evidence: /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/gpu3-cuda-first-diagnostic/rdt-qd-ed-final-20260921T093925Z__gpu3_cuda_first__c40589cf6c65/healthcheck-result.json. No owned GPU worker remains. Authoritative state: research-state.yaml and docs/03_evidence/qd_ed_final/iteration-ledger.md.
