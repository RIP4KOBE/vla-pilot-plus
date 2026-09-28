"""Opt-in Stage transport through the Codex CLI's existing managed login.

The Stage prompt, PNG pixels, parser and conservative fallback live in the
legacy recognizer. This module changes only the transport and its accounting.
No account token or credential file is opened by this adapter.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import psutil

from core.gemini_grounder import GeminiStageRecognizer
from core.codex_stage_lifecycle import LifecycleTelemetry, StageLifecycle


from core.codex_stage_policy import (
    _COUNTER_FIELDS, _MAX_EVENTS_BYTES, _REMOVED_ENVIRONMENT,
    discover_disabled_skill_paths, policy_sha256, public_invocation_policy,
)


class CodexCallCounter:
    def __init__(self):
        self.values = dict.fromkeys(_COUNTER_FIELDS, 0)
        self.values["call_latency_s"] = 0.0

    def snapshot(self):
        return {
            "backend": "codex_cli", "request_attempts": None,
            "sdk_retry_attempts": None, "observation_available": False,
            **self.values,
        }


class CodexStageError(RuntimeError):
    """Fixed public error codes: never include CLI stderr or environment data."""


def _stop_owned_process(process):
    """Terminate only this child and its descendants, staying in runner's group."""
    try:
        parent = psutil.Process(process.pid)
        owned = parent.children(recursive=True) + [parent]
    except psutil.NoSuchProcess:
        owned = []
    for child in owned:
        try:
            child.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(owned, timeout=2)
    for child in alive:
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


