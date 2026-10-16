"""Offline initialization fixes never mutate benchmark assets or live episodes."""
import json
from types import SimpleNamespace as NS

import numpy as np
import pytest

from mode_gate import collection_initialization as ci


@pytest.fixture
def physics():
    mujoco = pytest.importorskip("mujoco")
    model = mujoco.MjModel.from_xml_string('''<mujoco><worldbody>
      <body name="table"><geom type="box" size=".5 .5 .2" pos="0 0 .2"/></body>
      <body name="robot" pos="2 2 2"><joint name="robot_joint" type="hinge"/>
        <geom name="robot_contact" type="sphere" size=".01"/></body>
      <body name="object" pos=".1 .1 .41"><freejoint name="object_joint"/>
        <geom type="sphere" size=".03" mass=".1"/></body>
    </worldbody></mujoco>''')
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    env = NS(parsed_problem={"objects": {"test": ["object"]}, "fixtures": {"table": ["table"]},
        "regions": {"table_region": {"target": "table"}},
        "initial_state": [["on", "object", "table_region"]]},
        get_object=lambda name: NS(joints=["object_joint"], root_body="object"),
        _eval_predicate=lambda clause: True)
    wrapper = NS(env=env, sim=NS(model=NS(_model=model), data=NS(_data=data)),
        robots=[NS(robot_model=NS(contact_geoms=["robot_contact"]), gripper=NS(contact_geoms=[]),
                   controller=NS(qvel_index=[0]))], check_success=lambda: False)
    source = np.concatenate(([data.time], data.qpos, data.qvel, data.act))
    return wrapper, model, data, source, mujoco


def test_support_preparation_only_changes_scratch_z(physics):
    wrapper, model, data, source, _ = physics
    before = data.qpos.copy(), data.qvel.copy()
    candidate, corrections = ci.prepare_supported_state(wrapper, source)
    np.testing.assert_array_equal(data.qpos, before[0])
    np.testing.assert_array_equal(data.qvel, before[1])
    changed = np.flatnonzero(candidate != source)
    assert changed.tolist() == [4]  # time + robot hinge + free xyz -> z
    assert candidate[4] == pytest.approx(.432)
    assert corrections[0]["raise_z_m"] == pytest.approx(.022)
    assert corrections[0]["object"] == "object"


def test_bad_support_or_excessive_raise_is_not_guessed(physics):
    wrapper, _, _, source, _ = physics
    with pytest.raises(ValueError, match="bound"):
        ci.prepare_supported_state(wrapper, source, max_raise_m=.01)
    wrapper.env.parsed_problem["initial_state"] = []
    with pytest.raises(ValueError, match="On predicate"):
        ci.prepare_supported_state(wrapper, source)


@pytest.fixture
def stacked_physics():
    mujoco = pytest.importorskip("mujoco")
    model = mujoco.MjModel.from_xml_string('''<mujoco><worldbody>
      <body name="table"><geom type="box" size=".5 .5 .2" pos="0 0 .2"/></body>
      <body name="box" pos=".1 .1 .5"><freejoint name="box_joint"/>
        <geom type="box" size=".1 .1 .04" mass=".2"/></body>
      <body name="top" pos=".1 .1 .65"><freejoint name="top_joint"/>
        <geom type="sphere" size=".03" mass=".1"/></body>
    </worldbody></mujoco>''')
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    env = NS(parsed_problem={"objects": {"test": ["top", "box"]}, "fixtures": {"table": ["table"]},
        "regions": {"table_region": {"target": "table"}},
        "initial_state": [["on", "top", "box"], ["on", "box", "table_region"]]},
        get_object=lambda name: None if name == "table" else NS(joints=[name + "_joint"], root_body=name))
    wrapper = NS(env=env, sim=NS(model=NS(_model=model), data=NS(_data=data)))
    source = np.concatenate(([data.time], data.qpos, data.qvel, data.act))
    return wrapper, model, data, source


