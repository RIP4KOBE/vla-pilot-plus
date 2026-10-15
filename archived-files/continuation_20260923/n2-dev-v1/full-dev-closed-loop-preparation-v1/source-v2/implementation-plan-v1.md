# Minimal implementation plan — no code or execution yet

Scope is `protocol-draft-v1.md`. Prepare one new isolated reader, one synthetic test file and a source/input manifest schema only after root reviews this draft. Do not edit the frozen task0 helper or reuse its old authorization as permission for more episodes. Do not add a production hook, acceptance gate, target map, quality computation, generic analysis framework or automatic watcher.

## Existing capability to reuse

The frozen task0 reader `read_closed_loop.py` SHA `1212c3c9675403dc0e8f3b97948ab8d6d9a5f873ccfa615564041da3fe5c309f` already provides pure CPU `actual_steps` (lines134–154), `tensor_record` (66–67), `provider_signature` (86–89), `sign_runs` (157–167), and `motion_summary` (170–189). Import it only after byte-hash verification; importing the module does not call its `run` entrypoint. Retain it as a separately frozen dependency. Reuse these functions rather than rewriting command/observation extraction or EEF distance arithmetic.

Do **not** call or monkey-patch its task0-specific `run`: IDs, authorization hash, three-episode count and task0 seed are deliberately fixed (lines20–28, 260–305). Do not run the two old formatting scripts, which have top-level task0 file reads/writes. The existing `describe_stage_associations.py` is source reference for an exact-value join only; its asserted unique predecessor is too strong for generic step-zero/reset/partial-prefix cases and must become explicit association status in the new thin reducer. `summarize_decisions` can be reused on verified nonempty contiguous reset segments, or replaced only by a small chronology reducer that delegates motion/sign arithmetic to the frozen helpers; do not bridge reset boundaries or silently drop zero-action decisions. No call to `selected_quality`, `keypoint_link` or any scoring helper is needed.

## Five bounded implementation steps

1. **Explicit membership/entry.** New manifest schema binds the reviewed complete matrix report, its original/revision plans and source definitions, new protocol/reader/test hashes, frozen task0 helper and exact auditor bytes. Compare exactly 30 listed representatives to the matrix's valid IDs and full identities; preserve accepted recovery links. Reject extra/duplicate/missing cells or unlisted roots before any bundle opens. The matrix remains success/cost authority. Do not derive another numerical pass criterion.
2. **Reuse the existing audited CPU loading path.** Verify each named terminal, accepted original audit/compute/metadata, collector status/index and each SHA before decoding. Reuse the frozen auditor's `audit_episode` once per admitted cell, storing its new read-only verification separately. Stream bundles and release candidate-heavy payloads; retain only allowed decision/action/reset fields. Record the CPU audit/extraction latency separately, not as new GPU/episode cost. Check CUDA remains uninitialized. Hash inputs again before successful final publication.
3. **Thin full-chronology reducer.** Feed actual action events to `actual_steps`; retain original native dtype/shape/sequence. Keep reset boundaries/terminal flags explicitly. Build actual-guidance coverage and contiguous runs, all ON/OFF transitions and first/last endpoints. Reuse motion/sign functions with separate EEF/qpos/sign interval labels. Stage events remain allowlisted and ordered; classify exact same-step/current-state and preceding-prefix first/last sent-command associations without asserting every event has a predecessor. Keep ambiguous/missing joins and all events. No fresh scoring/projection/keypoint analysis.
4. **Uniform outputs.** Use a new schema, e.g. `n2-dev-closed-loop-chronology-v1`, with `matrix_authority`, `authorization`, `source_bindings`, `task0_previously_exposed=true`, and 30 fixed-order `cells`. Each cell has identity/attempt/retry/report references, decisions, actual steps, Stage events/associations, runs, transitions, coverage, motion interval provenance and Unknown reasons. Write `inputs-and-audit.json`, one chronological JSON per cell, an index JSON and a concise 30-row Markdown overview. Keep all details accessible; no hand-written selection of only favorable examples. Outputs are newly created, never replacements.
5. **Freeze before new reads.** Review code and targeted synthetic tests, then freeze source/test/protocol/dependency hashes. Root separately names all30 eligible representatives and authorizes actual CPU execution. Missing or corrupted chronology yields descriptive `complete=false` with the original task outcome untouched. No data-dependent patch/retry is silently applied; no execution occurs during this preparation.

