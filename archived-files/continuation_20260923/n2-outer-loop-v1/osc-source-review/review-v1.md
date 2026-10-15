# OSC action boundary: source-only review

The inspected source contains a concrete mismatch between the adapter projection and the controller-default action-to-goal map. This is a candidate for a separate bounded consistency test, not a demonstrated failure cause or repair. No environment was constructed, no native/GPU operation executed, and no new trajectory, image, selected projection or clipped trajectory was read/computed.

The frozen adapter has an empty action postprocessor (`/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/core/env_adapters/libero_adapter.py:1008`). At lines1699–1714 it binarizes the gripper, converts the action to FP32, records `executed_action`, and forwards the seven values. It does not clamp translation. `LiberoEnv.step` line813 forwards these values again. The `bounds=(-1,+1)` returned by `get_action_space_info` at line1621 is a declaration, not enforcement or a read of instance controller bounds.

The same adapter projection at lines1657–1674 takes the current EEF start, retains native action dtype and computes `start + cumsum(0.01 * action[:3])`. It does not clip action or read controller input/output ranges. Thus a sent-action log is a pre-controller command record, not a post-clipping goal or achieved displacement.

`_make_envs_task` at adapter lines718–724 passes BDDL/camera arguments only. The frozen LIBERO wrapper `/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/third_party/libero_pro/libero/libero/envs/env_wrapper.py` defaults to `controller="OSC_POSE"` (line17), loads the default controller JSON (line47), and forwards its dict (line59). OffScreenRenderEnv changes renderer flags only (lines157–161). BDDL domain passes controller configs through (line138); its step delegates to the robot environment (lines800–806).

The currently installed robosuite1.4.0 config `/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/robosuite/controllers/config/osc_pose.json` has input_min=-1,input_max=1; translation output_min=-0.05,output_max=0.05; orientation output ±0.5; control_delta=true, impedance_mode=fixed. `controller_factory.py:75–86` resolves and reads this default JSON. `base_controller.py:116–123` computes the affine scaling and executes `np.clip` first. Under these defaults, the symbolic positional goal increment is `0.05 * clip(a,-1,1)`, while the adapter projection uses `0.01*a`. These are different maps even before dynamics; no episode action was substituted into this expression in this review.

`osc.py:219–237` refreshes state and calls that scaling for delta control. Lines264–266 pass scaled translation and the current controller EEF position to `set_goal_position`; `utils/control_utils.py:132–145` adds the delta to current position and optionally clips a workspace limit. `single_arm.py:243–252` sets the goal once per policy step, runs the OSC and clips motor torques. Therefore even an exactly reconstructed goal map would not alone predict realized motion under orientation, inertia, contacts or joint/actuator limits.

## Provenance limit

Adapter SHA `029657074f6fc783beebc3b4a1431faceee51f970e4d79f0ead3796b6dd2f508` matches the frozen plan. LIBERO wrapper SHA `a782fb76c9792268d28979474fe72849e1e98ada49c8e997a65359a8d6b6acd0` and domain SHA `055836670ac5fcac7e033fc86404718fd53854996e5776b1ff68b646f7bbcc9d` match the runtime manifest. Its SHA is `2118d25a2e91c170c2842aec7ef11159df6c15a314d1a28153779722f22aea8e`; the runtime inventory SHA is `44d456203ca168eec9eddfb6834d54347153b2c859eb1b4fc0dea02c15138b83`. The inventory records robosuite1.4.0 and its installed module origin, but its historical libero origin entry is null; later wrapper source files are explicitly frozen. The runtime manifest contains **zero installed robosuite source/config file entries**. Current installed file hashes below establish what was read now, not immutable history of the production controller object. Actual episode-resolved `input_min/max`, `output_min/max`, `use_delta`, limits and controller class/kwargs remain **Unknown** absent an instance/config recording. The defaults must not be reported as directly observed runtime bounds.

## Minimal follow-up boundary

The source mismatch supports first binding the actual public controller attributes in a separately authorized observation of an existing environment, with no extra stepping. Any subsequent native action-bound or projected-versus-observed calculation requires its own scope; this review does not broaden the frozen tracking diagnostic. It does not rank this hypothesis over feedback, change QD/ED/reward selection, or claim clipping explains the task results.

## Read source hashes

- adapter: `/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/core/env_adapters/libero_adapter.py` — `029657074f6fc783beebc3b4a1431faceee51f970e4d79f0ead3796b6dd2f508`
- libero_wrapper: `/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/third_party/libero_pro/libero/libero/envs/env_wrapper.py` — `a782fb76c9792268d28979474fe72849e1e98ada49c8e997a65359a8d6b6acd0`
- libero_domain: `/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/third_party/libero_pro/libero/libero/envs/bddl_base_domain.py` — `055836670ac5fcac7e033fc86404718fd53854996e5776b1ff68b646f7bbcc9d`
- controller_config: `/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/robosuite/controllers/config/osc_pose.json` — `07f3a8b41d3eecc8a36700a85bd8207ee3fbc36eb73f6a2248340c96770d1e45`
- controller_base: `/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/robosuite/controllers/base_controller.py` — `61f99a2daeb4eb6e39bfb996d94c5a5689ef3bc771d030d070193ea56d6a8332`
- osc_controller: `/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/robosuite/controllers/osc.py` — `cfa62a0e719bc53ef0c701efa66f7b3e2272d4fca2150ec73c05bb145eba85cb`
- controller_factory: `/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/robosuite/controllers/controller_factory.py` — `1dab09602c41dcf3749bed43dd3bc4e098040cabc8f7fbfd030d9008bd3d5776`
- single_arm: `/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/robosuite/robots/single_arm.py` — `d233b1b785e8f88ffb5df1357666b02a397ae930ce98181b079e0496ab35fc57`
- goal_utils: `/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/robosuite/utils/control_utils.py` — `1d0f1a063894b1e8289339e223665e14e8aec492c31e9e00f42edea8dc735f43`

Structured evidence: `review-v1.json` SHA `47a97d97b81e27d36b8a163565f526c873e326540bda307427a7f2ea60a95611`. No W source/state edits; this documentation alone is written in isolated E.
