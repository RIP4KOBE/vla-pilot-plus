# CPU dependency startup clarification v1

This supplements root-cpu-protocol-v1.md (SHA a0eacf7dab4ee93c90f86c4e85d1ce2a7e14794085b38ce562f38e3a8e0f5e61) only for the isolated CPU reader and its synthetic tests.

Root inspected the installed Torch default dependency loader at torch/__init__.py lines 312–335 and dill/_dill.py lines 162–175. Permit exactly (1) read-only /proc/self/maps for this process's normal Torch dependency initialization, and (2) normal read/write opens of /dev/null as a sink, after confirming the path is the expected character device. No other /proc path, process map, device, network or external ordinary-file write is authorized. Do not export or persist map contents. Do not switch TORCH_USE_RTLD_GLOBAL, change installed libraries, substitute os.devnull or monkeypatch dependency loading to bypass the normal branch.

All original controls remain: before-import 8 GiB RLIMIT_AS, CPU affinity/threads <=2, CUDA invisible and uninitialized, no model/production imports or actual research inputs, finite container/storage/graph bounds, <=24 files/4 MiB and aggregate test time <=180 seconds inclusive of all failed tests/child probes. Include this clarification and installed-source hashes in the delivery. Preserve the first two failed invocations, denial evidence and SIGSEGV; neither is accepted startup proof. Continue with one justified guarded test run under this clarified startup scope, then inspect its result before any adaptive follow-up. Actual records/index/tensor reads remain closed.

