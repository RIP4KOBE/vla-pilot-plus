# Model selector review (read-only, CPU metadata only)

The reviewed project and Transformers source were read without loading weights,
models, GPU, network, or modifying repository/cache/shared environment. The four
Transformers selector implementation files have identical SHA-256 in the current
and newly installed clean environments. No large model weight was rehashed in this
selector review. Tiny synthetic counterexamples were created and removed under /tmp.

## Required fixes in the /tmp verifier

1. **RDT config uses exists, not is_file.** Runtime
   `core/rdt_policy_steer.py:1100–1109` selects the first existing config.yaml/json,
   then opens it. `_selections` currently uses `_first_file`, silently skipping a
   higher-priority directory. Creating `ema/config.yaml/` makes the verifier pass
   but the real loader selects a directory and fails. Select first existing config,
   then require regular-file access / accepted path+hash. Include a directory-shadow
   negative case, alongside the existing file/symlink shadows.

2. **Allow current __pycache__, reject new sourceless package bytecode.** All 75
   current DINO `.pyc` files are in `__pycache__` (25 each CPython 3.10/3.12/3.13).
   The default currently permits *all* extra `.pyc`, including
   `dinov2/hub/backbones/__init__.pyc`, which Python selects as a package before the
   hashed `backbones.py` module. Reject extra bytecode outside __pycache__; preserve
   the explicit limitation that existing cached bytecode is not attested.

3. **DINO directory symlinks conceal importable shadows.** rglob does not walk a
   symlink directory. `dinov2/hub/backbones -> foreign_package/` containing
   `__init__.py` changes actual import selection yet currently passes. Reject DINO
   directory symlinks (none exist in the current cache), including symlink ancestors;
   retain HF *file* blob-symlink compatibility as described below.

All three were independently reproduced with verifier `valid=true` in
`/tmp/steering-model-selector-negative-review.json`. For the DINO cases,
`importlib.machinery.PathFinder.find_spec` confirmed the new origin without executing
any module or bytecode. They affect hypothetical changed layouts, not the current
accepted assets.

## Exact RDT selection order

For accepted checkpoint directory R and weight_variant=ema:

- Weight directories, outer loop: `R/ema`, `R/rdt/ema`, `R`, `R/rdt`.
- Within each: `model.safetensors`, `pytorch_model.bin`,
  `mp_rank_00_model_states.pt`, `rdt-1b.pt`; first is_file wins.
- Effective config directory order: `R/ema`, `R`, `R/rdt/ema`, `R/rdt`, parent(R).
  Actual construction includes harmless duplicate R/R/rdt entries; do not sort.
- Within **each directory**, test config.yaml then config.json. It is not a global
  YAML-before-JSON search. If all are absent, the runtime falls back to bundled
  third_party/rdt/configs/base.yaml; this accepted-identity verifier should reject.
- Accepted selected files are `R/ema/model.safetensors` and `R/config.json`.
  Real config shadows are R/ema/config.yaml, R/ema/config.json and R/config.yaml.
  A config in R/rdt/ema or parent(R) is lower priority while accepted R/config.json
  exists, so it is safe to allow as unused.

Source: `_rdt_weight_search_dirs:524`, `_resolve_rdt_weight_file:537`, config search
`:1094`. Direct-file input has different checkpoint-root derivation at `:547–553`;
current local profile/verifier supports a directory root, not arbitrary direct-file
mode. Explicitly keep that supported boundary instead of emulating it incompletely.

## Exact T5 / SigLIP weight and tokenizer selection

RDT T5Embedder (`third_party/rdt/models/multimodal_encoder/t5_encoder.py:74–84`) calls
AutoTokenizer and T5EncoderModel without overriding use_fast/use_safetensors.
The project redirects the symbolic T5 name to the explicit snapshot and forces
local_files_only (`core/rdt_policy_steer.py:1204–1213`). Safetensors is installed.
Transformers modeling_utils.py:1035–1064 chooses, for this accepted invocation:

