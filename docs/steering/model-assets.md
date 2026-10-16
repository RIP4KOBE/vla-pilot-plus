# Model assets

The required RDT and π0.5 checkpoints are publicly hosted and still present in the maintainer's local cache. Their exact files have now been matched against fixed public revisions. A private model bundle is **not** required. The PaliGemma tokenizer requires the user's own approved Hugging Face access; model licenses remain separate from this repository's license.

## Fixed sources

| Logical directory | Public source and fixed revision | Required contents |
| --- | --- | --- |
| `rdt_checkpoint` | [TJ-chen/RDT-1B-LIBERO-Object](https://huggingface.co/TJ-chen/RDT-1B-LIBERO-Object/tree/45f425cfc22108fdf9043dd55b3bb440018db12d) · `45f425cfc22108fdf9043dd55b3bb440018db12d` | `config.json`, `ema/model.safetensors`; LIBERO Object adaptation, not generic RDT pretraining weights |
| `text_encoder` | [google/t5-v1_1-xxl](https://huggingface.co/google/t5-v1_1-xxl/tree/3db67ab1af984cf10548a73467f0e5bca2aaaeb2) · `3db67ab1af984cf10548a73467f0e5bca2aaaeb2` | `pytorch_model.bin`, config and tokenizer files; RDT only |
| `vision_encoder` | [google/siglip-so400m-patch14-384](https://huggingface.co/google/siglip-so400m-patch14-384/tree/9fdffc58afc957d1a03a25b10dba0329ab15c2a3) · `9fdffc58afc957d1a03a25b10dba0329ab15c2a3` | `model.safetensors`, config, preprocessor; RDT only |
| `pi05_checkpoint` | [lerobot/pi05_libero_finetuned_v044](https://huggingface.co/lerobot/pi05_libero_finetuned_v044/tree/dbf8a3f794a9c4297b44f40b752712f50073d945) · `dbf8a3f794a9c4297b44f40b752712f50073d945` | Model, config, pre/postprocessor JSON and both normalization safetensors; six files |
| `pi05_tokenizer` | [google/paligemma-3b-pt-224](https://huggingface.co/google/paligemma-3b-pt-224/tree/35e4f46485b4d07967e7e9935bc3786aad50687c) · `35e4f46485b4d07967e7e9935bc3786aad50687c` | Six tokenizer/config files; **no separate PaliGemma model weights** |
| `torch_home` | [DINOv2 source](https://github.com/facebookresearch/dinov2/tree/7b187bd4df8efce2cbcbbb67bd01532c19bf4c9c) · `7b187bd4df8efce2cbcbbb67bd01532c19bf4c9c`; [ViT-B/14 weights](https://dl.fbaipublicfiles.com/dinov2/dinov2_vitb14/dinov2_vitb14_pretrain.pth) | Fixed source plus the repository's explicit byte-preserving compatibility patch; pretrained perception weight |

The [upstream VLS policy configuration](https://github.com/Vision-Language-Steering/code/blob/b6e87edc217a2a7682caadba285677fc79eb6f81/configs/policy.yaml) selects the same `lerobot/pi05_libero_finetuned_v044` model identifier. The pinned model card identifies it as a LIBERO-trained checkpoint; this is not a generic π0.5 base checkpoint. Neither that name nor upstream scores establish this repository's steering performance.

The complete file list, sizes, SHA-256 values and download revisions are in [public_model_sources.json](../../scripts/public_model_sources.json). RDT's original accepted identity remains in [steering_model_assets_manifest.json](../../scripts/steering_model_assets_manifest.json). RDT requires about 50.9 GB of verified assets; π0.5 requires about 7.85 GB including tokenizer and DINO. Allow extra space for package/download caches and videos.

## Download

From the activated environment and repository root:

```bash
STEERING_ASSETS=/absolute/path/on/large-disk/vla-assets
python scripts/prepare_public_models.py download --model rdt --directory "$STEERING_ASSETS"

# PI05 only: first accept Google's model access terms on Hugging Face,
# receive access, then authenticate using your own account.
hf auth login
python scripts/prepare_public_models.py download --model pi05 --directory "$STEERING_ASSETS"
```

Each command fixes revisions, downloads only required HF files, reconstructs the exact DINO source, and verifies every output file. Existing different files cause an error; old accepted model directories are not overwritten. RDT and π0.5 can share the verified `torch_home`. Do not download generic RDT weights or substitute a similarly named π0.5 repository.

```text
vla-assets/
├── rdt_checkpoint/{config.json,ema/model.safetensors}
├── text_encoder/{config.json,pytorch_model.bin,spiece.model,...}
├── vision_encoder/{config.json,model.safetensors,preprocessor_config.json}
├── pi05_checkpoint/{model.safetensors,config.json,policy_preprocessor*,policy_postprocessor*}
├── pi05_tokenizer/{config.json,tokenizer.json,tokenizer.model,...}
└── torch_home/hub/
    ├── facebookresearch_dinov2_main/
    └── checkpoints/dinov2_vitb14_pretrain.pth
```

Only the directories for the selected model are needed. Task assets are installed separately with `prepare_steering_assets.py install-libero`; demonstration datasets are not required for rollout. Machine configuration and preflight commands are in [Installation](installation.md).

## Verification scope

Checked on 2026-10-16 UTC:

- Public metadata was retrieved at the exact revisions. All 22 local HF files were fully hashed; large files match public LFS SHA-256 and small files match public Git blob identities.
- RDT, T5, SigLIP and π0.5 config downloads returned matching complete files. Anonymous range downloads of each large model weight returned HTTP 206 with the expected full file length. These are download-access probes, **not** new full downloads of every large weight.
- The DINO source archive and complete 346,378,731-byte weight were downloaded afresh. All 203 source/config files were reconstructed to the accepted hashes. The one-file patch changes indentation and comments only; its Python AST is unchanged.
- The PaliGemma tokenizer's six cached files match the public revision. Anonymous download returns 401, as expected for gated access. A fresh download under a newly authorized collaborator account was not tested; local evaluation uses the existing authorized matching files.
- RDT's accepted [fresh-environment three-mode evaluation](onboarding-validation.md) used these same weight identities. The new π0.5 loader matched all 813 state-dict entries, including one metadata-declared tied-weight alias. Actual π0.5 rollout results and limits are in [its evaluation report](pi05-evaluation.md).

SHA identity establishes matching bytes, not training provenance beyond the publisher's metadata. A public download does not grant a new redistribution license. The DINO patch preserves the already accepted source; it does not introduce new perception behavior.

## Maintainer cache index

These paths identify the assets inspected on this server; collaborators should use their own download directory, not copy these paths into configuration.

| Asset | Maintainer location |
| --- | --- |
| RDT | `/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object` |
| T5 / SigLIP | `/mnt/data/hf_cache/hub/models--google--<model>/snapshots/<revision>` |
| π0.5 | `/mnt/data/hf_cache/hub/models--lerobot--pi05_libero_finetuned_v044/snapshots/dbf8a3f794a9c4297b44f40b752712f50073d945` |
| PaliGemma tokenizer | `/mnt/data/hf_cache/hub/models--google--paligemma-3b-pt-224/snapshots/35e4f46485b4d07967e7e9935bc3786aad50687c` |
| Accepted DINO cache | `/home/hynx/.cache/torch/hub/` |

The [compact verification record](validation/public-models-20261016.json) preserves the per-file public/local identity comparisons and download scope. Raw source metadata, comparisons, download receipts and new-environment logs are retained in the maintenance evidence archive linked from the evaluation report. Credentials are excluded.
