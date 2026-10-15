# N33 prospective observed-state capture proposal: CPU feasibility only

PROBE BLOCK
Q1 First principles: wrong stopping/timing representation. Turn510 task4 e0:d79:s624 selects and executes a proposal whose predicted arrival is 8.1cm from the fixed tracked target in actual EEF coordinates; turn511 six selected prefixes faithfully execute parent translations yet have 1.743–8.228cm projection residuals. This is not proof of target location or grasp.
Q2 Hidden assumption: a future point projected from action sums is a reliable time to stop translation and start closure. Dropping it permits a proposal conditioned only on current, contemporaneous observed hand/target geometry.
Q3 Elephant: the current tracked keypoint is not a verified grasp point; chunk-boundary observations can miss brief encounters, and ordinary quality scoring can reject even a physically useful proposal. None is solved by proposal activity alone.
Q4 Hamming: yes, coordinating closure with actual hand position addresses an execution bottleneck, but low trigger reachability would falsify this implementation before spending a new cohort.

Four moves considered:
- Assumption inversion: current-observation capture-dwell proposal, with no predicted future arrival. Selected for bounded CPU reachability investigation.
- Backward from success: explicit grasp/contact state observer. Deferred: authorized production observations do not establish contact or object pose, and adding privileged signals would change the input contract.
- Analogical transfer: online identified action-to-motion predictor. Deferred: N3 residual-feedback and N23/N25 clipping lessons warn that a fitted displacement correction is not validated capture timing; needs a separate uncertainty protocol.
- Failure-case reverse engineering: shorten execution adaptively and check proximity every action. Deferred: changes inference frequency, executor behavior and matched compute; not an isolated proposal test.

Survivor scratch declaration:
1. Assumption challenged: predicted prefix entry can stand in for observed present proximity.
2. Mechanism class: observation-conditioned proposal generation inside QD/ED.
3. Chain: a close-and-dwell competitor generated only when the currently observed EEF/hand frame contains the current recognized tracked keypoint may avoid predicted-arrival errors, because it does not extrapolate action sums. Evidence requires fresh matched dev task gains plus native selection/execution audits; trigger counts are feasibility only.
4. Orthogonality: N31 schedules a future entry from current-best parent; N32 retrieves any eligible projected-entry parent. N33 uses current observed entry, takes the ordinary current archive best, and constructs immediate close/dwell. It does not preserve a previous trajectory (N30), reshape geometric reward (N3/N23), clip RBF updates (N25), or force retained close commands (N24).
5. Conflicts: N31/N32 demonstrate that proposal selection is insufficient; N33 specifically removes future arrival extrapolation but does not claim capture or efficacy. N3 failed a previous-chunk displacement residual; this uses no learned/residual projection. N23/N25 failures rule out presenting clipping or scale substitution as the solution. The reachability failure of tree9.2 requires screening the exact trigger before implementation.

Self-check: not a numeric threshold change, prompt change, scaling request, or rerun. Concrete representation/control-flow change; counter to prior lessons stated. No effectiveness claim.

CPU scope before executor implementation:
Use only already exposed N32 logical-cohort development canonical context/native observation records, with exact identities and hashes. Evaluate the unchanged literal N31 hand prism at current observed EEF, quaternion and jaw state, against that decision's recognized tracked target. No projected positions, future observations, simulator ground truth, protected splits, new provider calls or GPU dispatch. Report total contexts, missing/malformed observations, recognized targets, nonempty jaw intervals, exact current-entry hits by task and decision, and possible native-byte proposal changes. Missing data is Unknown; never substitute predicted positions. Inspect availability before tensor reads and retain full denominator. If zero admissible changed opportunities, close this candidate as unreachable on exposed evidence; do not expand prism or search thresholds. Positive opportunity counts license CPU implementation review only, not GPU or scientific promotion.

Proposed method pending that check: one last-offspring-slot competitor from ordinary current archive best, immediate close and zero pose commands for first eight actions, preserving suffix/native dtype; unchanged canonical quality, archive retention and ED selection. Preserve no-op behavior when trigger false. Precise source/protocol/native-audit contracts must be frozen in an isolated executor worktree before any prospective development release. No historical score pooling; original validation/formal/ablation gates unchanged.
