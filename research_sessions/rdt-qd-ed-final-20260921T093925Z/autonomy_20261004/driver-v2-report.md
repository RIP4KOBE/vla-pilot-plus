# Driver v2: remove production CPU-test restrictions

Sole delta from frozen v1: remove main's sched_setaffinity(0,{0,1}) and remove child_environment's forced OMP/OPENBLAS/MKL/NUMEXPR=2 loop. All other bytes are identical; static AST comparison verifies only those two functions changed. The new driver inherits the service's intended affinity/environment, while the synthetic test launcher remains CPU0,1/threads2/CUDAhidden.

Three focused environment/command cases passed, exit0, guard_clean=true, denied=[]. Test CPU 0.049319400s / wall 0.049623957s. Unset thread variables remain absent; explicit non2 values and managed-auth/proxy environment are inherited; API/Poe-key overrides still removed; exact official command including --ephemeral is unchanged.

v1/release artifacts and live service/processes were untouched. No CLI/model/API/GPU invocation. Root must bind driver_v2.py's new hash in a reviewed release and change service ExecStart only after the existing coordinator naturally drains. Any service-level affinity/thread restrictions, if present, remain root-owned and must be checked there; v2 does not override them.
