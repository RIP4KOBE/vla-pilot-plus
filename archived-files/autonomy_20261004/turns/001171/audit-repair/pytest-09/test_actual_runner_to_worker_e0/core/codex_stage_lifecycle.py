"""Passive, bounded observations of the owned CLI's existing stdout file.

Times are local monotonic *observation* times, not remote event times. A second
descriptor is duplicated and owned by the observer: pread never moves the parser's
file offset. The observer neither waits on nor signals the child, and cannot
accept a response or update usage counters.
"""
from __future__ import annotations

import json
import os
import threading
import time


_EVENT_KINDS = frozenset({
    "thread.started", "turn.started", "turn.completed", "turn.failed",
    "item.started", "item.updated", "item.completed", "error",
})
_ITEM_KINDS = frozenset({"agent_message", "reasoning", "error"})
_POLL_SECONDS = 0.01
_MAX_OBSERVATIONS = 4096
_FINISH_TIMEOUT_SECONDS = 0.05
_OBSERVER_SLOT = threading.BoundedSemaphore(1)
_OBSERVER_DISABLED = threading.Event()


class StageLifecycle:
    """Diagnostic only. Its failures never replace the transport's result."""

    def __init__(self, maximum_bytes):
        self._data = {
            "schema": "codex-stage-lifecycle-v1",
            "clock": "monotonic_seconds",
            "timing_semantics": "local_file_observation_not_remote_arrival",
            "poll_interval_s": _POLL_SECONDS,
            "finish_join_limit_s": _FINISH_TIMEOUT_SECONDS,
            "request_started_at": time.monotonic(),
            "spawn_started_at": None, "spawn_returned_at": None,
            "communicate_started_at": None, "communicate_returned_at": None,
            "first_byte_observed_at": None, "first_completed_observed_at": None,
            "first_complete_usage_observed_at": None,
            "timeout_observed_at": None,
            "cleanup_started_at": None, "cleanup_returned_at": None,
            "process_exit_observed_at": None, "returncode": None,
            "observer_finished_at": None, "observation_complete": False,
            "observer_error_category": None, "events": [],
            "complete_usage_observed": False,
        }
        self.maximum_bytes = maximum_bytes
        self._offset = 0
        self._pending = b""
        self._fd = None
        self._thread = None
        self._stop = threading.Event()

    @property
    def data(self):
        # Return a snapshot, including independent event dicts. A timed-out
        # observer must never mutate the public Stage result after it returns.
        return {**self._data, "events": [dict(e) for e in self._data["events"]]}

    def mark(self, name):
        # Names are local constants at the transport call sites.
        self._data[name] = time.monotonic()

    def start(self, file):
        if _OBSERVER_DISABLED.is_set():
            self._fail("prior_observer_timeout")
            return
        if not _OBSERVER_SLOT.acquire(blocking=False):
            self._fail("observer_busy")
            return
        try:
            self._fd = os.dup(file.fileno())
            self._thread = threading.Thread(target=self._observe, daemon=True,
                                            name="codex-stage-lifecycle")
            self._thread.start()
        except Exception:
            self._fail("observer_start_failure")
            if self._thread is None or self._thread.ident is None:
                if self._fd is not None:
                    os.close(self._fd)
                    self._fd = None
                _OBSERVER_SLOT.release()

    def _fail(self, category):
        self._data["observer_error_category"] = category

    def _line(self, line, observed_at):
        if not line.strip():
            return
        if len(self._data["events"]) >= _MAX_OBSERVATIONS:
            self._fail("observer_event_limit")
            return
        try:
            event = json.loads(line)
        except (ValueError, UnicodeError):
            event = None
        if not isinstance(event, dict):
            record = {"kind": "invalid_json", "observed_at": observed_at}
        else:
            kind = event.get("type")
            record = {"kind": kind if isinstance(kind, str) and kind in _EVENT_KINDS
                      else "other", "observed_at": observed_at}
            if kind in ("item.started", "item.updated", "item.completed"):
                item = event.get("item")
                item_kind = item.get("type") if isinstance(item, dict) else None
                record["item_kind"] = (item_kind if isinstance(item_kind, str)
                                       and item_kind in _ITEM_KINDS else "other")
                if item_kind == "error":
                    record["error_category"] = "item_error"
            elif kind in ("error", "turn.failed"):
                record["error_category"] = "stream_error" if kind == "error" else "turn_failed"
            elif kind == "turn.completed":
                if self._data["first_completed_observed_at"] is None:
                    self._data["first_completed_observed_at"] = observed_at
                usage = event.get("usage")
                required = ("input_tokens", "cached_input_tokens", "output_tokens")
                valid = (isinstance(usage, dict) and all(
                    type(usage.get(key)) is int and usage[key] >= 0 for key in required
                ) and usage["cached_input_tokens"] <= usage["input_tokens"])
                record["complete_usage_observed"] = valid
                if valid:
                    self._data["complete_usage_observed"] = True
                    if self._data["first_complete_usage_observed_at"] is None:
                        self._data["first_complete_usage_observed_at"] = observed_at
        self._data["events"].append(record)

    def _drain(self, final=False):
        # Read at most the existing acceptance cap plus its one-byte sentinel.
        # No shared seek, buffering mutation, stdout pipe or reader backpressure.
        while self._offset <= self.maximum_bytes:
            if getattr(self, "_join_timed_out", False):
                return
            if not final and self._stop.is_set():
                return
            data = os.pread(self._fd, min(65536, self.maximum_bytes + 1 - self._offset),
                            self._offset)
            if getattr(self, "_join_timed_out", False):
                return
            if self._stop.is_set() and not final:
                return
            if not data:
                break
            observed_at = time.monotonic()
            if self._data["first_byte_observed_at"] is None:
                self._data["first_byte_observed_at"] = observed_at
            self._offset += len(data)
            if self._offset > self.maximum_bytes:
                self._fail("observer_byte_limit")
                break
            lines = (self._pending + data).split(b"\n")
            self._pending = lines.pop()
            for line in lines:
                self._line(line, observed_at)
        if final and self._pending:
            self._line(self._pending, time.monotonic())
            self._pending = b""

    def _observe(self):
        try:
            while not self._stop.is_set():
                self._drain()
                self._stop.wait(_POLL_SECONDS)
            # The final drain is requested only on an otherwise responsive
            # observer. Once a bounded join timed out, do not read again.
            if not getattr(self, "_join_timed_out", False):
                self._drain(final=True)
        except Exception:
            self._fail("observer_read_failure")
        finally:
            try:
                os.close(self._fd)
            except Exception:
                self._fail("observer_close_failure")
            finally:
                self._fd = None
                _OBSERVER_SLOT.release()

    def stop_observing(self):
        self._stop.set()
        if self._thread is not None and self._thread.ident is not None:
            self._thread.join(timeout=_FINISH_TIMEOUT_SECONDS)
            if self._thread.is_alive():
                self._join_timed_out = True
                _OBSERVER_DISABLED.set()
                self._fail("observer_join_timeout")

    def finish(self, process):
        try:
            self.stop_observing()
            if process is not None:
                # Already set by communicate/wait; never poll/reap the child.
                code = process.returncode
                if type(code) is int:
                    self._data["returncode"] = code
                    self.mark("process_exit_observed_at")
        except Exception:
            # Only a fixed local category, never a diagnostic exception string.
            self._fail("observer_finish_failure")
        self.mark("observer_finished_at")
        self._data["observation_complete"] = (
            self._thread is not None and self._thread.ident is not None
            and not self._thread.is_alive()
            and self._data["observer_error_category"] is None
        )


class LifecycleTelemetry:
    """No-throw boundary between optional diagnostics and Stage control flow."""

    def __init__(self, factory, maximum_bytes):
        self.observer = None
        self._error = None
        try:
            self.observer = factory(maximum_bytes)
        except Exception:
            self._error = "observer_constructor_failure"

    def _call(self, method, *args):
        if self.observer is not None:
            try:
                getattr(self.observer, method)(*args)
            except Exception:
                self._error = "observer_hook_failure"

    def mark(self, name):
        self._call("mark", name)

    def start(self, file):
        self._call("start", file)

    def finish(self, process):
        self._call("finish", process)
        if self._error is not None:
            # Also stop a worker if an injected/unexpected finish-hook failure
            # happened before its normal cleanup. No child-process operations.
            self._call("stop_observing")

    @property
    def data(self):
        try:
            value = self.observer.data if self.observer is not None else {}
        except Exception:
            value = {}
            self._error = "observer_snapshot_failure"
        if self._error is not None:
            value.update(schema="codex-stage-lifecycle-v1", observation_complete=False,
                         observer_error_category=self._error)
        return value
