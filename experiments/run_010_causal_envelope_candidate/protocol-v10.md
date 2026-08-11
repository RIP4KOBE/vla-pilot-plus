# `run_010_causal_envelope_candidate` Dev-B Execution-Context Recovery Protocol v10

Date: 2026-08-11 UTC

Parent Dev-B protocol: `protocol-v9.md`, commit `9664b9259373897fdeadd7b1963d8e1a00353dd6`. Initial Dev-B implementation: `9ae7c00c0699c3a27b8424ffddd64ad8eb6615cb`; manifest v1 SHA-256 `375f78307ab4b02b112979486cccadd8bfcda6982133dd3fafdfc5c89919d9d6`.

Scope: one protocol-first repair of a pre-reservation execution-context whitelist omission. It changes no algorithm/config/profile/task/seed/checkpoint/scientific threshold/promotion rule and authorizes no additional cell or episode.

## Observed boundary

The first Dev-B invocation passed immutable evidence, storage, credential/service health and fresh GPU admission, then failed while constructing attempt records because bound jobs lacked `execution_record`. Root cause: `configure_base()` extended `base.P2_LEVELS` with mechanism and Dev-A levels but omitted the newly added Dev-B level, so the base binder intentionally returned jobs unchanged.

- Exception: `KeyError: 'execution_record'` in `_attempt_records`.
- Attempt ledger remains SHA-256 `591be9196ef53bdd77dfc895100b304cb7b4be1202124dd49724de3ee392ade7`; IDs 27–34 do not exist.
- No `dev_b__*` output, worker, episode, task outcome or device-wall GPU-hour exists.
- Fresh admission artifact is preserved: `gpu_eds_qd_autoresearch_dev_b_1786410996.json`, SHA-256 `fa8d86718045a87a6cfcf3ef3e6dfd42b134fed16c6cc784ad402d497559310c`, selected GPUs 0/1. It cannot be reused.

This is `INFRASTRUCTURE_FAILURE / PRE_RESERVATION_EXECUTION_CONTEXT`, not candidate evidence and not a same-cell retry.

## Exact repair and manifest v2

After this protocol commit only the dedicated runner/tests/state may change:

1. add `DEV_B_LEVEL` to the temporary `base.P2_LEVELS` union;
2. add a regression test using the real configured binder that requires every bound Dev-B job to contain `execution_record`, config fingerprint and immutable versioned manifest binding;
3. point Dev-B manifest constant to new `manifests/dev_b_manifest.v2.json` and require preserved v1 hash above;
4. rerun dedicated and frozen nine-file suites; verify all four algorithm/config hashes remain unchanged;
5. commit the repair, then freeze immutable manifest v2 at that exact code-state with all v9 bindings unchanged plus preserved-v1 provenance;
6. perform completely fresh health and GPU admission before one gate-path retry; only then may IDs 27–34 be reserved.

Manifest v1 is valid historical plumbing evidence but cannot bind the repaired code-state. It remains mode 0444 and is never overwritten. Any further pre-reservation code-path failure stops Dev-B for outer-loop review; no third runner repair is authorized. All v9 success/safety/mechanism gates remain unchanged; validation/formal remain forbidden.