def test_stack_preparation_projects_support_chain_bottom_up_in_scratch(stacked_physics):
    wrapper, _, data, source = stacked_physics
    before = data.qpos.copy(), data.qvel.copy()
    candidate, corrections = ci.prepare_object_stack_state(wrapper, source)
    np.testing.assert_array_equal(data.qpos, before[0])
    np.testing.assert_array_equal(data.qvel, before[1])
    assert np.flatnonzero(candidate != source).tolist() == [3, 10]
    assert candidate[3] == pytest.approx(.442)
    assert candidate[10] == pytest.approx(.514)
    assert [c["object"] for c in corrections] == ["box", "top"]


@pytest.mark.parametrize("problem", ["cycle", "missing_base", "no_stack", "shift_bound", "no_xy_support", "nonfinite"])
def test_stack_repair_does_not_guess_invalid_support(stacked_physics, problem):
    wrapper, _, _, source = stacked_physics
    kwargs = {}
    if problem == "cycle":
        wrapper.env.parsed_problem["initial_state"] = [["on", "top", "box"], ["on", "box", "top"]]
    elif problem == "missing_base":
        wrapper.env.parsed_problem["initial_state"].pop()
    elif problem == "no_stack":
        wrapper.env.parsed_problem["initial_state"].pop(0)
    elif problem == "shift_bound":
        kwargs["max_vertical_shift_m"] = .01
    elif problem == "no_xy_support":
        source[8] = 2.0
    else:
        source[0] = np.nan
    with pytest.raises(ValueError):
        ci.prepare_object_stack_state(wrapper, source, **kwargs)


@pytest.fixture
def site_physics():
    mujoco = pytest.importorskip("mujoco")
    model = mujoco.MjModel.from_xml_string('''<mujoco><worldbody>
      <body name="table" pos=".1 -.2 0" euler="0 0 30">
        <geom name="table_top" type="box" size=".16 .12 .01" pos="0 0 .4"/>
        <site name="table_site" type="box" size=".15 .11 .002" pos="0 0 .41"/>
      </body>
      <body name="selected" pos=".3 .1 .7"><freejoint name="selected_joint"/>
        <geom type="sphere" size=".03" mass=".1"/></body>
      <body name="untouched" pos=".4 .3 .5"><freejoint name="untouched_joint"/>
        <geom type="sphere" size=".03" mass=".1"/></body>
    </worldbody></mujoco>''')
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    env = NS(parsed_problem={"objects": {"test": ["selected", "untouched"]},
        "fixtures": {"table": ["table"]}, "regions": {"table_site": {"target": "table", "ranges": []}},
        "initial_state": [["on", "selected", "table_site"]]},
        get_object=lambda name: None if name == "table" else NS(joints=[name + "_joint"], root_body=name))
    wrapper = NS(env=env, sim=NS(model=NS(_model=model), data=NS(_data=data)))
    source = np.concatenate(([data.time], data.qpos, data.qvel, data.act))
    return wrapper, model, data, source, mujoco


def test_fixture_site_preparation_only_edits_selected_xyz_in_scratch(site_physics):
    wrapper, model, data, source, _ = site_physics
    before = data.qpos.copy(), data.qvel.copy(), model.body_pos.copy(), model.geom_size.copy()
    candidate, corrections = ci.prepare_fixture_site_state(wrapper, source, site_offsets_xy={"selected": [.01, -.01]})
    assert np.flatnonzero(candidate != source).tolist() == [1, 2, 3]
    np.testing.assert_allclose(candidate[1:4], [.11366025404, -.20366025404, .442])
    np.testing.assert_array_equal(candidate[4:], source[4:])
    for actual, expected in zip([data.qpos, data.qvel, model.body_pos, model.geom_size], before):
        np.testing.assert_array_equal(actual, expected)
    assert corrections[0]["support_geom"] == "table_top"
    assert corrections[0]["predicate"] == ["on", "selected", "table_site"]
    assert corrections[0]["site_local_offset_xy_m"] == [.01, -.01]


