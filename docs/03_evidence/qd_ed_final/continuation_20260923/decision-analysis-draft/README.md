# CPU-only selected-decision analyzer

The prospective scientific definitions and evidence-selection rules are frozen in the sibling `../decision-analysis-draft.md`. This implementation reads one explicit complete episode; it does not wait for the four-row matrix and never aggregates a performance comparison automatically. It imports only the existing CPU auditor and torch for safe tensor loading/arithmetic. No model, provider, simulator, Stage, network or CUDA work is performed.

Run from the evidence worktree root. Use an output path that does not exist and is outside the episode directory:

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python \
  docs/03_evidence/qd_ed_final/continuation_20260923/decision-analysis-draft/analyze_episode.py \
  --episode-dir /absolute/attempt/eds_eval/decision_evidence/episode_000 \
  --episode-compute /absolute/attempt/eds_eval/episode_compute.jsonl \
  --target-map /absolute/reviewed-provider-target-map.json \
  --output /absolute/new-analysis.json
```

The script reruns `scripts/audit_decision_evidence.py::audit_episode`, requires complete accepted evidence, then rereads verified CPU bundles. The queue's saved `eds_eval/decision-evidence-audit.json` may first be checked for accepted/complete, but it is not a substitute for validating current bytes. Source status, index, bundles, compute row and optional target-map/source hashes are recorded and checked before output. Existing results are never overwritten. Failure exits before writing the output JSON.

Omit `--target-map` to obtain selected EEF projection errors and actual gripper feedback immediately. All target-distance and target-based mechanism witnesses then remain null/Unknown. The script neither assumes keypoint zero nor averages keypoints. Guided and unguided decisions, stages and provider identities remain separate; unguided decisions without saved scoring projections retain their actual feedback.

The reviewed map format is:

```json
{
  "schema": "qd-ed-provider-target-map-v1",
  "entries": [
    {
      "provider_code_sha256": "<64 lowercase hex from this decision's recorded provider>",
      "source_path": "/absolute/frozen/cached/reward_function.py",
      "source_sha256": "<SHA256 of the reviewed source bytes>",
      "target_selection": "fixed_keypoint_index",
      "keypoint_index": 2,
      "target_expression": "<exact source expression identifying this keypoint>",
      "reviewed_against_frozen_provider_source": true,
      "distance_progress_interpretation": "approach_proxy",
      "approach_review_basis": "<source expression establishing decreasing EEF distance as this stage's approach objective>"
    }
  ]
}
```

This is a schema example, **not an actual mapping**; index 2 is illustrative and must not be used without source review. Omit `distance_progress_interpretation` or set it to `descriptive_only` if distance is merely a geometric proxy; distances can still be reported, but the two approach hypotheses stay ineligible. No provider code is executed. The code-SHA/source-SHA association and semantic statement must be established by explicit review of the actual loader/cache provenance; the analyzer only verifies the binding and recorded data, and cannot prove a false annotation correct. Review cannot silently add a provider target where the source is conditional or ambiguous. One-provider fixed-index targets are supported; multiple providers, missing identity, reordered scoring keypoints and unavailable source are Unknown/rejected as appropriate. Do not point this map at credentials or unrelated source files.

JSON contains every actual decision and execution prefix, raw postprocessed command signs, gripper qpos/qvel if recorded, source and projection dtypes, canonical equal-value associations, associated provider returns/quality, per-prefix EEF errors, target distances if resolved, actual/projected step7→8 change, and the full-prefix versus through-step7 diagnostics. It includes strata and witness IDs without selecting a candidate. `hypothesis_eligible` excludes transformed translations, a non-normal reward mode, unresolved/non-approach targets and the wrong provider slice. `unknown_reasons` and `hypothesis_ineligible_reasons` preserve these exclusions. A raw numerical witness is only descriptive if hypothesis_eligible is false. Equal fingerprints are a content association, not recovered archive ancestry. Unexecuted counterfactual outcomes and physical grasp success remain Unknown.

The source arithmetic is float64 after loading; BF16 quantization is preserved and reported via a fixed adjacent-representable-spacing floor. ULP screens are not physical uncertainty estimates or statistical confidence. The script computes EEF tracking even when it cannot identify a target. It reports observation success/reward without changing the original episode outcome or accounting.

Focused CPU verification:

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /home/hynx/miniconda3/envs/vla-pilot/bin/python \
  -m pytest -q -p no:cacheprovider \
  docs/03_evidence/qd_ed_final/continuation_20260923/decision-analysis-draft/test_analysis.py
```

Tests use explicit synthetic arithmetic fixtures and the existing collector's CPU-generated audit fixture, marked `input_kind=synthetic_unit_fixture`. They verify exact tracking, tail reversal, projection optimism, unknown-target handling, short-prefix limits, BF16 resolution, nonzero reviewed keypoint selection/reorder rejection, source hashing, real audit acceptance and tamper refusal, canonical/auxiliary separation, ambiguous content association, and the CUDA-uninitialized guard. They are not runtime task data or evidence for either scientific hypothesis. No new observed episode was read to define the diagnostics.
