"""Opt-in observations of existing LIBERO instances; no simulator/GPU imports.

Records host wall time only. The original sim.render retains its render lock;
the interval before offscreen_render is NOT an isolated lock-wait measurement.
"""
import json
import time
from pathlib import Path


class RenderPhaseDiagnostics:
    def __init__(self, path):
        self.path = Path(path)
        self._phase = None
        self._stack = []
        self._sequence = 0
        self._hooks = []
        self._failed = False
        self._observer_elapsed_s = 0.0
        self._io_elapsed_s = 0.0
        self._record_count = 0
        self._phase_baseline = (0.0, 0.0, 0)

    def set_phase(self, episode, global_step, name, event):
        if event == "enter":
            self._phase = (int(episode), int(global_step), name)
            self._phase_baseline = (self._observer_elapsed_s, self._io_elapsed_s, self._record_count)
            return 0.0
        self._phase = None
        overhead, io, count = self._phase_baseline
        estimated_overhead = self._observer_elapsed_s - overhead
        if self._record_count > count:
            self._write({"schema": "qd-ed-render-overhead-v1", "episode": int(episode),
                "global_step": int(global_step), "parent_phase": name,
                "record_count": self._record_count - count,
                "estimated_observer_s": estimated_overhead, "append_io_s": self._io_elapsed_s - io},
                self.path.with_name("render_phase_overhead.jsonl"))
        return estimated_overhead

    def _write(self, record, path=None):
        if self._failed:
            return
        started = time.perf_counter()
        try:
            destination = path or self.path
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("a") as stream:
                stream.write(json.dumps(record, allow_nan=False) + "\n")
            if path is None:
                self._record_count += 1
        except Exception:
            # Diagnostic failures never expose input/exception text or stop control.
            self._failed = True
        finally:
            self._io_elapsed_s += time.perf_counter() - started

    @staticmethod
    def _render_fields(args, kwargs):
        # Only the public sim.render scalar signature; never repr/serialize args.
        def dimension(value):
            return value if type(value) is int and 0 < value <= 65536 else None
        camera = kwargs.get("camera_name")
        return {
            "camera": camera if camera in (None, "agentview", "robot0_eye_in_hand") else "other",
            "width": dimension(kwargs.get("width", args[0] if args else None)),
            "height": dimension(kwargs.get("height", args[1] if len(args) > 1 else None)),
            "depth": kwargs.get("depth") if type(kwargs.get("depth")) is bool else False,
            "segmentation": kwargs.get("segmentation") if type(kwargs.get("segmentation")) is bool else False,
        }

    def _hook(self, obj, attribute, name, before=None):
        if any(item[0] is obj and item[1] == attribute for item in self._hooks):
            return
        original = getattr(obj, attribute)
        if not callable(original):
            raise TypeError("Diagnostic hook requires an existing callable")
        own = vars(obj)
        had_own = attribute in own
        own_value = own.get(attribute)

        def observed(*args, **kwargs):
            if self._failed or self._phase is None:
                return original(*args, **kwargs)
            observer_started = time.perf_counter()
            try:
                if before is not None:
                    before()
                episode, global_step, parent_phase = self._phase
                self._sequence += 1
                call_id = self._sequence
                parent_call_id = self._stack[-1][0] if self._stack else None
                fields = self._render_fields(args, kwargs) if name == "sim_render_total" else (
                    self._stack[-1][1] if self._stack else {})
                record = {"schema": "qd-ed-render-phase-v1", "episode": episode,
                    "global_step": global_step, "parent_phase": parent_phase,
                    "name": name, "call_id": call_id, "parent_call_id": parent_call_id,
                    **fields}
                self._write({**record, "event": "enter", "elapsed_s": 0.0,
                    "observed_wall_s": 0.0, "nested_observer_s": 0.0})
                self._stack.append((call_id, fields))
                self._observer_elapsed_s += time.perf_counter() - observer_started
                nested_baseline = self._observer_elapsed_s
                started = time.perf_counter()
            except Exception:
                self._failed = True
                return original(*args, **kwargs)
            cleanup_started = None
            try:
                result = original(*args, **kwargs)
            except BaseException:
                # Native abort leaves enter-only too; Python failures remain identical.
                raise
            else:
                wall = time.perf_counter() - started
                cleanup_started = time.perf_counter()
                nested_overhead = self._observer_elapsed_s - nested_baseline
                self._write({**record, "event": "exit", "elapsed_s": max(0.0, wall - nested_overhead),
                    "observed_wall_s": wall, "nested_observer_s": nested_overhead})
                return result
            finally:
                # Only local cleanup on failure: no exit event, no retry/replacement.
                if cleanup_started is None:
                    cleanup_started = time.perf_counter()
                self._stack.pop()
                self._observer_elapsed_s += time.perf_counter() - cleanup_started

        setattr(obj, attribute, observed)
        self._hooks.append((obj, attribute, had_own, own_value, observed))

    def _render_context(self, sim):
        context = sim._render_context_offscreen
        if context is None:
            return
        # Reuse an existing context, including a replacement created by production.
        # This never constructs a context or calls make_current/render itself.
        self._hook(context, "render", "offscreen_render")
        self._hook(context, "read_pixels", "read_pixels")

    def install(self, adapter):
        """Install on the existing, known LIBERO object chain, not proxy wrappers."""
        try:
            env = adapter._env[adapter.current_task_idx]
            domain = env._env.env
            sim = domain.sim
            self._hook(env, "_format_raw_obs", "format_raw_obs")
            self._hook(domain, "_pre_action", "controller_pre_action")
            self._hook(domain, "_update_observables", "update_observables")
            self._hook(sim, "forward", "physics_forward")
            self._hook(sim, "step", "physics_step")
            self._render_context(sim)
            self._hook(sim, "render", "sim_render_total", before=lambda: self._render_context(sim))
        except Exception:
            self.close()
            raise

    def close(self):
        self._phase = None
        for obj, attribute, had_own, own_value, observed in reversed(self._hooks):
            try:
                if vars(obj).get(attribute) is observed:
                    if had_own:
                        setattr(obj, attribute, own_value)
                    else:
                        delattr(obj, attribute)
            except Exception:
                self._failed = True
        self._hooks.clear()
