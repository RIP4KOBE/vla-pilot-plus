# N3 diagnostic checkpoint admission v2 — preparation only

The old reader failed in metadata admission before decoding any native bundle. This package pins the exact base-null → named-checkpoint-reference change, leaving all scientific calculations and all other source/resource identity gates unchanged. `protocol-v2.md` is the narrow amendment; `inherited-protocol-v1.md` preserves the original scientific protocol verbatim. `reader-v1-to-v2.diff` and `diff-inventory-v2.json` provide the complete source change inventory.

No W, plan, terminal, old report, old launch or old diagnostic output was changed. The four public plan/checkpoint references are intentionally fixed in `dependencies-v2.json`; actual scientific input references and execution authorization remain separate. The checkpoint evidence list is not traversed.

Later root authorization uses the existing `n3-post-dev-read-authorization-v1` schema described in `input-schema-v2.json`: exact new freeze-v2 reference, exact new manifest, root-confirmed completed failed Dev cohort, complete30 accepted audit/status/index snapshots, metadata source hashes, reviewed matrix reference and a new output. The matrix input's base/revisions must equal `checkpoint_admission` exactly. An old authorization cannot authorize v2 because it binds different source/freeze bytes. No execution authority is created by this package.

Only after root's separate authorization:

```sh
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python read_full_dev.py \
  --authorization /absolute/NEW/root-authorization.json \
  --authorization-sha256 REVIEWED_NEW_SHA \
  --output /absolute/owned/continuation_20260923/n3-post-dev-analysis/NEW_RUN \
  --execute-reviewed
```

Focused CPU tests (invented episode fixtures only):

```sh
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -q -p no:cacheprovider test_checkpoint_admission.py
```

`public-metadata-validation-v2.json` separately records the authorized four-file public metadata check; it is not an actual diagnostic run or a scientific result. `v1-failure-provenance.json` names preserved v1 failure evidence. Historical native payloads were not decoded or interpreted during preparation. Scientific conclusions remain pending complete authorized extraction; no causal benefit or task-outcome change is asserted.
