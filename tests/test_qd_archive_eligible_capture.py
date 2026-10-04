"""CPU synthetic selector tests; isolated imports avoid adapters and simulation."""
import copy
from dataclasses import replace
import importlib
from pathlib import Path
import sys
import types

import pytest
import torch

PACKAGE = "_n32_cpu_synthetic"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(Path(__file__).resolve().parents[1] / "core")]
sys.modules[PACKAGE] = package
h = importlib.import_module(PACKAGE + ".qd_archive_eligible_capture")


def raw(x):
    return x.detach().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes()


def fixture(dtype=torch.float32):
    mask = torch.zeros(1, 1, 128, dtype=dtype)
    mask[:, :, [10, 39, 40, 41, 42, 43, 44]] = 1
    rows = []
    for i in range(16):
        plan = torch.zeros(64, 128, dtype=dtype)
        plan[:, 39:45] = (i + 1) / 32
        plan[:, 10] = -1
        xyz = torch.ones(8, 3, dtype=dtype)
        if i != 0:
            xyz[3:] = 0
        quality = torch.tensor(16 - i, dtype=dtype)
        rows.append(dict(iteration=-1, row=i, occurrence=i, plan=plan,
                         fingerprint=h.fingerprint_action(plan), projection=xyz,
                         projection_status="original_canonical", quality=quality,
                         cost=-quality, source_origin=torch.zeros(3, dtype=torch.float64),
                         cast_origin=torch.zeros(3, dtype=dtype)))
    entries = {i: h.QDArchiveEntry(r["plan"].clone(), float(r["quality"]), float(r["cost"]),
                                  torch.zeros(2), r["fingerprint"], -1, None, i)
               for i, r in enumerate(rows[:2])}
    kw = dict(decision_id=(0, 0, 0), iteration=0, action_mask=mask,
              target=torch.zeros(3, dtype=torch.float64),
              hand_quaternion_xyzw=torch.tensor([0., 0., 0., 1.]),
              gripper_qpos=torch.tensor([.02, -.02]), target_recognized=True)
    return entries, h.CanonicalCache((0, 0, 0), rows), kw


def select(entries, cache, kw):
    return h.select_eligible_parent(entries, cache, **kw)


@pytest.mark.parametrize("dtype", [torch.float32, torch.bfloat16])
def test_secondary_eligible_native_dtype_mask_and_immutability(dtype):
    entries, cache, kw = fixture(dtype)
    before = [raw(r["plan"]) for r in cache.entries]
    masks = raw(kw["action_mask"])
    rng = torch.random.get_rng_state().clone()
    result = select(entries, cache, kw)
    assert result.selected.cell_id == 1
    assert [p.reason for p in result.parents] == ["no_projected_entry", "capture_dwell_proposal"]
    out, base = result.candidate, entries[1].action
    assert out.dtype == dtype and out.device.type == "cpu"
    assert raw(out * kw["action_mask"][0]) == raw(out)
    edits = torch.zeros_like(out, dtype=torch.bool)
    edits[3:8, 10] = True
    edits[4:8, 39:45] = True
    assert raw(out[~edits]) == raw(base[~edits])
    assert raw(out[3:8, 10]) == raw(torch.ones(5, dtype=dtype))
    assert raw(out[4:8, 39:45]) == raw(torch.zeros(4, 6, dtype=dtype))
    assert [raw(r["plan"]) for r in cache.entries] == before
    assert raw(kw["action_mask"]) == masks
    assert torch.equal(rng, torch.random.get_rng_state())
    assert out.data_ptr() != base.data_ptr()


def test_best_eligible_exact_n31_parity():
    entries, cache, kw = fixture()
    cache.entries[0]["projection"].zero_()
    result = select(entries, cache, kw)
    expected = h.capture_dwell_proposal(entries[0].action, cache.entries[0]["projection"],
        **{k: kw[k] for k in ("target", "hand_quaternion_xyzw", "gripper_qpos", "target_recognized")})
    assert result.selected.cell_id == 0
    assert raw(result.candidate) == raw(expected.candidate)


