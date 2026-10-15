# Frozen EDS CPU golden preservation

Authoritative frozen behavior: `final-reference/behavior.json.gz`.
Candidate-running integration package: `portable/tests/`.
Frozen source generation evidence: `frozen_source/` and `source-provenance.json`.

No repository file, model asset, current cohort or shared environment was changed.
No phase4 getter/interface implementation is included. This captures deterministic
CPU reference behavior of commit `cfecb12db736f1a3408d9528d9336aadcb7e41b5`.

## What is preserved

The 23-file source closure is byte-identical to the corresponding current frozen
root files. A first capture executed that closure; a separate process then loaded
the current root and matched every recorded behavior field. Final packaged tests
also load the current root, not the frozen closure, and pass against the recorded
reference. The frozen code is retained only for independent generation provenance;
it is not a dependency or proposed tracked fixture for new-clone regression.

Both float32 and bfloat16 execute real EDS B16/10 iterations with real initial and
truncated RBF, H8, QD off, real DPMSolver scheduler and action/observation processing.
The actual online Stage/controller/handoff/reference/action-passthrough code runs;
Main Stage dispatch and the adapter trajectory projection are AST-loaded original
methods to avoid importing GPU/simulator/provider entrypoints. Expensive model,
encoders, environment sensors and provider are deterministic synthetic substitutes.

Per dtype the transcript contains176 actions /22 chunks /10 guided chunks,100
parent batches,110 search scoring batches and160 actual scoring batches with
enabled diagnostics (2560 policy reward calls). Every parent tensor matches the
actual subsequent renoise input; score values, dtypes, selected latent/actions,
RNG, counters, marker hashes, query/reset/gate events and cached actions are saved.

The actual progress score triggers grace at16; it expires at80. A synthetic held
observation causes Stage2 at96, and outside/not-held causes Stage1 at128. Guidance
toggles preserve the real reference; Stage transitions and a second episode reset
exercise the real reset methods. Both gripper signs and raw/executed equality are
covered. Stage probes and cached-action calls are asserted not to consume CPU RNG.

See the fixture README for exact exclusions. This is a controlled CPU regression,
not full Main simulation, provider transport, production RNG-hook replay, GPU
parity, model validation or an online performance result. Future full10 gate and
phase4 implementation remain separate.

## Portable package and verification

Proposed tracked files are only:

- `tests/steering_eds_golden.py` (candidate-running harness).
- `tests/test_steering_eds_parity.py`.
- `tests/fixtures/steering_eds_golden/{behavior.json.gz,capture-report.json,source-provenance.json,README.md}`.

There is no copied reference runtime in this package, no absolute test source path,
no dependence on prior runs/worktrees, and no missing-path skip. The test launches
the current clone in a fresh subprocess. Each scenario independently restores
Python/NumPy/Torch CPU RNG in `finally`; subprocess isolation also contains imports
and CPU thread settings. Socket and child-process operations are blocked inside
the harness, CUDA is hidden and checked uninitialized. Equality has no wall-clock
latencies/timestamps or run paths; PNG content hashes are retained.

Final actual test: **3 passed in20.65s**. It checks artifact SHA/portability, executes
the current root and compares all recorded values, and proves a modified expected
action is rejected with exit1 and a precise nested-field mismatch. The full log
and exact staging command are in `validation.json` / `pytest.log`.

From an eventual clone after copying the proposed test files:

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 \
  python -m pytest tests/test_steering_eds_parity.py -q -p no:cacheprovider
```

The temporary `STEERING_GOLDEN_SOURCE_ROOT` override lets the staged test target a
current clone before integration; it is not needed once tests reside in that clone.
The tested runtime used Torch2.7.1+cu126, NumPy2.2.6, Diffusers0.35.2, Pillow12.2.0,
PyYAML6.0.3 and OpenCV4.12.0/headless4.12.0.88. Actual imported versions and stale
distribution metadata are recorded separately. Reproduction across other CPU or
library builds is not claimed; investigate numerical drift instead of replacing
the reference silently.

Earlier development artifacts remain for transparency: `attempt-01` omitted Main's
diagnostic configuration and is superseded. The incomplete `baseline` directory
came from an overly narrow harness assertion of110 total score batches; enabling
the frozen diagnostics correctly produces160. This was a harness-accounting fix,
not a runtime change. `golden`/`current-root-verification` then matched before the
final packaging-only removal of output-path equality and explicit RNG restoration.
Only `final-reference` and the portable fixture define the final reference.
