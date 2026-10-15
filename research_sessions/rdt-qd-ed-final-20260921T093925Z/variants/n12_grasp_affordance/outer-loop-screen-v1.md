# Post-N11 bounded outer-loop screen — 2026-09-28

Decision: **COLLECT_TARGETED_EVIDENCE**. The overall target remains
`TARGET_NOT_MET`; N11 is rejected at Dev, and no N12 algorithm or GPU episode
has been authorized or run. This is the one bounded review required by the
frozen execution specification §6 before proposing another mechanism.

N11 completed all 16 same-task/same-seed Dev cells on GPU3 with audited
evidence: C0 1/4, Q0 0/4, N7 1/4, N11 1/4. N11 uniquely gained task3 and lost
N7's task6 success. Its exact-survivor lane changed selected actions and
preserved 120 exact parents in task3's three guided decisions, but did not
meet the frozen ≥3/4 and strictly-above-N7 gate. See the immutable
`../n11_parent_survival/dev-comparison-v1.json` and audit correction.

The SHA-verified terminal-pool audit
`terminal-affordance-readonly-v1.json` (SHA256
`337467dea683ba1fadc7877c792962c44257639292d91ef7cf39c5946b5a6447`)
rules out a simple “produce more near-target close commands” interpretation.
N11 task0 failed despite 28/43 guided decisions having an N5-eligible close
candidate; N11 task9 failed despite 2/4 such decisions. N7 task6 succeeded
with 0/2 eligible decisions. At N7 task3 step16, one unselected candidate
closed throughout and reached about 5.9 cm **in projection**, but the N5
relative-reach gate excluded it; N11's successful same-task episode selected
a different, exact-survivor candidate at about 1.8 cm projected reach. Their
states had already diverged. The effect of the unselected N7 candidate is
Unknown.

The separately SHA-verified actual-execution audit
`gripper-feedback-readonly-v1.json` (SHA256
`b4eabefc6fa7c82316cf21573f60dd6959071a443f1cecaa688f2ca17b3ae82d`)
found, in the first 120 steps, sustained nonzero gripper joint aperture and
substantial EEF lift in N11's successful task3 and N7's successful task6.
The failed N7 task3 and N11 task6 trajectories eventually reached nearly
fully closed gripper positions. This is an observed joint/EEF signature, not
a contact or object-carry label; failed N7 task0 also had nonzero aperture
after a short closing episode and little lift. A conservative closed-near-
target feedback rule (aperture <1 cm, EEF–keypoint distance <8 cm) would have
been eligible only at N11 task0 guided steps 352, 360, 368 and 704; it would
not distinguish the task3/task6 outcome exchange. Thresholds were exploratory
read-only screening, not frozen candidate settings.

Thus another exact-parent fraction, a gripper-close lane, N5 reach-threshold
relaxation, or a retrospective gripper-state veto would recycle a proxy that
already appears in failures. No distinct QD–ED change currently has enough
task-linked evidence to justify spending the remaining second matched Dev
cohort, and validation/formal remain closed. The next information gain is a
single same-state physical contrast: N7 task3 step16 selected terminal index7
versus index6, each for eight actions after identical recorded-prefix replay.
The complete fixed scope and SHA-bound pending plan are in this directory.
Under §5 that extra simulator branch requires separate approval; it is not
covered by the earlier task9-only approval. A result may identify a selection
failure or reject this lead, but cannot itself establish full-episode benefit.

Budget at this screen: 201/393 dispatched attempts and
26.8492431516/100 GPU-process hours. Baseline is 24/28, development 110/125,
validation 60/180, formal 0/40, recovery 7/20; protected reservations are
32 validation hours and 12 formal hours. No new attempt was dispatched by
this review. GPU3 is idle for this study.