@pytest.mark.parametrize("problem", ["empty", "nonfinite_source", "nonfinite_offset", "offset_bound",
    "translation_bound", "unknown_object", "ambiguous", "missing_site", "wrong_site_body",
    "ranged_region", "articulated_fixture", "tilted_site", "no_site_footprint", "no_physical_support"])
def test_fixture_site_preparation_rejects_unsafe_or_ambiguous_targets(site_physics, problem):
    wrapper, model, data, source, mujoco = site_physics
    kwargs = {"site_offsets_xy": {"selected": [.01, -.01]}}
    if problem == "empty":
        kwargs["site_offsets_xy"] = {}
    elif problem == "nonfinite_source":
        source[0] = np.nan
    elif problem == "nonfinite_offset":
        kwargs["site_offsets_xy"]["selected"][0] = np.nan
    elif problem == "offset_bound":
        kwargs["site_offsets_xy"]["selected"][0] = .026
    elif problem == "translation_bound":
        kwargs["max_translation_m"] = .1
    elif problem == "unknown_object":
        kwargs["site_offsets_xy"] = {"table": [0, 0]}
    elif problem == "ambiguous":
        wrapper.env.parsed_problem["initial_state"] *= 2
    elif problem == "missing_site":
        wrapper.env.parsed_problem["initial_state"][0][2] = "absent"
        wrapper.env.parsed_problem["regions"]["absent"] = {"target": "table"}
    elif problem == "wrong_site_body":
        model.site_bodyid[0] = 0
    elif problem == "ranged_region":
        wrapper.env.parsed_problem["regions"]["table_site"]["ranges"] = [[-.1, -.1, .1, .1]]
    elif problem == "articulated_fixture":
        model.site_bodyid[0] = 2
        wrapper.env.parsed_problem["regions"]["table_site"]["target"] = "selected"
        wrapper.env.parsed_problem["fixtures"]["table"].append("selected")
    elif problem == "tilted_site":
        model.site_quat[0] = [np.sqrt(.5), np.sqrt(.5), 0, 0]
        # MuJoCo caches identity-frame sites at compile time. Changing the
        # quaternion alone does not rotate such a site in current MuJoCo.
        model.site_sameframe[0] = 0
    elif problem == "no_site_footprint":
        model.site_size[0, 0] = .01
    else:
        model.geom_size[0, :2] = .01
    mujoco.mj_forward(model, data)
    before = data.qpos.copy(), data.qvel.copy()
    with pytest.raises(ValueError):
        ci.prepare_fixture_site_state(wrapper, source, **kwargs)
    np.testing.assert_array_equal(data.qpos, before[0])
    np.testing.assert_array_equal(data.qvel, before[1])


def test_readiness_rejects_overlap_without_mutating_state(physics):
    wrapper, _, data, _, _ = physics
    before = data.qpos.copy()
    with pytest.raises(ValueError, match="physically ready"):
        ci.validate_initial_state(wrapper)
    np.testing.assert_array_equal(before, data.qpos)


@pytest.mark.parametrize("problem", ["moving", "nonfinite", "already_success", "predicate"])
def test_readiness_rejects_invalid_start(physics, problem):
    wrapper, model, data, source, mujoco = physics
    candidate, _ = ci.prepare_supported_state(wrapper, source)
    # Separate test simulator initialization, never a collection action.
    data.qpos[:] = candidate[1:1 + model.nq]
    mujoco.mj_forward(model, data)
    ci.validate_initial_state(wrapper)
    if problem == "moving":
        data.qvel[1] = .2
    elif problem == "nonfinite":
        data.qvel[1] = np.nan
    elif problem == "already_success":
        wrapper.check_success = lambda: True
    else:
        wrapper.env._eval_predicate = lambda clause: False
    with pytest.raises(ValueError):
        ci.validate_initial_state(wrapper)


