# N26 conditional CPU implementation

Only the input of the existing initial and rollout diversity calculation changes.
`diversity_input_source=noisy_sample` is the default; `model_output_sample_v1`
requires both clipped RBF modes and the actual active scheduler's config to say
`prediction_type=sample`. Missing, epsilon and v-prediction configs fail before
the first forward and are checked again at each active call. The profile does
not supply or override this runtime assertion. Population caches remain off.

The caller passes the identical output object returned by its one existing
no-grad forward, preserving shape, dtype, device, stride and storage offset.
The shared N25 function creates its independent detached leaf. There is no
model Jacobian, extra forward, altered scheduler history, alpha/sigma weighting
or change to the original negative masked scale20 update. The same native
per-row projector/origin operation runs once per candidate per RBF call.
N25's mathematical helper and all quality, descriptor, decoder, selection and
parent-rescue implementations remain unchanged. N24 rescue stays off.

`CleanOutputWitness` specializes only metadata plus a strict input binding.
It uses `n26-rbf-call-summary-v1`, `n26-bounded-rbf-witness-v1`,
`n26_rbf_witness`, and `n26_rbf_witness_coverage`. The source is
`core.qd_clean_output_rbf:model_output_sample_v1`. Every scalar row binds
`input_source=model_output_sample_v1`, `prediction_type=sample`,
`input_binding=same_forward_unmodified_model_output`, and
`model_jacobian_used=false`.

The witness requires identical dtype/device/shape and identical uint8 bytes
between `input_xyz` and `model_output_before`, including signed zero. Both are
the existing first8 translation slice; no full action tensor is serialized.
Capture remains first guided decision, first active initial call and first
active call per ten rollout iterations, with no backfill. Inherited caps are
11 calls, 20 KiB numeric/call, 220 KiB/episode and 16 KiB metadata/call. Episode
reset resets the selector. `update_operand` is the intended operand, while
`model_output_before/after` observe the actual original in-place addition;
operand norm must not be described as measured rounded output-delta norm.
Zero gradients, coincident paths and complete saturation remain valid.

Tests use only toy tensors/models and source-extracted pure projection code.
An independent where-based derivative and cumulative projection expression
checks CPU byte equality. Layouts include contiguous, transpose-backed, and
model-like `(16,67,128)[:, -64:]` (stride8576/128/1, offset384). This last
layout is a static source-informed fixture, not an observation of live N25.

No runner/profile expansion, native auditor, controller, backend dispatch,
online plan, release, budget or protected-evaluation change is included.
The old N25 arithmetic proof does not establish N26 input wiring on CUDA.
Future release requires independently reviewed native arithmetic and
same-forward binding, including new profile-bound schema enforcement,
prospective cohort/budget/resource gates, and N25 terminal disposition.
CPU tests establish no task success, physical accuracy or timing improvement.
