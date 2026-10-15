"""N31 pure capture-dwell proposal; no policy hook or scoring is installed here.

The caller must bind the native archive plan and its already computed canonical
projection to the same decision, provider and target. This helper does not infer
that provenance, predict capture, retain a candidate, or execute an action.
"""
from dataclasses import dataclass
import math

import torch
from torch import Tensor


@dataclass(frozen=True)
class CaptureDwellProposal:
    candidate: Tensor | None
    arrival_index: int | None
    reason: str

    @property
    def changed(self) -> bool:
        return self.candidate is not None


def _native(x: Tensor, shape: tuple[int, ...], name: str) -> Tensor:
    if not isinstance(x, Tensor) or tuple(x.shape) != shape:
        raise ValueError(f"{name}: expected tensor shape {shape}")
    if x.dtype not in (torch.float32, torch.bfloat16):
        raise ValueError(f"{name}: expected native FP32 or BF16")
    if not bool(torch.isfinite(x).all()):
        raise ValueError(f"{name}: nonfinite input")
    return x


def _geometry_vector(x: Tensor | None, size: int, name: str) -> list[float] | None:
    if x is None:
        return None
    if not isinstance(x, Tensor) or tuple(x.shape) != (size,) or not x.is_floating_point():
        raise ValueError(f"{name}: expected floating tensor shape {(size,)} or None")
    if not bool(torch.isfinite(x).all()):
        raise ValueError(f"{name}: nonfinite input")
    return x.detach().to(device="cpu", dtype=torch.float64).tolist()


def _same_native_bytes(a: Tensor, b: Tensor) -> bool:
    av = a.detach().contiguous().reshape(-1).view(torch.uint8)
    bv = b.detach().contiguous().reshape(-1).view(torch.uint8)
    return bool(torch.equal(av, bv))


@torch.no_grad()
def capture_dwell_proposal(
    base_plan: Tensor,
    projected_outcomes: Tensor,
    *,
    target: Tensor | None,
    hand_quaternion_xyzw: Tensor | None,
    gripper_qpos: Tensor | None,
    target_recognized: bool,
) -> CaptureDwellProposal:
    """Construct one competing proposal, or explicitly leave offspring unchanged.

    ``projected_outcomes`` contains the original canonical outcome positions
    1..8 (shape8x3), not action increments and not a newly clipped projection.
    Geometry uses Python binary64 and the current observed fixed hand frame.
    Native plan dtype/device and all unedited logical entries are preserved.

    Malformed/nonfinite inputs raise ValueError; absent observation fields,
    unrecognized target, empty jaw interval, no hit, or no byte change return a
    candidate of None. The caller must not replace slot15 in these cases.
    """
    _native(base_plan, (64, 128), "base_plan")
    _native(projected_outcomes, (8, 3), "projected_outcomes")
    if projected_outcomes.dtype != base_plan.dtype:
        raise ValueError("projection and base native dtypes differ")
    if type(target_recognized) is not bool:
        raise ValueError("target_recognized must be an explicit bool")
    point = _geometry_vector(target, 3, "target")
    quat = _geometry_vector(hand_quaternion_xyzw, 4, "hand_quaternion_xyzw")
    jaw = _geometry_vector(gripper_qpos, 2, "gripper_qpos")
    if not target_recognized:
        return CaptureDwellProposal(None, None, "unrecognized_target")
    if point is None:
        return CaptureDwellProposal(None, None, "target_unavailable")
    if quat is None or jaw is None:
        return CaptureDwellProposal(None, None, "proprioception_unavailable")
    try:
        norm = math.sqrt(math.fsum(v * v for v in quat))
    except (OverflowError, ValueError) as exc:
        raise ValueError("invalid binary64 quaternion norm") from exc
    if not math.isfinite(norm) or norm == 0.0:
        raise ValueError("zero/nonfinite binary64 quaternion norm")
    x, y, z, w = (v / norm for v in quat)
    rotation = (
        (1 - 2 * (y*y + z*z), 2 * (x*y - z*w), 2 * (x*z + y*w)),
        (2 * (x*y + z*w), 1 - 2 * (x*x + z*z), 2 * (y*z - x*w)),
        (2 * (x*z - y*w), 2 * (y*z + x*w), 1 - 2 * (x*x + y*y)),
    )
    lower, upper = jaw[1] + 0.0005, jaw[0] - 0.0005
    if not all(math.isfinite(v) for v in (lower, upper)):
        raise ValueError("nonfinite binary64 jaw interval")
    if lower > upper:
        return CaptureDwellProposal(None, None, "empty_inner_gap")
    positions = projected_outcomes.detach().to(device="cpu", dtype=torch.float64).tolist()
    arrival = None
    for j, position in enumerate(positions):
        delta = [point[k] - position[k] for k in range(3)]
        if not all(math.isfinite(v) for v in delta):
            raise ValueError("nonfinite binary64 target displacement")
        try:
            a = [math.fsum(rotation[k][axis] * delta[k] for k in range(3)) for axis in range(3)]
        except (OverflowError, ValueError) as exc:
            raise ValueError("invalid binary64 hand transform") from exc
        if not all(math.isfinite(v) for v in a):
            raise ValueError("nonfinite binary64 hand transform")
        # Inclusive, literal source-calibrated prism: no epsilon or learned threshold.
        if -0.008 <= a[0] <= 0.008 and lower <= a[1] <= upper and -0.0116 <= a[2] <= 0.0044:
            arrival = j
            break
    if arrival is None:
        return CaptureDwellProposal(None, None, "no_projected_entry")
    proposal = base_plan.detach().clone()
    proposal[arrival:8, 10] = 1
    proposal[arrival + 1:8, 39:45] = 0
    if _same_native_bytes(proposal, base_plan):
        return CaptureDwellProposal(None, arrival, "no_native_change")
    return CaptureDwellProposal(proposal, arrival, "capture_dwell_proposal")
