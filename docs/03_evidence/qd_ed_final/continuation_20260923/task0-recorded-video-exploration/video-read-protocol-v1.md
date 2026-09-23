# Task0 recorded-video read protocol v1 — proposed, not yet visually executed

This is a separate bounded post-outcome Dev diagnosis. The completed numerical protocol excluded images; this document requests a distinct read scope for existing videos. No video frame/image pixel has been displayed or extracted in this preparation. Metadata collection used file hashes, PNG IHDR headers and ffprobe container/stream metadata only (no frame/count_frames output). No dependency, GPU, model, provider, projector, new environment or render call was used. Current N2 cohort, source, quality rule, evidence, budget and acceptance gates are unchanged.

## Exact eligible inputs

Only these three videos from the accepted task0 arms may be decoded after root authorization:

| Arm | Exact attempt ID | Relative video | SHA256 |
|---|---|---|---|
| C0 | `rdt-qd-ed-final-20260921T093925Z__n2_dev_t00_c0_20260923__3cc1e46f83d0` | `episode_1/episode_1_fail_agentview.mp4` | `8477b50c6e7c47bc6ac9684966748247e0a0ed923dffe1d6e88bf69ae6ab3615` |
| Q0 | `rdt-qd-ed-final-20260921T093925Z__n2_dev_t00_q0_recovery1_20260923__28dd3c7a9e74` | `episode_1/episode_1_fail_agentview.mp4` | `b57484efdec6e1e9282f5da535a4b87666c1bc6d6cf7e83454f0f00159370ce6` |
| N2 | `rdt-qd-ed-final-20260921T093925Z__n2_dev_t00_n2_20260923__45c5f8694f85` | `episode_1/episode_1_fail_agentview.mp4` | `5819b83c4ca547db7a0849116f301cca4aa83cb3e40eecf48d490a7395c6be65` |

All absolute paths are frozen in `visual-inventory-v1.json`. Each video reports a single H264/yuv420p 640×640 stream, 720 container frames, 10/1 average and nominal fps, start 0 and duration 72 s. These are reported container counts, not a claim that all decoded pixels have been examined. The inventory also binds C0 132, Q0 150 and N2 150 existing PNG artifacts and header shapes, but **none of those still images is in the proposed viewing scope**. Many are candidate overlays or plots rather than executed scene frames. No other attempt, invalid Q0, task, evaluation, historical video, tensor bundle, image, main log or Stage prose is admitted.

The only numerical inputs needed for captions are the already approved `explanatory-read-v1/output-v1/closed-loop-sequence.json` (SHA `b8a7c7bce23975ff1f421c7e7cd87eccc7d2517549301f4a81fb34189d1affa4`) and its `inputs-and-audit.json` (SHA `dfddb2ff80734cabf7a819beef213ded8ab3410a02cc0a6b49ebced48fe70910`) with three accepted complete fresh audits. This is not authorization to read any additional bundle or outcome. Before decoding, reverify these hashes, the source-frame mapping/inventory hashes, all three video hashes and the already bound accepted terminal/audit identities. Changed or missing inputs stop the affected read; do not substitute another attempt/video.

## Proven timing and residual uncertainty

Frozen source is `525506ca3198f54d86dadf84bbb76eb64926d87a`; source SHA and reviewed sites are in `source-frame-mapping-v1.json`. The recorder is cleared before episode reset. Resolved reset warmup is five no-op simulator steps, not recorded in the episode video. At every main-loop action, any new Stage decision and policy chunk happen first; image/status capture and one recorder append then occur **before** dispatch and adapter.step. Global step increments afterward. The saver writes the append-ordered frame list at 10 fps with no deliberate dropped/duplicate loop frames.

