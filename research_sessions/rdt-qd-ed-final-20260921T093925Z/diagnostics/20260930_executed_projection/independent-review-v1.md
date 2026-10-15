# Independent review of the executed-projection audit

Verdict: **PASS as a bounded descriptive audit, with a controller-origin measurement qualification and unresolved historical controller-configuration provenance.** The evidence justifies a separately specified saved-candidate activity screen. It does not justify claiming improved task success, exact historical controller clipping, or a calibrated forward model. No candidate implementation or freeze is recommended by this review alone; N22 remains unchanged and retains execution priority.

I independently reread only the three permitted native-valid exposed paths, the named audit artifacts, referenced static/controller code, and existing N2/N3 protocol/summary documentation. I did not invoke a GPU, simulator, provider service or test, and did not modify any study/implementation source, state, budget, ledger or tree. The only outputs are this review and `independent-review-v1.json`. The original protocol, reader and result JSON are unchanged.

## Native association and arithmetic

I checked all6139 referenced bundle hashes, bundle/index event metadata and contiguous event sequences, accepted native-audit hashes, and source result validity. The complete audit comprises89 +65 +89 =243 paired chunks, including17 +4 +16 =37 guided chunks. The sole excluded context in each path is the last unpaired context: global steps712,520,712 respectively.

For every included pair I independently confirmed:

- The first source origin occurs after its decision context and **before the first action dispatch**, a stricter boundary than the reader's before-first-sent-action test. All preexecution source origins within that decision are exactly equal.
- The eight dispatches, sent actions, pre-reset outcomes and returns have the correct per-step order and contiguous global steps; every return is nonterminal and nontruncated. There is no reset boundary, and the next context has the same episode/reset identity at current step+8.
- The next source origin is recorded after the eighth return and after the next context, before its first dispatch.
- The eight postprocessor/sent actions exactly equal the policy-decoded and committed eight-action chunk. This proves the commands supplied to the environment; it does not by itself observe the controller's internally clipped/scaled command.
- For all37 guided pairs, the selected latent matches the indexed terminal scoring candidate and the policy decode; its scoring-origin sequence resolves to the same source origin used by this audit. The stored native endpoint therefore belongs to the actually selected candidate.
- The per-step componentwise clipping, sums, endpoint-error norms and reported count/mean/median/min/max values reproduce within1e-14m. The reader correctly uses sum(clip(each command)), not clip(sum(commands)). No scale, gain or threshold was fitted.

The two historical committed adapter files (`5a268455...` for N17 and `23dba929...` for N21) are byte-identical to the currently fingerprinted adapter, including the0.01 translation proxy, executed-action hook and controller-origin accessor. Thus the relevant tracked adapter lineage is verified, rather than inferred solely from current source.

## Qualification: cached controller origin is not the exact returned observation

`get_ee_pose_world()` calls `get_ee_pose()`, which returns `controller.ee_pos.copy()`. The next controller-origin value is not bitwise identical to the eighth `pre_reset_outcome.observation.robot0_eef_pos`:

| Path | Maximum next-origin versus eighth returned EEF difference |
|---|---:|
| N17/N7 task0 | 0.803mm |
| N17/N7 task9 | 0.552mm |
| N21 task0 | 0.745mm |

The preregistered calculation is therefore most precisely described as **error against displacement between two preexecution controller origins**. Its `actual_displacement_m` field should be interpreted with that definition; it is not an exact N3-style acknowledged p8 measurement. This is a small distinction relative to the observed centimetre-scale effects, but it matters for any later feedback lifecycle or calibration claim.

At the coordinator's request I performed an explicitly supplemental calculation on the same243 permitted pairs, retaining the original forecast and decision-start origin but replacing only the endpoint target with the already recorded eighth pre-reset EEF:

`error = norm(start_controller_origin + forecast_displacement - recorded_p8)`.

This neither modifies nor supersedes the frozen next-origin analysis. Guided mean errors are:

| Path | Original raw0.01 → clipped0.01 | Supplemental exact-p8 raw0.01 → clipped0.01 | Exact-p8 clipped0.05 |
|---|---:|---:|---:|
| N17/N7 task0 | 5.591 →3.353cm | 5.604 →3.349cm | 37.132cm |
| N17/N7 task9 | 7.656 →2.729cm | 7.690 →2.704cm | 40.354cm |
| N21 task0 | 6.143 →2.973cm | 6.168 →2.971cm | 41.565cm |

