# User-authorized GPU5 resource amendment

The user explicitly instructs “改用5” on2026-09-22. For subsequent execution in this research task, physicalGPU5 replaces physicalGPU7 as the sole authorized local GPU. Keep one exclusive worker; do not share, preempt or terminate external processes or substitute any other device.

This changes resource binding only. Q0/P2/N1 retain the same algorithms, Codex login/provider policy, model and encoder weights, input images, prompts, frozen seeds/init rows, action and success contracts,720-step limit,1800-second timeout, and preregistered search costs and promotion gates. All thirty N1-round cells must use the same newly frozen source/runtime. No N1-round episode has been dispatched before this amendment.

Historical/restored profile metadata still contains its original `p2_render_gpu_index` and hardware provenance. These fields are not consumed by the owned command builder or current main/core rendering path. The effective CUDA mask and MuJoCo EGL selection come from the new runtime mapping; full resolved commands and public child environment must record GPU5 and its separately verified EGL index.

Freeze GPU5 UUID/PCI identity, enumerate its EGL association, and verify actual CUDA logical0 and EGL rendering under the GPU5-only mask with an accounted zero-step healthcheck. Do not reuse GPU7's context verification as evidence for GPU5. Bind admission, concurrent-process monitoring, child environment, manifest and journal physical-device fields to the same authorized device; reject state/runtime disagreement.

Preserve all prior GPU7 plans, manifests, healthchecks and the first invalid baseline attempt, including all costs. New hardware-specific files have new paths and hashes. The original baseline remains closed incomplete; N1's predeclared complete Q0/P2 controls run first and must all be valid before candidate dispatch. This is not a retry of the invalid original baseline sample.

Total budget remains240 dispatched attempts and48 GPU-hours across both earlierGPU7 work and subsequentGPU5 work. Healthchecks and startup failures count. Protected validation/formal reservations and the N1≤30 development allowance remain unchanged. No new seed block, outcome replacement, automatic retry or scientific threshold relaxation follows from this hardware change.
