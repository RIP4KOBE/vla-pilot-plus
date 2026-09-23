# Bounded cached-provider source review

Scope: the four already frozen development cache files for tasks 0 and 5, their metadata, and the production loader. No new observer artifact, validation/formal data, model, credential, provider call or GPU was used. `static_review.py` only reads these explicit source/metadata files, uses `compile` and `marshal` on code objects, and writes a new output directory. It does not import torch or execute the compiled code.

The existing `utils/guidance_utils.py` loader replaces specified numpy strings, executes the resulting text through `exec_safe`, and attaches `_guidance_source_text`, `_guidance_source_path` and `_guidance_original_func` to a device-fix wrapper (lines 75–126). The collector's previous `code_sha256` was that shared wrapper's bytecode, not the captured reward. Therefore stage1 and stage2 could have the same wrapper hash despite different meanings. Source identity must use the added original-code hash, loader-text hash and path. Stage/task labels explain a source association but cannot establish it.

`static-output/review.json` records Python/marshal/compiler versions and all reviewed file hashes. `static-output/provider-target-map-v2.json` contains only the two stage1 approach entries. These static original hashes remain **pending exact match against runtime-recorded identities**. A mismatch or missing metadata produces Unknown, never a stage-name fallback. An exact runtime triple match is marked `runtime_original_code_text_path_match=true` by the analyzer. This does not turn a static file into an observed task outcome.

| Task / stage | Actual source semantics | Target map disposition |
|---|---|---|
| task0 / stage1 | `target_idx = torch.tensor([0], ...)`; `target_pos = keypoints[target_idx][0]`; negative weighted sum of squared trajectory-to-target distances, then mean over batch | Fixed keypoint0; approach proxy. Frozen metadata labels it alphabet_soup_1_main. |
| task5 / stage1 | Byte-identical function to task0 stage1 | Fixed keypoint0; approach proxy. Frozen metadata labels it tomato_sauce_1_main. The alphabet-soup comment is stale and does not determine the actual object mapping. |
| task0 / stage2 | Returns `torch.tensor(0.0, device=action_sequence.device)`; no keypoint access | No target, no approach objective; intentionally absent from target map. |
| task5 / stage2 | Byte-identical constant function to task0 stage2 | No target, no approach objective; intentionally absent from target map. |

The approach classification follows the function expression, not its grasp comment: every normalized weight is positive, so reducing a scored point's target distance with the others fixed raises the reward. For seven input points, weights are `[1,1,1,1,3,3,3]/13`. This is a weighted **whole-prefix** objective, not an endpoint-only reward. It contains no gripper/contact/object-motion term and proves neither grasp nor task success. The analysis continues to call distance an EEF proxy relative to the decision's frozen target, not a live object position.

Reviewed raw source SHA256:

* Stage1 both tasks: `d374557f569b8c69f898a1596dfefd32a21774929511bb969d5d27e0050d4830`.
* Stage2 both tasks: `ca058cc1dcf87ce5910181800bb2f65b8cd4d92788b27f3b10b1e33dbc103f84`.
* Production loader: `b0fe9d6d5fc014143f5877918de9bd0986b1688b4a6a90980847b7d15cab0c82`.

Static original-function code hash candidates under the recorded Python 3.12.12/marshal/compiler settings:

* Stage1: `64bfc5d573100a463facb1849937b4fbd895070028584e2f0d8d3d3aa21dcfe6`.
* Stage2: `83ea6176054c2c82bbd3f94f1f3eb2c91a1169357f7eed6672b148868aff9a40`.

The raw byte hash and loader-text UTF8 hash are distinct fields. The exact SHA-bound loader replacement sequence is reproduced statically; it leaves these four specific torch source files unchanged. Equality here is checked, not generalized to arbitrary cached functions. The analyzer's minimal v2 map accepts only this explicitly verified `source_text_transform=identity` case. The file path participates in identity, so task0 and task5 remain separate even with byte-identical functions.

To reproduce the review, use a new output directory and the production worktree path as the compile filename for the loader. The cached original functions compile as `<string>`, matching the loader's `exec` string semantics; `dont_inherit=True` prevents the review script from supplying future flags. No `exec`, `eval`, function call or loader import occurs:

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python \
  docs/03_evidence/qd_ed_final/continuation_20260923/decision-analysis-draft/provider-target-review/static_review.py \
  --production-worktree /home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z \
  --artifact-root /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z \
  --output-dir /absolute/new-static-review
```

The script refuses changed reviewed source hashes and refuses an existing output directory. Hash candidates are interpreter/compiler-dependent. It deliberately does not certify that a future runtime used the source; matching recorded collector identity plus the existing complete episode audit is still required.
