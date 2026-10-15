# Focused Stage optional-field fix review v2

PASS for commit `e1d2dbccb1bda39cccb680bd80bb7e590ff00319`, reader SHA `b19331ff6861210056858d56da6dcbd2d6a24f06fc91e24dcc1beb0d4df18b3e`. The original v1 blocking report and reproductions are preserved.

Both reported defects are resolved: a missing/null or incorrectly typed Stage step remains Unknown without predecessor arithmetic, and incomplete or incorrectly typed after-state remains Unknown rather than a false mismatch. Known equal, stage-mismatch and guidance-mismatch cases remain distinguishable. Missing after-state does not erase independently known sent-command associations. No numeric/string/boolean coercion supplies missing semantic knowledge.

The independent focused rerun passed **22 pure-dictionary checks**: 6 location cases, 10 after-state cases, 3 known comparisons, absent/empty stream controls, and one mixed stream preserving all 19 input events in order. These overlap implementation tests and prior controls; they are not additional performance observations. The full 16/30-test suites were not rerun. All 11 freeze-v2 local files match their declared SHA and exact reviewed commit bytes.

The remaining runtime change only requires protocol-v2 in the freeze inventory. Admission/source/recovery/report-authority gates, exact dependencies/auditor, reset and partial-action reducers, and scientific exclusions are unchanged. No remaining blocker was found in this focused correction.

No actual episode/bundle/results were read; torch was not imported; no GPU/model/provider/projector/simulator calls occurred. No E/W or prior review file was modified. Actual cohort reading still requires separate root authorization. The practical limits of review-v1 remain.

Reproduction: `review_reproductions_v2.py`; output: `reproductions-v2.json`. Exact hashes and case groups are in `review-v2.json`.