The direction counts remain **29 better /2 worse /6 equal** in both definitions. The adverse cases must remain visible:

- N17/N7 task0 step24: original error2.312→2.404cm, worse by0.093cm; exact-p8 error2.329→2.407cm, worse by0.078cm.
- N21 task0 step176: original error1.852→3.448cm, worse by1.596cm; exact-p8 error1.844→3.410cm, worse by1.566cm.

The316 translation components outside[-1,1] are all in guided paired chunks (121/48/147). None occur in the206 paired unguided chunks; raw and clipped forecasts consequently coincide there. These are component counts from selected trajectories, not316 independent trials, and they do not estimate the frequency among all unselected candidates. Native stored projection versus float64 raw0.01 endpoint-error differences are at most1.532mm in these paths; native rounding is visible but much smaller than the aggregate clipping lead. The unchanged1–3cm residual errors also show that clipping is not a complete dynamics model.

## Controller semantics and provenance limits

The installed `base_controller.scale_action` clips each controller input between its actual `input_min/input_max` and applies an affine output scaling. Installed OSC pose defaults use[-1,1] input and±0.05m translation output. `OSC.set_goal` builds a target relative to the controller's current EEF state; it does not promise that the realized EEF reaches that target in a policy step. Tracking lag, robot dynamics, orientation commands, workspace constraints and contact can all invalidate direct target-increment integration. The0.05 forecast's much larger error rejects that particular naive endpoint predictor on these paths; it does not establish that the controller config is incorrect or that0.01 is universally calibrated.

The historical **resolved controller instance** bounds, delta/absolute mode, output scale and relevant overrides were not captured in these traces. Current installed JSON/source hashes establish today's inspected defaults, not the exact instance configuration at each historical run. The tracked adapter lineage does not close that gap. Accordingly, prefer “out-of-unit-range commands” or “clipping under the installed/default bounds” over an unqualified statement that316 effective historical clipping events were observed. Before a prospective clipping-aware method, bind/check the actual applicable controller metadata at environment construction, without changing actions or reading privileged environment state.

The original standalone reader relies on the pre-existing accepted native audit for some lifecycle/identity guarantees: it does not itself explicitly test every return's termination/truncation flags, every dispatch/outcome order, or the selected latent's same-call association. All those properties held in this independent reread, so they do not invalidate the current result. They should become explicit reader assertions if this analysis is reused more broadly.

For reproducibility, the original result fingerprints source code/config and each bundle but does not list its own reader executable hash or the attempt-result/events-index hashes. This review records those hashes for the independently inspected state. That strengthens current reproducibility; it does not retroactively certify an unrecorded original reader version. Do not overwrite the original result to add this information.

There are only three deliberately exposed, strongly correlated trajectories, with just four guided pairs in successful task9. Guidance use, states and policy distributions differ from unguided chunks. “All out-of-range components were guided” is descriptive evidence, not proof that guidance caused the error or that clipping will cause better grasp/placement success. The final success transition of task9 is unpaired and was excluded. No object transport, true grasp state or unexecuted candidate outcome is measured here.

## Relationship to N2 and N3

The existing preregistrations and iteration ledger distinguish these mechanisms:

| Direction | What it changed | What the old result establishes |
|---|---|---|
| N2 full-prefix quality | Recognized weighted squared target-distance objective over uncorrected x1..x8, with its8-point fractional weighting, while external provider remains on x1..x7 | Completed Dev: N2 1/10, Q0 1/10, C0 2/10; no demonstrated benefit from that extension |
| N3 previous-residual quality | One previous selected, fully acknowledged8-action residual transported with a fixed i/8 ramp into the next candidate's original7-point internal view; strict lifecycle/target identity | Completed Dev: N3 0/10, Q0 1/10, C0 3/10, despite extensive activity and improved retrospective prediction metrics |
| Prospective command-dependent clipping view | Deterministic transformation of each current candidate's own command components using bound controller semantics; no previous-chunk residual | Not tested online; this audit only motivates an activity/semantic screen |