## Minimal synthetic boundary tests

Use tiny CPU tensors and temporary local fake files; no original episode data, provider/model/projector, simulator or GPU:

- **Membership and recovery:** immutable original 30-cell plan plus separately bound recovery revision; exactly one representative per cell and both original/recovery references preserved. Reject partial29, duplicate/extra cell, invalid/rejected audit and unrelated roots before any bundle load. Changed source/hash rejects even with matching task/arm labels.
- **Complete chronology, no switch and repeated switches:** initial OFF, initial ON with no switch, ON→OFF→ON→OFF plus unchanged Stage queries, zero-action decision and success inside a short terminal prefix. Coverage counts actual actions, never eight per decision or a fixed720; every event/decision survives. All OFF→ON are retained; absence of a transition is not step0. An N2 episode with recorded unsupported-provider fallback remains included without inventing quality/applicability values or an activation gate.
- **Stage association edge cases:** event step0, unique preceding chunk with different first/last sent values, partial preceding prefix, gap/reset, no matching decision and multiple matching structured events. Exact comparisons can yield both/neither/Unknown. Query success/error/skipped-limit and absent/empty event files remain distinct; no free-text payload escapes the allowlist.
- **Reset and interval arithmetic:** pre-reset terminal EEF differs sharply from returned reset observation; helper must retain the former and never include a cross-reset edge. An initial origin is missing; another run has a valid prior post-action origin. Assert explicit edge count, qpos's different start step and exclusion of a boundary command flip from within-run sign changes. Optional missing/incompatible finger fields produce named Unknown, not zeros.
- **Precision, scope and determinism:** BF16/FP32/FP64 values retain truthful native dtype/shape; sent-action finite checks use actual commands. Sentinel candidate/keypoint/projection fields are not analyzed/exported. Trap forbidden file opens, old task0 `run`/formatter execution and CUDA/model/provider calls. Reordering the manifest cannot change frozen cell order or permit row selection; changed bundle bytes or unfinished output never produce complete status.

These tests are planned, not run. They validate reader boundaries, not manipulation performance, causal hypotheses or native runtime behavior. Broad project regression or GPU equivalence testing is unnecessary for this offline documentation stage.

## Read context and hashes

Paths below are relative to `A/continuation_20260923`, where `A=/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z`.

| Source/context read during preparation | SHA-256 |
| --- | --- |
| `n2-matrix-report/source-v1/summarize_matrix.py` | `8299647ed0ec904e230058a96a8d0b2d2714e2a3879341ea6917416093c3dfe2` |
| `n2-matrix-report/source-v1/protocol.md` | `5ff1478eec7a9d8e1e7fb0914d762bacd86195125ff863a7c918f533c225417c` |
| `n2-dev-v1/explanatory-read-v1/read_closed_loop.py` | `1212c3c9675403dc0e8f3b97948ab8d6d9a5f873ccfa615564041da3fe5c309f` |
| `n2-dev-v1/explanatory-read-v1/freeze-v1.json` (identity/hash only) | `5c6cfed4eb2286b3ca2494e189aeb3dc6f31af0cd4ec2ce120cea2aab55adec1` |
| `n2-dev-v1/explanatory-preparation-v1/read-protocol-v2.md` | `97a5a46ead5b91a8da3e5171b91ead6061cc89fe54433804e2e1f7ccdfa7f127` |
| `n2-dev-v1/explanatory-read-v1/output-v1/findings-v3.md` (already-exposed task0 context) | `e1b7fb423ad2733a838bc775b0b5d903ddfcf3d2e5e06cd60373e6fc70bece96` |
| `n2-dev-v1/explanatory-read-v1/describe_stage_associations.py` (source only, not executed) | `9710322a2bc0fd8345b2ed92d1dc2418bf386486641080d025eedea633d0f596` |

Only allowed source/protocol and the existing task0 findings were inspected. No task1–9 episode artifacts, current live outcomes, external scientific results, protected old design file, credentials, validation/formal outcomes or tensor bundles were read. No analysis code, scientific output, test run, model/provider call or GPU action was created by this preparation. W remains untouched; these two draft documents occupy their own E directory.
