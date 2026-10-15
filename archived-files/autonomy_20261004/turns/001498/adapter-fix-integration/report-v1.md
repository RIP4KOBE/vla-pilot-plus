**Node 15.6: F1_FIXED_PARTIAL_CPU_INTEGRATION_COMMITTED_VETO_RETAINED**

F1 is repaired and nine distinct new focused test groups passed across bounded runs, including the complete simulated health/episode/receipt/normal-restart lifecycle. One additional crash-matrix group failed at fixture clock restoration before exercising its first crash case; its fixture clock was corrected but the five-case matrix was not rerun. Public dispatch remains hard-disabled and the goal remains false.

Commit `3b05c0b557b59bf3dc9ddbb11593a41a4e49f4d1` → `3f6c4e8dd968ece8f6c2a558389f3851db173013` on `exp/n36-engineering-adapter-001482`. Goal remains **false**; public dispatch veto remains unconditional.

F1 now revalidates the engineering health handoff under the state lock after runner-lock reacquisition, binds unchanged plan/runtime/authority/post-sync state, and requires no episode plus the exact original sole reservation. Rejection leaves it spent and launches no child. Readiness also checks dispatch timestamp ordering. Legacy health branch and veto AST are unchanged.

**Tests and evidence**

- 1 error in 1.80s — `integration-001498-01.log` (SHA-256 `de31d768d36e44e054c072a2da8606d99ed2c92e31426cbb15199568b1b85e5d`).
- 1 failed in 14.03s — `integration-001498-02.log` (SHA-256 `2a53561df7b23c6eb17998341b916a1cb9a6035c4544c2ae366131429f9ce4ce`).
- 1 failed in 33.23s — `integration-001498-03.log` (SHA-256 `c4b6f6ac83405e17e2d763166ef1914a8f59c5b9622d2b589e5aba8dc827cf11`).
- 2 passed in 171.70s (0:02:51) — `integration-001498-04.log` (SHA-256 `83ab84cbdd7de28568391f67578f33cf8b66e56f06c32eb4ccb76484031a69ff`).
- no tests ran in 40.51s — `integration-001498-05.log` (SHA-256 `9cd861ce1cef2c8988d2f6c3fb0f83be8ef1a8ef4c9d1b614e993e973356b02e`).
- 5 passed in 278.96s (0:04:38) — `integration-001498-06.log` (SHA-256 `7b69125b2a67338523d3e527b44ac9c719b2b772463922d75b63e517129ac0c6`).
- 1 failed, 3 passed in 420.45s (0:07:00) — `integration-001498-07.log` (SHA-256 `022dc8145cd4b7071078b7fd3b069f08405510a92746b205517c080570668dc8`).
- 1 passed in 115.50s (0:01:55) — `integration-001498-08.log` (SHA-256 `f40d2c621d44b8c1d2d582e3b12e91211f66e6d1406520af19f6b1a3880bd73f`).
- 11 passed, 29 deselected in 2.63s — `001498-handoff-regression.log` (SHA-256 `5dca3889a22460e0f950a823a239475ebd7483d2407ac7c1d8a5a7267289f931`).

Reused, without rerunning: **190 passed**, bound log SHA-256 `41cf00a6965325ee293614f0abd5a6732157702dc55acc97e80521caa76ee7c1`.

**Coverage**

- F1: actual private copy of health orchestration and real reservation/full release validators, snapshot, append/fsync and state locks reject a foreign resource introduced during transfer; zero children, no output, one original spent reservation, subsequent reserve rejected.
- F1 locked snapshot matrix: foreign attempt, completed foreign health, foreign reservation, same-ID replay, dispatched health, changed original event, hold/private-budget/adoption/run/artifact/GPU/other-state mutations rejected. The unmodified spent snapshot is accepted. Thirteen negative variants use real locked production validation.
- Both release families reach real accepted full fixture closure on the positive lifecycle. NON-C0 manifest, source bytes, runtime bytes, native library bytes, controller semantics and runtime-closure mutations are rejected at asserted intended gates in both families (12 mutation invocations).
- Complete health reservation -> dispatch -> terminal -> readiness -> episode release -> private execute_one orchestration -> real context/receipt/terminal/generic outcome validation -> normal restart permanent stop passed. Append/fsync/locks/state accounting and production terminal/receipt/reconciliation validators are real. Child/device/provider/parent import observations are simulated; no public dispatch was enabled.
- Normal restart revalidates the receipt and terminal and stays PAUSED_FOR_ROOT_G3 with no next row or scientific outcomes after state G3 flags are changed.
- Readiness dispatch-before-reservation and dispatch-after-observation rejected; terminal timestamp/artifact and provider-binding mismatches rejected. No numeric TTL was invented.
- Full synthetic 506-attempt retained snapshot, all three prefixes, exact retained GPU total and margin, authority/adoption and state validation; caps, binding, prefix, weekly window, source adoption and full-snapshot mutations rejected.
- Actual predispatch health abort with zero child launches durably records reserved/aborted, blocks readiness and replay, and preserves the single consumed resource. Health/episode cross-release and legacy-family cross-use reject.
- Exact and one-microsecond-short 2100/1840/60 launch-guard windows; exact and one-microsecond-short 2100 detached health-release issuance window; 1900 local scope boundary and adjacent representable weekly/protected headroom values exercised.
- Public engineering execute_one, runner, health, reservation helper/wrapper and launch guard vetoes retained and tested. Static AST equality confirms the unconditional veto and legacy health branch are unchanged. Existing 190-case evidence hash matches and was reused without rerunning it.

