# Future immutable-cache integration: static design

A narrow future pilot is feasible through an existing dependency-injection boundary. **Defer all integration until N26 has closed**, and then consider only cached historical object bytes in the common reader. Do not refactor the provenance system, cache whole validation results, or change the worker as part of this pilot. Actual benefit is unmeasured.

This design inspected the exact 11 allowlisted source files (264,450 bytes), the eight accepted cache-delivery files, and the prior static report/index. Source sizes and hashes were verified before semantic inspection. No production imports/execution, tests, Git/history reads, runtime/experiment records, process inspection, network or GPU/API/model/simulator calls occurred. The source inventory is `source-scope-v1.json`; no embedded artifact references were followed.

## Exact boundary and minimal change

The existing [common reader](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation/scripts/qd_ed_n25_cont_downstream.py:154) accepts `build(data, objects=None, ...)`. Line 166 constructs a fresh `GitObjects(owner)` when no reader is supplied. Its [GitObjects implementation](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation/scripts/qd_ed_n25_cont_downstream.py:34) already caches within one build, but every default build starts a new cache. Lines 43–47 run a size command and then a blob command for each miss. The blob's `check_output` allocation precedes its length check; copying this loader unchanged would not meet the new component's bounded-callback requirement.

The narrow insertion is the [logical gate's line 56](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation/scripts/qd_ed_n26_logical.py:56): provide an explicitly constructed objects facade to `common.build(data, objects=facade)`. Keep the common module and its entire historical/live checking body byte-identical.

Prospective source delta, subject to separate authorization:

- Add a tracked, byte-identical copy of the accepted `verified_immutable_cache.py` and one small owning-source adapter module.
- Add one finite, reviewed historical-object inventory, then bind it and the two modules into the future source closure. A filename alone or a caller-supplied digest without a trusted review is insufficient.
- Change that single common-build call to inject the facade; extend the caller's explicit source-file set. Revise the future source bridge/review to disclose these administrative changes, without modifying science or relabeling old proofs.

No change to common `GitObjects`, `historical_sources`, historical helpers, runner dispatch primitives, worker, numerical audits or current N26 contracts is proposed. The adapter must use ordinary arguments, not monkeypatch globals or replace function implementations.

The facade preserves the old `__call__(commit,path)` / `authorize(pairs)` interface. Each build gets a new small facade initialized with only the bootstrap permission; all facades in the same controller process share one verified-byte cache. `authorize` may enable only already-inventoried identities and must be finitely bounded; it must never add keys to the cache's trusted allowlist. The facade remains truthy so the existing `objects or GitObjects(owner)` expression does not silently fall back.

Other repeated historical reads remain deliberately untouched:

| Boundary | Work left unchanged in the first pilot |
|---|---|
| `qd_ed_n26_logical.py:129–158` | Accepted c09/common ff composition and current-byte/reverse comparisons; its direct historical reads at line 139 |
| `qd_ed_n26_bridge.py:21–96` | Phase-A historical routes, exact reverse restoration and original N25 proof-source reads |
| `qd_ed_n23_worker.py:54–73` | Fresh HEAD, current source/link checks and worker/receipt source verification |
| `qd_ed_final_runner.py:157–170` | Existing stat-bound current-file digest cache, unchanged |

This limited reach avoids editing historical modules whose exact bytes are themselves checked. It will not eliminate all repeated Git or AST work.

## Trusted inventory and bounded loader

The [historical reader](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation/scripts/qd_ed_n25_cont_downstream.py:52) first reads the 6f bootstrap object `experiments/qd_ed_n25_continuation/original-source-v1.json`. It then validates 257 original and 271 continuation manifest entries and authorizes their commit/path pairs. Each existing entry contains exactly `path` and `sha256`, **not size**. The bootstrap path belongs to the continuation closure; a reviewed complete union would nominally contain 528 commit/path identities. This is a source-derived expected count, not an enumeration or size measurement performed here.

A future root-authorized, bounded metadata-only preparation must supply the missing inventory. For every pair, bind repository identity, full exact commit, relative path, expected SHA-256, declared byte size and verifier/source-bridge version. Preserve existing trusted source-manifest references and bootstrap/hash associations. Independently confirm closure membership, uniqueness and every declared size/hash; do not learn the allowlist opportunistically during admission or accept the first observed bytes as authority.

The inventory needs its own reviewed hash and must be included in the future source/review chain. The adapter checks that hash and schema on every factory call, although its verified bytes may then be served from memory. A new version/digest is a new cache identity, not permission to mutate an existing instance.

Bind the exact owning study root and a reviewed canonical Git/common-directory identity and object format. Validate those bindings fresh when supplying a facade; never derive repository identity merely from a mutable branch, an environment variable, or the requested historical object. Original exact commit IDs remain keys. Current HEAD stays a fresh original check and is not resolved or remembered by this cache. The eleven-file scope shows the owning-root constraints but does not contain a complete prospective Git-directory identity record; none is fabricated here.

Before any loader callback, the accepted component checks declared object and remaining retained-byte capacity. The prospective loader must separately:

1. Validate the exact pair against the trusted inventory and use argument-vector execution, never a shell.
2. Bound any Git size/header output, stderr and wall time before accumulation; compare reported size against the declared size and the 1 MiB object cap.
3. Read blob stdout incrementally with a hard declared-size-plus-one sentinel bound, a small fixed stderr cap and a deadline. On excess output, timeout or malformed output, terminate/reap its own CPU child and fail. Do not use unbounded `check_output` or `communicate` capture and only inspect size afterwards.
4. Return exact `bytes` only after successful bounded completion; the component independently checks actual length/SHA before retention.

The new cache's hard maxima remain 2,048 entries, 1 MiB/object and 64 MiB retained. Whether all historical objects fit is **Unknown within this scope**. The old reader permits 16 MiB/object and 128 MiB/build, so source inspection does not establish compatibility with the tighter cap. If the inventory exceeds the accepted limits, stop this pilot and review alternatives separately; do not silently enlarge limits, evict entries, expand the allowlist or fall back to the old unbounded loader.

## Lifetime, failures and semantic boundary

Use one cache per controller process and exact reviewed inventory/repository/verifier identity, with a fresh authorization facade per build. Nested metadata/authority/bridge calls and later episode admissions in that process can hit it. Separate root CLI, supervisor and worker processes each start cold; there is no disk cache, cross-process sharing, fork-inherited cache authority or promised cross-process reuse.

Every request still runs common's original SHA/byte/AST comparisons and current-state checks. Only repeated historical byte acquisition changes. Hash/size mismatch, unknown pair, capacity refusal, reentry/concurrency, malformed inventory, repository drift or a loader failure stops admission. Failures are not cached. A later separately permitted call can retry the same verified key, but the adapter does not automatically retry or resume an experiment. An identity/version change discards the process cache; it never silently rekeys existing entries.

A warm cache attests previously verified immutable bytes. It does **not** assert that a Git object is still readable from disk at that instant. Whether instantaneous historical-object availability is itself a required dispatch predicate is not specified by the inspected interface; root must resolve that semantics before integration. If continuous availability is required, it must remain a fresh explicit check, and the expected benefit may shrink. This distinction does not affect the existing historical-artifact absence checks, which remain live.

## Live checks retained at every original boundary

Retain all existing call ordering and locks. Do not cache `common.build`, `read_gate`, `final_review`, `validate_plan`, `authority`, `full_capacity` or any Boolean admission result.

- Current working files, HEAD, source membership, resolved paths, imported helper identity, protocol/review/authority hashes and source-equivalence assumptions remain freshly checked. Common's helper-byte comparisons at lines 78–83 remain active even on historical-byte hits.
- Common's original absence checks and process cleanup at line 174 remain active. `qd_ed_n25_cont_evidence.py:55–84` must still reject delayed audit files, links, surviving process identities/groups and owned commands.
- `logical.current_matching:75–83` still verifies the relevant current journal/resource subsets. Historical projection hashes do not replace current matching-event checks or proof settlement.
- Current adoption, locks, holds, single ownership, reservations, exact accepted prefix/recovery order, numerical futility, cumulative/local/bucket capacity and protected reserves remain enforced. The original full-1840-second per-dispatch admission and resource costs stay unchanged.
- GPU identity/EGL/exclusivity and the frozen current Codex-login transport policy remain checked. No Poe fallback, credential change, extra numerical preflight or model/API/simulator work is introduced.

The runner's two plan validations around dispatch remain intact (`qd_ed_final_runner.py:1750,1785`). An immutable-byte cache does not authorize removing either.

## Future acceptance tests and remaining evidence

No tests were executed for this design. A future small adapter change should demonstrate:

- A second build's identical historical-byte results with fewer loader calls, while each original live-check hook is still called; no cached whole PASS.
- Warm-cache rejection after current helper/source/HEAD or import-root drift, a changed authority, later matching reservation/resource event, reduced budget/reserve capacity, an appeared formerly absent audit, or a live owned process. GPU/provider drift must still be caught by the unchanged dispatch gates.
- Bootstrap/authorize ordering, mismatched inventory/repository/version, omitted or extra pairs, changed size/hash, malformed headers, short/extra blob output, stderr flooding, timeout cleanup and reentrant loads.
- Isolation between repositories, verifier versions and processes; no automatic fallback/retry, cross-process assumption or historical-proof relabeling.

The current scope cannot supply the actual object inventory/sizes, a trusted prospective repository binding, future source-review/schema edits, or a measured runtime breakdown. Imported control/proof helpers beyond the eleven files were not inspected, so no claim is made about their complete transitive cost or modification safety.

The expected opportunity is limited and plausible: eliminate repeated size/blob subprocess work for the common reader's historical objects within one process. Current metadata, SHA/AST reconstruction, other historical loops and live checks will still cost time. Measure equivalence and loader/time counters under a separately approved CPU-only source snapshot before deciding to release a future cohort. If constructing this thin adapter requires broad historical-helper exceptions or a provenance-system rewrite, **defer the optimization** and keep scientific work as the priority.

