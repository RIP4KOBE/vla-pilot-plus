# Q0 task0 qualitative check — N1S

Source: episode_1_fail_agentview.mp4, 720 frames at10fps; inspected frames0,360,719. Terminal outcome is a valid task failure.

At frame0 the basket is upright. At frame360 the basket is visibly raised/tilted near the closed gripper; overlay Stage1/GuideON. At frame719 the basket lies on its side, with a blue/yellow can adjacent to the gripper above it; overlay Stage2/GuideOFF. The snapshots support basket displacement and incomplete placement as visible failure features, but do not establish when/why contact occurred, a secure grasp, or whether QD, the reward, Stage decisions or base actions caused it.

Do not modify the frozen conditions from one failure. Compare the same-task C0 and N1 outcomes and their trajectories once available. This is a visual observation, not an additional success metric or simulator counterfactual.
