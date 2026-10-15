# Root N29 integration review notes v1 — interim, not source acceptance

Reviewed evolving CPU Phase B source against Phase A and N28 base52b9eb0. These notes do not freeze source or authorize any experiment.

- Opt-in policy routing currently applies the frozen population-relative helper to initial4 and selected-parent10 calls; QD/ED/model/score/executor/Stage contracts remain the prior ones. Shared-file changes are limited to policy and metered runner/worker routing. Final committed diff and tests still need review.
- The old native byte comparator cannot safely compare a zero-dimensional FP32 radius by directly viewing it as uint8. N29 now has a shape/dtype-aware flattened byte comparator; final scalar serialization/tamper evidence must pass. Old comparator/control sources are unchanged.
- Generic check_budget can shorten an1800s timeout before N29's protected_budget checks. Root identified that a near-exhausted global/protected budget could therefore be mislabeled engineering invalidity. N29 must reject an insufficient whole1840s before reservation through its own resource-incomplete path and preserve generic floor/grace semantics. A direct real check_budget routing test is required.
- Initial and parent witnesses must bind raw proposal, native scaled operand, beta, radius, row norms and actual assigned prefix. Old alpha only represents the final box ray. Both beta/alpha activation remain descriptive; neither can promote a scientifically failing candidate.
- Interim24-case native proof preparation includes production parent-wrapper/RBF/assignment/boundary plus fixed helper-domain cases. This is code only; no native GPU proof has run.
- Original Dev identities were independently reconstructed into root-original-dev-identity-preview-v1.json from N23's immutable40-row Dev-only plan. C0/Q0/N28/N29 share task/seed/init/scenario identity for tasks0..9; historical outcomes are not inherited.
- First Phase B test run:60 passed,1 missing synthetic reader fixture failure,5 owned-utils dependency guard errors. Entire run is not accepted. CUDA remained uninitialized. Agent reports49.16146961 cumulative accounted CPU seconds. Repairs and affected tests remain in progress; original logs retained.
- Source/runtime/provider/budget execution gates remain closed. Root independently confirmed official CLI ChatGPT login without reading credentials; no Poe/account/key fallback, stored Poe credentials preserved. Live GPU7 metadata showed no compute process at preparation time; admission must be checked again near actual launch.


- Phase B run2 exposed a real integration defect: production _EDSConfig is a frozen dataclass, so assigning to a shallow copy during validation raises FrozenInstanceError. The agent replaced it with a detached SimpleNamespace validation proxy, leaving original configuration and Phase A arithmetic unchanged. Run2 retained5 failures/9passes and owned-utils source denials; affected full-loop/native/config tests are being repeated.
