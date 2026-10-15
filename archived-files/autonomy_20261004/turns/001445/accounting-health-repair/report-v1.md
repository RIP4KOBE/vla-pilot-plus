# Leaf 15.6 — narrow engineering repair

Status: PASS_FOCUSED_CPU_ENGINEERING_REPAIR_ONLY. Score: null. Goal incomplete. Release disabled; source not adopted.

Base source: `e36f8b945f6b2fde9e81010b3d16987b8c771dd0`. Repair commit: `711602acc32031cfd977a2b3ec2e7ef0582e7377`. Clean worktree; five files, 40 insertions and 25 deletions. Exact patch: `repair-v1.patch` (SHA-256 `bec9078b52a0da7420bd2c7fe978609a64a3792c7ca23324bc089ed7b23018c8`).

Updated the three exact retained GPU-hour expectations in preparation/admission from 75.53031173955723 to 75.53335346582918, keeping 505 attempts and all fail-closed guards. Bound prospective identity `n36_healthcheck_n36r3_preparation_001445` under this authority. Prior identity `n36_healthcheck_n36r3_preparation_001426` and its 10.950214579002932-second charge remain retained; no readiness transfers. Focused fixtures retain earlier aborted health and prior completed health and reject reuse.

Tests: 31 focused CPU checks passed (1.72s). After a fixture-only correction preserving the earlier aborted status, all 22 affected accounting repair checks passed again (1.63s); the other nine checks and production code were unchanged. Coverage includes accepted exact accounting, stale and one-ULP changed costs, changed attempt counts, all three prefix guards, old/arbitrary/reused health identities, exact source/runtime references, charged-prefix retention, protected arithmetic and first-C0 pause. The admission test validates authority only; no health runner was executed. Two-CPU affinity and thread limits applied. `git diff --check` passed.

The narrow transitive scan covered preparation, admission, health reservation, accounting dispatch, release consumption and inherited preserved-charge checks. No stale production duplicate remains. Frozen science, episode identities, Main/native audit, lexical routing, deadline and G3 pause are unchanged. Three owning ledger hashes were verified against root reconciliation before edits and again after commit. STOP/deadline checks passed before edits, tests and reporting; completed within the 900-second cap.

Limitations: synthetic CPU engineering evidence only; full health/readiness suite was not run. No GPU/provider calls, health execution, binding refresh, adoption, owner state/ledger writes, child agents, cloud/credential access, protected results, locks/leases or historical provenance rebuild. The prohibited design document was not opened. No alternate executor/model was invoked.

Root review, fresh bindings/final manifests, independent B5, source/runtime adoption, separately authorized fresh charged health and first-C0 release/G3 review remain separate.

Full exact file before/after hashes, input bindings, unchanged ledger hashes and test commands/log hashes: `report-v1.json` (SHA-256 `ad37466102f84644ec45de04528da3ea9f81ff6b457ff491b3aad8dd457db184`).
