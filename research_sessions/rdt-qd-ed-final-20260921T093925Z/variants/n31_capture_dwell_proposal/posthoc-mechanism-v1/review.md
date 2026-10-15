# N31 bounded posthoc JSON review

Outcome remains C0 0/6, Q0 0/6, N31 0/6; tasks 6–9 Unknown. No scientific gate changes or new evaluations.

| Task | Q0 guided decisions | N31 guided decisions | Opportunities | No projected entry | No native change | Changed proposals | Decisions selecting proposal content |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | 47 | 15 | 150 | 143 | 5 | 2 | 2 |
| 1 | 3 | 12 | 120 | 83 | 31 | 6 | 4 |
| 2 | 51 | 28 | 280 | 254 | 9 | 17 | 2 |
| 3 | 3 | 3 | 30 | 30 | 0 | 0 | 0 |
| 4 | 20 | 20 | 200 | 164 | 30 | 6 | 4 |
| 5 | 6 | 6 | 60 | 59 | 0 | 1 | 0 |

Across 840 offspring opportunities, 733 had no projected entry, 75 produced no native change, and 32 produced changed proposals. Final selected plan content equalled a changed proposal in 12 of 84 guided decisions. These are different denominators: 12/32 is not a survival probability. Native audit source scripts/qd_ed_n31_native.py:234 tests exact content equality with any changed proposal within that decision; this supports content selection, not a unique causal genealogy.

The proposal was exercised in tasks 0,1,2,4,5; selected proposal content occurred in tasks 0,1,2,4. Task3 never generated a changed proposal. Thus uniform non-exercise is ruled out, while scarcity of projected entry and some rejection by normal selection remain distinct descriptive bottlenecks. This does not establish why no task succeeded or justify changing ranking/geometry by itself.

The native receipt verifies 672 executed actions across the 84 guided decisions, including decoder/commit/prefix linkage (scripts/qd_ed_n31_native.py:210–234). Its aggregate count does not expose when closure occurred, how much dwell actually executed, measured jaw closure, or physical target motion. All remain unresolved here. Zero translation is approximate dwell; +1 is a closing command, not proof of capture. Selected trajectory target_distance fields are planning quantities, not observed object motion (core/rdt_policy_steer.py:7426–7430).

Matched Q0 has 130 guided decisions versus N31 84. This is a realized trajectory/Stage difference, not a violation of the frozen per-search schedule, and is not pooled into equal decision denominators. Success comparisons remain six matched task blocks.

Next bounded step: inventory only the twelve accepted Dev Q0/N31 events.jsonl manifests, bind hashes/bytes, then extract N31 changed/selected decision IDs and packet/action references. Freeze a minimal native payload set and CPU/decode limits before any tensor load. Use all six tasks, retain task3 and task5 negative cases, and matched Q0 descriptive context. Avoid full replay of accepted audits. Actual close/dwell and tracked target motion must precede a scientifically justified new candidate. No GPU dispatch or validation/formal access is released.

Provenance: scope-v1.json defines 24 fixed JSON inputs (18,382,422 bytes); analyze_json.py verifies hashes and agrees with accepted native counts. summary.json records 0.1562 CPU seconds. Source and protocol unchanged. Attempt and health ledgers unchanged. Delegation tool failed before creating a child; coordinator performed read-only observation and artifact writing only.
