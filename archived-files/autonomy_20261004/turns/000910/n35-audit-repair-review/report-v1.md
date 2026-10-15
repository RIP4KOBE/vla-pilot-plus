**PASS — independent CPU delta review, Arbor node 15.5.**

N35-IR-001 and N35-IR-002 are fixed in the reviewed delta without weakening mandatory reset/acknowledgement evidence or rejecting the examined legitimate recorder/Main paths. PASS is scoped to CPU repair acceptance only.

Base `c3730e5287fe659dffc95c40bf6d8b7ba95d1da9` → final `52a87af0bf11f95b21ce17aba456dc98944d9774`; tree `cd86d9de46115624bb82bce03dc2285388a33c6e`. Scientific score: **null**.

**N35-IR-001: FIXED.** Ordered replay accepts the real recorder epoch transition without a decision-wide constant-epoch assumption. Every event must carry the current integer epoch; only a correctly positioned terminated automatic-reset boundary advances it once. Return termination and success bind to the pre-reset outcome. Truncation alone preserves the epoch.

- `scripts/qd_ed_n35_lifecycle.py:25-57` — Strict event order, epoch replay, outcome/reset identity, reset metadata, returned flags and unfinished-return rejection.
- `scripts/qd_ed_n35_native.py:59,87-93` — Replay runs before native checks; old constant-epoch check removed while episode binding remains.
- `core/decision_evidence.py:252-270` — Outcome and reset marker use old epoch; increment precedes step_returned.
- `core/env_adapters/libero_adapter.py:818-844,1722-1736` — done or success terminates; auto reset occurs inside step; outer wrapper independently sets truncation.
- `main.py:2185-2190` — Return record immediately precedes closure memory acknowledgement.

Final six termination/truncation cases at prefixes 1/4/8 and original termination reproduction pass; additional CPU fixture accepts termination without success and simultaneous termination/truncation, rejects initial/missing/extra epoch and success mismatch.

**N35-IR-002: FIXED.** Each guided returned step requires its adjacent identity-linked acknowledgement. A terminal acknowledgement requires exactly one immediately adjacent terminal memory reset with matching episode, decision, step and epoch. Obligations cannot be bypassed at another event, boundary or end of stream; duplicate or premature terminal reset fails after pending state is cleared or before terminal_due exists.

- `scripts/qd_ed_n35_lifecycle.py:72-90` — Mandatory return-to-acknowledgement and acknowledgement-to-terminal-reset adjacency; terminal reset requires pending state and obligation.
- `scripts/qd_ed_n35_lifecycle.py:172-185,197-205` — Acknowledgement binds actual returned/executed action and identity; terminal obligation and end-of-stream enforcement; exact acknowledgement count.
- `core/qd_closure_intent.py:159-183` — Actual acknowledge emits step_acknowledged then immediate terminal reset; eighth terminal step resets rather than creating a token.
- `tests/test_n35_terminal_reset_audit.py:11-109` — Actual recorder/helper traces; legitimate prefix assertions and 159 independent corruptions with renumbering to avoid incidental sequence-only failures.

Original deletion reproduction passes in final evidence; missing, duplicate, wrong-reason, identity-mismatched, delayed and premature resets plus missing/duplicate/misplaced acknowledgements reject. Additional fixture rejects delayed nonterminal acknowledgement.

**Verification and evidence.** All authority direct-reference hashes and three bounded ledger prefixes match. Four changed files match final commit and repair report. All other tracked files are unchanged between commits; named scientific/recording dependencies also match their base and final blobs. Pre-existing untracked `AGENTS.md` is preserved. Exact verification: [verification-v1.json](verification-v1.json).

Authority SHA-256: `50846af06bf9761f5380c969859ac250ffe7a831da2b9bd1692acb2ae6abac80`. Protocol: `b8ac519a02623a7f033c5ce4b9c805bf1970f10224e29c0f851ba8568b000345`. Accounting: `0e6925d214c7613ef2f6a7ffe5b8ec04d6f90fb134b40f0e77e111a67204491c`.

- `scripts/qd_ed_n35_lifecycle.py`: `d56c93bc49a15734e3c95b05aa1d008f4cc218e2ddf3156c50930841a8bc1b81`
- `scripts/qd_ed_n35_native.py`: `9e412f940746876c6690fd8064b303bd91eea694580d06242c72614d2997fc39`
- `tests/test_n35_closure_intent_integration.py`: `052e8d19f220a8a2f9092af585bd92c075e5caa05fb0d2bdc5d0b7d7a3d954fc`
- `tests/test_n35_terminal_reset_audit.py`: `ca7ffa2d340b3744ee2a1d42a8592b6712111889f95040e0eb5554883b46ce1c`
- `core/qd_closure_intent.py`: `1c3d9ac04d0fcf5c0014ca17b836de283c508de4bc94b8306ef5c65a0c41b53d` (unchanged)
- `core/decision_evidence.py`: `899659e6060822e6abf31c25ca3624066633527beb20a5883560a64ee29e2295` (unchanged)
- `core/env_adapters/libero_adapter.py`: `22e8be88e1a68bcffdd72536b79e7f9e4d56efdc0b12b5a0c3fb1c7877930c64` (unchanged)
- `main.py`: `431b0f04f0e5e3b8d8bef9eb83516c5a80f20b7be407014970b75217192f27db` (unchanged)
- `configs/config.yaml`: `36d9f4d1499da67e059ad943d3b3fec47de6cc6520835aa76897ecec3ad0801d` (unchanged)
- `core/qd_ed.py`: `6f13929fd816e8ccc524726b91af4e84da425d3c840c1bfb7438a2a1acf7eb4c` (unchanged)
- `core/rdt_policy_steer.py`: `e22b6f096421b13f9e1c69955bfcac488f9e5a73ad0ff017e8ac3b5c82a2c5f5` (unchanged)
- `scripts/audit_decision_evidence.py`: `01b2c293677529ebc3bd6201903f4962786104050253d108e194b731a5b47d55` (unchanged)
- `scripts/qd_ed_n31_reference.py`: `6cda9a87566ec4e7dfae301fbf9c618d6d8fc0872ee4f8dbd46179ccaea580c2` (unchanged)

