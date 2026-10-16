"""Chinese operator guidance derived from the active LIBERO-PRO predicates.

The simulator owns success. Intermediate grasp/lift hints are deliberately
separate from benchmark predicates and never manufacture a success label.
No rendering, policy inference, network request, or simulator step occurs here.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping


OBJECT_NAMES_ZH = {
    "akita_black_bowl": "黑色碗", "bigger_akita_black_bowl": "大号黑色碗",
    "black_bowl": "黑色碗", "alphabet_soup": "字母汤罐头",
    "bigger_alphabet_soup": "大号字母汤罐头", "basket": "篮子",
    "red_basket": "红色篮子", "bbq_sauce": "烧烤酱瓶",
    "green_bbq_sauce": "绿色烧烤酱瓶", "black_book": "黑色书本",
    "butter": "黄油盒", "green_butter": "绿色黄油盒",
    "chocolate_pudding": "巧克力布丁盒", "green_chocolate_pudding": "绿色巧克力布丁盒",
    "cream_cheese": "奶油奶酪盒", "red_cream_cheese": "红色奶油奶酪盒",
    "desk_caddy": "桌面收纳架", "flat_stove": "炉子", "yellow_stove": "黄色炉子",
    "ketchup": "番茄调味酱瓶", "blue_ketchup": "蓝色番茄调味酱瓶",
    "microwave": "微波炉", "milk": "牛奶盒", "yellow_milk": "黄色牛奶盒",
    "moka_pot": "摩卡壶", "yellow_moka_pot": "黄色摩卡壶",
    "orange_juice": "橙汁盒", "plate": "盘子", "yellow_plate": "黄色盘子",
    "porcelain_mug": "白色马克杯", "white_yellow_mug": "黄白色马克杯",
    "red_coffee_mug": "红色咖啡杯", "salad_dressing": "沙拉酱瓶",
    "red_salad_dressing": "红色沙拉酱瓶", "tomato_sauce": "番茄酱罐头",
    "yellow_tomato_sauce": "黄色番茄酱罐头", "white_bottle": "白色瓶子",
    "wine_bottle": "葡萄酒瓶", "wine_rack": "酒架", "brown_rack": "棕色酒架",
    "wooden_cabinet": "木柜", "white_cabinet": "白色柜子", "yellow_cabinet": "黄色柜子",
    "ramekin": "小烤碗", "cookies": "饼干盒", "cookie_box": "饼干盒",
    "chefmate_8_frypan": "平底锅",
}
REGIONS_ZH = {
    "cook_region": "加热区", "heating_region": "内部加热区",
    "contain_region": "内部", "back_contain_region": "后侧隔间",
    "top_side": "顶面", "top_region": "上层抽屉",
    "middle_region": "中层抽屉", "bottom_region": "下层抽屉",
}


def object_name_zh(name: str, *, task_id: str = "") -> str:
    for ending, text in (("stove_front_region", "炉子前方的桌面区域"),
                         ("yellow_plate_right_region", "黄色盘子右侧的桌面区域"),
                         ("plate_right_region", "盘子右侧的桌面区域")):
        if name.endswith(ending):
            return text
    match = re.fullmatch(r"(.+)_(\d+)(?:_(.+))?", name)
    if match is None or match[1] not in OBJECT_NAMES_ZH:
        raise ValueError(f"missing Chinese simulator object name: {name}")
    kind, number, region = match.groups()
    label = OBJECT_NAMES_ZH[kind]
    if kind in {"plate", "yellow_plate"} and "left_plate" in task_id:
        label = ("左侧" if number == "1" else "右侧") + label
    elif number != "1" or "both_moka_pots" in task_id:
        label += f"（{number}号）"
    if region:
        if region not in REGIONS_ZH:
            raise ValueError(f"missing Chinese simulator region name: {name}")
        region_zh = REGIONS_ZH[region]
        if "rack" in kind and region == "top_region":
            region_zh = "上层置物区"
        label += "的" + region_zh
    return label


def source_hint_zh(task_id: str) -> str:
    """Retain spatial disambiguation; object variants still use their real names."""
    sources = {
        "between_the_plate_and_the_ramekin": "盘子与小烤碗之间的",
        "from_table_center": "桌面中央的",
        "in_the_top_drawer": "柜子上层抽屉内的",
        "next_to_the_cookie_box": "饼干盒旁的",
        "next_to_the_plate": "盘子旁的",
        "next_to_the_ramekin": "小烤碗旁的",
        "on_the_cookie_box": "饼干盒上的",
        "on_the_ramekin": "小烤碗上的",
        "on_the_stove_and_place": "炉子上的",
        "on_the_wooden_cabinet_and_place": "木柜顶面的",
    }
    if "pick_up_the_black_bowl" not in task_id:
        return ""
    return next((value for key, value in sources.items() if key in task_id), "")


@dataclass(frozen=True)
class OperatorStep:
    kind: str
    predicate: tuple[str, ...]
    text: str
    next_action: str
    # An access/grasp step is no longer needed once its dependent placement is
    # true. This is not historical latching: falling objects revoke progress.
    satisfied_by: tuple[tuple[str, ...], ...] = ()
    dependencies: tuple[tuple[str, ...], ...] = ()


def build_operator_steps(problem: Mapping[str, Any], *, task_id: str) -> list[OperatorStep]:
    goals = [tuple(str(value).lower() for value in goal) for goal in problem["goal_state"]]
    if not goals or any(g[0] not in {"on", "in", "open", "close", "turnon", "turnoff"}
                        or len(g) != (3 if g[0] in {"on", "in"} else 2) for g in goals):
        raise ValueError("unsupported LIBERO goal; cannot claim automatic step coverage")
    name = lambda value: object_name_zh(value, task_id=task_id)
    placements = [goal for goal in goals if goal[0] in {"on", "in"}]
    steps: list[OperatorStep] = []
    # BDDL is a conjunction, not a temporal plan: open before inserting, close
    # afterwards, and turn on before placing on the burner.
    for goal in goals:
        if goal[0] not in {"turnon", "turnoff", "open"}:
            continue
        target = name(goal[1])
        verb = {"turnon": "开启", "turnoff": "关闭", "open": "打开"}[goal[0]]
        action = (f"操纵{target}的旋钮，直到模拟器显示已{verb}；不是向下按压按钮。"
                  if "stove" in goal[1] else f"握住{target}的把手，沿活动方向缓慢{verb}。")
        steps.append(OperatorStep("goal", goal, f"{verb}{target}。", action))

    for goal in placements:
        obj, destination = goal[1:]
        # Infer the mechanical access prerequisite from exact source/destination
        # sites, not from a language-model guess about this particular task.
        access = []
        for state in problem.get("initial_state", []):
            if len(state) == 3 and str(state[0]).lower() == "in" and state[1] == obj:
                access.append(str(state[2]))
        access.append(destination)
        for site in dict.fromkeys(access):
            if "cabinet" in site and site.endswith(("top_region", "middle_region", "bottom_region")):
                open_target = site
            elif "microwave" in site:
                open_target = site.split("_heating_region")[0]
            else:
                continue
            opening = ("open", open_target)
            if not any(step.predicate == opening for step in steps):
                text = f"打开{name(open_target)}。"
                steps.append(OperatorStep("access", opening, text,
                    f"先握住把手打开{name(open_target)}，为取放物体留出空间。", (goal,)))
        target = source_hint_zh(task_id) + name(obj)
        pushing = "push_the_plate" in task_id
        if not pushing:
            steps.append(OperatorStep("grasp_lift", ("grasp_lift", obj),
                f"抓住{target}并抬离原支撑面。",
                f"张开夹爪对准{target}，闭合后缓慢抬起；需要两指接触且抬升至少 2 厘米。",
                (goal,)))
        # Some BDDL 'On' bowl relations describe containment in the task text.
        inside = goal[0] == "in" or ("bowl" in destination and "in_the_bowl" in task_id)
        verb = "推到" if pushing else "放入" if inside else "放到"
        text = f"把{name(obj)}{verb}{name(destination)}。"
        action = (f"贴近{name(obj)}侧面，沿桌面缓慢推向{name(destination)}，不要抬起。"
                  if pushing else f"保持抓稳，将{name(obj)}移向{name(destination)}，缓慢放下；避免提前松手。")
        steps.append(OperatorStep("goal", goal, text, action))
    for goal in goals:
        if goal[0] == "close":
            relevant = tuple(p for p in placements if p[2].startswith(goal[1]))
            steps.append(OperatorStep("goal", goal, f"关闭{name(goal[1])}。",
                f"确认物体已放入、夹爪已退出，再缓慢关闭{name(goal[1])}。",
                dependencies=relevant))
    return steps


class LiberoTaskGuidance:
    """A new instance per queue entry; predicates recompute on step and undo."""

    def __init__(self, adapter: Any, *, task_id: str) -> None:
        self.adapter = adapter
        self.wrapper = adapter._get_current_robosuite_env()
        self.env = getattr(self.wrapper, "env", self.wrapper)
        self.task_id = task_id
        self.steps = build_operator_steps(self.env.parsed_problem, task_id=task_id)
        self.initial_z: dict[str, float] = {}
        for step in self.steps:
            if step.kind == "grasp_lift":
                obj = step.predicate[1]
                self.initial_z[obj] = float(self.env.object_states_dict[obj].get_geom_state()["pos"][2])

    @property
    def task_instruction_zh(self) -> str:
        return "；".join(step.text.rstrip("。") for step in self.steps if step.kind == "goal") + "。"

    @property
    def mechanics_zh(self) -> list[str]:
        notes = []
        if any("stove" in step.predicate[1] for step in self.steps):
            notes.append("此模拟器炉子开关为绕竖直轴旋转的旋钮，不是下压按钮；开启阈值为旋钮关节位置达到 0.5。纠正与此冲突的按压或禁止旋转说明，保留接近方向要求。")
        return notes

    def status(self, *, coverage_hint: str = "") -> dict[str, Any]:
        cache: dict[tuple[str, ...], bool | None] = {}
        diagnostics: list[str] = []

        def predicate(value: tuple[str, ...]) -> bool | None:
            if value not in cache:
                try:
                    cache[value] = bool(self.env._eval_predicate(list(value)))
                except Exception as exc:
                    cache[value] = None
                    diagnostics.append(f"{value}: {type(exc).__name__}: {exc}")
            return cache[value]

        try:
            success = bool(self.wrapper.check_success())
        except Exception as exc:
            success = None
            diagnostics.append(f"task_success: {type(exc).__name__}: {exc}")
        complete: list[bool | None] = []
        metrics: dict[str, Any] = {}
        for step in self.steps:
            dependents = [predicate(value) for value in step.satisfied_by]
            if step.kind in {"grasp_lift", "access"} and any(value is True for value in dependents):
                value: bool | None = True
                metrics[" ".join(step.predicate)] = {"satisfied_by_placement": True}
            elif step.kind == "grasp_lift":
                obj = step.predicate[1]
                try:
                    position = self.env.object_states_dict[obj].get_geom_state()["pos"]
                    lift = float(position[2]) - self.initial_z[obj]
                    grasped = bool(self.env._check_grasp(
                        gripper=self.env.robots[0].gripper,
                        object_geoms=self.env.get_object(obj).contact_geoms,
                    ))
                    value = grasped and lift >= 0.02
                    metrics[obj] = {"grasped": grasped, "lift_m": lift}
                except Exception as exc:
                    value = None
                    diagnostics.append(f"grasp {obj}: {type(exc).__name__}: {exc}")
            else:
                value = predicate(step.predicate)
            required = [predicate(dep) for dep in step.dependencies]
            if required and not all(item is True for item in required):
                value = None if any(item is None for item in required) else False
            complete.append(value)
        # Intermediate hints are not extra benchmark requirements. Authoritative
        # success can finish the task even if an optional grasp hint was missed.
        if success is True:
            complete = [True] * len(self.steps)
        current = next((i for i, value in enumerate(complete) if value is not True), len(self.steps))
        if success is True:
            title = "LIBERO-PRO 已判定成功"
            action = "停止移动，点击“标记成功”，然后点击“保存 / 下一条”。"
        elif current < len(self.steps):
            title = f"第 {current + 1}/{len(self.steps)} 步：{self.steps[current].text}"
            action = self.steps[current].next_action
        else:
            title = "步骤条件已满足，整项成功尚未确认"
            action = "请检查目标物体是否保持正确位置；整项成功以模拟器信号为准。"
        if diagnostics and success is not True:
            action = "部分状态暂不可读，不会据此判定完成。" + action
        summaries = []
        for key, value in cache.items():
            if key[0] in {"turnon", "turnoff", "open", "close"}:
                state = "已满足" if value is True else "未满足" if value is False else "未知"
                summaries.append(f"{object_name_zh(key[1], task_id=self.task_id)}：{state}")
        for obj, value in metrics.items():
            if "lift_m" in value:
                summaries.append(f"{object_name_zh(obj, task_id=self.task_id)}：两指抓持{'是' if value['grasped'] else '否'}，抬升 {100 * value['lift_m']:.1f} 厘米")
        return {
            "schema_version": "libero-predicate-guidance-v1",
            "stage_index": current, "stage_title": title, "next_action": action,
            "checklist": [step.text for step in self.steps],
            "checklist_complete": complete,
            "checklist_sources": ["抓持与抬升辅助信号" if step.kind == "grasp_lift" else "模拟器状态条件" for step in self.steps],
            "task_success": success, "progress": " · ".join(summaries),
            "coverage_hint": coverage_hint, "metrics": metrics,
            "predicate_values": {" ".join(key): value for key, value in cache.items()},
            "diagnostics": diagnostics,
        }
