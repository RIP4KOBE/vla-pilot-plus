# Optional N25 native witness, proposal only

No tensor capture is implemented in this CPU phase. Existing new-mode telemetry is scalar/shape/dtype/count evidence, not exact CUDA replay proof. The same-call original projector is used once per candidate with an RBF-only clipped input; its origin acquisition count and order stay unchanged.

If root later authorizes exact capture, bound it to the first guided decision of each episode: the first active initial call plus the first active call of each of ten rollout iterations, at most11 calls. Do not choose calls based on saturation, reward, outcome or gradient size. Missing scheduled calls remain explicit, without replacement.

For each chosen call retain native-dtype first8 xyz (16×8×3), same-call pre-cast origins and cast origins (16×3 each), projected xyz (16×8×3), pre-normalization xyz gradient, normalized xyz gradient, scaled masked xyz update, and translation-only model output before/after addition. Preserve tensor dtype/shape/stride, device/UUID, scheduler timestep, phase/iteration, decision/reset/attempt identity, source hashes and actual normalization scalar. Nontranslation invariance is independently enforced and checked in CPU tests; no full64×128 latent dump. Budget at most20KiB numeric payload/call plus bounded identity metadata, <=220KiB numeric payload/episode. This is a proposed cap, subject to exact serialization-size review.

Capture must tap existing arithmetic outputs and the same projector origin; no second projection/gradient/model/provider/simulator or shadow inference. CPU replay alone cannot certify CUDA reduction; any future backend verification must be separately reviewed, metered and same-worker. Exact capture is NOT authorized by this proposal. No additional native input was read to create it.
