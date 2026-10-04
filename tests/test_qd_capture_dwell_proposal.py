"""Synthetic action semantics for the pure N31 helper; no production imports."""
import importlib.util
from pathlib import Path
import sys

import pytest
import torch

PATH = Path(__file__).resolve().parents[1] / "core/qd_capture_dwell_proposal.py"
SPEC = importlib.util.spec_from_file_location("n31_pure_helper", PATH)
h = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = h
SPEC.loader.exec_module(h)


def raw(x):
    return x.detach().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes()


def inputs(dtype=torch.float32, arrival=0):
    # Deliberately nonzero values in inactive native fields make accidental masking visible.
    base = (torch.arange(64*128).reshape(64, 128) % 23 - 11).to(dtype)
    projected = torch.ones(8, 3, dtype=dtype)
    if arrival is not None:
        projected[arrival:] = 0
    kw = dict(target=torch.zeros(3, dtype=torch.float64),
              hand_quaternion_xyzw=torch.tensor([0., 0., 0., 1.], dtype=torch.float64),
              gripper_qpos=torch.tensor([.02, -.02], dtype=torch.float64),
              target_recognized=True)
    return base, projected, kw


@pytest.mark.parametrize("dtype", [torch.float32, torch.bfloat16])
@pytest.mark.parametrize("arrival", [0, 3, 7])
def test_exact_arrival_prefix_tail_and_only_prescribed_fields(dtype, arrival):
    base, projected, kw = inputs(dtype, arrival)
    before, projection_before = raw(base), raw(projected)
    result = h.capture_dwell_proposal(base, projected, **kw)
    out = result.candidate
    assert result.changed and result.arrival_index == arrival
    assert out.dtype == base.dtype and out.device == base.device and out.shape == base.shape
    assert raw(base) == before and raw(projected) == projection_before
    assert out.data_ptr() != base.data_ptr()
    assert raw(out[:arrival]) == raw(base[:arrival])
    assert raw(out[8:]) == raw(base[8:])
    assert raw(out[arrival, 39:45]) == raw(base[arrival, 39:45])  # Arrival command survives.
    assert torch.equal(out[arrival:8, 10], torch.ones(8-arrival, dtype=dtype))
    assert raw(out[arrival+1:8, 39:45]) == raw(torch.zeros_like(out[arrival+1:8, 39:45]))
    inactive = [k for k in range(128) if k not in [10,39,40,41,42,43,44]]
    assert raw(out[:, inactive]) == raw(base[:, inactive])


def test_earliest_inclusive_entry_and_leave_later_reentry_unexamined():
    base, xyz, kw = inputs(arrival=None)
    xyz[2] = 0
    xyz[5] = 0
    assert h.capture_dwell_proposal(base, xyz, **kw).arrival_index == 2


@pytest.mark.parametrize("axis,coordinate", [(0,-.008),(0,.008),(2,-.0116),(2,.0044),(1,-.0195),(1,.0195)])
def test_binary64_exact_inclusive_faces_without_tolerance(axis, coordinate):
    base, xyz, kw = inputs(arrival=None)
    xyz[0] = 0
    kw['target'][axis] = coordinate
    assert h.capture_dwell_proposal(base, xyz, **kw).arrival_index == 0
    # Move only the target one binary64 representable value beyond that face.
    direction = float('inf') if coordinate > 0 else -float('inf')
    kw['target'][axis] = torch.nextafter(kw['target'][axis], torch.tensor(direction, dtype=torch.float64))
    assert h.capture_dwell_proposal(base, xyz, **kw).reason == 'no_projected_entry'


def test_hand_frame_not_world_frame_and_quaternion_scale_invariance():
    base, xyz, kw = inputs()
    kw['target'] = torch.tensor([.015, 0., 0.], dtype=torch.float64)
    assert h.capture_dwell_proposal(base, xyz, **kw).reason == 'no_projected_entry'
    # Quarter turn maps the wide jaw axis to world x; no predicted wrist rotation.
    kw['hand_quaternion_xyzw'] = torch.tensor([0., 0., 1., 1.], dtype=torch.float64)
    rotated = h.capture_dwell_proposal(base, xyz, **kw)
    kw['hand_quaternion_xyzw'] *= 2
    scaled = h.capture_dwell_proposal(base, xyz, **kw)
    assert rotated.arrival_index == scaled.arrival_index == 0
    assert raw(rotated.candidate) == raw(scaled.candidate)


@pytest.mark.parametrize("dtype", [torch.float32, torch.bfloat16])
def test_zero_gap_is_not_negative_gap(dtype):
    base, xyz, kw = inputs(dtype)
    kw['gripper_qpos'] = torch.tensor([.0005, -.0005], dtype=torch.float64)
    assert h.capture_dwell_proposal(base, xyz, **kw).changed
    kw['gripper_qpos'] = torch.zeros(2, dtype=torch.float64)
    assert h.capture_dwell_proposal(base, xyz, **kw).reason == 'empty_inner_gap'


