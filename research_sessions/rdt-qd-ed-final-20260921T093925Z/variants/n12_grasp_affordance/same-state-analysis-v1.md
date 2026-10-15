# N7 task3 same-state diagnostic: completed, no candidate promoted

The user approved exactly one exposed-Dev task3 diagnostic. GPU3 executed one
attempt (`rdt-qd-ed-final-20260921T093925Z__n12_same_state_t03_20260928__9b0c6d255b89`)
with 4 resets, 20 settling actions and exactly 96 diagnostic transitions. The
four 16-step replays matched their complete recorded state, and the two
selected dry runs matched the selected contrast at every snapshot. Both
branches began from the same state. No official episode success rate is
defined; validation and formal remained closed. The approved plan SHA256 is
`298341649c9195bc1d534194132873ae21f91b5b92dd1779eaf8a31f95b81bfe`,
raw child-result SHA256 is
`ef85beefaca49c26c1ee4f0fb1610d0dadfb0ea814e20fcc223ec0aff7ec59e3`,
and analysis JSON SHA256 is
`4f2ea168ef40890fc62d4fa0dfcb18652d1014c735ca750847ded14475e79eb7`.

The first post-run analysis attempt failed before writing an output because
the approved runtime manifest calls the target geometry `bbq_sauce_1_main`
while the simulator snapshot uses the body key `bbq_sauce_1`. The analysis-only
script was corrected to resolve the exact `_main` suffix, require that body
key in every snapshot and disclose both names. The raw result, frozen plan,
GPU run and budget event were unchanged; no GPU retry occurred. Corrected
analysis-script SHA256 is
`138cbbed3cfea6dd8ecf164efe08b0c6d59a2ef1b35f1c1cd5248339012a720f`.

| Eight-action branch | Target displacement | Target height change | Closest EEF–target distance | Final EEF–target distance | Sampled target–finger contacts | Prefix success |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| N7 selected index 7, gripper open | 0.070102 m | −0.042400 m | 0.031854 m | 0.077501 m | 0 | false |
| Alternative index 6, gripper closing | 0.070696 m | −0.042003 m | 0.040910 m | 0.098356 m | 0 | false |

The object moved about 5.6 cm in negative x and dropped about 4.2 cm in both
branches. In the alternative, the object was already about 5.8 cm from the
EEF by step 2 while the gripper was just beginning to close; by step 8 it was
9.8 cm away. No target–finger pair appeared in the action-boundary contact
snapshots, which does not exclude transient contact between snapshots. Both
branches failed the short-prefix task predicate. The contrast therefore
rejects a simple relaxation of N5's close-command reach gate as the next
candidate: the unselected N7 index 6 did not show a useful physical grasp or
placement signal in this one state. These data do not estimate a full-episode
counterfactual or prove that N11's separate successful task3 path was caused
by its exact-parent lane.

Read-only montages of already recorded N7/N11 task3/task6 videos are under
`readonly_visual_audit/`. They corroborate that the two profiles have
different early physical paths; the green/red video labels refer to the
whole episode, not success at each displayed frame. They do not identify a
task-general selector. Prior N9 already penalized projected near-target
lateral motion and lost a Dev success, while N10's intended object-feedback
measurement was invalid due incomplete Stage turns. This bounded post-N11
review has no evidence-backed new QD–ED rule ready for a full Dev cohort.
The additional SHA-verified, simulation-free early-feedback audit in
`early-feedback-analysis-v1.md` shows a posthoc closer-versus-farther
gripper-switch association across four trajectories, but one successful switch
occurred after QD–ED guidance had ended. It therefore does not supply a
general final-population selection rule.

Decision: **REJECT THIS N12 GRASP-RELAXATION LEAD; TARGET_NOT_MET**. Cumulative
GPU3 study accounting is 202/393 dispatched attempts, 26.8531882286/100 GPU
hours; development 111/125, baseline 24/28, validation 60/180, formal 0/40,
recovery 7/20. The remaining 14 development attempts and protected 32/12 GPU
hours for validation/formal are preserved. Under execution specification §6,
no additional GPU candidate should be invented from this one proxy. Further
work needs a distinct, falsifiable QD–ED hypothesis supported by deployable
object-contact/progress evidence, or a separately scoped physical diagnostic
approved under §5. No further GPU dispatch is authorized by this diagnostic.
