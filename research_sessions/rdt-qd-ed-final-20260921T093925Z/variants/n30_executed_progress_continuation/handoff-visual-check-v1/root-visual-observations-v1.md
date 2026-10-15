# Root inspection of the twelve fixed handoff frames

Root viewed all twelve delivered 640×640 PNGs at original detail, without another video decode. The visible Step overlays match frame indices 16, 20, 24, 28, 32 and 40 in both episodes. Stage is 1 throughout; Guide is ON at 16/20 and OFF at 24/28/32/40. These observations supplement the accepted handoff record, not episode-level success or a causal intervention.

For task0, the blue/yellow cylindrical can in the target vicinity remains upright on the surface in the selected frames. At 16 the fingers and path overlays partly occlude its upper region; at 20 the hand is higher. At 24/28/32 there is visible separation as the hand rises above the can. By 40 the open hand is again lower near its top. There is no visible sustained carrying of this can in these six samples. Exact transient contacts between frames, semantic target correctness and the cause of capture failure remain unknown. Grip overlays are C at 16/20 and O at 24/28/32/40.

For task1, the low target vicinity is substantially occluded by the gripper and trajectory overlays. The hand descends from 16 to 20 and remains low in the later samples. All six selected Grip overlays are O. They show the pending command before each action: frame32 therefore does not contradict the recorded close commands at steps29–31. Object identity, finger contact and whether an object is held cannot be reliably resolved from these views.

The stored FAIL label was added at episode export to every frame. It is not used as a per-frame failure detector. The encoded 10fps presentation rate is not the 20Hz simulation clock.

Combined with the tensor-derived record, task0's withdrawal was already present during the guided close prefix, while task1 continued approaching after guidance turned off. A universal handoff interruption is unsupported. Blindly retaining a trajectory or extending closed commands is not yet justified, and close-suffix/lift credit has already been explored by N22.

Next bounded question: does the available target point lie in a plausible closing region when expressed in the robot's calibrated gripper frame, and could a QD/ED feature distinguish approach from capture readiness without changing Stage, perception or the executor? Robot geometry, quaternion conventions, target-point semantics and candidate rollout observability must be established first. No new algorithm or numerical threshold is nominated here.
