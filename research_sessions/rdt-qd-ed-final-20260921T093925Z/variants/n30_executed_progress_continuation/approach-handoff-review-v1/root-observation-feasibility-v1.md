# Static observation feasibility note — no new algorithm nomination

2026-10-04, root coordinator. Current priority remains the released preparation of the fixed step16→24 tensor reader. This note changes neither that sampling rule nor any execution permission.

The accepted first-active evidence supports actual approach, but does not measure grasp. A useful later question, conditional on the handoff results, is whether current observation geometry could distinguish candidate gripper orientation/clearance at the target, rather than repeating a distance/close-command bonus. This is an untested question, not a nominated candidate, a claim of novelty, or an approved sensor/provider change. Existing N12/N15/N16 scope/results would need comparison before a future nomination.

Static observations at current source 6292fc8cffad2eec0f789e023d835ad3c1df146a:
- core/env_adapters/libero_adapter.py:718–724 creates OffScreenRenderEnv with camera_depths=True. This does not by itself prove which depth arrays are currently retained or accessible to policy.
- The same file:1532–1612 get_keypoint_detection_inputs renders RGB/depth AND segmentation anew, converts normalized depth, invokes process_segmentation and camera calibration, and returns world points. Calling that whole function is not equivalent to reading an already-recorded depth field; it includes segmentation/object-name information that a new deployment feature must not silently consume.
- main.py:543–570 uses that tuple in keypoint detection/retry. It is not evidence that each decision currently receives this tuple as a policy observation.
- get_obs at adapter:1787 returns cached _last_obs. The present static inspection does not establish contents, freshness, camera alignment, masking, or whether saved artifacts contain depth. No environment was imported, rendered, queried, or stepped.

The original execution specification permits internal QD quality from currently available observations/actions/history (§5), freezes Stage/cache/perception/prompt and the external provider, and requires declared matched controls for extra search compute (§8). Therefore existence of a depth API is insufficient authorization or evidence for changing perception, using segmentation/object poses, extending Stage, or increasing compute without a frozen matched protocol. No such change is made here.

Source bindings:
- main.py: 5209b0ac07362e1df85bf2fd842e57d4786e24c0a625ee5b9e49bee48f528f93 (108959 bytes).
- core/env_adapters/libero_adapter.py: 22e8be88e1a68bcffdd72536b79e7f9e4d56efdc0b12b5a0c3fb1c7877930c64 (72160 bytes).
- docs/01_specs/2026-09-21-rdt-qd-ed-autoresearch-execution-prompt.md: 3a45e53d3b40fa0a40c43ad53a34cfbb8c9fe497dc98a5e178e4c1ef016999ef (21913 bytes).

Method: static rg/sed plus source hashes only. No payload/image/video decode, production import, tests, scientific numerical analysis, API or GPU use. Some initial rg path guesses did not exist; successful reads came from the paths above. This note is not part of the agent's already-frozen PhaseC manifest and does not amend its NONE_YET conclusion.
