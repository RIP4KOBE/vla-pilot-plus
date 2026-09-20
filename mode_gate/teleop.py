"""Localhost-only step-per-key browser teleoperation for hgpu1 EGL."""

import base64
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np
import torch

from .data_pipeline import DemoFrame, DemoWriter


KEY_ACTIONS: dict[str, np.ndarray] = {
    "w": np.array([+0.25, 0, 0, 0, 0, 0, 0], dtype=np.float32),
    "s": np.array([-0.25, 0, 0, 0, 0, 0, 0], dtype=np.float32),
    "a": np.array([0, +0.25, 0, 0, 0, 0, 0], dtype=np.float32),
    "d": np.array([0, -0.25, 0, 0, 0, 0, 0], dtype=np.float32),
    "q": np.array([0, 0, +0.25, 0, 0, 0, 0], dtype=np.float32),
    "e": np.array([0, 0, -0.25, 0, 0, 0, 0], dtype=np.float32),
    "arrowup": np.array([0, 0, 0, +0.20, 0, 0, 0], dtype=np.float32),
    "arrowdown": np.array([0, 0, 0, -0.20, 0, 0, 0], dtype=np.float32),
    "arrowleft": np.array([0, 0, 0, 0, +0.20, 0, 0], dtype=np.float32),
    "arrowright": np.array([0, 0, 0, 0, -0.20, 0, 0], dtype=np.float32),
    "z": np.array([0, 0, 0, 0, 0, +0.20, 0], dtype=np.float32),
    "x": np.array([0, 0, 0, 0, 0, -0.20, 0], dtype=np.float32),
}


