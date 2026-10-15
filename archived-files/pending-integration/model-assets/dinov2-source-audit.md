# Read-only DINOv2 source identity audit

No network/model execution, GPU, imports of DINO/Torch, repository writes, or shared
environment writes occurred. Only the requested cache tree, project loader source,
PyTorch hub loader source and supplied asset evidence were read.

## Identity

The cache has no `.git`, `.git_archival.txt`, `.gitmodules`, package distribution
metadata, retained zip or commit receipt. The hub parent only contains the DINO and
DINOv2 cache directories, `checkpoints`, and `trusted_list` (its contents were not
needed/read). `main` in the directory name is a ref label, not a pinned commit.
DINOv2 `dinov2/__init__.py:6` states version `0.0.1`; `setup.py:42` reads that value.
README:130–139 and MODEL_CARD:72–81 show unpinned torch.hub usage. An upstream commit
cannot be independently recovered from this local evidence; use null/unknown.

## Coverage

`environment/model-assets.json` SHA-256:
`b9701e584d6e3522716063af8ea5874007d352d1af620cdbc868afcd55ba0c7e`.

Its 178 unique DINO source entries all exist and match their SHA-256 values:
157 Python files (all Python source in this cache), 20 YAML files, one TOML file.
The actual tree has 278 files: those 178, 75 bytecode `.pyc` files, and 25 other files.
The 25 omissions include three shell scripts, four executable notebooks, three
requirements files, setup.cfg, documentation/licenses/images. Consequently say
“all 157 Python source files”, not “all executable source/artifacts”.
No symlinks were found. Current missing/mismatched listed files: zero.

A complete portable non-bytecode tree is recorded in
`/tmp/dinov2-source-portable-manifest.json`: 203 regular files, 3,956,001 bytes.
The canonical relative-path -> size/SHA map digest is
`317ea4c4766462192095a32a5850b571a7df607d5979215da7de6878a203a9ca`.
This is content identity, not a verified upstream Git commit.

## Actual loading chain (source inspection)

- `configs/evaluation/libero_object_swap.yaml:46`: `dinov2_vitb14`.
- `scripts/steering_runtime.py:68`: explicitly sets local `TORCH_HOME`.
- `core/keypoint_detector.py:120–127`: checks `torch.hub.get_dir()` plus
  `facebookresearch_dinov2_main/hubconf.py`, then invokes torch.hub with source local.
  If hubconf is absent, lines 129–132 fall back to an unpinned remote repository.
- The cache `hubconf.py:7–15` eagerly imports backbone/cell/xray/classifier/depth/text
  hub modules. Preserve this import closure, not only `backbones.py`.
- `dinov2/hub/backbones.py:89–93` chooses vit_base; line 49 imports the local models
  module; `models/vision_transformer.py:21` imports dinov2 layers.
- `backbones.py:43–46` defaults pretrained true and check_hash false; lines 73–77
  form the weight URL, call `load_state_dict_from_url`, and load strict state dict.
- The installed PyTorch hub.py:675–680 adds the cache directory to sys.path and
  executes its hubconf; 854–875 selects `get_dir()/checkpoints/<URL basename>`,
  downloads if missing, and otherwise loads the local file. Source local alone
  does not prohibit weight downloads. Pre-existing `dinov2` sys.modules entries
  can also affect Python import origin; a fresh process/origin proof is useful.

The weight was independently SHA-256-read in this review (no deserialization):
`hub/checkpoints/dinov2_vitb14_pretrain.pth`, 346,378,731 bytes,
`0b8b82f85de91b424aded121c7e1dcc2b7bc6d0adeea651bf73a13307fad8c73`.

## Strict portable validation

Install the 203 manifest files into a new empty tree and require exact relative
file-set equality, sizes and hashes; reject missing files, any extra source/native
module/bytecode, symlinks and path escapes. Do not carry over old `__pycache__`.
Verify the weight before creating a model; missing local code or weight must fail
rather than enter the remote fallback. This is a deployment/provenance check, not
an algorithm change to the frozen run.

`PYTHONDONTWRITEBYTECODE=1` prevents bytecode writes; it does not prevent reading old
bytecode. A fresh tree without bytecode (or a fresh private pycache prefix) avoids
this gap. The current source-only manifest does not independently attest the 75
cached bytecode files. Also retain environment/package identities: layer attention
uses optional xFormers (`layers/attention.py:21–33`), outside this source-tree hash.

The current `scripts/prepare_steering_assets.py:160–165` only requires DINO hubconf
and the weight; full-tree strict validation would be an additional provenance
check after the current runtime freeze, not a claim that it already exists.

Portable manifest metadata now uses logical_root=torch_home and
relative_source_root=hub/facebookresearch_dinov2_main; no machine absolute path
is embedded. File-set digest is unchanged. Final manifest file SHA-256:
`c7c7be63a1979638451f8f6f6ef5b21bfabda90c5b23e8db77ec22ee0be2d193`.
