CPU-only DINO import repair committed as `80a9d945e688da17485239b3d5bb11c558c214d6` (source before `711602acc32031cfd977a2b3ec2e7ef0582e7377`). Status: prospective engineering, root review required. Score: null. Goal complete: false.

The bootstrap now admits only manifest-enumerated Python source files under the exact declared DINO hub root. It verifies canonical paths, hashes and module origins, records hubconf execution outside `sys.modules`, and checks cached module identity. Worker binding follows verified context/dispatch; source receipt verification retains the existing runtime and generated-code audits.

Validation used two CPU threads and no model construction, weights, GPU or provider calls:

- Local `torch.hub.load(source="local")` returned 42 on first and cached loads. All 24 admission/tamper/cache negatives and five complete-receipt mutations were rejected; full producer/consumer passed (1,269 compiled sources).
- Actual frozen DINO hubconf imported twice: all 14 executed DINO sources, including hubconf, passed; full producer/consumer passed (1,279 compiled sources).
- Existing generated-code positive/negative regression passed, including its complete receipt consumer.
- The combined command reported `47 failed, 5 passed` because the added legacy runner harness hit `NameError: owner_root`. A single representative failure reproduced from starting-commit functions; the runner is unchanged. This unrelated harness remains unresolved.

The exact patch, per-file before/after hashes, test commands, captured evidence and evidence hashes are in [report-v1.json](report-v1.json). Patch SHA256: `c89cb57bc7659afeb1663dd179a59edd8d09459a2319f80ef44ab50961e11111`. Captured combined output is explicitly labeled as a truncated excerpt.

Only five code/test files were committed. Frozen cache sources were read only; mutations used temporary test fixtures. No frozen plans, releases, results, ledgers or owner state changed, and N36R3 was not replayed. Model-construction-only imports and episode execution remain untested. Recovery identity, source adoption, runtime rebinding and release are deferred to root review.