class TeleopSession:
    def __init__(
        self,
        *,
        adapter: Any,
        writer: DemoWriter,
        observation_provider: Callable[[], tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
        on_save: Callable[[str], DemoWriter | None] | None = None,
        ui_context: Mapping[str, Any] | None = None,
        guidance_provider: Callable[["TeleopSession"], Mapping[str, Any]] | None = None,
        queue_position_provider: Callable[[], tuple[int, int]] | None = None,
        reset_current: Callable[[], DemoWriter] | None = None,
        task_success_provider: Callable[[], bool] | None = None,
        preview_provider: Callable[[], tuple[np.ndarray, np.ndarray]] | None = None,
        max_steps: int | None = None,
    ) -> None:
        self.adapter = adapter
        self.writer = writer
        self.observation_provider = observation_provider
        self.on_save = on_save
        self.ui_context = dict(ui_context or {})
        self.guidance_provider = guidance_provider
        self.queue_position_provider = queue_position_provider
        self.reset_current = reset_current
        self.task_success_provider = task_success_provider
        self.preview_provider = preview_provider
        self.max_steps = int(max_steps) if max_steps is not None else None
        self.gripper = -1.0
        self.state_history: list[Mapping[str, np.ndarray]] = []
        self.initial_state: Mapping[str, np.ndarray] | None = None
        self.saved = False
        self.pending_saved_path: Path | None = None
        self.last_error: str | None = None
        self.terminal_state: str | None = None
        self._last_image: np.ndarray | None = None
        self._last_image2: np.ndarray | None = None
        self._last_guidance: dict[str, Any] | None = None
        self.last_action_scale = 1.0

    def initialize(self) -> None:
        self.saved = False
        self.pending_saved_path = None
        self.last_error = None
        self.terminal_state = None
        self._last_guidance = None
        self.last_action_scale = 1.0
        state = self.adapter.capture_simulator_state()
        self.initial_state = {key: np.asarray(value).copy() for key, value in state.items()}
        self.state_history = [self.initial_state]
        frame, ee = self._frame(state)
        self.writer.start(frame, ee_position=ee)

    def handle(self, key: str) -> dict[str, Any]:
        driver = getattr(self, "collection_driver", None)
        if driver is not None and not driver.needs_human:
            return self.status("automatic_control_active")
        key = key.lower()
        if key == "hq":
            return self.status("high_quality_preview", high_quality=True)
        action_scale = 1.0
        coarse = key.startswith("coarse:")
        if key.startswith("scale:"):
            parts = key.split(":", 2)
            if len(parts) != 3:
                return self.status("ignored")
            try:
                action_scale = float(parts[1])
            except ValueError:
                return self.status("ignored")
            if action_scale not in {1.0, 2.0, 4.0}:
                return self.status("ignored")
            key = parts[2]
        elif coarse:
            action_scale = 3.0
            key = key.split(":", 1)[1]
        if self.saved:
            return self.status("queue_complete")
        if key == "u":
            if self.terminal_state is not None:
                return self.status("terminal_episode_reset_required")
            if len(self.state_history) <= 1:
                return self.status("nothing_to_undo")
            self.state_history.pop()
            self.adapter.restore_simulator_state(self.state_history[-1])
            self.writer.undo()
            self._refresh_observation_cache()
            return self.status("undone")
        if key == "r":
            if driver is not None:
                driver.before_human_reset()
            if self.reset_current is not None:
                self.writer = self.reset_current()
                self.gripper = -1.0
                self.initialize()
                if driver is not None:
                    driver.after_human_reset()
                return self.status("reset")
            if self.initial_state is None:
                raise RuntimeError("teleop session is not initialized")
            self.adapter.restore_simulator_state(self.initial_state)
            self.state_history = [self.initial_state]
            frame, ee = self._frame(self.initial_state)
            self.writer.reset(frame, ee_position=ee)
            self.terminal_state = None
            return self.status("reset")
        if key == "success":
            if self.terminal_state == "invalid":
                return self.status("invalid_episode_reset_required")
            if not self._task_success():
                return self.status("simulator_has_not_confirmed_success")
            self.writer.set_explicit_success(True)
            self.terminal_state = "success"
            self.last_error = None
            return self.status("success_marked")
        if key == "n":
            if self.terminal_state == "invalid":
                return self.status("invalid_episode_reset_required")
            if len(self.writer.actions) < 50:
                return self.status("need_at_least_50_steps")
            if self._gripper_toggle_count() > 4:
                return self.status("too_many_gripper_toggles_reset_required")
            if not self._task_success():
                return self.status("simulator_has_not_confirmed_success")
            if not bool(getattr(self.writer, "explicit_success", False)):
                return self.status("mark_success_before_save")
            if self.pending_saved_path is None:
                self.pending_saved_path = self.writer.save()
            path = self.pending_saved_path
            next_writer = None
            try:
                if self.on_save is not None:
                    next_writer = self.on_save(str(path))
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                return self.status("save_validation_failed")
            if isinstance(next_writer, DemoWriter):
                self.writer = next_writer
                self.gripper = -1.0
                self.initialize()
                if driver is not None:
                    driver.human_demo_saved()
                return self.status("saved_next")
            self.saved = True
            self.pending_saved_path = None
            self.last_error = None
            if driver is not None:
                driver.human_demo_saved()
            return self.status("saved_queue_complete")
        if self.terminal_state == "invalid":
            return self.status("invalid_episode_reset_required")
        if self.terminal_state == "success":
            return self.status("task_success_stop_and_mark")
        if key == " ":
            next_gripper = -self.gripper
            toggles = self._gripper_toggle_count()
            if self.writer.actions and bool(
                np.signbit(self.writer.actions[-1][6])
                != np.signbit(next_gripper)
            ):
                toggles += 1
            if toggles > 4:
                return self.status("gripper_toggle_limit_reached")
            self.gripper = next_gripper
            action = np.zeros(7, dtype=np.float32)
        elif key in KEY_ACTIONS:
            action = KEY_ACTIONS[key].copy()
            action[:6] = np.clip(action_scale * action[:6], -1.0, 1.0)
        else:
            return self.status("ignored")
        action[6] = self.gripper
        self.last_action_scale = action_scale
        message = self.execute_action(action)
        return self.status(message if message != "stepped" or action_scale == 1.0
                           else f"stepped_scale_{int(action_scale)}")

    def execute_action(self, action: np.ndarray) -> str:
        """Record a real continuous-controller action without a browser key/JPEG.

        Caller must run on the simulator's owning thread. The same T+1/T
        recorder is shared by automatic collection and manual fallback.
        """
        if self.saved or self.terminal_state is not None:
            raise ValueError("cannot move a completed or terminated episode")
        action = np.asarray(action, dtype=np.float32)
        if action.shape != (7,) or not np.isfinite(action).all() or np.max(np.abs(action)) > 1.0:
            raise ValueError("controller action must be finite normalized [7]")
        self.gripper = float(action[6])
        try:
            step = getattr(self.adapter, "step_teleop", None)
            if not callable(step):
                step = self.adapter.step
            _, reward, terminated, truncated, info = step(
                torch.from_numpy(action).to(self.adapter.device)
            )
        except ValueError as exc:
            if "terminated episode" not in str(exc).lower():
                raise
            if self._task_success():
                self.terminal_state = "success"
                return "task_success_stop_and_mark"
            self.terminal_state = "invalid"
            return "episode_timeout_reset_required"
        state = self.adapter.capture_simulator_state()
        self.state_history.append({key: np.asarray(value).copy() for key, value in state.items()})
        frame, ee = self._frame(state)
        simulator_success = bool(info.get("success", False)) or self._task_success()
        self.writer.append(
            action,
            frame,
            reward=float(reward),
            done=bool(terminated or truncated),
            success=simulator_success,
            ee_position=ee,
        )
        if terminated or truncated:
            if simulator_success:
                self.terminal_state = "success"
                return "task_success_stop_and_mark"
            self.terminal_state = "invalid"
            return "episode_timeout_reset_required"
        return "stepped"

    def _task_success(self) -> bool:
        if self.task_success_provider is not None:
            return bool(self.task_success_provider())
        return bool(self.writer.successes and self.writer.successes[-1])

    def _gripper_toggle_count(self) -> int:
        if len(self.writer.actions) < 2:
            return 0
        commands = np.asarray(
            [np.asarray(action).reshape(-1)[6] for action in self.writer.actions],
            dtype=np.float32,
        )
        return int(np.sum(np.signbit(commands[:-1]) != np.signbit(commands[1:])))

    def status(self, message: str, *, high_quality: bool = False) -> dict[str, Any]:
        if self._last_image is None or self._last_image2 is None:
            self._refresh_observation_cache()
        queue_index, queue_total = (1, 1)
        if self.queue_position_provider is not None:
            queue_index, queue_total = self.queue_position_provider()
        guidance: dict[str, Any] = {}
        if self.guidance_provider is not None:
            try:
                guidance = dict(self.guidance_provider(self))
                previous = (self._last_guidance or {}).get("checklist_complete", [])
                current = guidance.get("checklist_complete", [])
                if len(previous) == len(current):
                    added = [str(i + 1) for i, value in enumerate(current)
                             if value is True and previous[i] is not True]
                    lost = [str(i + 1) for i, value in enumerate(current)
                            if value is False and previous[i] is True]
                    if lost:
                        guidance["transition_message"] = f"第 {'、'.join(lost)} 步条件已失效，请重新检查。"
                    elif added:
                        guidance["transition_message"] = f"第 {'、'.join(added)} 步已完成。"
                self._last_guidance = dict(guidance)
            except Exception as exc:
                if self._last_guidance is not None:
                    guidance = dict(self._last_guidance)
                    guidance["stage_title"] = (
                        "阶段信号短暂异常，继续显示上一次可靠提示"
                    )
                    guidance["stale"] = True
                    guidance["checklist_complete"] = [None] * len(guidance.get("checklist", []))
                    guidance.pop("transition_message", None)
                else:
                    guidance = {
                        "stage_index": 0,
                        "stage_title": "当前任务状态暂不可读",
                        "next_action": "请暂缓操作，刷新页面重试；不会把未知状态标记为完成。",
                        "checklist": list(self.ui_context.get("must_demonstrate_zh", [])),
                        "checklist_complete": [None] * len(self.ui_context.get("must_demonstrate_zh", [])),
                        "stale": True,
                    }
                guidance["diagnostic"] = f"{type(exc).__name__}: {exc}"
                guidance["task_success"] = None
                self._last_guidance = dict(guidance)
        coverage_cell = str(self.writer.metadata["coverage_cell"])
        return {
            "message": message,
            "steps": len(self.writer.actions),
            "gripper": self.gripper,
            "gripper_toggles": self._gripper_toggle_count(),
            "gripper_toggle_limit": 4,
            "init_state_id": self.writer.metadata["init_state_id"],
            "coverage_cell": coverage_cell,
            "coverage_hint": self.ui_context.get("coverage_hints_zh", {}).get(coverage_cell)
                             or coverage_hint_zh(coverage_cell),
            "queue_index": int(queue_index),
            "queue_total": int(queue_total),
            "max_steps": self.max_steps,
            "remaining_steps": (
                max(0, self.max_steps - len(self.writer.actions))
                if self.max_steps is not None
                else None
            ),
            "terminal_state": self.terminal_state,
            "error_detail": self.last_error,
            "pending_saved_path": (
                str(self.pending_saved_path)
                if self.pending_saved_path is not None
                else None
            ),
            "action_scale": self.last_action_scale,
            "ui": self.ui_context,
            "guidance": guidance,
            "preview_quality": "high" if high_quality else "interactive",
            "image": _jpeg_data_url(
                self._last_image, quality=94 if high_quality else 80
            ),
            "image2": _jpeg_data_url(
                self._last_image2, quality=94 if high_quality else 80
            ),
        }

    def service_status(self) -> dict[str, Any]:
        """Return a cheap health payload without rendering either camera.

        The slow-loop supervisor polls this endpoint while the operator is not
        interacting with the page.  Keeping it independent from ``status``
        avoids extra MuJoCo renders and prevents health checks from adding
        latency to step-per-key teleoperation.
        """

        queue_index, queue_total = (1, 1)
        if self.queue_position_provider is not None:
            queue_index, queue_total = self.queue_position_provider()
        return {
            "schema_version": "vls-teleop-session-health-v1",
            "ticket_id": str(self.writer.metadata.get("ticket_id", "")),
            "queue_index": min(int(queue_index), int(queue_total)),
            "queue_total": int(queue_total),
            "queue_complete": bool(self.saved),
            "steps": len(self.writer.actions),
            "terminal_state": self.terminal_state,
            "last_error": self.last_error,
            "guidance": self._last_guidance,
            "operator_language": "zh-CN" if self.ui_context.get("must_avoid_zh") else None,
        }

    def _refresh_observation_cache(
        self,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        image, image2, robot_state, ee_position = self.observation_provider()
        preview, preview2 = (image, image2)
        if self.preview_provider is not None:
            preview, preview2 = self.preview_provider()
        self._last_image = np.ascontiguousarray(np.asarray(preview, dtype=np.uint8))
        self._last_image2 = np.ascontiguousarray(np.asarray(preview2, dtype=np.uint8))
        return (
            np.ascontiguousarray(np.asarray(image, dtype=np.uint8)),
            np.ascontiguousarray(np.asarray(image2, dtype=np.uint8)),
            robot_state,
            ee_position,
        )

    def _frame(
        self, simulator_state: Mapping[str, np.ndarray]
    ) -> tuple[DemoFrame, np.ndarray]:
        image, image2, robot_state, ee_position = self._refresh_observation_cache()
        if "flattened_sim_state" in simulator_state:
            flat = np.asarray(simulator_state["flattened_sim_state"]).reshape(-1)
        else:
            parts = [
                np.asarray(simulator_state[key]).reshape(-1)
                for key in ("qpos", "qvel", "act", "time")
                if key in simulator_state
            ]
            if not parts:
                raise ValueError("simulator state has no replayable numeric fields")
            flat = np.concatenate(parts)
        return (
            DemoFrame(
                image=np.asarray(image, dtype=np.uint8),
                image2=np.asarray(image2, dtype=np.uint8),
                state=np.asarray(robot_state, dtype=np.float32),
                simulator_state=flat,
            ),
            np.asarray(ee_position, dtype=np.float32),
        )


def coverage_hint_zh(coverage_cell: str) -> str:
    """Turn the code-owned ticket cell into an operator-facing instruction."""

    value = str(coverage_cell).split("=", 1)[-1].strip().lower().replace("_", " ")
    translations = {
        "from the top-left": "本条从目标物体的左上方接近并完成抓取。",
        "from the top-right": "本条从目标物体的右上方接近并完成抓取。",
        "from the front": "本条从目标物体的正前方接近并完成抓取。",
        "from the back": "本条从目标物体的后方接近并完成抓取。",
        "from directly above": "本条从目标物体的正上方垂直接近并完成抓取。",
    }
    return translations.get(value, "请遵循下方本条示范要求。")


def create_teleop_app(
    session: TeleopSession,
    *,
    service_metadata: Mapping[str, Any] | None = None,
):
    try:
        from fastapi import FastAPI, WebSocket, WebSocketDisconnect
        from fastapi.responses import HTMLResponse
    except ImportError as exc:
        raise RuntimeError("install fastapi and uvicorn from requirements.txt") from exc

    app = FastAPI(title="VLS T2 Teleoperation")
    driver = getattr(session, "collection_driver", None)
    if driver is not None:
        import asyncio

        @app.on_event("startup")
        async def start_collection():
            app.state.collection_task = asyncio.create_task(driver.run())

        @app.on_event("shutdown")
        async def stop_collection():
            app.state.collection_task.cancel()
            try:
                await app.state.collection_task
            except asyncio.CancelledError:
                pass

    @app.get("/")
    async def index():
        if driver is not None and not driver.needs_human:
            return HTMLResponse("<html lang='zh'><p>自动采集中；只有连续失败后才开放人工操作。</p></html>", status_code=409)
        return HTMLResponse(_HTML)

    @app.get("/healthz")
    async def healthz():
        if hasattr(session, "service_status"):
            payload = dict(session.service_status())
        else:
            payload = {
                "schema_version": "vls-teleop-session-health-v1",
                "queue_complete": False,
            }
        return {
            **payload,
            **(driver.status() if driver is not None else {}),
            **dict(service_metadata or {}),
            "service": "vls-teleop",
            "ready": True,
        }

    def ticket_media():
        refs = {}
        def visit(value):
            if isinstance(value, Mapping):
                if value.get("path") and value.get("sha256"):
                    refs[str(value["sha256"])] = value
                for child in value.values():
                    visit(child)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    visit(child)
        ui = getattr(session, "ui_context", {})
        visit(ui.get("multimodal_evidence", {}))
        visit(ui.get("suggested_path"))
        return refs

    @app.get("/ticket/evidence")
    async def ticket_evidence():
        ui = getattr(session, "ui_context", {})
        return {"guidance": ui.get("visual_guidance", {}),
                "media": [{"url": f"/ticket/media/{digest}", "kind": ref.get("kind"),
                           "name": Path(ref["path"]).name}
                          for digest, ref in ticket_media().items()],
                "legend_zh": ui.get("multimodal_evidence", {}).get("legend_zh", "")}

    @app.get("/ticket/media/{digest}")
    async def ticket_media_file(digest: str):
        from fastapi import HTTPException
        from fastapi.responses import FileResponse
        from .io_utils import sha256_file
        ref = ticket_media().get(digest)
        if ref is None or not Path(ref["path"]).is_file() or sha256_file(Path(ref["path"])) != digest:
            raise HTTPException(status_code=404, detail="ticket evidence unavailable")
        return FileResponse(ref["path"])

    @app.websocket("/ws")
    async def websocket(websocket: WebSocket):
        if driver is not None and not driver.needs_human:
            await websocket.close(code=1008, reason="automatic collector owns the simulator")
            return
        await websocket.accept()
        if isinstance(session, TeleopSession):
            connected = session.status("connected", high_quality=True)
        else:
            connected = session.status("connected")
        await websocket.send_json(connected)
        try:
            while True:
                payload = await websocket.receive_json()
                try:
                    # MuJoCo's EGL context is bound to the thread that created
                    # the environment.  Step and render synchronously on the
                    # uvicorn/event-loop thread; moving this call through
                    # asyncio.to_thread corrupts subsequent camera buffers.
                    result = session.handle(str(payload.get("key", "")))
                except Exception as exc:
                    result = session.status(f"error: {type(exc).__name__}: {exc}")
                await websocket.send_json(result)
        except WebSocketDisconnect:
            pass

    return app


def _jpeg_data_url(image: np.ndarray, *, quality: int = 80) -> str:
    from PIL import Image

    quality = int(quality)
    if not 50 <= quality <= 95:
        raise ValueError("preview JPEG quality must be in [50, 95]")
    buffer = BytesIO()
    Image.fromarray(np.asarray(image, dtype=np.uint8)).save(
        buffer,
        format="JPEG",
        quality=quality,
        subsampling=0 if quality >= 90 else 2,
        optimize=False,
    )
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>VLS Teleop</title>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#111;color:#eee;margin:18px}
.mission,.control-panel{background:#20242a;border:1px solid #56606c;border-radius:10px;padding:14px 18px;margin:0 auto 14px;max-width:1160px}
.mission h2{margin:0 0 8px}.queue{color:#9ee;font-weight:700}.target{font-size:20px;margin:7px 0}.coverage{color:#ffd479;font-size:18px}
.stage{margin-top:10px;color:#7ee787;font-size:21px;font-weight:700}.next{background:#12251a;border-left:5px solid #3fb950;padding:10px 12px;margin:8px 0;font-size:18px;line-height:1.5}.progress{color:#b7c7d6}
.lists{display:grid;grid-template-columns:1fr 1fr;gap:20px}.lists li{margin:7px 0;line-height:1.5}.done{color:#7ee787}.current{color:#ffd479;font-weight:700}.unknown{color:#ffab70}.notice{color:#7ee787;font-size:19px;min-height:26px}.note{color:#b7c7d6;font-size:14px;margin:8px 0}
.frames{display:flex;gap:18px;justify-content:center;max-width:1160px;margin:auto}.camera{flex:1;max-width:560px;text-align:center}.camera img{width:100%;border:1px solid #555;transform:rotate(180deg)}
button{font-size:16px;margin:4px;padding:9px 12px;border-radius:7px;border:1px solid #77818d;cursor:pointer}.speed button.active{background:#238636;color:white;border-color:#3fb950}
.drive{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:10px}.pad{display:grid;grid-template-columns:repeat(3,minmax(95px,1fr));gap:5px}.pad button{min-height:48px;touch-action:none}.pad-title{grid-column:1/-1;color:#9ee;font-weight:700}
.actions{margin-top:10px}.status,.help,.warning{max-width:1160px;margin-left:auto;margin-right:auto}.status{padding:10px 4px;font-size:17px;color:#9ee}.status.invalid{color:#ff7b72;font-weight:800;background:#341a1a;border:1px solid #ff7b72;border-radius:8px}.status.success{color:#7ee787;font-weight:800}.help{line-height:1.6}.warning{color:#ffd479}
@media(max-width:900px){.frames{display:block}.camera{margin:auto}.lists,.drive{grid-template-columns:1fr}}
</style></head><body>
<div class="mission"><h2>LIBERO-PRO 人工示范</h2><div class="queue" id="queue">正在连接…</div><div class="target" id="task"></div><div class="coverage" id="coverage"></div><div class="stage" id="stage"></div><div class="notice" id="notice" role="status" aria-live="polite"></div><div class="next" id="next"></div><div class="progress" id="progress"></div><div class="note" id="guidance-note"></div><div class="lists"><div><b>完整任务步骤（自动更新）</b><ol id="checklist"></ol><b>本条示范要求（操作时遵守）</b><ul id="demo-requirements"></ul></div><div><b>必须避免</b><ul id="avoid"></ul></div></div></div>
<div class="frames"><div class="camera"><div>外部相机（看全局）</div><img id="cam1"></div><div class="camera"><div>腕部相机（对准抓取）</div><img id="cam2"><small>画面边缘的灰/黑块通常是夹爪或机械臂自遮挡，不是缺帧。</small></div></div>
<div class="mission"><h2>扩张依据与建议</h2><div id="ticket-evidence"></div></div>\n<div class="status" id="status"></div>
<div class="control-panel"><div class="speed"><b>移动速度：</b><button data-speed="1">精细 1×</button><button data-speed="2" class="active">标准 2×</button><button data-speed="4">快速 4×</button><span>　可按住键盘连续移动，松手即停；Shift 临时使用快速 4×。</span></div>
<div class="drive"><div class="pad"><div class="pad-title">平移（按住按钮或键盘）</div><span></span><button data-hold="w">W　向前</button><button data-hold="q">Q　上升</button><button data-hold="a">A　向左</button><button data-hold="s">S　向后</button><button data-hold="d">D　向右</button><span></span><button data-hold="e">E　下降</button><span></span></div>
<div class="pad"><div class="pad-title">旋转（接近目标后使用精细档）</div><span></span><button data-hold="arrowup">↑　前倾</button><button data-hold="z">Z　左旋</button><button data-hold="arrowleft">←　左倾</button><button data-hold="arrowdown">↓　后倾</button><button data-hold="arrowright">→　右倾</button><span></span><button data-hold="x">X　右旋</button><span></span></div></div>
<div class="actions"><button data-k=" ">切换夹爪（空格）</button><button data-k="u">撤销一步 U</button><button data-k="r">本条重置 R</button><button data-k="success">标记成功</button><button data-k="n">保存 / 下一条 N</button><button data-k="hq">刷新高清画面</button><button id="rotate">切换画面方向</button></div></div>
<div class="help"><b>推荐操作：</b>远距离移动用“快速 4×”，靠近目标物体、把手或容器边缘后切换“精细 1×”。按住方向键会在收到上一帧后继续走，不会积压失控；松开立即停止后续动作。<br><b>坐标：</b>W/S 前后，A/D 左右，Q/E 上下；方向键与 Z/X 控制姿态。grip=-1 为张开，grip=1 为闭合。</div>
<p class="warning">只有页面显示“LIBERO-PRO 已判定成功”后才能标记并保存。每条至少 50 步，夹爪切换最多 4 次；第 5 次会被页面直接阻止，请重置本条后重做。画面旋转只影响浏览器显示，保存数据仍保持冻结的 LIBERO-PRO / LeRobot 图像语义。</p>
<script>
const byId=id=>document.getElementById(id),status=byId('status'),cam1=byId('cam1'),cam2=byId('cam2'),rotate=byId('rotate');
const ws=new WebSocket(`ws://${location.host}/ws`),moveKeys=new Set(['w','s','a','d','q','e','arrowup','arrowdown','arrowleft','arrowright','z','x']);
let busy=false,sentAt=0,heldKey=null,heldScale=2,selectedScale=2,pendingHq=false;
const renderList=(id,items,completed=[],active=-1)=>{const root=byId(id);root.replaceChildren();(items||[]).forEach((value,index)=>{const li=document.createElement('li'),tracked=id==='checklist';li.textContent=(tracked?(completed[index]===true?'✓ 已完成 · ':completed[index]==null?'？状态未知 · ':index===active?'▶ 当前步骤 · ':'○ 待完成 · '):'')+value;li.className=tracked?(completed[index]===true?'done':completed[index]==null?'unknown':index===active?'current':''):'';root.appendChild(li)})};
const sendRaw=key=>{if(ws.readyState!==WebSocket.OPEN||busy)return false;busy=true;sentAt=performance.now();status.textContent=key==='n'?'正在原子保存…通常只需数秒；耗时的物理回放将在采集后批量进行。':'正在执行并刷新画面…（松开按键即可停止连续移动）';ws.send(JSON.stringify({key}));return true};
const sendMove=()=>{if(heldKey)sendRaw(`scale:${heldScale}:${heldKey}`)};
const startHold=(key,scale)=>{heldKey=key;heldScale=scale;sendMove()};
const stopHold=key=>{if(!key||heldKey===key){if(heldKey)pendingHq=true;heldKey=null;if(pendingHq&&!busy){pendingHq=false;setTimeout(()=>sendRaw('hq'),0)}}};
const terminalMessages=new Set(['episode_timeout_reset_required','invalid_episode_reset_required','task_success_stop_and_mark','success_marked','saved_next','saved_queue_complete']);
ws.onmessage=e=>{const latency=sentAt?` · ${Math.round(performance.now()-sentAt)} ms`:'';busy=false;sentAt=0;const x=JSON.parse(e.data),ui=x.ui||{},g=x.guidance||{},left=x.remaining_steps==null?'':` · 剩余 ${x.remaining_steps}/${x.max_steps} 步`;cam1.src=x.image;cam2.src=x.image2;byId('queue').textContent=`第 ${x.queue_index}/${x.queue_total} 条示范 · init=${x.init_state_id} · ${x.steps} 步${left}`;byId('task').textContent=`总目标：${ui.task_instruction_zh||ui.task_instruction||x.ui?.task_id||''}`;byId('coverage').textContent=`本条变化要求：${x.coverage_hint}`;byId('stage').textContent=g.stage_title||'读取当前阶段…';byId('next').textContent=g.next_action||'请按完整任务步骤操作。';byId('progress').textContent=`${g.progress||''} · 夹爪切换 ${x.gripper_toggles||0}/${x.gripper_toggle_limit||4}`;renderList('checklist',g.checklist||ui.must_demonstrate_zh,g.checklist_complete,g.stage_index);renderList('avoid',ui.must_avoid_zh);renderList('demo-requirements',ui.must_demonstrate_zh);byId('guidance-note').textContent=ui.guidance_note_zh||'';if(['reset','saved_next','connected'].includes(x.message))byId('notice').textContent='';if(g.transition_message)byId('notice').textContent=g.transition_message;if(g.stale)byId('notice').textContent='状态暂不可读，完成标记已置为未知。';const messages={episode_timeout_reset_required:'本条已超时作废，不能保存。请点击“本条重置”。',invalid_episode_reset_required:'本条已作废，不能继续或保存。请点击“本条重置”。',terminal_episode_reset_required:'episode 已结束；如需重做，请点击“本条重置”。',simulator_has_not_confirmed_success:'LIBERO-PRO 尚未判定任务成功，当前不能标记或保存。',gripper_toggle_limit_reached:'夹爪已切换 4 次，第 5 次未执行；本条无法再满足整理规则，请重置后重做。',too_many_gripper_toggles_reset_required:'夹爪切换超过 4 次，本条不能保存，请重置后重做。',task_success_stop_and_mark:'LIBERO-PRO 已判定成功，请停止移动，点击“标记成功”，再保存。',success_marked:'成功已确认，现在可以保存 / 下一条。',save_validation_failed:'文件已经保留，但自动回放校验失败；不需要重做，请暂停操作并查看下方原因。',saved_next:'保存完成，已进入下一条；物理回放将在采集后批量校验。',saved_queue_complete:'全部示范已保存；物理回放将在采集后批量校验。',high_quality_preview:'高清静止画面已刷新。',reset:'本条已完整重置，可以重新采集。',stepped_scale_2:'标准 2× 移动完成。',stepped_scale_4:'快速 4× 移动完成；接近目标后请切换精细档。'};const detail=x.error_detail?` · 原因：${x.error_detail}`:'';status.textContent=`${messages[x.message]||`状态=${x.message}`}${detail} · 速度=${x.action_scale||selectedScale}× · grip=${x.gripper===-1?'张开 (-1)':'闭合 (1)'} · 夹爪切换=${x.gripper_toggles||0}/${x.gripper_toggle_limit||4}${latency}`;status.className=`status ${x.terminal_state==='invalid'||x.message==='save_validation_failed'||x.message==='gripper_toggle_limit_reached'?'invalid':x.terminal_state==='success'?'success':''}`;if(terminalMessages.has(x.message)||x.terminal_state)stopHold();if(heldKey&&!x.terminal_state)setTimeout(sendMove,25);else if(pendingHq&&!x.terminal_state&&x.message!=='high_quality_preview'){pendingHq=false;setTimeout(()=>sendRaw('hq'),0)}};
fetch('/ticket/evidence').then(r=>r.json()).then(data=>{const root=byId('ticket-evidence');const p=document.createElement('p');p.textContent=[data.guidance.failure_description_zh,data.guidance.desired_capability_zh,data.legend_zh].filter(Boolean).join('；');root.appendChild(p);for(const m of data.media||[]){let el;if(['real_observation','observed_overlay','suggested_path_overlay'].includes(m.kind)){el=document.createElement('img');el.src=m.url;el.style.maxWidth='360px';el.alt=m.kind==='suggested_path_overlay'?'Planner 建议路径（未执行）':'真实观测／实测轨迹';}else if(m.kind==='executed_video'){el=document.createElement('video');el.src=m.url;el.controls=true;el.preload='metadata';el.style.maxWidth='480px';}else if(m.kind==='complete_episode_video'){el=document.createElement('a');el.href=m.url;el.textContent='完整原视频索引';el.target='_blank';}if(el)root.appendChild(el);}}).catch(()=>{byId('ticket-evidence').textContent='当前 ticket 暂无历史图像证据。'});
ws.onerror=()=>{busy=false;stopHold();status.textContent='WebSocket 连接失败，请刷新'};ws.onclose=e=>{busy=false;stopHold();if(e.code!==1000)status.textContent=`WebSocket 已断开 (${e.code})，请刷新重连`};
document.querySelectorAll('[data-speed]').forEach(button=>button.onclick=()=>{selectedScale=Number(button.dataset.speed);document.querySelectorAll('[data-speed]').forEach(item=>item.classList.toggle('active',item===button))});
document.querySelectorAll('[data-hold]').forEach(button=>{button.onpointerdown=e=>{e.preventDefault();button.setPointerCapture(e.pointerId);startHold(button.dataset.hold,selectedScale)};button.onpointerup=button.onpointercancel=()=>stopHold(button.dataset.hold)});
document.querySelectorAll('[data-k]').forEach(button=>button.onclick=()=>{stopHold();sendRaw(button.dataset.k)});
document.onkeydown=e=>{const key=e.key.toLowerCase();if(moveKeys.has(key)){e.preventDefault();if(!e.repeat)startHold(key,e.shiftKey?4:selectedScale)}else if(key===' '||key==='u'||key==='r'||key==='n'){e.preventDefault();if(!e.repeat){stopHold();sendRaw(key)}}};
document.onkeyup=e=>stopHold(e.key.toLowerCase());window.onblur=()=>stopHold();document.onvisibilitychange=()=>{if(document.hidden)stopHold()};
rotate.onclick=()=>document.querySelectorAll('.camera img').forEach(img=>img.style.transform=img.style.transform==='none'?'rotate(180deg)':'none');
</script></body></html>"""


__all__ = [
    "TeleopSession",
    "coverage_hint_zh",
    "create_teleop_app",
]
