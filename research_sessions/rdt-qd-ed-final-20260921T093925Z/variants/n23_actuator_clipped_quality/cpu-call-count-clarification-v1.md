# N23 CPU protocol clarification: invocation count versus archive population size

The original `protocol-cpu-v1.md` is unchanged (SHA256 `e38d4c6825cca743539282818e8b49168c1910cf688720bd1901b7405ab8cf67`). This note records evidence found while checking its unchanged external-call requirement; it does not release an experiment or change an algorithm.

The N7 and N23 native CPU fixtures both perform exactly 347 population-projector invocations at the same seven existing caller sites. The canonical scorer accounts for 11 invocations / 176 candidate projections; no N23 quality caller invokes the external projector. Both use 176 provider returns, 16 stub-model forward calls / 256 model rows, and 25 visualization decoder calls. Per-caller counts and unchanged-domain row counts are in `cpu-native-final-v1/test_n23_full_native_cpu_loop_{0,1}/compute-comparison.json`.

The existing `_eds_target_distance` diagnostic projects the current archive-reference population after final selection. Its two invocations (one initial population and one final occupied archive) are unchanged, but the archive occupancy is a result of the search. In FP32, those invocations process 29 rows for N7 and 28 for N23, producing global per-candidate adapter projection counts of 1949 and 1948 respectively. BF16 has 29 rows and 1949 total for both. All other caller row counts match. Neither diagnostic nor work has been padded or removed.

Therefore, identical counts are established for canonical scoring, external provider/model/decoder work and population projection invocations. Identical **global candidate projection rows** are not a valid claim. The existing archive-dependent diagnostic work belongs in full episode costs. The new internal tensor projection/check is additional quality arithmetic, explicitly timed and bounded separately; it does not constitute a new call to the external adapter projector.

The initial assertion of equal global adapter-row counts failed on FP32; `cpu-native-third-v1.log` and its native fixtures retain this failure. Its replacement checks caller identities and invocation counts individually, asserts equality of all fixed-domain row counts, bounds both archive diagnostics to the unchanged 16-cell domain, and records the variable global counts.

No CPU fixture establishes CUDA bitwise parity. The independent, read-only replay in `cpu-gpu-boundary-readonly-v1.json` found real BF16 backend differences; the strict CPU auditor is not cleared for GPU-native release.
