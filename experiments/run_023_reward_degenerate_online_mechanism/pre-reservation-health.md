# Pre-reservation health incident — run_023

Status: `BLOCKED — INVALID RUNTIME CREDENTIAL, ZERO RESERVATIONS`

Frozen runner implementation: `d3f09b82dcd87ad0cde2038da0200e93287db3b7`

Immutable mechanism manifest:

- path: owned `run_023_reward_degenerate_online_mechanism/manifests/mechanism_manifest.json`
- mode: `0444`
- size: 15,842 bytes
- file SHA-256: `d51a44042357b129595cc220faeecd5a9029f2424e0b803711a32ed31a8ec718`
- payload SHA-256: `944047076b4347e582f9dd442e685c7b820f358e78dd0a9631fca01d700066c3`
- code state: `26001c7644b0a07183d35a3bef9591bf6bd928af279d6cffcc4327406c5bbb96`

The first online invocation passed manifest, storage, runtime-cache, and credential-presence checks. Its required real pre-reservation Stage/Poe health check returned failure. One bounded sanitized diagnostic classified the failure as:

```text
exception_type: AuthenticationError
HTTP status: 401
error_code: invalid_api_key
credential value logged: false
credential fingerprint logged: false
```

The diagnostic did not serialize exception text, request headers, the credential, or a reversible credential fingerprint.

Failure boundary: before two-snapshot GPU admission, immediate dispatch snapshot, GPU manifest, attempt reservation, phase dispatch, worker/model load, LIBERO reset, episode, or task outcome. The run_023 attempt ledger does not exist; global reservations remain 54 and expected IDs 55–60 remain unused. Added GPU hours, online episodes, validation uses, and formal uses are all zero.

This is not algorithm evidence and does not change the historical formal best `2/10` or gap 3. The exact six-cell matrix, profiles, thresholds, horizon, and single H2 candidate remain frozen.

Resume condition: a valid process-environment credential must pass one real bounded health check. Because this incident record advances documentation HEAD after the immutable v1 manifest's implementation binding, any resumed dispatch must first use a protocol-first versioned manifest/rebinding that preserves the exact runner, algorithm/config hashes, profiles, matrix, checkpoint, LIBERO inputs, cache, caps, and unused attempt IDs. No scientific or result-driven change is authorized.
