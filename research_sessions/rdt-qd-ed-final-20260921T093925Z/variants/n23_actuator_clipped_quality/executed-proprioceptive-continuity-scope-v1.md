# N23 executed proprioception diagnostic — bounded CPU-only scope

This is a distinct read-only follow-up to the closed planned-tail diagnostic. It grants no candidate implementation, active-source change, budget amendment, API/GPU/simulator dispatch, or protected-data access. It does not alter the closed earlier read scopes or their manifests.

Question: What actual policy-visible gripper and end-effector motion accompanied the four already completed N23 Dev episodes and the complete set of 15 strict-identity, full-positive prior-tail pairs reported previously? Differences in unexecuted plans alone do not show physical regression. This diagnostic measures recorded execution, without inferring that a different unexecuted command would succeed.

## Inputs and finite read boundary

Use exactly the four completed attempts in planned-gripper-continuity-attempts-v1.json (SHA256 cca36ad827d720aa7973e808d86db7fb00da961f44ba4203f57123626adc39f4) and the existing planned_gripper_continuity_diagnostic derived outputs. No running/future attempts, controls, other variants or protected evaluation outcomes.

Before native reads, freeze a manifest of the necessary decision-evidence index/bundle paths and hashes. Read each chosen native bundle once in the actual screen. Allowed new fields are action_dispatch/step_returned identity and pre_reset_outcome.observation.robot0_eef_pos, robot0_eef_quat, robot0_gripper_qpos and robot0_gripper_qvel, plus existing decoded/committed executed actions and causal Stage/reset/target identity needed for association. The named observation fields are exposed to policy by core/decision_evidence.py:250-258. Exclude reward, success, termination outcomes as tuning features, contact flags, object simulator poses, physics replay, images and unrelated tensor payloads. The manifests may be bound to existing terminal/audit references, without rescoring/replaying the experiment.

Maximum 4 x 720 = 2880 actual executed transitions; no new environment steps. Boundary-start observation may be the immediately preceding recorded step result; missing initial observation remains Unknown. Reuse earlier exact decoded action bindings; do not reproject trajectories or recompute quality.

## Descriptive outputs and interpretation

Report per-attempt coverage and missing/nonfinite fields; all command-sign runs; observed ranges and net changes of both gripper joints and EEF xyz; and joint/motion summaries split by exact all-positive, mixed and all-nonpositive eight-action prefixes. Do not fit a contact/grasp threshold, tune a coefficient, choose a success-correlated subset, or label gripper stall as grasp.

For all 15 previously reported strict full-positive prior-tail pairs, report both actually executed eight-action prefixes, starting/ending qpos and EEF (Unknown where unavailable), target displacement already recorded in the earlier diagnostic, and whether Stage/reset/target identity permits that descriptive comparison. Include the five retained pairs as well as all mixed/absent pairs. No causal benefit or defect is inferred from correlation; tracked target motion is not object ground truth and physical grasp remains Unknown.

CPU only, two threads, CUDA invisible, no provider/simulator imports or subprocess evaluation. Reuse a guard that fails on forbidden dispatch. At most 180 seconds native-screen wall time plus two bounded engineering reruns for extraction bugs, preserving errors; if exceeded, return incomplete evidence. Write extractor, frozen read scope, exact outputs and conclusion under variants/n23_actuator_clipped_quality/executed_proprioceptive_continuity_diagnostic/. Do not modify W or research state/ledger. Root will review before any successor decision.
