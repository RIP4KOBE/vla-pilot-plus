# Root static action-semantics review for N31

This note clarifies the already frozen proposal; it adds no numerical diagnosis or algorithm change.

Installed source:
- /home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/robosuite/controllers/osc.py:202–265
- /home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/robosuite/utils/control_utils.py:114–147
- /home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/robosuite/models/grippers/panda_gripper.py:47–66
- study_worktree/core/env_adapters/libero_adapter.py:1139–1147

For delta OSC, a zero translation command makes the goal position the controller's current ee_pos. A zero rotation command retains the previous orientation goal rather than setting a newly measured orientation. Dynamic response still depends on controller state, interpolation, inertia and contacts. Thus N31 zeroing later native pose increments is an approximate dwell proposal, not a guarantee of fixed physical pose or completion of the arrival command.

Panda +1 is the closing direction, incrementing the gripper command state by its speed; it is not an instantaneous measured jaw closure. The existing handoff data already distinguishes commanded closure from observed qpos.

The adapter's _get_raw_obs helper steps the simulator with zero action. It must not be used to obtain N31 observation inputs. Reuse the already available pre-decision raw observation, with episode/reset/step identity. No new simulator transition, environment query with side effects, or privileged contact/object state is authorized.

N31's original canonical scoring occurs inside rollout, before the outer call returns. The production integration must place the completion proposal after the original model/mask/diversity work and before the existing canonical score, rather than replace a row after it was scored. Reuse the projection from that scoring path in a current-decision cache, not additional provider/model/scoring calls. These are static interface findings only; implementation and runtime parity remain to be verified by the executor.

