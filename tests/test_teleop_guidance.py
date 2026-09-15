from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from mode_gate.teleop_guidance import LiberoTaskGuidance, build_operator_steps


def fake_guide(goals, *, initial=(), task_id="task"):
    relations, held, positions = {}, set(), {}
    for goal in goals:
        for obj in goal[1:]:
            positions[obj] = [0.0, 0.0, 0.9]
    env = SimpleNamespace(
        parsed_problem={"goal_state": goals, "initial_state": initial},
        object_states_dict={obj: SimpleNamespace(get_geom_state=lambda key=obj: {"pos": positions[key]})
                            for obj in positions},
        robots=[SimpleNamespace(gripper=object())],
        get_object=lambda obj: SimpleNamespace(contact_geoms=[obj]),
        _check_grasp=lambda *, gripper, object_geoms: object_geoms[0] in held,
        _eval_predicate=lambda value: relations.get(tuple(value), False),
        check_success=lambda: all(relations.get(tuple(goal), False) for goal in goals),
    )
    guide = LiberoTaskGuidance(SimpleNamespace(_get_current_robosuite_env=lambda: env), task_id=task_id)
    return guide, relations, held, positions, env


def test_stove_steps_use_real_predicates_and_contact_not_closed_gripper():
    on = ("turnon", "flat_stove_1")
    placed = ("on", "moka_pot_1", "flat_stove_1_cook_region")
    guide, relations, held, positions, _ = fake_guide([on, placed])
    assert guide.status()["checklist_complete"] == [False, False, False]
    relations[on] = True
    assert guide.status()["checklist_complete"] == [True, False, False]
    # Lifting height or closing empty fingers alone is not a grasp.
    positions["moka_pot_1"][2] += 0.03
    assert guide.status()["checklist_complete"] == [True, False, False]
    held.add("moka_pot_1")
    assert guide.status()["checklist_complete"] == [True, True, False]
    held.clear()
    assert guide.status()["checklist_complete"] == [True, False, False]
    relations[placed] = True
    assert guide.status()["task_success"] is True
    assert guide.status()["checklist_complete"] == [True, True, True]
    relations[on] = False
    assert guide.status()["task_success"] is False
    assert guide.status()["stage_index"] == 0
    relations[placed] = False
    assert guide.status()["checklist_complete"] == [False, False, False]
    assert "旋钮" in guide.steps[0].next_action


def test_container_access_precedes_placement_and_close_waits_for_contents():
    closing = ("close", "white_cabinet_1_bottom_region")
    placed = ("in", "akita_black_bowl_1", "white_cabinet_1_bottom_region")
    guide, relations, _, _, _ = fake_guide([closing, placed])
    assert [step.predicate[0] for step in guide.steps] == ["open", "grasp_lift", "in", "close"]
    relations[closing] = True
    assert guide.status()["checklist_complete"][-1] is False
    relations[("open", closing[1])] = True
    relations[closing] = False
    relations[placed] = True
    assert guide.status()["stage_index"] == 3
    relations[closing] = True
    assert guide.status()["task_success"] is True


def test_push_task_does_not_instruct_grasp_or_lift():
    guide, *_ = fake_guide([("on", "plate_1", "main_table_stove_front_region")],
                          task_id="push_the_plate_to_the_front_of_the_stove")
    assert len(guide.steps) == 1
    assert "推到" in guide.steps[0].text
    assert "不要抬起" in guide.steps[0].next_action


def test_source_drawer_and_spatial_object_disambiguation_are_preserved():
    guide, *_ = fake_guide([("on", "bigger_akita_black_bowl_1", "plate_1")],
        initial=[("in", "bigger_akita_black_bowl_1", "wooden_cabinet_1_top_region")],
        task_id="pick_up_the_black_bowl_in_the_top_drawer_of_the_wooden_cabinet_and_place_it_on_the_plate")
    assert guide.steps[0].predicate == ("open", "wooden_cabinet_1_top_region")
    assert "大号黑色碗" in guide.steps[1].text
    assert "上层抽屉内" in guide.steps[1].text


def test_unknown_signal_is_not_false_success_and_fresh_instance_resets_height():
    goal = ("on", "moka_pot_1", "flat_stove_1_cook_region")
    guide, _, held, positions, env = fake_guide([goal])
    held.add("moka_pot_1")
    positions["moka_pot_1"][2] += 0.03
    assert guide.status()["checklist_complete"][0] is True
    new = LiberoTaskGuidance(guide.adapter, task_id="task")
    assert new.status()["checklist_complete"][0] is False

    def broken(value):
        raise RuntimeError("signal unavailable")

    env._eval_predicate = broken
    status = guide.status()
    assert status["checklist_complete"][-1] is None
    assert status["task_success"] is False
    assert status["diagnostics"]
    env.check_success = lambda: True
    assert all(guide.status()["checklist_complete"])


