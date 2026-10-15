# Mechanism decision: no nomination yet

The one frozen calculation completed 32/32 outcomes. The fixed target is outside the small inner-pad prism at every sample. That is a point-location result, **not** 32 failed grasps or proof of an incorrect Stage decision. Root visual evidence says the task0 can is not visibly carried in the selected frames; task1 remains occluded. Neither observation establishes where this arbitrary target point lies within an object.

|Task / outcome steps|Pad-center X range (mm)|Pad-center Z range (mm)|Inner-face gap range (mm)|Point-to-prism distance range (mm)|
|---|---:|---:|---:|---:|
|0 / 16–23|-1.798–14.994|12.904–41.164|21.603–73.037|4.904–33.893|
|0 / 24–31|-1.378–15.887|47.628–61.548|13.433–57.436|40.431–53.548|
|1 / 16–23|15.736–28.535|-5.531–37.878|74.788–77.468|7.736–36.254|
|1 / 24–31|13.103–15.227|-3.871–-3.626|72.987–78.825|5.103–7.227|

Physical pad half-width/half-length are each 8mm in these axes. Task0’s fixed point is longitudinally beyond the pad range already during guided16–23 and farther in24–31; task1 is laterally offset despite close longitudinal alignment late in the window. These describe different selected-trajectory geometry. They do not identify an unselected action that would capture an object. Full 32-row coverage is in `geometry-table-v1.csv`; no threshold or offset was tuned.

One distinct *considered but not nominated* QD mechanism is a jaw-plane archive descriptor: replace world-XY endpoint coordinates by the existing projected endpoint’s lateral/longitudinal coordinates in the **current observed** hand frame. Insertion would be the canonical QD descriptor before unchanged archive/parent selection; inputs would be existing target, raw hand pose and projected xyz. It changes diversity coverage, not a close bonus, retained lane, lift suffix, Stage or action executor. A matched removal control would use the original world-XY descriptor with identical candidates, score/model/RNG calls, grid/selection settings and all other logic. The minimal falsifiable claim would be that the archive retains distinguishable jaw-plane alignment that world-XY aliases, and that changed selected candidates actually improve measured alignment rather than merely relabel cells. No such pool/causal evidence was read here.

**Why it is not nominated:** this fixed-orientation descriptor is mathematically definable without new model calls, but it is not candidate capture geometry. Existing projection does not forecast candidate orientation or actual jaw response. Worse, the sole keypoint has no established relation to grasp center/object extent. Two failed selected trajectories and a physical pad box cannot supply that missing semantics. A bonus or validity veto using the prism would therefore overstate observability. No GPU mechanism or new numerical threshold is recommended from this screen.

Novelty boundary: N12’s outer-loop screen already found near-close candidates and ambiguous joint/EEF signatures in both failures and successes. N15 was an un-dispatched stalled-contact screen with inadequate trigger coverage; N16 was an un-dispatched near-close projected-pool screen, not proof that all feedback is futile. N22 conditioned lift on a continuous close suffix and showed weak fixed-pool ranking changes. N30 continued a previous winner after measured approach. Jaw-plane coordinates differ from those temporal/gripper/progress rules, but difference alone is not enough evidence to run them; no claim of global novelty beyond these reviewed records is made.

Specific missing evidence: a deployment-visible, target-identified grasp-region/extent interpretation (not privileged object pose), plus a bounded validation that a stated candidate orientation/jaw proxy corresponds to observed pose/aperture over the executed prefix. Current data establish the observed-frame transform only. Root may separately choose how to obtain that evidence; this report authorizes no additional read, perception change or experiment.

Execution: child process CPU 0.030233000s including startup, external wall 0.031956271s, exit0; internal calculation CPU 0.002594503s. Two-CPU affinity and thread settings held, zero retries/Torch/production imports/GPU/API/model/simulator calls. Existing JSON was read once structurally before freezing and once by the unique calculation. No tensors or video reopened.
