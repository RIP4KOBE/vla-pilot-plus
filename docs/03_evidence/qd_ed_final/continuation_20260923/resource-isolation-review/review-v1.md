# Read-only resource ownership partition review

Snapshot: **2026-09-24 07:32:16.581089 UTC**. This review does not migrate journals, release a GPU, change budgets, or assess scientific outcomes. User-authorized future caps reported by the root coordinator are W/N4 **240 attempts / 48 GPU-hours** and X/GPU2 **250 attempts / 48 GPU-hours**, independently accounted with each side's attributed history retained. This document does not infer extra allocation from concurrency alone.

W is `/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z`; its artifact root is `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z`. X is `/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z`; its artifact root is `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z`.

## Result

Every attempt/health resource group has one consistent, exact artifact-root owner. There are **zero unknown/conflicting owners, duplicate group output directories, or cross-ledger duplicate IDs**. All source/plan/runtime/GPU resource fields present within a group are stable. All event sequences conform to the original resource lifecycle. Classification does not use task success, outcome validity, retry eligibility, metrics, or scientific narratives.

| Resource quantity | W | X | Shared snapshot |
|---|---:|---:|---:|
| Dispatched attempt groups | 75 | 41 | 116 |
| Terminal attempt groups with settled time | 75 | 40 | 115 |
| Unsettled attempt groups | 0 | 1 | 1 |
| Attempt journal events | 225 | 122 | 347 |
| Settled health resource groups | 17 | 5 | 22 |
| Health journal events | 51 | 15 | 66 |
| Attempt seconds | 37603.100030797207857 | 19670.891586554598710 | 57273.991617351806567 |
| Health seconds | 754.614483984692477 | 182.308608273009214 | 936.923092257701691 |
| Combined settled seconds | 38357.714514781900334 | 19853.200194827607924 | 58210.914709609508258 |
| Combined settled GPU-hours, rounded | 10.654920698551 | 5.514777831897 | 16.169698530447 |

The reservation ledger is empty: zero bytes/events. The two nonempty ledgers contain 413 resource events altogether. All 11 count/time conservation assertions pass. Decimal sums preserve the stored duration literals; they do not assert more timing accuracy than the original process wall-time accounting. A resource-only replay of the original W `event_groups` and `budget_snapshot` functions matches the shared float hours within 1e-10. No original outcome values were supplied to that replay, and its outcome counters are intentionally discarded.

| Original attempt bucket | W dispatched | X dispatched | W settled seconds | X settled seconds |
|---|---:|---:|---:|---:|
| baseline | 13 | 0 | 4853.731713943852880 | 0 |
| development | 56 | 40 | 29626.812214885985301 | 19538.240969421704010 |
| recovery | 6 | 1 | 3122.556101967369676 | 132.650617132894700 |

Health time is additionally charged to recovery hours under the unchanged source accounting; health resources consume no episode-attempt slots. Existing bucket assignments must be retained rather than relabeled to create capacity. No validation/formal resource groups occur in this snapshot.

The unsettled X group is `rdt-qd-ed-final-20260921T093925Z__n1w_dev_t00_q0__78b926984be3`. Its dispatched slot is counted, but terminal GPU time is **Unknown**, not zero. The snapshot totals are settled subtotals, not final migration balances. Wait for the running episode's natural terminal and quiescent writers, then take a new locked snapshot. Do not terminate it, cut its group, or transfer only its current prefix under this review.

## Ownership rule and byte preservation

1. Use `(ledger kind, immutable attempt_id/resource_id)` to collect every event of a resource group. The identifier identifies the group but its textual prefix does not assign the owner.
2. Require every group's `output_dir` to be an absolute path without `..`, anchored under exactly one declared run artifact root. Require consistency across all group events. Check existing source/plan/runtime/GPU attribution fields for contradictions; an ID/source name/GPU index alone cannot overrule an exact output-root conflict.
3. Retain the original bucket and time of every terminal, regardless of scientific status. Assign every original group exactly once; preserve its original ID. If path ownership is absent or conflicts with independently established source/plan ownership, quarantine as Unknown for explicit adjudication; never default it to W or use experiment results to choose.
4. Filter original raw JSONL lines by whole-group owner **in original file order**, preserving every byte, including newlines. Do not serialize projected resource dictionaries back into replacement journals. Keep the original shared snapshot immutable. Store source snapshot SHA, line offset/length/SHA, owner/group mapping, and expected partition SHA so that re-interleaving by original line number reconstructs the exact original snapshot.
5. Verify disjoint group sets, total coverage, byte lengths, event counts, bucket counts, settled duration sums, and resource proof membership before switching local writers. Recheck at the final quiet cutover; the present 1-inflight snapshot is evidence for planning, not executable migration input.

