# Post-N2 outer loop and Arbor ideation

Prepared before N3 implementation or N3 rescoring/online outcomes. Decision: PIVOT_WITHIN_QD_ED to a single, testable past-execution feedback mechanism from the original Q0 starting point. N2 remains rejected.

## Probe

1. First principles: imperfect prediction of executed motion is a candidate bottleneck class, not an established cause of task failure. All516 selected guided prefixes have exact recorded projection/action/response joins. Across the30 cells, mean endpoint L2 discrepancy ranges0.03072–0.12717m. In Q0 task0, fixed past-residual transport lowers next-prefix mean squared error from about0.0032702 to0.0018822m² over46 eligible pairs; task2 changes about0.0040120 to0.0006152m² over31. These within-episode pairs are dependent observations.
2. Hidden assumption: the fixed open-loop projection is already sufficient for useful quality ranking. Dropping that assumption opens a feedback-conditioned internal objective using only the immediately preceding, actually executed prefix.
3. Elephant: Q8 was active on131 guided chunks but achieved1/10, tying Q0 and below C0's2/10. Better proxy bookkeeping is not manipulation success. C0's fixed residual prediction worsens in8/10 episodes, and Q0 worsens in tasks1,3; no universal correction is established.
4. Hamming: yes, conditionally. QD/ED quality directs the permitted search and is a plausible place to test a deployment-available signal. Its task relevance still requires matched online evidence and the unchanged success gates.

## Four idea moves and filtering

- Assumption inversion: replace an exclusively open-loop quality view with a fixed previous-execution residual. Retain for one prospective experiment because the originally chosen Q0 starting point shows lower episode-mean prediction error in8/10 cases without fitting the rule.
- Backward from success: retaining productive action plans would need evidence of task progress and useful unexecuted continuation. That evidence is missing, so do not enable historical chunk-memory or a proposal-carry mechanism now.
- Analogical transfer: a fixed innovation term from feedback control can correct a geometric proxy without training a dynamics/scoring model. Its applicability is limited to complete adjacent execution under known unchanged identities; it is not a fitted controller.
- Failure-case reverse engineering: large observed projection errors and commands outside declared unit bounds also motivate actuator-realizability questions. Current installed controller defaults differ from the projection, but historical resolved bounds were not recorded. Do not add a clipping correction or change the projector in this candidate.

## Survivor declaration

Assumption challenged: immediately available executed feedback adds no useful information beyond the open-loop projection.

Mechanism class: verification/feedback used by QD quality and ED search ranking.

Mechanism/hypothesis chain: a fixed, identity-checked previous-prefix displacement residual may make Q0's internal geometry more useful for selecting actions; its value is falsified by inactive/native-inconsistent behavior or failure of the preregistered matched Dev gate. Lower retrospective prediction error alone cannot pass that gate.

Orthogonality: N2 changed the objective horizon; N3 restores the original seven-point provider horizon and changes only the internal geometric view using past execution. N1 changed archive representation and ended cohort-invalid; H3 carried plans/memory, while N3 retains no plan tail or archive population.

Conflicts: the adverse C0 results and Q0 tasks1,3 remain counterevidence. No task-specific enabling, gain fitting, clipping, longer history, additional model work or Stage change is permitted to hide them. Historical tracker validity was not logged, so retrospective numerical eligibility cannot certify future runtime applicability.

Self-check: the mechanism is a new feedback pathway and quality definition, not a scalar retuning, prompt edit, more-compute proposal or relabeling of an old invalid cohort. Implementation and data use are specified in protocol.md before execution.

Evidence: N2 full report SHA d376f98a0d0d23d7b73b0a20ab768594c63ed6a6abce9473e0e67d2247bc88ab; selected-tracking index SHA d0ed98c7b8dfd4c3c1fd1a584368b5b33a3ff91383dc0e6beb90d04f941fada7; selected-tracking provenance SHA b76e99c0d1985a93ce285c84f0068a04519f09973388082f7aac7aeba3395ba6. These are exposed Dev evidence, not independent validation.
