# Proposed post-cohort infrastructure fixes

These files are an external review copy. Nothing here has been applied to the repository runtime or the live runs. Base scientific commit: `33954ead452927fc3168efb610487a688f89169e`. Wait for all three cohorts to finish and retain their final original-source checks before applying any patch.

`post-cohort-fixes.patch` changes only six launcher/offline-audit scripts and adds two CPU test files. It changes no policy, Stage implementation, simulator, model/cache, scientific configuration, or local configuration. `candidate/` contains unmodified supporting script/config copies to make the proposed changes executable in isolation; those unchanged copies are not part of the patch.

## Launcher ownership and cancellation

The launcher claims a new output directory atomically after GPU admission. Only a successful claimant enters the managed lifecycle and may write its status. The GPU lock remains held through cleanup and durable terminal status writing. SIGINT/SIGTERM during the claimed run stop the owned worker and discovered descendants, including descendants in separate sessions, using recorded PID/create-time identities; unrelated processes are not selected or signaled. Repeated cancellation is ignored during cleanup. Partial outputs remain in place, no retry/resume happens, and status becomes `interrupted` (or `launcher_failed` for monitoring exceptions). Existing preflight-failed classification is retained for preflight exceptions.

The worker's argv, cwd, environment and scientific inputs are unchanged. It receives its own process session; that is a lifetime/terminal-isolation change. No provider/model command is added. A terminated run cannot pass the existing finished-worker acceptance gate.

Limits are explicit: SIGKILL, host/power failure, and children already reparented out of the discoverable tree cannot be fully handled by this Python launcher. A durable external supervisor/cgroup is needed for guarantees across those events. There is no automatic recovery that converts such a run into an accepted experiment. Signal handlers apply after directory ownership is claimed; a cancellation before admission/claim starts no scientific worker.

## Portable offline archive lookup

The auditor derives the original output directory and job ID from the SHA-bound resolved configuration, cross-checks original status metadata, and uses them only as execution provenance. It reads archived artifacts from their current run-relative locations. It no longer constructs expected configuration values from the archive's current folder name or location.

A separate support bundle contains exactly the task-map and RNG fixture manifest bytes needed for offline audit. Their expected hashes come from the original source asset manifest and resolved config/environment, not from an arbitrary replacement receipt. The support receipt additionally binds the original run manifest/config/environment hashes. A present invalid bundle fails; it cannot fall back to an available original file. The builder refuses live runs, incorrect supplied bytes, existing destinations, and destinations inside the preserved original run.

Raw marker frames always resolve inside the current archive by episode/step and are checked against the original PNG hash. An original absolute PNG path is provenance only; an incomplete copied archive cannot borrow the old machine's frame to pass. Traversal/symlink escape and same-size corruption are negative test cases.

After integration, a completed run can be archived without modifying its receipts:

```bash
python scripts/prepare_steering_archive.py /preserved/run \
  --support-dir /archive/run-support
# If the original asset paths are unavailable, supply byte-identical copies:
#   --task-map /verified/libero_suite_task_map.py
#   --rng-manifest /verified/fixture-manifest.json

python scripts/audit_steering.py /archive/copied-or-renamed-run \
  --archive-support /archive/run-support \
  --output /archive/new-review/audit.json
```

The original manifest/config/environment files must be copied byte-for-byte into the archive. All original source, raw streams, prompt/response/image evidence, videos, and outcome files still need preservation; the small support bundle is not a full archive exporter. It does not replace model weight distribution or the RNG state files needed for a scientific rerun. No saved reward code or response is executed by these audit helpers.

A new audit-only commit can re-audit the old frozen snapshot. Record its checker commit/source SHA and explicit invocation separately; retain the original audit. The experiment remains tested at `33954ea`, never at the later checker commit. No model/mechanism/numeric validity threshold has been relaxed.

## Validation

- 36 new CPU regressions passed in 4.81 seconds. This includes actual owned sleep worker/grandchild cancellation, a separate unrelated process, lock lifetime, output-directory ownership race, double cancellation, preflight interruption, monitor exception, missing/corrupt/misbound sidecars, moved/renamed archives without original assets, and raw-frame isolation.
- 140 existing runner and offline-contract tests passed against the staged modules in 10.37 seconds. Their original fixture roots were explicitly retained by `run-existing-wrapper-tests.py`; no scientific source was patched to run them.
- All three actual CLI `--print-config` outputs match the frozen baseline after normalizing only the external copy's repository-root lookup paths. Those three comparisons are staging-only and explicitly skip after integration to avoid a meaningless self-comparison. Other new tests do not depend on local run directories, local machine config, model assets, or network credentials.
- `git apply --check` passes for the main proposal and the separate comment-only proposal. This is a check, not an application.
- All 113 files in the original frozen runtime manifest still match their original hashes. No GPU/API/simulator calls were made by this work.

Independent review by the algorithm reviewer identified two issues in the first draft: a losing output-directory claimant could overwrite another run's status, and a moved archive could borrow an original raw PNG. Both were fixed with negative regressions; subsequent review found no remaining blocker. The final additional builder guard prevents writing support inside the original run.

`comment-only-proposal.patch` is separate. It replaces the stale historical-name/version comment with neutral transport-policy wording. Python AST equality was checked; original fixture/source blobs are not altered. Apply it only after the cohorts finish if desired, keeping the historical blob exception in provenance.

Commands and stdout are in `new-regressions.log`, `existing-wrapper-tests.log`, and `validation.json`. Patch/source hashes are in the validation receipt. Full CPU, GPU, API and new scientific cohort validation of an eventual integrated commit were not performed here.

## Real copied legacy archive check

A full byte copy of the completed migration archive was moved to a different directory name: 4,045 regular files, 913,826,636 bytes, no symlinks or hardlinks. All original files and all copied files matched their recorded hashes after verification. An audit hook prohibited reads anywhere in the original workspace outside the new validation directory. All ten task contracts passed, totaling 14,081 checks. Missing or same-size corrupted archived raw frames and a same-size corrupted support file were rejected while the originals remained present. CUDA remained uninitialized; no simulator/API/model execution occurred.

The first actual support-build attempt exposed a legacy protocol difference, retained in `../archive-candidate-validation/prepare-support.log`: the frozen v1 job ID is exactly `output`, while v2 requires the original run directory name. The helper now accepts those two explicit schema rules and rejects mismatches, arbitrary IDs, and unknown schemas. Original config/environment hashes and the original status path check remain unchanged. The latter check is conditional on status.run_dir being present; both actual runs contain it. The algorithm reviewer independently confirmed the narrow compatibility change.

The legacy wrapper still has `scope=legacy_basic_only` and `full_audit_performed=false`; it is not promoted to v2. Its legacy fixture lookup uses the auditor's own repository fixture path, so this isolated validation supplied the exact hash-verified support fixture at that path. The ten separate task-contract audits directly used the support bundle. This limitation is explicit rather than hidden by a broad validity bypass. Full provenance, source hashes, successful outputs and the preserved first failure are under `../archive-candidate-validation/`.
