# GPU2 post-reboot production-path diagnostic — 2026-09-23

The user explicitly resumed after reboot to address the GPU fault. Execution
remains exclusively physical GPU2, UUID GPU-a5d6a5f8-b6df-7f3a-c3dc-19734c41ec0e,
PCI 00000000:41:00.0. Current boot: 2a1fa95f-ab0d-488c-a298-fc488ddd2af7.
The unchanged driver is 580.65.06. Re-enumerate EGL and require a fresh,
accounted CUDA/EGL probe from this boot before episode dispatch.

The interrupted uncached memcheck attempt ending 2113e44a689a remains aborted,
KeyboardInterrupt, outcome_valid=false, retryable_infrastructure=false, with
143.82796022621915 seconds charged. Restored logs end during the first search:
zero environment actions, zero Stage queries; sanitizer log has only its
header, without a completed summary. This is not a clean memcheck result.

Prospectively run exactly one development diagnostic GPU2_POST_REBOOT_C0,
key gpu2_post_reboot_c0_t00. Task0, C0, env/policy seed1969522881, init0,
unchanged weights, precision, B16, EDS, Stage, and720-step episode horizon.
Maximum process wall time900seconds. No retry_of. Restore the ordinary
production path: no sanitizer, caching allocator at its default, serialization
and renderer lifetime diagnostics disabled. The hypothesis is whether the
fresh system boot permits inference followed by rendering without Xid/corrupt
frames. Compare engineering behavior with prior ordinary-path failures;
this is not a controlled allocator or sanitizer comparison.

This one diagnostic is not a member of the prospective N1R scientific cohort
and cannot replace a failed historical cell. Count its costs and any valid
task outcome separately. Require complete episode/cost telemetry, inspect
frames and render timings, and review kernel Xids before declaring runtime
usable. Preserve user pause and historical parent closure as historical facts.

Keep shared locks, one exclusive worker,120seconds observed idle, device
identity checks,240attempt/48GPU-hour ceilings and protected validation/formal
reserves. Stop on Xid31/109 or loss of exclusivity. No automatic retry after
dispatch. If runtime is usable, separately freeze the common C0/Q0/N1 N1R
comparison before dispatch; if not, review exact failing phase before choosing
another bounded diagnostic. This plan itself dispatches no N1R or formal cells.

Storage recovery: /mnt/data mount failed because fstab used volatile /dev/sdb;
read-only filesystem inspection identified the original data on UUID
87195613-9a14-44c8-9ec6-1a7cb2b41017, now /dev/sdc. Both it and the existing
shared2 UUID7eef54ab-275f-429b-9a26-de570a1d05a2 were mounted at their original
paths. No filesystem repair, formatting or historical artifact rewrite.