Thus the source/container-consistent mapping is presentation frame f = **before action global_step f**, with f completed episode actions (warmups excluded). Frame0 is the initial prepared scene before action0; frame f≥1 can depict the response to action f−1 when no intervening reset/action occurs. Frame719 precedes action719. There is no frame720 showing the last action's response, so a final video thumbnail is not the terminal post-action observation. The accepted numerical records have no terminated/reset boundary, and all end in truncation after720 actions. If visual Step text or decoded count contradicts the mapping, record the discrepancy and leave timing Unknown; do not shift or cherry-pick frames to obtain agreement.

The resolved camera is agentview, with 640×640 visualization renders; policy images are128×128 and can include other views not present in this video. Normal LIBERO overlay capture uses the raw render then vertical flip before text. Early-return rendering exceptions can bypass that flip, so orientation is a source expectation pending visual inspection, not pixel-verified provenance. Video f/10 is playback time, not inference wall time or asserted simulator time.

Debug trajectory drawing is enabled in all3 recorded configs. Colored curves/markers are projected **predictions**, not an executed path or measured object motion. Stage/Guide text describes the pending action's active state; Grip text describes a planned gripper command, not observed qpos/contact. `Norm_R`, shown only with guidance, is rounded to two decimals after the current policy call and must not be used to reconstruct the earlier exact Stage-query normalized reward. The save routine retrospectively stamps FAIL/SUCCESS onto every frame; that label says nothing about when failure/success occurred. Status text, predictions and lossy encoding can obscure physical scene details.

## Fixed selection before any pixel inspection

Use exactly the same zero-based frame grid for all3 arms:

`[0, 8, 16, 24, 32, 64, 96, 128, 160, 240, 320, 400, 480, 560, 640, 719]`

This gives16 frames per arm,48 total. It samples early chunk boundaries densely and then the whole episode coarsely; it is not exhaustive coverage of all Stage events. No extra frame, crop, zoom-selected region or alternative view is added after viewing. Any follow-up requires a separately stated bounded scope.

After root approval, software-decode by exact presentation ordinal (e.g. ffmpeg decoded-frame select n, with hardware acceleration disabled), not approximate keyframe/timestamp seeking. Preserve selected frames as lossless640×640 PNG, recording parent video SHA, ordinal, intended action index, presentation time and decoded-frame SHA. A stream decoder may process intervening compressed frames to reach the selected ordinals; those nonselected frames are not exported or inspected. Do not invoke a model, OCR service, provider, simulator or renderer. Use installed CPU tools only.

Make four deterministic contact sheets: three rows in fixed order C0 / Q0 recovery1 / N2, four chronological columns per page, using the16 indices in order. Retain the entire image without crop/enhancement or removal of original overlays; any resizing is uniform with the transformation recorded. Add an external caption showing arm, exact frame/action-before index and existing recorded Stage/guidance, clearly separated from the recorded image. Use a fixed tile size for allarms (480×480 for sheets, native selected frames retained). Do not use source candidate-plot PNGs to fill obscured scenes. Check only the already selected frames' visible step/state labels against the source/numerical mapping; no extra frames for repair.

## Allowed interpretation and outputs

Describe directly visible robot/gripper arrangement, object scene arrangement and their chronological changes, tied to selected frame ordinals. An apparently nearby/touching object is not proven contact or a sustained grasp; visibility through occlusion, exact3D pose, force, goal identity, insertion, object capture/release and counterfactual outcomes stay Unknown without independent admitted evidence. A colored prediction is not observed movement. Do not infer success/grasp from reaching a timeout, from FAIL text, or from finger-command sign. Same seed/init does not create matched post-action states between arms. Sparse views cannot rule out intervening transient motion. No target map is supplied; do not label index0 as the manipulation target or compute target progress.

Produce only a decode/caption manifest with input/source/tool/frame/sheet SHA and all selected indices, the48 selected frames and4 contact sheets, and a short chronological observation note that separates visible facts, source-associated timing and Unknowns. Keep any mapping failures visible. All outputs must be exclusive new files under a new `visual-read-v1/` sibling directory; preserve all current videos, PNGs, numerical outputs, original audits and this proposal. Root review/authorization precedes any decoding/extraction or visual inspection. This document supplies no new online dispatch or promotion permission.