N2 is more than appending one scalar point: changing to8 points also changes the fractional weighting cutoff. N3 explicitly prohibited actuator-bound correction and required actual acknowledged p8 rather than the next cached controller origin. Thus neither failure is a direct test of clipping-aware internal quality. Nevertheless, N3 is a particularly strong warning: lower retrospective prediction error and many ranking changes did not produce task success. Neither a new endpoint-error improvement nor a nonzero saved-pool ranking witness should be treated as an efficacy gate substitute.

Sources: `study_worktree/experiments/iteration_002_executed_quality/protocol.md`, `iteration_003_executed_feedback/protocol.md`, and `study_worktree/docs/03_evidence/qd_ed_final/iteration-ledger.md` N2 closure at line542, N3 closure at line639 and retrospective diagnostic at line654. I used these existing documents, not additional native outcomes.

## Is a saved-pool screen justified?

**Yes, as a bounded falsification/activity screen after a separate prospective definition, not as candidate promotion.** The clipping lead survives the exact-p8 sensitivity check, occurs in native-valid N7/N21 records, and concerns a current-candidate property. Before any screen, choose and freeze one consumer and one mathematical definition: internal quality, QD descriptor geometry, or existing lift-contact geometry. Changing all of them together would obscure what is being tested.

The screen should cover all preregistered eligible canonical batches in the same permitted paths and retain unsupported/unknown semantics, tied maxima, adverse cases and no-effect results. Decode each candidate with the exact deployed decoder; use its recorded source origin and native dtype, preserve original raw provider scores and native fingerprints, and report per-candidate clipping, quality/rank changes and ties. If archive behavior is the hypothesis, replay capacity-one cell comparisons and actual parent identities, identify the first insertion/replacement and allocated-parent divergence, and clearly mark later saved pools as forced rather than regenerated. Global argmax or final-choice changes alone can miss a within-cell parent effect. Conversely, unchanged effective archive/parent behavior would weaken the case for spending a GPU cohort.

Semantic risks that must be resolved prospectively:

1. **Preserve external channels.** Editing the global adapter projector would change frozen provider inputs, guidance gradients, possibly descriptor and selector geometry, and Stage semantics together. A valid isolated proposal needs a separately named internal candidate view from existing data; the external provider, deployed decoder/actions, raw selected Stage reward and established Stage normalization input definition remain unchanged. Auxiliary gradient/pretest calls must retain their original contracts and full-episode/canonical176/11 computation remains accountable.
2. **Keep the intended horizon and arithmetic explicit.** The diagnostic measures an8-action endpoint, while the original provider objective uses seven projected points. An internal objective must declare exactly which points, fractional weights and FP32/BF16 casts it uses; silently combining clipping with N2's full-prefix change would add a second intervention. Native projection origin rounding and per-step rounding must be retained or explicitly declared, not replaced by diagnostic float64 arithmetic under a claim of equivalence.
3. **Bounds are instance-specific.** Unit per-component clipping is not vector-norm clipping, clipping the summed displacement, gripper modification or direct0.05 integration. Asymmetric bounds, output transforms, rotation/translation coupling and control mode must not be guessed from defaults. Snapshot/check the actual applicable deployment metadata before asserting exact actuator semantics.
4. **Quality, archive and search can disagree.** Preserving raw external gradients while changing internal archive quality is an intentional new algorithm; it may continue proposing saturated candidates. Clipping can create many ties or collapse geometry. A descriptor proposal must consistently freeze bounds in its declared geometry; a quality-only proposal must leave cell geometry alone. Raw/action/effective associations and stable tie handling need independent audit.
5. **Prediction is not task quality.** A better EEF displacement approximation does not identify the correct target, recognize object retention, or certify that an unexecuted candidate is better. Closed-loop candidate distribution shifts and lost successful behavior remain possible, especially given the adverse step176 and the N3 precedent. Any subsequent online hypothesis still needs fresh matched controls, unchanged success gates and protected validation/formal separation.

No such screen, formula, candidate or GPU experiment was implemented or frozen by this review. The JSON companion records independent provenance, exact association checks, reproduced statistics, adverse cases, historical adapter equality and the supplemental exact-p8 comparison.
