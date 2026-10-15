# EDS CPU golden fixture

This is synthetic offline reference behavior of the frozen source commit identified
in `source-provenance.json`. It is **not a robot experiment, replay of online replies,
or success-rate result**. No model weight or simulator asset is included.

`behavior.json.gz` contains the compressed exact transcript. `capture-report.json`
records its compressed/uncompressed SHA-256, actual imported versions (separate
from potentially stale distribution metadata), source hashes, and coverage checks.
The original source closure is retained separately as experiment evidence; it is
not required to run the candidate regression and should not be copied into tests.

The adjacent candidate harness loads the current repository from an explicit root.
It runs real RDT EDS, real Diffusers DPMSolver scheduler, real observation/action
conversion and cache, real online Stage/probe/contact/grasp/carry/recovery logic,
real action passthrough, and the exact source methods for Main's Stage dispatcher
and the adapter's linear trajectory projection (AST-loaded without heavy imports).

The DiT/encoder outputs, environment sensors, camera, tracked keypoints and provider
replies are deterministic synthetic fixtures. At each eight-step boundary the fake
environment positions the hand at a fixed sensor anchor; between boundaries it
integrates executed actions. This deliberately covers progress/contact branches
and is not a physics prediction or claim of realistic task progress. The actual
reward computation uses the unchanged target-distance reference formula.

Per dtype (float32 and bfloat16):

- Two synthetic episodes, 160+16 actions; 22 chunks, 10 guided and 12 unguided.
- Real EDS B16 / 10 iterations / initial and rollout RBF / H8 / QD off.
- 100 batches of actual parent indices, plus fingerprints of the parent latent
  tensor and the actual renoise input; these are asserted equal for every batch.
- 110 search-score batches, 160 actual batches including the enabled mechanism
  diagnostics, and 2560 actual policy reward calls. All scored trajectories use p1..p7.
- Contact grace begins at step16 and ends at80; stage2 at96, stage1 recovery at128;
  guidance toggle reference preservation, stage reference reset and episode reset.
- Raw/executed action equality, both gripper signs, eight cached actions per chunk,
  cache countdown, selected latent/action fingerprints, scalar rewards/references,
  query events, reset events, counters and Python/NumPy/Torch CPU RNG hashes.

The harness restores all three CPU RNG states in `finally`, blocks socket/process
calls, hides CUDA and asserts it was not initialized. Pytest launches it in a fresh
subprocess to isolate imports and CPU thread settings. Model/encoder forward work
is synthetic; those zero encoder counters do not describe production inference.

Golden equality excludes elapsed time/latency and output paths. PNG content hashes
remain, so target-marker behavior is observable. Rendering/video encoding, full
Main episode lifecycle, environment processor internals, production initialization
fixture hooks, real provider transport, model weights and GPU kernels are outside
this harness. The runtime also runs contract checks during preparation; this
harness exercises Stage score capability probes but does not emulate fresh online
reward generation or its complete preparation audit.

Exact numeric equality is evidence for the controlled CPU paths and captured
library versions. It is not a guarantee across different CPU/library builds, GPU
execution, or fresh provider responses. A mismatch must be diagnosed; do not relax
the golden comparison or regenerate its reference merely to make a test pass.

After these files are integrated into `tests/`, run from any current clone:

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 \
  python -m pytest tests/test_steering_eds_parity.py -q -p no:cacheprovider
```

Required CPU packages are the validated torch/numpy/diffusers/Pillow/PyYAML/OpenCV
versions recorded in the report, plus pytest. No old worktree, model directory,
stored 720-step episode, GPU, service login, or missing-path skip is required.
