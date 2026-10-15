# Selected tracking independent review — protocol/source stage

Status: protocol SHA verified; implementation and synthetic regression review pending.
Only source files listed in source-review-inputs.json were read. No real episode
bundle, tensor, trajectory, image/video or additional outcome was read. Existing
future-evaluation commits ed56611/78aa664 remain unchanged.

The bounded descriptive question is supported by the recorded hooks: canonical
scoring stores a full t0..t8 projection plus explicit origin sequence references;
the selected latent and committed chunk are recorded before action dispatch;
actual sent action and pre-reset EEF are recorded inside that dispatch window.
The required i-th response maps to x_i, not x_(i-1). No model, new projection,
provider score or target value is needed for the proposed arithmetic.

Implementation checks to apply:

1. Fingerprints normalize samples to FP32 and are only an index. Compare native
   shapes/dtypes/bytes and explicitly documented output casts. The production
   guided return performs action masking then FP32 conversion; do not use a
   broad numeric-equality join. Preserve all equivalent occurrences and mark
   distinct native projection/origin values ambiguous rather than choose one.
2. Use each canonical scoring row's projection_origin_sequences link, require
   same decision and earlier sequence, and compare cast origin with x0. Later
   debug drawing may also emit projection_origin, so the last origin in the
   decision is not necessarily the selected score's origin.
3. action_dispatch(s+i-1,i), executed_action, pre_reset_outcome and step_returned
   must be joined in order. Automatic reset increments reset_sequence between
   the old pre-reset outcome and terminal step_returned. Preserve that final
   old-episode response while ending temporal continuity; do not attach the new
   initial observation or reject the response solely due to the increment.
4. Decode→commit→sent positions/rotations must retain the frozen native/FP32 path;
   gripper sign conversion is separate. Report real mismatches instead of
   reconstructing the decoder to hide them. The declared +/-1 bounds and0.01
   projector constant are descriptive, not evidence of actual controller gains,
   clipping, contact or a reason to tune the constant.
5. Retrospective pair eligibility must use the immediately preceding complete
   eight-action guided decision, with all responses occurring before the next
   decision. OFF, reset, terminal/truncation, missing identity, stage/provider
   changes or execution gaps break continuity. Use only the prior endpoint in
   the fixed i/8 rule. Actual current prefix length never changes denominator8.
6. Origin cast error and origin bridge remain distinct. Float64 subtraction
   describes stored values only; it does not restore native lost precision.
   Per-episode summaries must keep all decisions and Unknown reasons, with no
   success/error-based row selection or chunk-level independent-sample claims.

The accepted protocol deliberately does not identify physical causes or infer a
counterfactual task outcome. A lower fixed predictor error is not deployment,
quality, controller-fix or promotion evidence. No new gate is proposed here;
these checks implement the already frozen scope. Root must bind the eventual
reader, its tests, exact30 representatives and fresh-audit/input hashes before
any authorized real tensor decode.