1. model.safetensors
2. model.safetensors.index.json
3. pytorch_model.bin
4. pytorch_model.bin.index.json

Current T5 has only the third choice; either safetensors file/index is a real shadow.
A bin index is lower priority while the accepted bin exists and may be tolerated.
Current SigLIP uses the first choice; extra .bin/index/unused checkpoints are ignored.
Reject selection changes, not every *.bin/*.safetensors in a directory.
The current prepare_steering_assets.py:166–169 enumerates .bin before safetensors;
that presence check is not the actual Transformers selection order.

AutoTokenizer defaults use_fast=True (tokenization_auto.py:948), chooses T5 fast
from config.model_type=t5, and T5 maps `spiece.model` plus `tokenizer.json`
(tokenization_t5_fast.py:35). tokenizer.json, when present and not from_slow, creates
the backend directly (tokenization_utils_fast.py:115–120), bypassing the accepted
SentencePiece conversion. Thus a new tokenizer.json must be rejected unless an
explicit accepted manifest records that different tokenizer contract.

Also hash/check tokenizer_config.json, special_tokens_map.json, spiece.model; reject
unrecorded added_tokens.json (tokenization_utils_base.py:1897–1906). Current
configuration has no tokenizer_class override, auto_map, fast_tokenizer_files or
from_slow override. Versioned tokenizer files only matter if the hashed config
points to them (:1943–1945); do not blanket-reject arbitrary similarly named docs.
chat_template.jinja is irrelevant to this ordinary T5 tokenizer(text) call; it is not
an action-changing shadow merely by existing. The preserved config/special-token
hashes protect the tokenizer settings that are actually consumed.

The draft additionally rejects adapter_config.json for T5/SigLIP. This is a prudent
unsupported-profile guard but is stricter than this exact environment: neither
current nor clean environment has PEFT installed, and modeling_utils.py:4491–4495
only performs adapter redirection when is_peft_available(). State the conservative
scope instead of claiming that file necessarily changes current loading.

## Minimal compatibility boundary

- Continue permitting the observed __pycache__ files (with unverified-bytecode
  limitation), extra documentation, and lower-priority unused model/checkpoint files.
- Reject extra DINO .py/native modules and source/package directory symlinks, plus
  legacy/sourceless bytecode outside __pycache__. The optional clean-distribution
  mode can require exact regular-file set and no bytecode at all; do not apply it
  retrospectively to or mutate the live cache.
- HF snapshot paths are normally symlinks into sibling blobs outside snapshot root.
  Allow expected file symlinks with live regular-file referents and verify target
  content size/SHA. Reject missing/broken links. Manifest relative names themselves
  must remain normalized and nonescaping; do not require resolved blob targets to
  stay inside the snapshot root. A new higher-priority shadow symlink still changes
  selected filename/format and must be rejected even if its target shares bytes.
- Avoid importing Torch/Transformers/model code merely to choose a filename; static
  selection against these version-pinned rules is sufficient. Report the selected
  lexical paths and verification/library identity, not an inferred model load.
- Do not edit the verifier while its large-file hash run is active: it currently
  hashes __file__ only at return, so changing that file mid-run can misattribute the
  running code. Capture/compare start and end script hashes or serialize revisions.

Recommended regression additions: the three reproduced failures; allowed lower-
priority config under R/rdt/ema and parent(R); allow unused T5 bin index; reject both
T5 safe candidates; accepted HF blob links pass and broken/shadow links fail. Existing
31 tests already cover many of these and should remain small synthetic CPU tests.

## Final re-review

The author fixed all three required points and reports 34 CPU tests passing. An
independent rerun of the three counterexamples now rejects all three; details in
`/tmp/steering-model-selector-negative-review-final.json`. No new blocking issue
was found in the current-compatible selector scope. The default bytecode limitation
and conservative PEFT adapter_config rejection remain explicitly bounded above.

Reviewed verifier SHA-256: `1f233713300231ce1397c4e7fcc67b378ee5aa63014c69ba73551ae7dba17d30`.