Final evidence: **22 passed**, 22 warnings, 88.17s; **159 rejected corruptions**, 30 per terminated-prefix case and 23 per truncated-prefix case. Final log SHA-256: `bfce000168faaea806f79d5171282fd779fef31db94ac0b0800f1900d8bbb10d`. Both original blocker reproductions pass within that run. No broad suite was repeated.

Additional targeted fixture: **1 passed**, 1 warning, 6.84s. Three valid termination/success/truncation combinations accepted; five ordering/epoch/outcome faults rejected. [Fixture](test_delta_edges.py), SHA-256 `677ee9112a81856747b9b0668822921ddcf02c330244f267b63099a29deb7562`; [log](test-delta-edges-v1.log), SHA-256 `c0f761520d7b2fba6ab77ee0722105762f662a101417e2be4d0820bd1d4bbffd`.

```sh
env CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=.:tests /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -q -s -p no:cacheprovider --basetemp=/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000910/n35-audit-repair-review/fixtures-delta-edges /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000910/n35-audit-repair-review/test_delta_edges.py
```

**Semantic checks.**

- Termination prefixes 1, 4, 8: outcome/automatic-reset epochs 0,0 then return/ack/reset epochs 1,1,1; exactly one terminal reset and no completed token.
- Truncation prefixes 1, 4, 8: no automatic reset and all four terminal events retain epoch 0; exactly one terminal reset and no completed token.
- Missing/duplicate/misplaced automatic reset, automatic-reset identity/metadata corruption and premature event epochs reject; missing/extra/initial epoch offsets separately rejected.
- Missing/duplicate/misplaced memory reset, wrong reason, episode/decision/step/epoch mismatch, reset without terminal acknowledgement, and stream ending with obligation reject.
- Guided returns require adjacent acknowledgements with matching identity, decoded action, execution index and terminal flags; missing trigger measurements remain ineligible and valid, and unguided gaps retain reset behavior.
- No legitimate event intervenes in the frozen N35 path: adapter reset emits no additional evidence; Main records return then acknowledges immediately; memory emits acknowledgement then reset synchronously. Recorder is created per episode at epoch zero (main.py:1100-1111).
- Generic audit remains mandatory and unchanged: contiguous event sequences, dispatch/action/outcome linkage, no dispatch after episode end and complete executed prefixes (scripts/audit_decision_evidence.py:59,1242-1277). Native lifecycle is a composed audit, not a standalone substitute for generic validation.

**Limitations.**

- Delta review only: prior implementation review read for blockers and obligations; no recursive rebuild of older provenance or broad suite repeat. Authority digest computed locally because caller supplied no external expected authority digest.
- Existing final 22-case evidence is hash-verified, not rerun. It includes six parametrized prefix cases with 159 corruptions, 13 integration cases, one N35 worker case and two original reproductions. Earlier 61-case and four-arm results precede final adjacency hardening and are supporting evidence only.
- Synthetic model/observations and actual recorder/memory helpers; Main hooks statically traced and prior CPU Main tests inspected. No native simulator, live model/provider, installed runtime, controller or GPU execution proven.
- Same-process worker test stubs Main execution, dispatch/source/runtime/controller attestation and CUDA identity (tests/test_n35_production.py:106-129). CPU acceptance cannot certify installation or release readiness.
- Source-bound native GPU cell assignments and other15 commitments remain trusted recorded inputs; CPU tests do not rerun GPU arithmetic or establish scientific efficacy.
- Initial epoch zero is appropriate to the full per-episode recorder stream. Filtered/suffix-only event streams are not accepted audit inputs. Generic audit continues to enforce contiguous sequences and episode completion.
- Pre-existing core/fkd_class.py:39 invalid-escape SyntaxWarning remains outside this delta.
- Ledger prefixes were byte-hashed only; protected outcome records were not interpreted and balances were not adopted or recomputed.

**Remaining obligations; no authorization supplied by this PASS.**

- Before any later root release, separately adopt exact reviewed source, materialize pinned dependencies and prove installed runtime/provider/controller/source closure. CPU synthetic fixtures and --help imports are not that proof.
- Reconcile owning attempt, healthcheck and reservation prefixes and protected balances against both cumulative caps; retain full1840-second atomic admission and bounded separate health preparation. This review performs no state or ledger adoption.
- Revalidate source-bound CUDA/EGL evidence after the probe/queue source hash changes. Any newly required preparation needs its own applicable authority and accounting; this report supplies none.
- Freeze all40 fresh manifests and detached root execution release only after implementation acceptance. Report trigger exclusions, creation/consumption/expiry/reset, native versus decoded deltas including zero, archive survival, direct selected origins and actual execution separately from task success.
- All40 valid and N35>=5 and >=each control remain necessary Dev conditions only. Independent scientific/mechanism review and separately frozen validation/formal authority remain required; no benchmark score, efficacy or promotion is established here.

Source read-only; only review artifacts and CPU fixtures written in the authorized directory. No commits, adoption, state/ledger/resource changes, GPU query/episode, native simulator, protected evaluation access, external messages, delegation, credentials, alternate provider/account, disabled skills or prohibited document access. GPU authorization, installed-runtime proof, scientific promotion and target-met remain false.

Machine-readable report: [report-v1.json](report-v1.json).
