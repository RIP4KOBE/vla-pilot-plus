# Independent targeted fix review

Reviewed commit: `ed56611dc45d28dbc59ffa172a810a810360dfc1`, atop `78aa6646503a114602dc08b799b49e2c60084ba8`. R was clean during review.

Authority checked: protocol `75766ff02c4722c25f772e647937fc68cf9a3361129791585430115595f0e8fa`; budget clarification `9b1ccf9932f8fe2bf637d0e2a4674fae866740424ef523d83d665bac8c14c77c`.

Both previously reported defects are fixed in the reviewed code:

- Recovery report: `terminal_check` supplies the exact row from each terminal's SHA-bound plan. `recompute` passes a complete `validated_rows` inventory into `summarize`; it does not recover unknown keys heuristically. The regression keeps the 60-row base immutable, appends one recovery only to a separate 61-row revision, and includes all 61 terminal records. It retains the original `event=valid/outcome_valid=false`, selects the accepted recovery once, and includes both 12s/25s costs. Omitting the revision is rejected.
- Promotion source identity: `source_identity` compares the recorded source commit and full path-to-SHA code inventory, rejecting duplicate paths. Validation promotion checks every reported Dev base/revision against the selected Dev source. Formal promotion checks the validation report's bound Dev source against the selected Dev source; evaluation report revisions also preserve full phase source and bound Dev source. Core-byte-only, source-commit-only and combined changes are rejected. Legal checkpoint/recovery plan revisions with unchanged source remain accepted, including a reported revision. A changed reported revision is rejected.

Independently executed only the six new targeted CPU regression cases:

```sh
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -q -p no:cacheprovider tests/test_qd_ed_n2_evaluation.py -k 'report_joins_recovery_to_its_immutable_derived_plan or promotion_cannot_reuse_old_pass_for_changed_selected_Dev_source or promotion_allows_checkpoint_recovery_plan_revision_with_same_Dev_source or formal_cannot_switch_selected_Dev_source_after_validation'
```

Result: **6 passed, 31 deselected in 1.32s**, exit 0. The executor's broader 140-pass result was not rerun. No additional definite bug was found in this bounded fix delta review.

Source SHA-256:

- `scripts/qd_ed_n2_evaluation.py`: `cdb8d3b3068ccff8c62b796f05ba6da2559134c892c4cd566450e42331367889`
- `scripts/qd_ed_n2_evaluation_report.py`: `bfb02ada30d49e01a3300b7146e57393a83d3581afa63c6bd40a207002465ce5`
- `tests/test_qd_ed_n2_evaluation.py`: `3ee6dfe47ddf0fd27953714995fc62622c2eebb6cb35d04d14400b785bd4f934`

This review uses source and synthetic temporary fixtures only. No actual validation/formal outcomes, models, provider calls or GPU execution were used. No R/W source, scientific state, ledger, plan, or threshold was changed. This is engineering review evidence, **not promotion or execution authority**; all original protocol gates remain required.
