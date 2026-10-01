"""Focused synthetic N29 CPU checks; never read experiment fixtures."""
import math

import pytest
import torch

from core.qd_feasible_ray_update import feasible_ray_update
from core.qd_population_relative_trust import population_relative_trust_update as update

DTYPES = [torch.float32, torch.bfloat16]


def exact(a, b):
    return (a.dtype == b.dtype and a.shape == b.shape and
            torch.equal(a.reshape(-1).contiguous().view(torch.uint8), b.reshape(-1).contiguous().view(torch.uint8)))


def population(dtype, amplitude=.5):
    b = torch.zeros(16, 8, 3, dtype=dtype)
    b[:8, 0, 0] = -amplitude
    b[8:, 0, 0] = amplitude
    return b


def scalar_reference(b, p):
    # Independent Python real-arithmetic reference, used on exactly representable
    # hand cases; production FP32 reduction order is separately specified.
    B = b.double().reshape(16, 24).tolist()
    P = p.double().reshape(16, 24).tolist()
    mu = [math.fsum(row[j] for row in B)/16 for j in range(24)]
    s = math.sqrt(math.fsum(math.fsum((row[j]-mu[j])**2 for j in range(24)) for row in B)/16)
    norms = [math.sqrt(math.fsum(v*v for v in row)) for row in P]
    beta = [min(1., s/n) if n > 0 else 1. for n in norms]
    U = torch.tensor([[v*beta[i] for v in row] for i,row in enumerate(P)], dtype=b.dtype).reshape_as(b)
    return s, norms, beta, U


@pytest.mark.parametrize('dtype', DTYPES)
def test_hand_rms_row_specific_scaling_and_independent_reference(dtype):
    b = population(dtype)
    p = torch.zeros_like(b)
    magnitude = [0., .25, .5, 1., 2., .25, .5, 1.] * 2
    p[:, 0, 1] = torch.tensor(magnitude, dtype=dtype)
    before, operand = b.clone(), p.clone()
    s, norms, beta, u = scalar_reference(b, p)
    r = update(b, p)
    assert s == .5 == r.radius.item()
    assert r.operand_norms.tolist() == norms
    assert r.beta.tolist() == beta
    assert exact(r.scaled_operand, u)
    assert exact(r.prefix, feasible_ray_update(b, u).prefix)
    assert exact(b, before) and exact(p, operand)


@pytest.mark.parametrize('dtype', DTYPES)
def test_rms_radius_sums_coordinates_not_coordinate_average(dtype):
    b = population(dtype, .375)
    b[:8, 0, 1] = -.5
    b[8:, 0, 1] = .5
    p = torch.zeros_like(b);p[:, 0, 2] = 1.25
    r = update(b, p)
    assert r.radius.item() == .625
    assert r.beta.tolist() == [.5] * 16
    assert r.scaled_operand[:, 0, 2].tolist() == [.625] * 16


@pytest.mark.parametrize('dtype', DTYPES)
def test_population_dependent_cap_not_a_fixed_scale(dtype):
    p = torch.zeros(16, 8, 3, dtype=dtype);p[:, 0, 1] = 2
    small = update(population(dtype, .125), p)
    large = update(population(dtype, .5), p)
    assert small.beta.tolist() == [.0625] * 16
    assert large.beta.tolist() == [.25] * 16


@pytest.mark.parametrize('dtype', DTYPES)
def test_true_zero_spread_closes_nonzero_updates_and_preserves_zero_bits(dtype):
    b = torch.full((16, 8, 3), -.0, dtype=dtype)
    p = torch.ones_like(b);p[0] = 0
    r = update(b, p)
    assert r.radius.item() == 0
    assert r.beta.tolist() == [1.] + [0.] * 15
    assert exact(r.prefix, b)
    assert torch.count_nonzero(r.scaled_operand).item() == 0


@pytest.mark.parametrize('dtype', DTYPES)
def test_zero_operand_keeps_exterior_and_signed_zero_bytes(dtype):
    b = population(dtype);b[0, 0, 0] = 2.;b[1, 0, 0] = -2.;b[2, 0, 0] = -0.
    r = update(b, torch.zeros_like(b))
    assert r.beta.tolist() == [1.] * 16 and exact(r.prefix, b)


@pytest.mark.parametrize('dtype', DTYPES)
def test_inactive_cap_exact_old_ray_parity_rng_and_no_autograd(dtype):
    b = population(dtype).requires_grad_()
    p = torch.full_like(b, .0625).requires_grad_()
    rng = torch.random.get_rng_state().clone()
    reference = feasible_ray_update(b, p)
    r = update(b, p)
    assert r.beta.tolist() == [1.] * 16
    assert exact(r.prefix, reference.prefix) and exact(r.alpha, reference.alpha)
    assert exact(r.scaled_operand, p)
    assert torch.equal(rng, torch.random.get_rng_state())
    assert not any(t.requires_grad for t in r)


