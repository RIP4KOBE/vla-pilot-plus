# GPU2 blocking CUDA memcheck diagnostic

The GPU2 migration and CUDA/EGL probe succeeded. The initial memcheck attempt
`rdt-qd-ed-final-20260921T093925Z__gpu5_cuda_memcheck_c0_t00__66eec8a1ab74`
ended after164.742965seconds with exit86, four CUDA API allocation error reports,
zero environment actions andzero Stage calls. It did not finish its first EDS
search. Preserve the invalid result and its cost; it is not a clean memory check.
Audit: artifact `analysis/gpu2-cuda-memcheck/audit.json`.

NVIDIA documents that concurrent launches can increase sanitizer tracking memory
and that `--force-blocking-launches` can reduce this footprint:
https://docs.nvidia.com/compute-sanitizer/ComputeSanitizer/index.html#memory-footprint
Installed CUDA12.8 Compute Sanitizer2025.1.0.0 help confirms this flag.
This is a hypothesis to test, not an established explanation for the OOM or
the prior graphics Xid31/109 failures. The failed PyTorch allocation was in RDT
RMS normalization; that observed DiT call is already under `torch.no_grad()`.

Run exactly one prospective condition `GPU2_CUDA_MEMCHECK_BLOCKING_C0`, key
`gpu2_cuda_memcheck_blocking_c0_t00`: C0/task0/env+policyseed1969522881/init0,
dev/development, no retry_of,600second diagnostic maximum. Freeze the same
production command and scientific settings, adding only the fixed sanitizer
`--force-blocking-launches` flag. Keep original taskseed/720step configuration,
QDoff, B16 andEDS settings. Both CUDA andEGL usephysicalGPU2, mappedEGL1.
No batch-size reduction, precision change, algorithm change, kernel filter,
error suppression, dependency upgrade, GPU reset or password persistence.

The distinct iteration identity prevents replacement of the original result.
Account all elapsed GPU time and stop on new Xid31/109,600seconds, external GPU
occupation, or child exit. Retain study-wide single worker,120second idle gate,
240attempt/48GPU-hour limits andprotected validation/formal reserves. No automatic
retry or N1R dispatch. Previous serialization/lifetime envflags stay0.

Review errors, phase reached, andmemory. Blocking changes execution timing and
may hide concurrency defects; even an error-free report is not proof that the
ordinary asynchronous path is correct. An incomplete run, timeout or Xid cannot
be labeled a clean pass. This diagnostic never contributes a success-rate sample
or candidate promotion. Decide further work only after preserving this result.