def _region_discrepancy(physics):
    wrapper, model, data, source, mujoco = physics
    # Original XY lies outside a narrow intended sampling rectangle, but over
    # the physical tabletop. Keep the native region predicate false.
    wrapper.env.parsed_problem["regions"]["table_region"]["ranges"] = [[0, 0, .05, .05]]
    wrapper.env.get_object = lambda name: None if name == "table" else NS(joints=["object_joint"], root_body="object")
    wrapper.env._eval_predicate = lambda clause: False
    data.qpos[3] = .429999
    mujoco.mj_forward(model, data)
    samples = [{"predicate": ["on", "object", "table_region"], "source_xy": [.1, .1]}]
    return wrapper, model, data, source, mujoco, samples


def test_preserved_region_sampling_keeps_native_false_and_requires_physical_support(physics):
    wrapper, _, data, source, _, samples = _region_discrepancy(physics)
    before = data.qpos.copy()
    with pytest.raises(ValueError):
        ci.validate_initial_state(wrapper)
    ci._preserved_region_specs(wrapper, samples, source_state=source)
    result = ci.validate_initial_state(wrapper, preserved_region_sampling=samples)
    assert result["initial_predicates"] == {"on object table_region": False}
    record = result["preserved_source_region_sampling"]["on object table_region"]
    assert record["physical_support_contact"] and record["horizontal_drift_m"] == 0
    np.testing.assert_array_equal(before, data.qpos)


@pytest.mark.parametrize("problem", ["drift", "floating", "goal", "stack", "inside_region", "source_mismatch", "duplicate", "moving"])
def test_region_disclosure_cannot_waive_success_or_invalid_physics(physics, problem):
    wrapper, model, data, source, mujoco, samples = _region_discrepancy(physics)
    if problem == "drift":
        data.qpos[1] += .006
    elif problem == "floating":
        data.qpos[3] += .01
    elif problem == "goal":
        wrapper.check_success = lambda: True
    elif problem == "stack":
        samples[0]["predicate"][-1] = "object"
        wrapper.env.parsed_problem["initial_state"] = [samples[0]["predicate"]]
    elif problem == "inside_region":
        wrapper.env.parsed_problem["regions"]["table_region"]["ranges"] = [[0, 0, .2, .2]]
    elif problem == "source_mismatch":
        samples[0]["source_xy"][0] = .11
    elif problem == "duplicate":
        samples *= 2
    else:
        data.qvel[1] = .2
    mujoco.mj_forward(model, data)
    with pytest.raises(ValueError):
        ci._preserved_region_specs(wrapper, samples, source_state=source)
        ci.validate_initial_state(wrapper, preserved_region_sampling=samples)


def test_static_workspace_alias_resolves_from_region_site_not_guessed():
    mujoco = pytest.importorskip("mujoco")
    model = mujoco.MjModel.from_xml_string('''<mujoco><worldbody>
      <body name="physical_worktop"><geom type="box" size=".5 .5 .2"/>
        <site name="workspace_region" type="box" size=".01 .01 .001" pos="0 0 .2"/>
      </body></worldbody></mujoco>''')
    env = NS(get_object=lambda name: None, parsed_problem={
        "regions": {"workspace_region": {"target": "logical_workspace"}}})
    root, geoms = ci._static_fixture_parts(env, model, "logical_workspace")
    assert root == mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "physical_worktop")
    assert geoms == {0}


