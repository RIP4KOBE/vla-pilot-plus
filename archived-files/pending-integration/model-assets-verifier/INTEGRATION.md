# Model asset verifier prepared for integration after the runtime freeze

This directory contains a standalone, pure CPU implementation for `scripts/steering_model_assets.py`, an expected content manifest, and targeted synthetic tests. Nothing has been copied into the active runtime. Existing model caches, the shared Python environment, and the running cohort were not changed. No network, downloads, model deserialization, GPU, or API calls were used.

## Prepared files and real validation

- `scripts/steering_model_assets.py`: standard-library-only verifier API; the CLI optionally imports PyYAML to parse YAML machine configuration.
- `model-assets.expected.json`: the same 214 content entries and three normalization source hashes as the prior portable draft. Only advisory verification-profile metadata changed: current-compatible validation is the default, and exact clean-distribution checks are optional. It contains no machine absolute paths.
- `tests/test_steering_model_assets.py`: 34 synthetic CPU tests. The test script discovers the module relative to its own checkout, so copying `scripts/` and `tests/` into the root layout works.
- `pytest.log`, `pytest-execution.json`: **34 passed in 0.20s**, exit 0, including same-size corruption, actual config/weight shadowing, missing tokenizer/DINO inputs, HF external blob symlinks, bytecode compatibility, additional importable-source shadowing, and the no-Torch-import subprocess check.
- `current-assets-verification-final.json`: **PASS** after actually streaming and recomputing SHA-256 for all **214 files / 50,861,376,376 bytes**, plus all **3 normalization source files**. This is a content-identity result, not a model inference/performance result. The report records 75 existing DINO bytecode files without failing them. Unlike the earlier manifest-only review, this final verification does rehash the large RDT/T5/SigLIP weights.
- `current-assets-verification.json`: retained initial implementation verification; use `current-assets-verification-final.json` for the final implementation.

Final implementation SHA-256: `1f233713300231ce1397c4e7fcc67b378ee5aa63014c69ba73551ae7dba17d30`.
Expected manifest SHA-256: `de4c7da58023099e7d6c8d2cdbc08736b7ab60e67c8355c3fe354f0bafef4687`.

The real current-assets check used:

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/steering-cpu-guard \
  /home/hynx/miniconda3/envs/vla-pilot/bin/python \
  /tmp/steering-model-assets-verifier/scripts/steering_model_assets.py \
  --local-config .worktrees/exp/steering-integration/local.yaml \
  --manifest /tmp/steering-model-assets-verifier/model-assets.expected.json \
  --repository-root /home/hynx/lizhuo/VLA-Pilot++ \
  --report /tmp/steering-model-assets-verifier/current-assets-verification-final.json
