# N30 compute interpretation clarification

This clarifies the frozen protocol's primary/canonical search budget; it does not change the algorithm or authorize execution.

Accepted N29-cohort actual compute records show C0 and Q0 have256 total provider reward evaluations /16 total scoring batches per guided decision, including existing auxiliary calls. Their primary canonical search remains176 candidate evaluations /11 canonical batches. Q0 has19 existing RBF gradient calls per guided decision. The sampled complete Q0/C0 episodes also reconcile to21 model forwards x16 rows per guided decision and5 model forwards x1 row per unguided decision. These are observed accounting values, to verify against source and any implemented-path tests rather than hard-code as universal truths.

N30 is Q0-derived. It must add zero model, denoise, provider-score or RNG work to the corresponding Q0 guided path; current original auxiliary calls remain and must be reported. It must not claim11 TOTAL score batches or176 TOTAL provider evaluations. N28/N29 use different auxiliary/RBF counts and are not the N30 compute-matched parent.

Evidence: closed-task-relevance-20261004-v1/result-v1.json rows for accepted C0/Q0 episodes. Example task0 Q0:52guided/38unguided,13312reward evaluations/832scoring batches,988RBF calls,1282model forwards/17662model rows. Task0C0:29guided/61unguided,7424reward evaluations/464batches,551RBF calls,914model forwards/10049model rows. Both satisfy the counts above.

Whole-episode compute can still differ because guidance occupancy and episode length may change; do not describe equal total episode work from equal per-guided-decision contracts. Keep original telemetry, actual GPUprocess-wall accounting and Stage costs.