class CodexStageRecognizer(GeminiStageRecognizer):
    def _configure_transport(self, config):
        self.model = str(config.get("model", "gpt-6-astra"))
        self.reasoning_effort = str(config.get("reasoning_effort", "low"))
        self.timeout_seconds = float(config.get("timeout_seconds", 90))
        self.allow_recovered_error_events = config.get("allow_recovered_error_events", False)
        if type(self.allow_recovered_error_events) is not bool:
            raise ValueError("allow_recovered_error_events must be a boolean")
        if not 0 < self.timeout_seconds <= 600:
            raise ValueError("Codex Stage timeout must be in (0, 600] seconds")
        configured_cli = config.get("cli_path") or shutil.which("codex")
        if not configured_cli:
            raise ValueError("Codex CLI is unavailable")
        self.cli_path = str(Path(configured_cli).resolve())
        if not Path(self.cli_path).is_file():
            raise ValueError("Codex CLI path does not exist")
        self.api_request_counter = CodexCallCounter()
        self.public_policy = public_invocation_policy(
            model=self.model, reasoning_effort=self.reasoning_effort,
            timeout_seconds=self.timeout_seconds, cli_path=self.cli_path,
            disabled_skill_paths=(config["disabled_skill_paths"] if config.get("disabled_skill_paths") is not None
                                  else discover_disabled_skill_paths()),
        )
        self.transport_metadata = {
            "backend": "codex_cli", "auth_mode": "chatgpt", "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "timeout_seconds": self.timeout_seconds, "cli_path": self.cli_path,
            "public_config_sha256": policy_sha256(self.public_policy),
            "disabled_skill_paths": self.public_policy["disabled_skill_paths"],
            "application_max_attempts": 1,
            "internal_http_retry_observation_available": False,
            "internal_retry_policy": "cli_managed_unknown",
        }
        if self.allow_recovered_error_events:
            self.transport_metadata["allow_recovered_error_events"] = True
            self.transport_metadata["recovered_error_policy"] = "pre_final_only_v1"
        self._call_transport = {}
        self._call_raw_response = None

    def _command(self, directory, image_paths):
        policy = self.public_policy
        command = [self.cli_path, *policy["fixed_arguments"], "--model", self.model,
                   "--cd", str(directory)]
        for key, value in policy["config_overrides"].items():
            # JSON strings/bools/numbers are valid TOML here. Empty inline table
            # is a TOML table, while all other configured values are scalars.
            if key == "skills.config":
                encoded = "[" + ",".join(
                    "{path=" + json.dumps(item["path"]) + ",enabled=false}"
                    for item in value
                ) + "]"
            else:
                encoded = "{}" if value == {} else json.dumps(value)
            command.extend(["--config", f"{key}={encoded}"])
        command.extend(["--config", f"log_dir={json.dumps(str(directory / 'log'))}"])
        for feature in policy["disabled_features"]:
            command.extend(["--disable", feature])
        for feature in policy["enabled_features"]:
            command.extend(["--enable", feature])
        for path in image_paths:
            command.extend(["--image", str(path)])
        command.append("-")
        return command

    def _parse_events(self, raw_events):
        """Account observed usage even if the response later fails validation."""
        events = []
        stream_error = None
        try:
            for line in raw_events.splitlines():
                if line.strip():
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise ValueError
                    events.append(event)
        except (ValueError, UnicodeDecodeError):
            stream_error = "codex_invalid_event_stream"
        starts = 0
        messages = []
        error_code = stream_error
        event_types = []
        item_types = []
        usages = []
        recoverable_error_indices = []
        recoverable_error_events = 0
        recoverable_error_items = 0
        started_turn_indices = []
        completed_message_indices = []
        completed_turn_indices = []
        for index, event in enumerate(events):
            kind = event.get("type")
            event_types.append(kind if isinstance(kind, str) else "invalid")
            if kind == "turn.started":
                starts += 1
                started_turn_indices.append(index)
            elif kind == "turn.completed":
                completed_turn_indices.append(index)
                self.api_request_counter.values["completed_turns"] += 1
                usage = event.get("usage")
                required = ("input_tokens", "cached_input_tokens", "output_tokens")
                if (not isinstance(usage, dict) or any(
                    type(usage.get(key)) is not int or usage[key] < 0 for key in required
                ) or usage["cached_input_tokens"] > usage["input_tokens"]):
                    error_code = "codex_missing_usage"
                    continue
                normalized = {key: usage[key] for key in required}
                reasoning = usage.get("reasoning_output_tokens")
                normalized["reasoning_output_tokens"] = (
                    reasoning if type(reasoning) is int and reasoning >= 0 else None
                )
                usages.append(normalized)
                for key, value in normalized.items():
                    previous = self.api_request_counter.values[key]
                    self.api_request_counter.values[key] = (
                        None if value is None or previous is None else previous + value
                    )
            elif kind in ("item.started", "item.updated", "item.completed"):
                item = event.get("item")
                item_kind = item.get("type") if isinstance(item, dict) else None
                item_types.append(item_kind if isinstance(item_kind, str) else "invalid")
                if item_kind == "error" and kind == "item.completed" and self.allow_recovered_error_events:
                    recoverable_error_indices.append(index)
                    recoverable_error_items += 1
                elif item_kind not in ("agent_message", "reasoning"):
                    error_code = "codex_unexpected_item"
                if item_kind == "agent_message" and kind == "item.completed":
                    completed_message_indices.append(index)
                    text = item.get("text")
                    if not isinstance(text, str) or not text.strip():
                        error_code = "codex_empty_response"
                    else:
                        messages.append(text.strip())
            elif kind == "error" and self.allow_recovered_error_events:
                recoverable_error_indices.append(index)
                recoverable_error_events += 1
            elif kind not in ("thread.started",):
                error_code = "codex_unexpected_event"
        complete_turns = sum(kind == "turn.completed" for kind in event_types)
        if len(messages) == 1:
            self._call_raw_response = messages[0]
        self._call_transport.update(
            event_types=event_types, item_types=item_types, observed_usage=usages,
            completed_turns=complete_turns,
        )
        if self.allow_recovered_error_events:
            self._call_transport.update(
                recoverable_error_event_count=recoverable_error_events,
                recoverable_error_item_count=recoverable_error_items,
                recovered_error_events_accepted=False,
            )
        if recoverable_error_indices and not (
            len(started_turn_indices) == len(completed_message_indices) == len(completed_turn_indices) == 1
            and started_turn_indices[0] < min(recoverable_error_indices)
            and max(recoverable_error_indices) < completed_message_indices[0] < completed_turn_indices[0]
        ):
            error_code = "codex_recovery_order_violation"
        if starts == complete_turns == len(usages) == 1 and stream_error is None:
            self.api_request_counter.values["usage_complete_calls"] += 1
        if starts != 1 or complete_turns != 1:
            error_code = "codex_expected_one_completed_turn"
        elif len(usages) != 1:
            error_code = "codex_missing_usage"
        elif len(messages) != 1:
            error_code = "codex_expected_one_response"
        if error_code:
            raise CodexStageError(error_code)
        if self.allow_recovered_error_events:
            self._call_transport["recovered_error_events_accepted"] = bool(recoverable_error_indices)
        return messages[0]

    def _request_stage_response(self, content):
        self.api_request_counter.values["logical_call_attempts"] += 1
        self._call_transport = dict(self.transport_metadata)
        self._call_raw_response = None
        lifecycle = LifecycleTelemetry(StageLifecycle, _MAX_EVENTS_BYTES)
        self._call_transport["lifecycle"] = lifecycle.data
        child_env = os.environ.copy()
        for name in _REMOVED_ENVIRONMENT:
            child_env.pop(name, None)
        texts = []
        try:
            with tempfile.TemporaryDirectory(prefix="qd_ed_codex_stage_") as temp:
                directory = Path(temp)
                images = []
                for part in content:
                    if part["type"] == "text":
                        texts.append(part["text"])
                    elif part["type"] == "image_url":
                        prefix = "data:image/png;base64,"
                        uri = part["image_url"]["url"]
                        if not uri.startswith(prefix):
                            raise CodexStageError("codex_expected_png")
                        path = directory / f"image_{len(images) + 1:02d}.png"
                        path.write_bytes(base64.b64decode(uri[len(prefix):], validate=True))
                        images.append(path)
                    else:
                        raise CodexStageError("codex_unexpected_content")
                if not 1 <= len(images) <= 2:
                    raise CodexStageError("codex_expected_one_or_two_images")
                command = self._command(directory, images)
                with (directory / "events.jsonl").open("w+b") as events_file, (
                    directory / "stderr.txt"
                ).open("w+b") as error_file:
                    process = None
                    try:
                        lifecycle.mark("spawn_started_at")
                        process = subprocess.Popen(
                            command, stdin=subprocess.PIPE, stdout=events_file,
                            stderr=error_file, cwd=directory, env=child_env,
                            text=True, start_new_session=False,
                        )
                        lifecycle.mark("spawn_returned_at")
                        lifecycle.start(events_file)
                        try:
                            lifecycle.mark("communicate_started_at")
                            process.communicate(input="\n\n".join(texts), timeout=self.timeout_seconds)
                            lifecycle.mark("communicate_returned_at")
                        except subprocess.TimeoutExpired:
                            lifecycle.mark("timeout_observed_at")
                            lifecycle.mark("cleanup_started_at")
                            _stop_owned_process(process)
                            lifecycle.mark("cleanup_returned_at")
                            events_file.seek(0)
                            partial = events_file.read(_MAX_EVENTS_BYTES + 1)
                            if len(partial) <= _MAX_EVENTS_BYTES:
                                try:
                                    self._parse_events(partial)
                                except CodexStageError:
                                    pass
                            raise CodexStageError("codex_timeout") from None
                        except BaseException:
                            lifecycle.mark("cleanup_started_at")
                            _stop_owned_process(process)
                            lifecycle.mark("cleanup_returned_at")
                            raise
                        events_file.seek(0)
                        raw_events = events_file.read(_MAX_EVENTS_BYTES + 1)
                        if len(raw_events) > _MAX_EVENTS_BYTES:
                            raise CodexStageError("codex_event_stream_too_large")
                        output = self._parse_events(raw_events)
                        if process.returncode != 0:
                            raise CodexStageError("codex_nonzero_exit")
                        return output
                    finally:
                        lifecycle.finish(process)
                        self._call_transport["lifecycle"] = lifecycle.data
        except CodexStageError:
            raise
        except Exception:
            # Library/process exceptions may contain argv or server error text.
            raise CodexStageError("codex_transport_failure") from None

    def _record_transport_result(self, counter_before):
        counter = self.api_request_counter
        counter.values["call_latency_s"] += self._last_result["query_latency_s"]
        if not self._last_result["ok"]:
            counter.values["failed_calls"] += 1
        after = counter.snapshot()
        self._last_result.update(
            api_request_attempts=None, api_sdk_retry_attempts=None,
            api_request_counter_available=False, transport=dict(self._call_transport),
        )
        if self._last_result["raw_response"] is None:
            self._last_result["raw_response"] = self._call_raw_response
        for key in _COUNTER_FIELDS:
            before_value = counter_before[key]
            after_value = after[key]
            self._last_result["codex_" + key] = (
                None if before_value is None or after_value is None else after_value - before_value
            )
        usages = self._call_transport.get("observed_usage", [])
        if len(usages) == 1:
            self._last_result["codex_reasoning_output_tokens"] = usages[0]["reasoning_output_tokens"]
