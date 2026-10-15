# CPU startup preflight — strict guard check failed

The single permitted startup process completed Torch import and passed the small synthetic CPU BF16 clamp/cumsum and FP32 norm dtype/finite checks, but **did not pass the final clean-guard condition**. The process stopped after 1.181964968 seconds. CUDA remained uninitialized; experiment payload reads, temporary writes, API/model/simulator operations were zero. No retry was performed.

Setting `tempfile.tempdir` to the pre-existing owned `tmp` directory avoided dill's global temporary-directory probes. The guard retained the same exact file, network, process and CUDA boundaries and granted no writes under `tmp`.

The guard nevertheless blocked six optional dependency read attempts, which dependency import handled internally:

- `/home/hynx/miniconda3/envs/vla-pilot/lib/python312.zip`: three attempts.
- `.../site-packages/tqdm-4.67.3.dist-info/METADATA`: one attempt.
- `.../site-packages/tqdm-4.67.3.dist-info/PKG-INFO`: one attempt.
- `.../site-packages/tqdm-4.67.3.dist-info`: one attempt.

The final gate intentionally rejected this nonempty blocked-access list. These accesses were rejected by the narrow dependency extension whitelist; no experiment path was requested. The outcome must remain a failed overall preflight, not a clean runtime-readiness proof.

The completed synthetic checks are established from the preserved exception location after those checks in the frozen script. Their numerical outputs were not persisted before the final gate; nothing was rerun to reconstruct them. No native or historical result files were read, including the prior closure reference named in the scope.

All scope, script, manifest, process log, exception and guard evidence is retained. The previous geometry diagnostic remains closed. No scientific code, plan, state, ledger, controller or GPU workload was altered.
