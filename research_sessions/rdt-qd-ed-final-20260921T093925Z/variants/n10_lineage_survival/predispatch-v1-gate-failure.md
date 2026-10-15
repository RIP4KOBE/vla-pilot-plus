# Passive diagnostic v1 predispatch gate failure

The first supervisor start used frozen plan SHA-256
`ea54c97d0062f919a0681180da74d6a177504f0eeeafcaa63010a16ad58afa78`
and source `d1bd424ae73200ba97f7fa7c2185bdce9a8bf74e`. It stopped at
`require_scope` before any attempt reservation, ledger event, GPU process or
provider call. The command file ran as `__main__`, whereas the runner loaded
the same file as its support module; each had a distinct `_SCOPE` global.

The immutable `diagnostic_runs/status.json` records `failed` with
`completed_keys=[]` and reason `GateError`. No `n7_passive_*` attempt event
exists in the ledger at the time of this note. The fix in source
`dbe65b6e1db1d23b4ce8a68368dfbd7278c80a13` opens the scope in the
runner-loaded module. A direct CPU scope test passed. The v2 plan and release
use separate files and a distinct `status-v2.json`; no v1 file was rewritten.