@pytest.mark.parametrize('dtype', DTYPES)
@pytest.mark.parametrize('layout', ['model_slice', 'transpose'])
def test_noncontiguous_inputs_have_exact_cpu_contiguous_parity(dtype, layout):
    b = population(dtype)
    p = torch.zeros_like(b);p[:, 0, 1] = 2
    def convert(x):
        if layout == 'model_slice':
            backing = torch.zeros(16, 67, 128, dtype=dtype)
            view = backing[:, -64:, :][:, :8, 39:42]
            view.copy_(x)
            assert view.stride() == (8576, 128, 1) and view.storage_offset() == 423
            return view
        return x.transpose(1,2).contiguous().transpose(1,2)
    bn, pn = convert(b), convert(p)
    assert not bn.is_contiguous() and not pn.is_contiguous()
    result, reference = update(bn, pn), update(b, p)
    assert all(exact(a, b) for a,b in zip(result, reference))


@pytest.mark.parametrize('dtype', DTYPES)
@pytest.mark.parametrize('value', [-1., 1., 1.25])
def test_raw_support_rejected_before_scaling_can_hide_it(dtype, value):
    b = torch.full((16,8,3), value, dtype=dtype)
    p = torch.zeros_like(b);p[0,0,0] = .25
    with pytest.raises(ValueError, match='raw nonzero update outside'):
        update(b,p)


@pytest.mark.parametrize('dtype', DTYPES)
def test_nonzero_operand_squared_norm_underflow_is_not_zero_operand(dtype):
    b = population(dtype);p = torch.zeros_like(b);p[0,0,1] = 1e-30
    assert p[0,0,1] != 0
    with pytest.raises(ValueError, match='operand norm underflow'):
        update(b,p)


@pytest.mark.parametrize('dtype', DTYPES)
def test_nonzero_centered_spread_underflow_is_not_true_zero_spread(dtype):
    b = population(dtype, 1e-30);p = torch.zeros_like(b)
    assert torch.count_nonzero(b).item() == 16
    with pytest.raises(ValueError, match='population spread underflow'):
        update(b,p)


@pytest.mark.parametrize('which', ['before','operand'])
def test_finite_inputs_with_square_overflow_fail_closed(which):
    b = population(torch.float32);p = torch.zeros_like(b)
    if which == 'before': b = population(torch.float32, 1e20)
    else: p[:,0,1] = 1e20
    with pytest.raises(ValueError, match='nonfinite .*square'):
        update(b,p)


@pytest.mark.parametrize('which', ['before','operand'])
@pytest.mark.parametrize('value', [float('nan'),float('inf')])
def test_nonfinite_input_rejected(which,value):
    b = population(torch.float32);p=torch.zeros_like(b)
    (b if which=='before' else p)[0,0,1]=value
    with pytest.raises(ValueError, match='nonfinite .*input'):
        update(b,p)


def test_bad_shape_dtype_and_meta_device_rejected():
    b=population(torch.float32)
    with pytest.raises(ValueError,match='strided'):update(b[:15],b[:15])
    with pytest.raises(ValueError,match='matching FP32/BF16'):update(b,b.to(torch.bfloat16))
    with pytest.raises(ValueError,match='matching FP32/BF16'):update(b.double(),b.double())
    with pytest.raises(ValueError,match='matching CPU/CUDA'):update(torch.empty(16,8,3,device='meta'),torch.empty(16,8,3,device='meta'))


def test_native_rounding_can_exceed_real_radius_no_false_strict_bound():
    b=population(torch.bfloat16, .1)
    b[:8,0,1]=-.1;b[8:,0,1]=.1
    p=torch.zeros_like(b);p[:,0,2]=1
    r=update(b,p)
    actual=(r.prefix.float()-b.float()).reshape(16,24).square().sum(1).sqrt()
    assert bool((actual > r.radius).all())
    assert bool((r.prefix.abs()<=1).all())


@pytest.mark.parametrize('dtype', DTYPES)
def test_nonzero_mean_is_removed_before_population_radius(dtype):
    b = population(dtype) + .125
    p = torch.zeros_like(b);p[:,0,1] = 2
    r = update(b,p)
    assert r.radius.item() == .5
    assert r.beta.tolist() == [.25] * 16
    assert r.prefix[:,0,1].tolist() == [.625] * 16


@pytest.mark.parametrize('dtype', DTYPES)
def test_population_cap_then_active_original_box_ray(dtype):
    b = population(dtype, .875)
    p = torch.zeros_like(b);p[:,0,0] = 2
    r = update(b,p)
    assert r.radius.item() == .875
    assert r.beta.tolist() == [.4375] * 16
    assert r.scaled_operand[:,0,0].tolist() == [.875] * 16
    assert r.alpha[:8].tolist() == [1.] * 8
    assert torch.equal(r.alpha[8:], torch.full((8,),1/7,dtype=torch.float32))
    assert r.prefix[:8,0,0].tolist() == [0.] * 8
    assert r.prefix[8:,0,0].tolist() == [1.] * 8
    assert exact(r.prefix, feasible_ray_update(b,r.scaled_operand).prefix)
