# Root prior-feedback contrast, before new trajectory results

Read-only comparison of earlier Dev findings and current source. No algorithm is nominated or implemented here.

- N14 signal audit: eight N7/N11 Dev paths,562 contexts all target0 tracking valid;13 same-stage next-guided target shifts at least1cm were observed, concentrated on tasks0/3. This established availability of the existing keypoint signal, not task utility or real-world vision equivalence. Its motion-gated four-parent-survivor proposal did not activate on the failed task0/task9 N7 paths and was not dispatched. This is not a universal rejection of feedback or memory.
- N15 stalled-contact gate (projected reach<=6cm, observed EEF displacement>=2cm, target shift<1cm, stable next same-stage guide) activated on only tasks0/3 and was not dispatched. Thus a new candidate cannot simply copy that gate or quietly lower thresholds and call it a new mechanism.
- N16 terminal pool near-close screen found projected<=2cm positive-command proposals on a few task0/task3 decisions, and showed both selection without success and success without that screen. It did not establish causal grasp or justify a bonus.
- Existing select_grasp_timing in core/qd_grasp_timing.py recognizes any of eight positive-gripper commands when its projected point lies within6cm and within3cm of the best projected reach. It then uses native minimum cost among eligible rows. This function does not consume actual EEF quaternion, measured gripper qpos/qvel or object contact. This is a source fact, not proof that adding those fields will help.
- Earlier N3 execution residual correction improved modelled displacement error but failed Dev0/10. N24 preserved command-capable proposals within each chunk yet failed0/6. The full-trajectory audit must distinguish any later cross-chunk or grasp-related proposal from those negative mechanisms.
- Current N29 metadata:465 guided decisions versus N28199, all arms0/6. Current numerical extraction is still in progress; do not pretend its observations already establish an algorithm.

Sources read: variants/n14_feedback_signal/{signal-audit-conclusion.md,gated-survivor-screen.md}; variants/n15_stalled_contact/screen-conclusion.md; variants/n16_gripper_quality/screen-conclusion.md; study_worktree/core/qd_grasp_timing.py. Only already exposed Dev/source evidence, no validation/formal or new simulation. Keypoint tracking comes from the frozen benchmark object-pose interface; a deployment on a real robot would require corresponding observations and calibration, not hidden simulator contact.

