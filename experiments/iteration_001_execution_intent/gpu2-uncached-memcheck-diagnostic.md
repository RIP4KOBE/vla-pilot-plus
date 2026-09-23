# GPU2 uncached CUDA memcheck diagnostic

GPU2 blocking memcheck ended at2026-09-23T03:10:15UTC after154.896566seconds,
with four CUDA allocation errors at the ninth model call, zero environment
actions andzero Stage calls. Allocated PyTorch memory was136.90GiB andthe
failed allocation548MiB. No Xid or illegal memory access was reported, but the
first EDS search was incomplete. Preserve this invalid result andcost.
Audit: artifact `analysis/gpu2-blocking-memcheck/audit.json`.

PyTorch documents that its caching allocator can interfere with memcheck and
instructs setting `PYTORCH_NO_CUDA_MEMORY_CACHING=1` for memory debugging:
https://docs.pytorch.org/docs/2.7/notes/cuda.html#optimizing-memory-usage-with-pytorch-cuda-alloc-conf
The launching environment has neither this variable norPYTORCH_CUDA_ALLOC_CONF;
the prior frozen runtime did not set it. This proposed allocator condition is
a diagnostic correction, not a proven root cause or production fix. Production
DiT calls andinput encoding are already under no_grad.

Run one newcondition `GPU2_CUDA_MEMCHECK_NOCACHE_C0`, episodekey
`gpu2_cuda_memcheck_nocache_c0_t00`: task0C0/env+policyseed1969522881/init0,
dev/development, no retry_of,600second maximum. Keep the sameCUDA12.8 sanitizer,
fixed blocking launch option, task/seed/init, weights, precision, B16/EDS,
Stage configuration and720-step limit. The only diagnostic intervention from
the prior blocking condition is disabling the PyTorch caching allocator before
Python starts. Enforce the exact environment string1 anddistinct iteration;
strip inherited allocator-disable flags from ordinary runs. Never add arbitrary
CUDA options, suppressions or kernel filters.

Both CUDA andEGL remain onphysicalGPU2/EGL1. Keep120second idle admission,
shared singleworker locking, append-only attempts/costs,240attempt/48GPU-hour
limits, protected validation/formal reserves andXid31/109 early termination.
No automatic retry, no scientific orN1R comparison, no adoption, no alteration
of the closed parent cohorts/report. Runtime manifests disclose the allocator
change; device identity proof may be reused if its original gate validates.

Review whether first EDS search completes, allocator errors, any precise memory
access errors, andsubsequent rendering phases. A timeout or incomplete report
is not a clean pass. Removing caching changes allocation layout andtiming and
can expose orhide concurrency defects. Even a completed error-free diagnostic
does not validate the ordinary cached/asynchronous production path. Record
only NVIDIA public memory/PID/time samples for progress; no secret environments.
