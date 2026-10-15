Implemented the bounded B1/B3 engineering repair in `b1d20fc0481721da6ebaab161c5a2ef7c3d50173`. **Focused CPU checks pass; production remains blocked.** No scientific promotion or completion claim.

- Canonical source-bound STOP pair is independent of checkout resolution. Shared fail-closed lstat/deadline checks cover admission, healthcheck reservation/start, reservation-to-launch races, worker entry/pre-Main and next dispatch. Draining and settlement remain available without STOP signalling.
- `n36-source-execution-v2` proves only `os.path -> posixpath`: live module identity, canonical frozen spec and loaders, `_imp.is_frozen`, exact file/hash inventory, and external context/process/phase/interpreter binding. Ordinary compiled/startup and native/generated/_cyutility audits remain.
- N36R2 release/admission hard rejections remain. Owner HEAD is unchanged at `ca4e6a96d049c7ebb1f302d755883388ddbfdbd8`; the isolated worktree is clean and preserved. The 18-file patch is `source-changes-v1.patch`, SHA-256 `07500cc315138b3548ffed0f0095633a09825f19dd1e4305132697404e641988`.

Focused results (commands, environments, log hashes and all retained failures are in the JSON):

| Run | Result | Purpose |
| --- | --- | --- |
| 1 | 18 failed / 99 passed | Synthetic worktree fixture deficiency, retained |
| 2 | 124 passed | STOP, launch races/drain, alias proof, runner, disabled N36R2 |
| 3 | 25 failed / 52 passed | Generated TMPDIR lexical-path mismatch; source-loader/alias checks passed |
| 4 | 40 passed / 6 deselected | Resolved evidence TMPDIR; _cyutility regression and pre-Main STOP |
| 5 | 1 failed / 14 passed | Imported autouse fixture scope, retained |
| 6 | 21 passed | Scoped fixture; release/context and worker boundaries |
| 7 | 38 passed | Final producer loaders/lexical paths and alias negatives |
| 8 | 23 passed / 18 deselected | Valid-shaped binding substitutions and fresh source-bootstrap receipt |

Total pytest-reported time: 37.11s, under two-CPU affinity with CUDA hidden. One additional mistyped shell redirection failed before pytest started; no file was created there. No broad suite, real GPU/probe, simulator, provider, package installation or subagent was used.

`fresh-cpu-alias-receipt-v1.json` retains a newly executed source-bootstrap proof; its producer hash equals the committed source. It uses a synthetic CPU context and partial test inventory. `after=False` passes for that diagnostic and `after=True` rejects missing required coverage. **This is not a full production receipt, final source freeze, independent source review, or post-episode coverage.** No additional frozen alias receives an exemption.

Follow-ups remain B2 complete final source/scientific-source freeze and dependent artifacts; B4 immutable isolated runtime/controller composition and complete all40 checks; B5 finite admission/accounting/resource routing and detached approval. B1/B3 changes still require independent source review and new complete receipts. Nothing activates authority beyond `2026-10-11T11:13:13Z`.

Retained without ledger mutation: **504 dispatches / 75.49265038509455 GPUh**, INVALID N36 **86.40354533703066s**, INVALID N36R1 **809.4826372319367s**. These inherited values were not recomputed from protected/private records. Historical artifacts and earlier failures remain intact; no owner state, source adoption, release, driver lock or coordinator lease was written.

Reports completed 2026-10-10T03:04:35.191301+00:00; elapsed wall 1033.2s of 1200s. Both canonical STOP entries were absent and the deadline open at final verification; absence supplies no execution authority.