@pytest.mark.parametrize("dtype", [torch.float32, torch.bfloat16])
def test_no_change_zero_native_sign_and_last_arrival(dtype):
    base, xyz, kw = inputs(dtype, 7)
    base[7, 10] = 1
    same = h.capture_dwell_proposal(base, xyz, **kw)
    assert not same.changed and same.arrival_index == 7 and same.reason == 'no_native_change'
    base[7, 10] = -0.0  # Decoder would already close; literal native +1 still changes content.
    result = h.capture_dwell_proposal(base, xyz, **kw)
    assert result.changed and result.candidate[7, 10] == 1
    assert raw(result.candidate[8:]) == raw(base[8:])


def test_signed_zero_hold_is_a_native_byte_change():
    base, xyz, kw = inputs()
    base[:8, 10] = 1
    base[1:8, 39:45] = -0.0
    result = h.capture_dwell_proposal(base, xyz, **kw)
    assert result.changed and not torch.signbit(result.candidate[1:8, 39:45]).any()
    assert torch.signbit(base[1:8, 39:45]).all()


def test_existing_complete_dwell_is_not_reinjected():
    base, xyz, kw = inputs()
    base[:8, 10] = 1
    base[1:8, 39:45] = 0
    before = raw(base)
    result = h.capture_dwell_proposal(base, xyz, **kw)
    assert result.reason == 'no_native_change' and result.arrival_index == 0
    assert result.candidate is None and raw(base) == before


@pytest.mark.parametrize("missing,reason", [('target','target_unavailable'),('hand_quaternion_xyzw','proprioception_unavailable'),('gripper_qpos','proprioception_unavailable')])
def test_missing_snapshot_explicitly_skips(missing, reason):
    base, xyz, kw = inputs();kw[missing] = None
    result = h.capture_dwell_proposal(base, xyz, **kw)
    assert result.candidate is None and result.arrival_index is None and result.reason == reason


def test_unrecognized_and_no_entry_skip_without_input_mutation():
    base, xyz, kw = inputs(arrival=None);before=raw(base)
    assert h.capture_dwell_proposal(base, xyz, **kw).reason == 'no_projected_entry'
    kw['target_recognized'] = False
    assert h.capture_dwell_proposal(base, xyz, **kw).reason == 'unrecognized_target'
    assert raw(base) == before


@pytest.mark.parametrize("bad", ['base_shape','projection_shape','projection_dtype','base_int','nan_base','inf_projection','nan_target','zero_quaternion','bad_qpos_shape','nonbool_recognition'])
def test_malformed_input_raises_without_fallback(bad):
    base, xyz, kw = inputs()
    if bad == 'base_shape':base=base[:8]
    elif bad == 'projection_shape':xyz=xyz[:7]
    elif bad == 'projection_dtype':xyz=xyz.bfloat16()
    elif bad == 'base_int':base=base.long()
    elif bad == 'nan_base':base[63,127]=float('nan')
    elif bad == 'inf_projection':xyz[7,2]=float('inf')
    elif bad == 'nan_target':kw['target'][0]=float('nan')
    elif bad == 'zero_quaternion':kw['hand_quaternion_xyzw'].zero_()
    elif bad == 'bad_qpos_shape':kw['gripper_qpos']=torch.zeros(3)
    else:kw['target_recognized']=1
    with pytest.raises(ValueError):h.capture_dwell_proposal(base, xyz, **kw)


@pytest.mark.parametrize("dtype", [torch.float32, torch.bfloat16])
def test_noncontiguous_inputs_native_tail_and_rng_unchanged(dtype):
    base, xyz, kw = inputs(dtype, 3)
    storage=torch.empty(128,64,dtype=dtype);view=storage.T;view.copy_(base)
    pstore=torch.empty(3,8,dtype=dtype);pview=pstore.T;pview.copy_(xyz)
    before=raw(view);state=torch.random.get_rng_state().clone()
    result=h.capture_dwell_proposal(view,pview,**kw)
    assert raw(view)==before and torch.equal(state,torch.random.get_rng_state())
    assert raw(result.candidate[8:])==raw(view[8:])
    assert not result.candidate.requires_grad


def test_no_parameter_or_hidden_population_selection():
    # Helper produces one plan only. The future caller must replace slot15, never select a better slot.
    base, xyz, kw=inputs();result=h.capture_dwell_proposal(base,xyz,**kw)
    assert result.candidate.shape==(64,128)
    assert set(result.__dataclass_fields__)=={'candidate','arrival_index','reason'}
