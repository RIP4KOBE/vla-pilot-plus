"""Passive, bounded observations of the owned CLI's existing stdout file.

Times are local monotonic *observation* times, not remote event times. A second
file descriptor is deliberately unnecessary: pread never moves the parser's
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


class StageLifecycle:
    """Diagnostic only. Its failures never replace the transport's result."""

    def __init__(self, maximum_bytes):
        self.data = {
            "schema": "codex-stage-lifecycle-v1",
            "clock": "monotonic_seconds",
            "timing_semantics": "local_file_observation_not_remote_arrival",
            "poll_interval_s": _POLL_SECONDS,
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

    def mark(self, name):
        # Names are local constants at the transport call sites.
        self.data[name] = time.monotonic()

    def start(self, file):
        try:
            self._fd = file.fileno()
            self._thread = threading.Thread(target=self._observe, daemon=True,
                                            name="codex-stage-lifecycle")
            self._thread.start()
        except Exception:
            self._fail("observer_start_failure")

    def _fail(self, category):
        self.data["observer_error_category"] = category

    def _line(self, line, observed_at):
        if not line.strip():
            return
        if len(self.data["events"]) >= _MAX_OBSERVATIONS:
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
                if self.data["first_completed_observed_at"] is None:
                    self.data["first_completed_observed_at"] = observed_at
                usage = event.get("usage")
                required = ("input_tokens", "cached_input_tokens", "output_tokens")
                valid = (isinstance(usage, dict) and all(
                    type(usage.get(key)) is int and usage[key] >= 0 for key in required
                ) and usage["cached_input_tokens"] <= usage["input_tokens"])
                record["complete_usage_observed"] = valid
                if valid:
                    self.data["complete_usage_observed"] = True
                    if self.data["first_complete_usage_observed_at"] is None:
                        self.data["first_complete_usage_observed_at"] = observed_at
        self.data["events"].append(record)

    def _drain(self, final=False):
        # Read at most the existing acceptance cap plus its one-byte sentinel.
        # No shared seek, buffering mutation, stdout pipe or reader backpressure.
        while self._offset <= self.maximum_bytes:
            data = os.pread(self._fd, min(65536, self.maximum_bytes + 1 - self._offset),
                            self._offset)
            if not data:
                break
            observed_at = time.monotonic()
            if self.data["first_byte_observed_at"] is None:
                self.data["first_byte_observed_at"] = observed_at
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
            self._drain(final=True)
        except Exception:
            self._fail("observer_read_failure")

    def finish(self, process):
        self._stop.set()
        try:
            if self._thread is not None and self._thread.ident is not None:
                self._thread.join()
            if process is not None:
                # Already set by communicate/wait; never poll/reap the child.
                code = process.returncode
                if type(code) is int:
                    self.data["returncode"] = code
                    self.mark("process_exit_observed_at")
        except Exception:
            # Only a fixed local category, never a diagnostic exception string.
            self._fail("observer_finish_failure")
        self.mark("observer_finished_at")
        self.data["observation_complete"] = (
            self._thread is not None and self._thread.ident is not None
            and self.data["observer_error_category"] is None
        )