def parse_problem_text(text):
    """Minimal test-only s-expression reader; production uses LIBERO's parser."""
    stack = [[]]
    for token in re.findall(r"\(|\)|[^\s()]+", re.sub(r";[^\n]*", "", text.lower())):
        if token == "(":
            node = []
            stack[-1].append(node)
            stack.append(node)
        elif token == ")":
            stack.pop()
        else:
            stack[-1].append(token)
    sections = {part[0]: part[1:] for part in stack[0][0][1:] if isinstance(part, list)}
    goal = sections[":goal"][0]
    return {"goal_state": goal[1:] if goal[0] == "and" else [goal],
            "initial_state": sections[":init"]}


def test_all_160_libero_pro_task_variants_have_chinese_grounded_steps():
    root = Path(__file__).resolve().parents[1] / "third_party/libero_pro/libero/libero/bddl_files"
    if not root.exists():
        pytest.skip("LIBERO-PRO submodule is available on the simulator host")
    paths = [path for path in root.glob("*/*.bddl") if re.fullmatch(
        r"libero_(10|goal|object|spatial)_(lan|env|object|swap)", path.parent.name)]
    assert len(paths) == 160
    for path in paths:
        problem = parse_problem_text(path.read_text())
        steps = build_operator_steps(problem, task_id=path.stem)
        assert steps, path
        assert {tuple(goal) for goal in problem["goal_state"]} == {
            step.predicate for step in steps if step.kind == "goal"}, path
        for step in steps:
            for text in (step.text, step.next_action):
                assert re.search(r"[\u3400-\u9fff]", text), (path, text)
                assert not re.search(r"[a-zA-Z_]", text), (path, text)


def test_unknown_predicate_fails_closed_instead_of_silent_static_steps():
    with pytest.raises(ValueError, match="unsupported LIBERO goal"):
        build_operator_steps({"goal_state": [["unexpected", "moka_pot_1"]]}, task_id="unknown")


def test_backend_port_handoff_persists_for_later_queues(tmp_path):
    from mode_gate.io_utils import atomic_write_json
    from mode_gate.teleop_supervisor import TeleopSupervisor

    assert TeleopSupervisor.recorded_backend_port(tmp_path, default=8766) == 8766
    atomic_write_json(tmp_path / "active.json", {"health_url": "http://127.0.0.1:8767/healthz"})
    assert TeleopSupervisor.recorded_backend_port(tmp_path, default=8766) == 8767
    atomic_write_json(tmp_path / "active.json", {"health_url": "https://example.com/healthz"})
    with pytest.raises(ValueError, match="invalid backend"):
        TeleopSupervisor.recorded_backend_port(tmp_path, default=8766)


def test_legacy_translation_is_cached_without_mutating_ticket_or_coverage(tmp_path):
    import json
    from mode_gate.tickets import CollectionSpec, operator_collection_zh

    source = CollectionSpec(capability_gap="grasp", coverage_axes=[
        {"axis": "direction", "value": "from_above", "quota": 15}],
        must_demonstrate=["grasp the pot"], must_avoid=["dropping the pot"])
    original = source.model_dump()
    calls = []
    chinese = {**original, "capability_gap": "抓持能力不足",
        "coverage_axes": [{**original["coverage_axes"][0], "operator_instruction_zh": "从正上方接近。"}],
        "must_demonstrate": ["抓稳摩卡壶。"], "must_avoid": ["不要使摩卡壶掉落。"]}
    planner = SimpleNamespace(max_retries=0, model="test", timeout_seconds=5,
        thinking_level="medium", call_budget=SimpleNamespace(reserve=lambda **kw: calls.append(kw)),
        _call=lambda prompt: SimpleNamespace(text=json.dumps(chinese)))
    kwargs = dict(cache_path=tmp_path / "operator_guide_zh.json", task_instruction="put pot on stove",
        simulator_goals_zh="将摩卡壶放到炉子上。", mechanics_zh=[], planner_factory=lambda: planner)
    first = operator_collection_zh(source, **kwargs)
    second = operator_collection_zh(source, **kwargs)
    assert first == second and len(calls) == 1
    assert source.model_dump() == original
    assert first.coverage_axes[0].value == "from_above"
    assert first.coverage_axes[0].quota == 15
    assert operator_collection_zh(first, **kwargs) == first
    assert len(calls) == 1


def test_chinese_translation_rejects_changed_coverage_and_english_items():
    from mode_gate.tickets import CollectionSpec, _validate_operator_translation

    source = CollectionSpec(capability_gap="gap", coverage_axes=[
        {"axis": "direction", "value": "above", "quota": 15}],
        must_demonstrate=["grasp"], must_avoid=["collision"])
    with pytest.raises(ValueError, match="Simplified Chinese"):
        _validate_operator_translation(source, source)
    changed = source.model_copy(update={"must_avoid": []})
    with pytest.raises(ValueError, match="preserve"):
        _validate_operator_translation(source, changed)