```

The `/tmp/steering-cpu-guard/sitecustomize.py` audit hook prohibited network socket connections and Codex/GPU utility subprocesses. The verifier itself uses no subprocesses or model libraries. The command only reads the root/cohort machine config and asset/source files, and writes the explicitly named `/tmp` report. It does not call the existing online runner or GPU/API preflight.

## Default compatibility and scope

The verifier hashes every expected file and compares size and SHA. HF snapshot symlinks pointing outside the snapshot into blob storage are accepted if the resolved file content matches. Root directories must exist and the two encoders must be explicit snapshots, not directories containing `snapshots/`.

Selection checks mirror the frozen implementation's behavior:

- RDT weight search: `ema`, `rdt/ema`, root, `rdt`; each searches the current loader's four weight filenames. The selected file must remain `ema/model.safetensors`.
- RDT config search preserves the real directory/parent order and `config.yaml` before `config.json`, using `exists()` as the real code does. It must select the accepted root `config.json`. An earlier file or even a directory at `ema/config.yaml` cannot pass.
- The pinned Transformers implementation prefers `model.safetensors`, then its index, before `pytorch_model.bin` and its index. T5 must select the accepted `.bin`; SigLIP must select the accepted `.safetensors`. A symlink named `model.safetensors` still changes loader format and is rejected as a T5 shadow.
- Extra T5 `tokenizer.json`/`added_tokens.json` are rejected because they add tokenizer inputs beyond the accepted content. HF `adapter_config.json` is also rejected as an unsupported adapter profile: neither validated environment has PEFT, so this conservative guard does not claim the sidecar necessarily changes the current environment's loader behavior; with PEFT installed it can redirect model loading.
- Required DINO source files and its weight are hashed. Extra Python/native source, sourceless bytecode outside `__pycache__`, and extra directory symlinks are rejected because they can shadow a hashed module or package.

The default **allows** existing DINO `__pycache__` files, extra documentation, and unselected checkpoint weights/configs. For example, RDT root `pytorch_model.bin`, `ema/pytorch_model.bin`, and lower-priority `rdt/ema/config.yaml` do not change the selected accepted EMA/config and pass. SigLIP's extra lower-priority `.bin` is also allowed. No files are removed or modified.

Existing `__pycache__` content is recorded by count but not attested. Source hashes plus loader path evidence do not prove which bytecode bytes Python read; this limitation appears in every success report. The policy does not invalidate the current cohort retrospectively. `--clean-distribution` is an optional check for a newly assembled DINO source pack: exact 203-file regular-file set, no extra files/bytecode/symlinks. It is **not** required for the current live cache or current run.

The verifier does not prove upstream publication/revision provenance, authenticate an externally replaced expected manifest, lock files against concurrent modifications, import processors, or execute models. Keep the expected manifest in the reviewed commit and keep asset trees unchanged between verification and use. The selection model is deliberately tied to the frozen RDT loader and Transformers 4.53.3; update/review it when those loaders change. Package/submodule/CLI identity checks remain the existing environment mechanisms' responsibility.

## Narrow integration points for the root owner

Suggested paths after the current cohort freeze ends:

- `scripts/steering_model_assets.py`
- `configs/assets/model-assets.json` (copy the prepared `model-assets.expected.json`)
- `tests/test_steering_model_assets.py`

Call API:

```python
from scripts.steering_model_assets import verify_model_assets
verified = verify_model_assets(
    local,
    ROOT / 'configs/assets/model-assets.json',
    repository_root=ROOT,
)
```

`local` must already contain resolved logical roots, as returned by existing `load_local`. No existing model library imports are needed. The report carries the expected-manifest SHA, verifier source SHA, actual selected files, complete verified content entries, normalization results, and bytecode limitation.

1. `prepare_steering_assets.configure`: construct the proposed `local` mapping, call this verifier **before writing** the machine/LIBERO config files, and include the verification report in the preparation report. This prevents writing a seemingly accepted configuration for mismatched assets. Default validation should remain current-compatible; do not turn on `clean_distribution` implicitly.
2. `steering_runtime.dependency_manifest`: verify against the expected manifest before starting a worker and include the verification in `environment.json`. Its full content report can replace the currently repeated model SHA reads; preserve any existing `models` field shape needed by consumers using the verified root/path lookup. Do not hash 50 GB twice merely to fill both old and new fields.
3. `check_steering`: if the root owner wants GPU/API service preflight to imply asset readiness, call the same CPU gate before the first `--api`/`--gpu` probe and include the result. Plain provider diagnostics can otherwise remain separately labelled and must not claim model identity acceptance.
4. `run_steering`: the existing dependency-manifest call before worker launch is sufficient; no algorithm or rollout change is needed. Keep `--print-config` a cheap configuration-only command, clearly not a content-verification result. The runtime manifest's source snapshot already captures `scripts/*.py` and `configs/*.json`, so the new verifier and expected JSON can be included in source identity by the current mechanism.
5. Error handling should preserve `ModelAssetsError` and its concrete mismatch/selection message. Do not silently download, replace, or pick alternative weights. Only write new verification evidence; do not rewrite the frozen run's existing `environment.json`.

After integrating, rerun these tests and the existing CPU suite at the new source commit. A new implementation check and the existing frozen cohort remain separate evidence; this prepared verifier does not claim the runtime hookup has already been tested.