@pytest.mark.parametrize("dtype", [torch.float32, torch.bfloat16])
def test_no_eligible_population_parity_in_synthetic_caller(dtype):
    entries, cache, kw = fixture(dtype)
    cache.entries[1]["projection"].fill_(1)
    ordinary = torch.stack([r["plan"] for r in cache.entries])
    before = raw(ordinary)
    result = select(entries, cache, kw)
    # Prospective caller contract only; no production slot substitution is installed.
    actual = ordinary if result.candidate is None else ordinary.clone()
    if result.candidate is not None:
        actual[15] = result.candidate
    assert result.selected is None and result.candidate is None
    assert actual is ordinary and raw(actual) == before


def test_stable_reward_fingerprint_and_cell_ties():
    entries, cache, kw = fixture()
    cache.entries[0]["projection"].zero_()
    cache.entries[1]["quality"] = cache.entries[0]["quality"].clone()
    cache.entries[1]["cost"] = cache.entries[0]["cost"].clone()
    entries[1] = replace(entries[1], reward=16., cost=-16.)
    expected = min(entries, key=lambda c: (entries[c].fingerprint, c))
    assert select(dict(reversed(list(entries.items()))), cache, kw).selected.cell_id == expected
    entries = {9: entries[1], 3: entries[1]}
    assert select(entries, cache, kw).selected.cell_id == 3


def test_duplicate_content_records_all_occurrences_not_unique_lineage():
    entries, cache, kw = fixture()
    cache.entries[2] = {**copy.deepcopy(cache.entries[1]), "row": 2, "occurrence": 2}
    result = select(entries, cache, kw)
    assert result.selected.matching_occurrences == (1, 2)
    assert result.selected.association == "identical_content_multiple_occurrences"


@pytest.mark.parametrize("field", ["quality", "cost", "projection", "source_origin", "cast_origin"])
def test_contradictory_duplicate_fields_abort_even_with_eligible_best(field):
    entries, cache, kw = fixture()
    cache.entries[0]["projection"].zero_()  # Must not short-circuit after best qualifies.
    cache.entries[2] = {**copy.deepcopy(cache.entries[1]), "row": 2, "occurrence": 2}
    cache.entries[2][field].reshape(-1)[0] += 1
    with pytest.raises(h.AssociationError):
        select(entries, cache, kw)


def test_source_origin_native_difference_that_rounds_to_same_cast_fails():
    entries, cache, kw = fixture()
    cache.entries[2] = {**copy.deepcopy(cache.entries[1]), "row": 2, "occurrence": 2}
    cache.entries[2]["source_origin"][0] = 1e-100
    with pytest.raises(h.AssociationError, match="duplicate source_origin"):
        select(entries, cache, kw)


@pytest.mark.parametrize("fault", ["absent", "wrong_iteration", "fingerprint", "signed_zero",
    "quality", "cost", "projection_dtype", "missing_origin", "mask", "decision", "cache_order",
    "incomplete_cache", "nonfinite", "archive_dtype", "oversize", "empty"])
def test_bad_native_association_fails(fault):
    entries, cache, kw = fixture()
    if fault == "absent":
        action = entries[1].action.clone(); action[63, 39] = 7
        entries[1] = replace(entries[1], action=action, fingerprint=h.fingerprint_action(action))
    elif fault == "wrong_iteration": entries[1] = replace(entries[1], source_iter=0)
    elif fault == "fingerprint": entries[1] = replace(entries[1], fingerprint="false")
    elif fault == "signed_zero":
        action = entries[1].action.clone(); action[63, 0] = -0.
        entries[1] = replace(entries[1], action=action)
    elif fault == "quality": entries[1] = replace(entries[1], reward=99.)
    elif fault == "cost": cache.entries[1]["cost"] = torch.tensor(-99.)
    elif fault == "projection_dtype": cache.entries[1]["projection"] = cache.entries[1]["projection"].bfloat16()
    elif fault == "missing_origin": cache.entries[1]["source_origin"] = None
    elif fault == "mask": kw["action_mask"][0, 0, 11] = 1
    elif fault == "decision": kw["decision_id"] = (0, 0, 1)
    elif fault == "cache_order": cache.entries[1]["row"] = 9
    elif fault == "incomplete_cache": cache = replace(cache, entries=cache.entries[:-1])
    elif fault == "nonfinite": cache.entries[1]["projection"][0, 0] = float("nan")
    elif fault == "archive_dtype": entries[1] = replace(entries[1], action=entries[1].action.bfloat16())
    elif fault == "oversize": entries = {i: entries[1] for i in range(17)}
    elif fault == "empty": entries = {}
    with pytest.raises(h.AssociationError):
        select(entries, cache, kw)