**Remaining gaps**

- The five-case actual runner crash/restart matrix (reservation-only, dispatched, terminal-before-artifact, receipt mismatch, aborted episode exhaustion) did not execute its intended assertions: the fixture reset its clock before retained health completion and production readiness correctly rejected it. Final test source advances the restored clock beyond retained observations; this correction is syntax-checked but the expensive matrix was not rerun within the cap. Normal valid receipt/terminal restart and G3 exhaustion DID pass.
- Fresh episode predispatch abort and full accepted-context cross-family mutation remain unexercised in the new integrated graph. Release-family cross-use and actual health predispatch abort/exhaustion passed; older predicate/journal evidence does not close these remaining paths.
- The exact weekly/protected arithmetic tests bracket the boundary using adjacent representable floats; no claim of literal Decimal equality for all global/protected/absolute cap combinations or full integrated admission at each bound. The stricter unchanged weekly ceiling remains active.
- The fixture uses a synthetic retained history and disposable source/runtime graph (closure v1 plus interpreter aliases), not the actual owner snapshot, final deployed source inventory, generated-module-v2 closure or native/GPU runtime. Parent bootstrap admission/import observations are simulated; no real launch admission is certified.
- Existing broader shared evidence of 49 failures / 43 passes is outside this bounded follow-up and was not rerun or resolved; no global all-tests-pass claim is made.
- Production inventories/manifests, independent B5, owner accounting/source adoption, readiness/releases, GPU execution and scientific promotion remain out of scope. Keep the unconditional dispatch veto; enabling requires a separate reviewed change and authority.

**Fixture and scope limits**

- All approval-shaped documents and local Git stores exist only inside TemporaryDirectory under this worktree; fixture identities and SOURCE/OWNER/SESSION/specification/accounting/protocol pins are test-local. Temporary directories were removed. No operational approval, source inventory, readiness or release was created.
- Fixture source tree includes copied composition/core inputs and inert source/dependency files. Actual Git/blob/source validation and all40 Hydra/constructor composition run; this is not a final-source production inventory or real owner retained history.
- Loaded parent-module observations are a test-local sys module view; source-only bootstrap active/attest observations are simulated. They do not establish actual parent bootstrap admission.
- Device admission, provider observation, credential-free child environment, process identity/Popen/wait, clocks and child-produced evidence are simulated. No model/GPU/provider process or credential read occurred.
- Private AST copies of health/reservation/runner/guard orchestration remove only explicit dispatch-veto calls and route an isolated test-local API facade; production public veto functions are unchanged and tested. Public dispatch was never enabled.
- Real plan/authority/adoption/prefix/full-snapshot/scientific-equivalence/source/runtime/native/controller/all40/engineering-manifest/readiness/context/receipt/terminal/generic result validators remain. Real append/fsync/locks/state sync/reconciliation operate only on the disposable graph.
- Episode child observations use zero-guided-chunk synthetic telemetry and a CPU-encoded one-frame video; native/GPU/provider claims are explicitly simulated child claims, not scientific outcomes or native recomputation evidence.
- The fixture covers runtime-closure v1 plus closed interpreter aliases; it does not build the production generated-module v2 closure or attest installed production runtime/GPU readiness.

Changed files (exact committed bytes):

- `scripts/qd_ed_n36_engineering.py` — `1dc19cdb1c775725142105a305ee7aba34fea6f9101a7ab1e3efaf31f5ba5dc6`.
- `scripts/qd_ed_n36_healthcheck.py` — `badcf727efaf169ce2f1848bd512fbb58bfd0136e6313ad0012281ae6e08c939`.
- `tests/n36_engineering_cpu_fixture.py` — `6118201b92c99fca997730e7aaa5c01b70bea7de01016206b61d8ca862927dbc`.
- `tests/test_n36_engineering_integration.py` — `19339408b8c2d9a5702a30c223e1ff1b8c8cc8faf05c751f697fe7927f81ced3`.

CPU threads limited to 2. Finalized in 1731.9s from task start (1753.3s since authority). No owner-state, ledger, tree, checkpoint, other-worktree, frozen scientific-file or authority edits; no GPU, network, credentials, protected results, prohibited design, cloud, alternate model or subagents. Exact commands, artifact byte counts and scope checks are in report-v1.json.
