# N11 task0 terminal parent-cell audit correction

The four-arm N11 Dev supervisor stopped after task0 because the original native audit rejected the N11 trace with `n4_selected_parent_cell_mismatch`. The GPU episode itself completed and the attempt ledger marked its task outcome valid and unsuccessful. No task3/6/9 cell was dispatched and no task0 cell will be retried.

The original audit compared the terminal candidate's `parent_cell_ids` against `archive_parent_allocation[9].parent_cell_ids`, which is the order *before* N11 moves its four exact survivors to the front. The recorded `parent_allocation[9].parent_indices` is the ordered permutation. The terminal parent cells equal both `parent_allocation[9].parent_cell_ids` and `archive_parent_allocation[9].parent_cell_ids.index_select(parent_indices)`; the selected parent cell also equals the cell at the selected terminal index. The original unpermuted equality is false. The earlier audit loop already verifies the allocation-to-parent permutation and exact survivor latents, so the corrected terminal check uses the verified post-permutation parent cells only in N11 mode. The N7/C0/Q0 check remains unchanged.

The fix is code-only commit `9f10df8` in the study worktree (isolated implementation commit `ce13259`). The new non-identity permutation regression checks both acceptance of a valid reordered trace and rejection of a falsified selected parent cell. All 38 terminal-audit tests pass. Reauditing the unchanged SHA-verified GPU evidence accepts all 43 guided decisions and 430 survivor rounds. This audit correction does not change policy weights, candidate generation, success labels, Stage calls, seeds, or the original evidence files.

Original frozen plan SHA-256: `ec2f0f15f51ded24022ffd9cc39ca184813a4c53ef5f4334ca76ddf6a1ebc879`.

Original failed audit SHA-256: `ba8d0ad5fb5af48ece88f6ec5ed1d8f140767186974e15dd2e68e98f7ebaa814`.

Corrected independent audit SHA-256: `975c520454f4d030257456ee60976382ff7fbf506015c704e6ccfb0ed8e10e9c`.

The four task0 outcomes are valid failures: C0 0, Q0 0, N7 0, N11 0. A prospective continuation may run only the twelve previously frozen task3/6/9 identities under a new source-commit/plan hash and release file, with the original four attempts linked as prior evidence. The original failed supervisor status and audit remain immutable.
