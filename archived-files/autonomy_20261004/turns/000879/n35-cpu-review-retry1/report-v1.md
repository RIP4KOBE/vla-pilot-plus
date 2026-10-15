# N35 independent CPU feasibility review — existing node15.5

**Verdict: FEASIBLE_CPU_ONLY.** All four frozen eligibility gates pass for Dev task6 boundary544. This is a bounded evidence and production-hook review, not an implementation or efficacy result.

HEAD before/after: `969d5fb57c90f61dfc93331346f0ea8158f4eaf1`. Source remained read-only. CPU tensor inspection used at most two threads; no network, GPU, model calls, benchmark, delegation, state/ledger/lock writes or commits. All generated artifacts are in this report directory.

| Gate | Result | Evidence |
|---|---|---|
| (a) Guided536, direct selected observed_close_dwell | PASS | Guidance true; iteration0 slot15 candidate and final selected native tensor are byte-identical. Selected canonical fingerprint `a251e09e30e8af609be5f4cee561f512fc78e813ef7ff3f45d37ff680fb57ab1`; direct content, not ancestry. |
| (b) Eight identity-linked positive executed commands | PASS | Steps536–543, execution indices1–8, decision `e0:d68:s536`; all gripper +1 and all seven action components exactly equal corresponding decoded rows. Decode-selected tensor matches final selection. Each step returned with terminated=false/truncated=false. |
| (c) Same recognized target/Stage, guidance544 | PASS | Target0, Stage1, episode0, tracker instance135739403876448/generation1, tracked status and provider identity unchanged; guidance true at536 and544; previous decision at544 explicitly links536. |
| (d) Finite strict measured jaw decrease | PASS | qpos separation (qpos[0]−qpos[1]) 0.07847506989516687 → 0.021828545780436356 m; decrease 0.05664652411473051 m. No grasp inference. |

The first ordinary archive best at544 is initial canonical row8, cell14, source iteration−1, insert sequence10, reward −0.00104522705078125. Reordering all12 entries in the bound initial archive snapshot by production global-best ordering confirms this source. Snapshot event78550 and opportunity event78818 are in `bundle_001701.pt`.

A CPU-only copy changes precisely coordinates [0:8,10] of the bfloat16 [64,128] template to native +1. Native values before: `[0.98828125, 0.98828125, 0.984375, 0.984375, 0.984375, 0.9921875, 0.9921875, 0.9921875]`. Translation/rotation channels39:45, every later action, and all other coordinates remain identical. Raw contiguous byte SHA256:

- Original: `ec743f3fb841779e17b0290d979d9fdf4777dcea2449bae1df7693ebc4a76422`
- Copy: `26b69ae5afa5d12e863f404cf3c5d274c9b52e2f6893e7f859b6b10e67cf2225`

These raw-byte hashes exclude dtype/shape metadata and differ from production native_identity hashes. The original eight gripper values already decode to +1. The frozen native-byte requirement passes; decoded action novelty is not established.

Production hook findings:

- FEASIBLE_SOURCE_HOOK: ObservedJawDecision.prepare reuses CaptureDwellDecision.prepare to select current archive global best and bind exact native canonical occurrence, reward, cost, fingerprint and source iteration. Boundary544 first parent round is uniquely bound to initial row8, cell14; independently recomputed archive ordering agrees. Source: `core/qd_observed_jaw_approach.py:144`, `core/qd_capture_dwell.py:221`, `core/qd_ed.py:648`.

- FEASIBLE_SOURCE_HOOK: Ten prepare/apply rounds occur per boundary; pending is consumed once per apply and close requires 11 canonical batches and 10 opportunities. A cross-boundary memory must be transferred/consumed once into the boundary-local decision before these rounds. Keep the eligibility latch immutable through this boundary; each round uses its current archive best in the existing slot15. Clearing the latch in the first apply would incorrectly change later rounds to the N34 fallback. No token survives boundary close, selection failure or exception. Source: `core/rdt_policy_steer.py:5770`, `core/qd_capture_dwell.py:257`, `core/qd_capture_dwell.py:290`.

- FEASIBLE_SOURCE_HOOK: Both ordinary and RBF rollout paths apply one replacement after denoising and before existing score call. Population remains [16,64,128]; apply clones population and assigns only row15. Candidate clone with [:8,10]=native+1 requires no model, rescore, additional candidate or change to ordinary quality/archive/ED. Other15 means untouched at the replacement operation; future parent allocations may change through ordinary competition. Source: `core/rdt_policy_steer.py:3783`, `core/rdt_policy_steer.py:4139`, `core/qd_capture_dwell.py:257`.