@pytest.fixture
def revision(tmp_path):
    ticket_path = tmp_path / "ticket.json"
    ticket_path.write_text('{}')
    ticket = NS(ticket_id="ticket", task_id="task", suite="suite", perturbation_variant="env",
                init_state_ids=["1"])
    original = np.arange(30, dtype=np.float64).reshape(3, 10)
    source = tmp_path / "original.npy"
    np.save(source, original)
    bddl = tmp_path / "task.bddl"
    bddl.write_text("unchanged")
    states = tmp_path / "states.npz"
    new = original[1] + 1
    np.savez(states, init_1=new)
    entry = {"init_state_id": "1", "state_key": "init_1", "source_state_sha256": ci.state_sha256(original[1]),
             "revised_state_sha256": ci.state_sha256(new)}
    payload = {"schema_version": ci.SCHEMA, "revision": "v1", "requested_by": "user",
        "scope": "offline_demonstration_only", "ticket_id": ticket.ticket_id,
        "ticket_sha256": ci.file_sha256(ticket_path), "task_id": ticket.task_id, "suite": ticket.suite,
        "perturbation_variant": ticket.perturbation_variant, "source_catalog_sha256": ci.file_sha256(source),
        "bddl_sha256": ci.file_sha256(bddl), "states_file": states.name,
        "states_sha256": ci.file_sha256(states), "entries": [entry]}
    path = tmp_path / "initialization_revision.json"
    path.write_text(json.dumps(payload))
    environment = NS(task_id=7, init_states_file=source, bddl_file_name=bddl, _init_states=original)
    adapter = NS(_env=[environment], current_task_idx=0)
    manifest = {"tasks": [{"suite": ticket.suite, "task_id": ticket.task_id,
        "perturbation_variant": ticket.perturbation_variant, "task_index": 7,
        "splits": {"demo_online_pool": ["1"]}}]}
    args = dict(ticket=ticket, ticket_path=ticket_path, manifest=manifest, offline_root=tmp_path / "offline")
    return adapter, args, path, payload, original


def test_catalog_revision_is_private_and_original_assets_unchanged(revision):
    adapter, args, path, _, original = revision
    env = adapter._env[0]
    asset_before = env.init_states_file.read_bytes(), env.bddl_file_name.read_bytes()
    handle = ci.activate_collection_revision(adapter, **args)
    assert handle.init_ids == {"1"} and handle.metadata["revision"] == "v1"
    assert handle.metadata["revision_manifest_sha256"] == ci.file_sha256(path)
    assert not np.shares_memory(env._init_states, original)
    np.testing.assert_array_equal(env._init_states[[0, 2]], original[[0, 2]])
    np.testing.assert_array_equal(env._init_states[1], original[1] + 1)
    assert asset_before == (env.init_states_file.read_bytes(), env.bddl_file_name.read_bytes())
    assert handle.validate(adapter, "0") is None


def test_no_revision_is_noop_even_online(revision):
    adapter, args, path, _, original = revision
    path.unlink()
    args["offline_root"] = None
    assert ci.activate_collection_revision(adapter, **args) is None
    assert adapter._env[0]._init_states is original


@pytest.mark.parametrize("problem", ["online", "ticket", "heldout", "unselected", "source_hash",
    "payload_hash", "row_hash", "state_hash", "bddl_hash", "wrong_task", "missing_version", "escape_path"])
def test_revision_rejects_mismatch_before_catalog_mutation(revision, problem):
    adapter, args, path, payload, original = revision
    if problem == "online":
        args["offline_root"] = None
    elif problem == "ticket":
        payload["ticket_id"] = "another"
    elif problem == "heldout":
        args["manifest"]["tasks"][0]["splits"]["demo_online_pool"] = ["0"]
    elif problem == "unselected":
        args["ticket"].init_state_ids = ["0"]
    elif problem == "source_hash":
        payload["source_catalog_sha256"] = "bad"
    elif problem == "payload_hash":
        payload["states_sha256"] = "bad"
    elif problem == "row_hash":
        payload["entries"][0]["source_state_sha256"] = "bad"
    elif problem == "state_hash":
        payload["entries"][0]["revised_state_sha256"] = "bad"
    elif problem == "bddl_hash":
        payload["bddl_sha256"] = "bad"
    elif problem == "wrong_task":
        adapter._env[0].task_id = 8
    elif problem == "missing_version":
        payload.pop("revision")
    elif problem == "escape_path":
        payload["states_file"] = "../outside.npz"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        ci.activate_collection_revision(adapter, **args)
    assert adapter._env[0]._init_states is original
