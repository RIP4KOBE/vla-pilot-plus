# Node 15.6 bounded CPU executor report

Status: PARTIAL_FRESH_EXPECTATION_CORRECTED_CONTEXT_PASS. CPU engineering evidence only; goal_complete=false.

Commit: `3f6c4e8dd968ece8f6c2a558389f3851db173013` → `b4295b3b53823dceb314bd7782fbe56193bfab91`. No production code changes or owner source adoption.

Changed paths:
- `tests/n36_engineering_cpu_fixture.py`
- `tests/test_n36_engineering_integration.py`

Context test passed, exit 0, 250.48 seconds wall time; initial fresh test failed after 700.61 seconds, its final status expectation was corrected but not rerun, CPU affinity [0, 1], numerical-library thread limits 2. Existing F1/restart tests were not rerun. The failed fresh-test log is retained. Total focused test time: 951.09 seconds. No tests remain running. `git diff --check` passed.

Command: `/home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -vv --durations=10 tests/test_n36_engineering_integration.py::test_accepted_context_cross_family_rejection -x`

Logs: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree/.cpu-test-artifacts/integration-gap-001513/targeted-1.log` (failure) and `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree/.cpu-test-artifacts/integration-gap-001513/targeted-2.log` (context pass). SHA256 values for both logs are recorded in report-v1.json. Exact timestamps, timing and test-file hashes are in report-v1.json.

Actual assertions reached:

fresh_episode:

- Real accepted health/release prerequisite using simulated device/provider/import evidence; each episode starts with no local attempt suffix.
- STOP inserted after real durable reserved append raises STOP; suffix is reserved only, no Popen call, no process or terminal artifact.
- STOP inserted after real durable dispatched append raises STOP; suffix is reserved/dispatched, no Popen call, no process or terminal artifact.
- Simulated Popen OSError before child creation produces reserved/dispatched/aborted and INVALID_STOP; outcome_valid=false, success=null, retryable_infrastructure=false, required_cost_telemetry_complete=false.
- Aborted terminal matches durable attempt-result artifact; zero seconds is from a stationary simulated clock and is not measured real launch cost.
- Every case retains both 1840-second reservation fields and creates no episode child.
- Both STOP cases pass all restart assertions: LIVE_OR_UNSETTLED, scope_exhausted=true, continuation_authorized=false, scientific_eligible=false, next_row=null, outcomes=[].
- Aborted pre-child launch restart actually returned LIVE_OR_UNSETTLED, failing the initial test expectation INVALID_STOP. Static review identifies existing_handles UNKNOWN classification for absent process.json. Expectation corrected without production changes; this corrected test was not rerun within the remaining budget.
- Both STOP restarts leave disposable owner/output bytes unchanged and make no launch. Final aborted-case scope flags/byte equality and the last veto assertion were not reached because of the status mismatch; these remain unverified in the corrected test.

accepted_context:

- Context constructed by real context_for and accepted by real validate_context before mutations; admission=True raises unchanged public dispatch veto.
- Ordinary worker-context schema with ordinary field set plus engineering plan/release reaches explicit worker context/release family cross-use rejection after full release transaction verification.
- Health release in accepted episode context rejects at engineering detached release fields.
- Audit-view plan in operational context rejects at unsupported worker release schema.
- Foreign purpose, foreign scope, and foreign audit_plan each reject at engineering context bindings after release validation.
- Each of six mutations leaves disposable owner/output file bytes and simulated launch list unchanged; original accepted context still validates afterward.

Arithmetic accounting (static source review; prior arithmetic tests not rerun):

- Exact datetime deadline headroom equality and one microsecond short for need=2100,1840,60 seconds; detached issuance also has 2100-second and one-microsecond-short cases.
- Nominal health reservation 60 seconds and episode reservation 1840 seconds; local 60/3600 float accepted and (60+1e-8)/3600 rejected by 1900-second engineering cap.
- Weekly/protected bound bracketed by adjacent representable floats with protected=44 hours, retained margin=0.23357169027962 hours, total need=1900 for health and need=1840 for episode.
- No literal Decimal equality claim for float 60/3600 or adjacent representable weekly-boundary inputs.
- No exhaustive exact-equality/just-over matrix across global, protected, absolute, weekly, local scope and separate health caps.
- No integrated admission at each arithmetic boundary; new runner cases use nominal accepted fixture accounting only.
- No isolated accepted absolute-cap boundary under the simultaneously active stricter weekly ceiling.

The unchanged weekly ceiling is 221.08404692669838 hours, stricter than the unchanged 224-hour absolute ceiling. No arithmetic guards or scientific/audit gates were modified.

Remaining gaps and scope limits:

- Fresh episode test failed only at the final aborted-case restart status expectation. Corrected to observed conservative LIVE_OR_UNSETTLED, but no full rerun fits the 1000-second budget. Remaining assertions after that line are unverified for this case.
- Arithmetic boundary limitations itemized in arithmetic_coverage remain open.
- No reverse cross-family case from an independently accepted production-family graph; coverage starts from accepted engineering context only.
- Synthetic retained history and disposable source/runtime graph, closure v1 and interpreter aliases only; no actual owner snapshot, production inventory or generated-module-v2 closure.
- Native library bytes and import/bootstrap/device/provider observations are simulated or inert; no actual native/GPU child execution or real launch-admission certification.
- Prior broader 49 failures / 43 passes are not rerun or resolved; no global all-tests-pass claim.
- Production inventories/manifests, independent B5, owner accounting/source adoption, readiness/releases, GPU execution and scientific promotion remain out of scope.
- Original validation/formal/required-ablation completion contract remains unsatisfied.

The disposable graph was removed. Existing untracked CPU artifacts were retained. Only these reports were written at the designated owner report location; no owner research-state/checkpoint/tree/ledger mutation occurred.

The unconditional dispatch veto remains. GPU authorization=false, release_enabled=false, native_or_gpu_evidence=false, scientific_success_or_promotion=false, goal_complete=false.

Report and commit completed within 1141.52 seconds measured conservatively from the earlier authority issuance timestamp, below the 1500-second reporting deadline and 1800-second total cap.
