# N2 accounting clarification before any N2 execution

2026-09-23. The frozen protocol's phrase “Every dispatch and health check counts toward the unchanged global240 attempts/48GPUh” uses the original study's accounting units: every dispatched **episode attempt** consumes one of240; all GPU work, including health checks and interrupted/failed attempts, consumes the48 GPU-hour allowance. A health check without an episode is not fabricated as an episode attempt. Preserve the existing raw journal and counters.

The N2 local34-attempt allowance consists of30 unique scientific episode cells and at most4 infrastructure recovery attempts, at most one recovery per cell. Its18-hour local ceiling includes newly incurred N2 GPU work. If an existing CUDA/EGL proof is reused, report that resource and its prior cost separately; never charge it again to the global total. Admission always preserves the unchanged global validation/formal reservations. Reusing a valid exact-condition proof does not require another GPU probe solely to obtain a new resource ID.

This clarifies units before implementation/testing finishes, recorded Q8 results, or N2 dispatch. It changes no objective formula, task/seed mapping, retry eligibility, scientific gate, total study budget or previous outcome.