def test_missing_projection_retains_unknown_in_failure():
    entries, cache, kw = fixture()
    cache.entries[1]["projection"] = None
    cache.entries[1]["projection_status"] = "Unknown_original_score_short_circuit"
    kw["target_recognized"] = False
    with pytest.raises(h.AssociationError, match="Unknown_original_score_short_circuit"):
        select(entries, cache, kw)


@pytest.mark.parametrize("field,reason", [("target", "target_unavailable"),
    ("gripper_qpos", "proprioception_unavailable")])
def test_helper_unknown_reason_preserved(field, reason):
    entries, cache, kw = fixture(); kw[field] = None
    result = select(entries, cache, kw)
    assert result.candidate is None and all(p.reason == reason for p in result.parents)


def test_complete_dwell_is_ineligible_not_reinserted():
    entries, cache, kw = fixture()
    row = cache.entries[1]
    row["plan"][3:8, 10] = 1; row["plan"][4:8, 39:45] = 0
    row["fingerprint"] = h.fingerprint_action(row["plan"])
    entries[1] = replace(entries[1], action=row["plan"].clone(), fingerprint=row["fingerprint"])
    result = select(entries, cache, kw)
    assert result.candidate is None and result.parents[1].reason == "no_native_change"


def test_later_opportunity_matches_only_source_iteration():
    entries, cache, kw = fixture()
    batch = [{**copy.deepcopy(r), "iteration": 0, "occurrence": r["occurrence"] + 16}
             for r in cache.entries]
    batch[1]["projection"].fill_(1)
    cache = replace(cache, entries=[*cache.entries, *batch]); kw["iteration"] = 1
    assert select(entries, cache, kw).selected.matching_occurrences == (1,)
    entries[1] = replace(entries[1], source_iter=0)
    assert select(entries, cache, kw).candidate is None


def test_fingerprint_collision_still_requires_exact_native_bytes(monkeypatch):
    entries, cache, kw = fixture()
    monkeypatch.setattr(h, "fingerprint_action", lambda _: "collision")
    for row in cache.entries:
        row["fingerprint"] = "collision"
    entries = {c: replace(e, fingerprint="collision") for c, e in entries.items()}
    assert select(entries, cache, kw).selected.matching_occurrences == (1,)
    action = entries[1].action.clone(); action[63, 39] = 7
    entries[1] = replace(entries[1], action=action)
    with pytest.raises(h.AssociationError, match="absent"):
        select(entries, cache, kw)


@pytest.mark.parametrize("dtype", [torch.float32, torch.bfloat16])
def test_synthetic_slot15_composition_preserves_other15_bytes(dtype):
    entries, cache, kw = fixture(dtype)
    ordinary = torch.stack([r["plan"] for r in cache.entries])
    ordinary[0, 63, 0] = -0.
    before = raw(ordinary)
    result = select(entries, cache, kw)
    actual = ordinary.clone(); actual[15] = result.candidate
    assert raw(actual[:15]) == raw(ordinary[:15])
    assert raw(actual[15]) == raw(result.candidate)
    assert raw(ordinary) == before


def test_signed_zero_duplicate_quality_disagreement_is_not_numeric_agreement():
    entries, cache, kw = fixture()
    cache.entries[1]["quality"] = torch.tensor(0.)
    cache.entries[1]["cost"] = torch.tensor(-0.)
    entries[1] = replace(entries[1], reward=0., cost=-0.)
    cache.entries[2] = {**copy.deepcopy(cache.entries[1]), "row": 2, "occurrence": 2}
    cache.entries[2]["quality"] = torch.tensor(-0.)
    cache.entries[2]["cost"] = torch.tensor(0.)
    with pytest.raises(h.AssociationError, match="duplicate quality"):
        select(entries, cache, kw)
