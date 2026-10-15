# Provider identity correction: CPU reproduction and unactivated supplement

2026-09-23 UTC. This is a **post-data identity engineering correction**, prepared after the completed task-0 C0 frozen analysis reported zero exact target-map matches among 29 guided decisions. It does not replace that analysis, alter an A/B formula or threshold, change a promotion condition, or authorize another analysis/run. W remains frozen at `0d59b853a241cd88d984f5126428720a14abbfd5`. Only this new E directory is written.

The mismatch is reproduced exactly without calling a provider. The static review compiled the text with a literal filename `'<string>'`; the production loader passed the same text to `exec`. On the frozen Python 3.12.12 / marshal v4 runtime, the resulting code fields have equal values, but `co_filename` has a different string-interning representation in marshal. That one byte changes the raw code SHA. Compiling with an independently interned filename reproduces the real loader's marshal bytes exactly. Thus matching the filename's text was insufficient for matching this raw serialization identity.

Sources in W:

- `utils/guidance_utils.py:45`: `exec(code_str, custom_gvars, lvars)`; `:105` invokes it; `:112`–`:114` attach transformed source text, source path and original function. The module has no future import. Its `exec_safe` future-flag mask is zero in the reconstruction.
- `core/decision_evidence.py:47`–`:68`: original identity is SHA-256 of `marshal.dumps(original.__code__)`, with no canonicalization of interning/representation. The observer's own future-annotations flag does not recompile the provider.
- `docs/03_evidence/qd_ed_final/continuation_20260923/decision-analysis-draft/provider-target-review/static_review.py:77`–`:82`: static compile uses `flags=0, dont_inherit=True, optimize=0`, then marshals the nested code directly.

| Reviewed sources | Original static SHA | Derived real-loader SHA | Sole marshal byte difference |
| --- | --- | --- | --- |
| task 0 and task 5, stage 1 | `64bfc5d573100a463facb1849937b4fbd895070028584e2f0d8d3d3aa21dcfe6` | `a6efff2bb46ca4038d30b63cbcdf340a126b10efeffa0830288ba0879b8484fa` | offset 891: `0xfa` → `0xda`, before `\x08<string>` |
| task 0 and task 5, stage 2 | `83ea6176054c2c82bbd3f94f1f3eb2c91a1169357f7eed6672b148868aff9a40` | `0a648f81c0572e440ea64777199d1e22bcefcce77ed74e31757a8d7cbe8a0a00` | offset 175: same filename marker change |

The markers encode non-interned versus interned short ASCII, respectively, including the same reference flag. The controlled `sys.intern` filename experiment changes no source, arguments, optimization setting, bytecode, constants, line table, or function flag values; its complete marshal bytes equal the actual loader reconstruction for all four definitions. Static and actual `co_flags` are both 3. A separate future-annotations control gives 16777219 and is rejected as equivalent. This rules out inherited future flags as the cause of this particular original-code mismatch.

`output/reproduction.json` records every non-callable public `co_*` field's typed value and canonical value hash, the full value-structure hash, raw marshal SHA/length, differing-byte context, source hashes and identities for static, actual-loader, interned-filename-control, and future-flags-control variants. Canonical value hashing is an experimental equality check, not a new deployed provider identity or map acceptance rule. For each stage, static/loader/interned variants have equal field values; task 0/5 share the same source. No runtime code object was captured by the original collector, so field equivalence is a **CPU reconstruction**. The observed runtime source/text/path and original SHA match the reconstruction for completed C0 stage 1; runtime code fields, stage 2 identity and task 5 identity were not newly observed here.

## Reproduction safeguards and result

`reproduce_identity.py` executes the frozen loader and collector module definitions under forbidden `torch`/`numpy` stubs. It calls the original `load_functions_from_txt(..., validate=False)` and `_provider_identity`, preserving their source transformation, `exec` definition, wrapping and metadata logic. The four provider sources are AST-checked to contain only a function definition without decorators/defaults/annotations; creating those definitions cannot run a provider body. A profile guard raises on any provider-body or validation call. No tensor/model/GPU API, real torch/numpy import, provider validation, reward computation, simulator operation, or network call occurs.

The complete CPU reproduction succeeded: four source definitions, four exact static-hash reproductions, four full code-field equalities, four one-byte differences, four interned-filename-control matches, four future-flag negative controls, **zero provider calls and zero validation calls**. Source transformation was identity for all four. The old map was rehashed after generation and was unchanged. No additional project test suite was run for this artifact-only change.

From E, the command used was:

```bash
/home/hynx/miniconda3/envs/vla-pilot/bin/python docs/03_evidence/qd_ed_final/continuation_20260923/provider-identity-correction/reproduce_identity.py \
  --production-worktree /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z \
  --old-map docs/03_evidence/qd_ed_final/continuation_20260923/decision-analysis-draft/provider-target-review/static-output/provider-target-map-v2.json \
  --old-review docs/03_evidence/qd_ed_final/continuation_20260923/decision-analysis-draft/provider-target-review/static-output/review.json \
  --completed-identity-summary /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/observed-pairs-v1/analysis/t00-c0/run_20260923T063829Z/interpretation-summary.json \
  --output-dir docs/03_evidence/qd_ed_final/continuation_20260923/provider-identity-correction/output
```

For reproduction, use a **new** output directory; the script refuses to overwrite an existing one. The complete episode summary is read only after deriving the supplemental map, solely for an identity comparison. It is not an input to the replacement-hash calculation. No ongoing Q0 or other episode bundle was read.

## Supplement status and exact scope

`output/supplemental-map-v3.json` preserves the `qd-ed-provider-target-map-v2` payload schema accepted by the unchanged frozen analyzer, and adds `supplement_version=3` plus post-data provenance metadata. **Inside each existing target entry the only changed field is `original_code_sha256`.** Both replacements are produced by the real loader definition path from the frozen source, not copied from observed hashes. All existing source/raw hashes, source paths, target expressions, index, object labels, objective annotations, and wrapper descriptive fields are unchanged; historical `static_original_hash_status` labels inside copied entries remain historical, with the top-level supplement metadata documenting the correction. Stage 2 is verified in the reproduction but has no target, so no target entry is added.

The frozen map's SHA is `26fe347f9f343723943927b5bed84339f59fa284252698594dcb207f8cfc0585` (also independently checked in W). The old frozen C0 result remains **0/29 exact target matches, A/B Unknown**. This directory does not rerun, replace, or merge it. Root review and explicit authorization are required before separate supplemental analysis.

The completed C0 summary contains two wrapper-code hashes (8 and 21 records). The CPU loader matches the first, but the cause of the second is **Unknown** and is not explained by this original-function filename experiment. Wrapper identity is descriptive only; the supplement retains the original-function/source-text/path triple. Raw marshal identity can be representation-sensitive, so this result is bounded to the frozen interpreter/source/loader path; it is not a general cross-version semantic fingerprint design.

Artifact SHA-256:

```text
e0547e51c6565f9554f859926540e99d0b86dfc19d234864c6b8fc66aadac9e0  reproduce_identity.py
4b04ad468f811029cab8dbb3904326947e4d7e2ff6594fb44a8adfc16f9d0af2  output/reproduction.json
b7ccff3644c4adfa0b2ac3b0b695048f0da97660c46ea1a433491ad8305e49ae  output/supplemental-map-v3.json
33d017b44e793075b5b3d308c6e49f54c2ecf48dc700473d4614db6d8aaf1195  completed C0 interpretation-summary.json (external input, unchanged)
```
