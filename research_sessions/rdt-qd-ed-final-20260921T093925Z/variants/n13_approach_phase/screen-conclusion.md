# N13 closest-approach QD descriptor: reject before GPU

The SHA-verified, read-only audit in `readonly_screen.py` used the 33 exposed N7 Dev guided decisions (363 canonical 16-candidate batches) from tasks 0, 3, 6 and 9. Each projected trajectory was matched by `scoring_batch_id` to the exact canonical batch; the recorded N7 descriptor was reconstructed from the matching BF16 projection and keypoint tensors. N13 would replace endpoint quadrant and height with the quadrant and height at the projected XY-closest point in the eight-action chunk, retaining the same 4×4 cells and initial-pool height-bound rule.

The new partition splits 2,147 formerly colliding candidate pairs but conflates 5,496 formerly distinct pairs. Summed occupied cells fall from 3,207 to 2,457 across the 363 batches. The failure-task subset (tasks 0 and 3) splits 1,737 pairs but conflates 4,497. Earlier closest approach is common (4,760 of 5,808 candidates), so this is a material representation change, yet it loses much more diversity than it recovers. These are partitions of saved pools, not counterfactual executions.

Decision: **REJECT N13 before GPU**. It does not justify one of the remaining 14 development slots. Native BF16 projection is adequate to reproduce the recorded descriptor but does not supply full-precision physical outcome evidence. No validation or formal set was accessed.