**All 41 X attempt IDs and all 5 X health IDs retain the W run-ID prefix.** For example, `...__gpu6_native_c0_t00__6e57273c45b3` belongs to X through its original X output path. Group history spans physical GPUs 6/5/2; GPU number is not the accounting owner. No ambiguity remains after output-root attribution in this snapshot. Source/plan hashes are retained as provenance, not reinterpreted as scientific identity or results.

## Health proof membership and shared engineering references

Current necessary proof IDs are already owned by their respective journals:

| Consumer | Required resource suffix | Charged owner |
|---|---|---|
| W runtime + N4 `health_resources` | `gpu3_cuda_egl__060fecd66f77` | W |
| W N4 `health_resources` | `gpu3_freshboot_model_first__be47760b9287` | W |
| X current runtime | `gpu2_cuda_egl__ca0a661d87c1` | X |

All are settled groups in this snapshot. W's five runtime-prerequisite path references also stay under W's artifact root. Only their metadata paths/hashes were examined; referenced result files, proof images, or native data were not opened. This verifies ownership/membership, not current GPU health or semantic validity of an old proof.

Source constraints matter:

- W `scripts/qd_ed_n4_plan.py:253–258` requires explicit `health_resources` attribution of the runtime proof. Lines 434–439 require every declared proof group to exist terminally in the locally supplied resource events. `reused_prior` avoids adding it again to the local N4 allowance, while global history is still charged once by `budget_snapshot`.
- W `scripts/qd_ed_available_gpu_queue.py:221–245` and X's same file at 222–249 first require the referenced resource ID in the supplied health journal, then verify source-script SHA, device mapping and evidence beneath `runtime.artifact_root`. X additionally checks current boot at 242–244. `find_probe` only considers matching worktree/artifact-root manifests (W 248–265; X 252–269).
- X `scripts/qd_ed_n1v_supervise.py:119–127` passes its local health ledger and requires the approved GPU2 proof. Therefore a detached proof file alone is not accepted by the existing code.
- W `scripts/qd_ed_final_runner.py:618–659` and X 675–717 charge each terminal health group exactly once. Copying one charged group into both future ledgers would double-charge the combined history. A genuinely cross-side engineering proof would need an explicit, prospective, zero-charge reference design distinct from cost events if existing checks require it. **No such cross-side copy is necessary for the current required proof IDs.**

X `scripts/qd_ed_available_gpu_queue.py:283–303` also enforces, when `execution_migration.same_study_budget` is true, that the three ledgers and two locks are symlinks to the declared shared root before refreshing cached state. A safe future separation must update the shared-migration contract and local state/lock bindings together; changing only links would trip this source guard. The present audit neither reads cached scientific state nor changes that contract.

## Exact snapshot evidence

| Ledger | Snapshot SHA256 | Bytes |
|---|---|---:|
| attempt-ledger.jsonl | `15de3f53501161e47e5267d84314fedc4f27d8593d757daf3f7d297a4f4265fc` | 1443638 |
| gpu-healthcheck-ledger.jsonl | `6494a93c4a36da0b4202aa82ccf6a746613f4ad0723eddf6594c128558bb77e7` | 66268 |
| gpu-hour-reservation-ledger.jsonl | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 |

`snapshot-v1.json` contains all 413 raw-line byte references, 138 resource-group records, virtual partition hashes and exact Decimal totals (SHA `ad563e5dda37ab1c3c59edf8a89cf775489c92da0967dba81e34e5bb586e2838`). It does not contain scientific outcome fields. `proof-and-source-review-v1.json` binds the four exact current runtime/plan metadata files and six inspected source files (SHA `ed3ec60aa5c6edcf81d3cc00a64d772c78aba35619cfaf9d567a6671e43d8dc3`). The self-contained, standard-library-only audit script SHA is `238cce531fd856b41a10f59d11cc8e970bb3797fb97d0e01339ebe384ebd48d8`; its sole execution wrote this report directory and exited 0.

No source, ledger, state, budget, symlink, lock, GPU process, proof, or external branch file was modified. Only this isolated review directory was created. No scientific payload/outcome analysis, credentials, model/provider call, simulator, GPU enumeration, or new health test was performed.
