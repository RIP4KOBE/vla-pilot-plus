# N29 native arithmetic specification v1 — Phase A only

Frozen hypothesis: population-relative cap of the existing raw diversity proposal,
then the unchanged N27 feasible ray. Base52b9eb0. No policy/config/runner/auditor wiring.
The global normalized-gradient scale20, N28 placement,14 calls, QD/ED contracts and
all model/score calls are outside this pure-helper change and remain untouched.

Inputs B,P: matching CPU/CUDA strided native FP32/BF1616×8×3. Reject wrong shape,
dtype/device/nonfinite. Before any scaling, reject raw P!=0 where B is not strictly
inside(-1,1). This ensures beta0 cannot hide a support violation. No input mutation,
RNG, persistent state, parameter, target/task branch, model or score call.

Exact operation order (all reductions are FP32, no autocast/norm/std substitution):
1. b=B.detach().to(float32).reshape(16,24), p analogous.
2. mu=b.mean(dim=0); centered=b-mu; square=centered*centered;
   row_energy=square.sum(dim=1); mean_energy=row_energy.mean(); s=mean_energy.sqrt().
3. p_square=p*p; p_energy=p_square.sum(dim=1); n=p_energy.sqrt().
4. denominator=where(n>0,n,ones_like(n)); ratio=s/denominator;
   beta=where(n>0,clamp(ratio,max=1),ones_like(n)).
5. scaled_fp32=p*beta[:,None]; U=scaled_fp32.reshape(16,8,3).to(B.dtype).
6. feasible_ray_update(B,U) exactly once. Return its prefix/alpha and beta/s/n/U.

Check finite inputs and every stated intermediate; overflow/nonfinite including
ratio overflow fails closed. Prospectively confirmed finite-precision domain gates:
if centered has any nonzero FP32 value yet s==0, reject spread underflow; if a raw
row has nonzero p yet n==0, reject norm underflow. No epsilon, scaled norm rewrite,
backup scale or silently retained tiny raw operand. These gates can create a future
runtime failure; they are not observed scientific failure evidence. They preserve
literal arithmetic rather than pretending representational underflow is true zero.

True centered-zero population gives s=0; nonzero-n rows get beta0 and zero U;
zero-P rows get beta1. Casting U may round or underflow individual coordinates.
The unchanged feasible ray preserves original B bytes wherever U==0, including
signed zero/exterior stationary coordinates; only moving strict-interior coordinates
receive its native box correction. No claim of exact-real post-cast norm<=s: BF16
round-up may exceed that real bound (a focused counterexample is tested). Record
actual ratios in a future native audit, not a tolerance-based invented guarantee.
No CUDA parity has been tested in this phase. CPU layout checks are not GPU proof.

Scientific critique: the data-dependent per-row distance cap addresses observed
update/spread imbalance and differs from global-scale sweeps, N27 box-only alpha,
and N28 operator relocation. But duplicates shrink spread, outliers enlarge it,
zero spread suppresses exploration, and one shared radius conflates meaningful and
irrelevant variation. Empirical spread is neither model uncertainty nor prior mass.
The diagnosed88 first-active slots are not all calls, independent tasks or a causal
model-transport experiment. N27 task2 success remains counterevidence to universal
magnitude harm. Smaller ratios/boundary pressure are descriptive predictions, not
success or admission criteria. The coefficient1 is prospective and unoptimized;
matched task evaluation is still necessary. No projection, Stage/perception/executor
change, runtime fallback, new budget, protected read or GPU release follows here.

Tests use hand-solvable powers-of-two populations, independent Python fsum/sqrt
reference in that exact domain, native-bit inactive-cap parity against old ray,
zero/signed-zero, raw support, duplicates, finite/underflow domains, model-sliced
and transposed layouts, CPU RNG/autograd/input immutability and BF16 rounding.
Full tensor tail/config/worker routing remain future integration work, not claimed.

Root clarifications: native-input-domain-clarification-v1.md and existing-adaptive-controller-overlap-v1.md (N29 variant root). The repository already contains a reference-band/reward-confidence/iteration-decay adaptive rollout controller, inactive in the frozen N28 profile; N29 does not invoke it and is not the repository's first adaptive mechanism. A concentrated but wrong OOD population can make this bound suppress necessary exploration. Smaller updates or fewer boundary coordinates are never efficacy gates.

Bound root input SHA256 values:
- hypothesis-and-cpu-phase-a-v1.md: ae3bd67079501da29369d9b5235f6abfec4413eca2fcfe0a090cd63759771e9b
- native-input-domain-clarification-v1.md: 581ea6df968fe2aab63f9f3b68ffe7f46d8996a0c65ebc7a6838631d2ad3b86b
- existing-adaptive-controller-overlap-v1.md: f4e881184ef66f0e3b74a2fba4fc1909cee1a9490c40c7a97d8591a70482ae5a