- REQUIRES_FUTURE_IMPLEMENTATION: N34 is decision-local and has no closure-intent execution history. Hook selected-native/direct-proposal identity before close, bind decoded/committed eight-action prefix, and acknowledge actual adapter commands only after each step returns. Existing adapter postprocessed action_numpy and main return path provide actual command and completion locations. Existing N30/feedback helpers demonstrate lifecycle locations but are mode-gated off in this configuration and cannot be assumed active or enabled by changing quality mode. Source: `main.py:1840`, `main.py:1950`, `main.py:2157`, `core/env_adapters/libero_adapter.py:1704`, `core/rdt_policy_steer.py:1683`, `core/rdt_policy_steer.py:5125`.

- REQUIRES_FUTURE_IMPLEMENTATION: Store a separate minimal completed-execution token (not a replay trajectory) with episode, stage, recognized target/provider/tracker identity, direct observed_close_dwell origin, selected native identity, exact execution count and initial jaw measurement. Require consecutive full execution and finite next-boundary jaw decrease. Clear on episode/stage/target change, guidance gap, incomplete execution and completion/exception of eligible boundary. Existing reset and sampling entry points are suitable; N34 itself does not implement these guards. Source: `core/rdt_policy_steer.py:1432`, `core/rdt_policy_steer.py:1474`, `core/rdt_policy_steer.py:1625`, `core/rdt_policy_steer.py:7620`.

- REQUIRES_FUTURE_IMPLEMENTATION: Memory-produced candidates require explicit origin provenance. Arm only from direct selected observed_close_dwell origin with full executed prefix; deny arming from memory-generated closure, including ambiguous equal-content origin. Positive executed commands or jaw motion alone never arm memory. Preserve origin outside the decision-local cache before close clears it. When memory eligibility is false use existing N34 fallback in the same slot; no extra proposal or forced execution. Source: `core/qd_observed_jaw_approach.py:144`, `core/rdt_policy_steer.py:1683`, `core/rdt_policy_steer.py:7620`.

- NOT_EXECUTED: No N35 implementation, production integration test, model execution, benchmark, GPU work or prospective Dev protocol was performed. Hook feasibility is source analysis only.

The contract’s single-use memory is interpreted as consumption by one boundary. A boundary-local latch may supply the existing slot in all ten parent rounds, with the current best re-read each round. Per-round pending consumption is separate from boundary consumption. No extra slot or model call is needed. This is a review of a feasible future hook, not proof of implemented lifecycle behavior.

Evidence SHA256 references:

- contract: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000878/n35-cpu-hypothesis-v1.md` — `7c2ac4588bdccd21290c8aef88cfafcdd9a80accf715129668cf2d9c04fe855a`
- bound_review: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000877/native-mechanism-review-v1.json` — `134b51bb00b415bb7ca4af716d67ff9b6df5548f4d84f3d95cce7e167ca48a05`
- extraction: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000877/native-mechanism-extraction-v1.json` — `28be4784c2bb4f78c7dba500fba6c5da4c1625b5f697f8b82ae0dd0a594f1401`
- extractor: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000877/extract.py` — `5415152485ca82acb8f89f37c0f51bcbca440706a8bd4e8a261a48f0f1c427a1`

Native bundle references, per-event sequence/decision IDs, exact gate values, source hashes (all seven inspected production files match the bound event hashes), and review-script references are in [report-v1.json](report-v1.json) and [bounded-facts-v1.json](bounded-facts-v1.json).

Unresolved evidence and limitations:

- CPU feasibility does not establish grasp, contact, selection probability, task gain or efficacy. No success claim is made.
- The first-round template already decodes all eight gripper commands to +1. Native-byte nonidentity passes the frozen requirement but does not establish a decoded action difference from that template.
- No counterfactual later parent rounds were executed. Current archive best after an inserted N35 proposal cannot be inferred from this N34 trace; the source loop supplies it at runtime.
- Boundary-scoped consumption, reset/exception cleanup, origin guards and execution acknowledgements require separately authorized implementation and verification. Existing N34 code does not already enforce N35 state semantics.
- Repeated rounds are interpreted as ten existing opportunities within one consumed boundary, with no latch refresh or next-boundary persistence. This interpretation must be recorded in the separate frozen prospective implementation/Dev protocol.
- No missing mandatory trigger fields remained for this bound boundary. Feasibility beyond the exact task6 boundary544 is not evaluated.
- Current-login official gpt-6-astra is the user-authorized reviewer requirement. No external model, credential or login attestation was queried; runtime model/login identity is not independently certified by these artifacts.

**No implementation or GPU authorization follows from this verdict. A separate frozen prospective Dev protocol and review remains required before either.**
