"""Opt-in Stage transport through the Codex CLI's existing managed login.

The Stage prompt, PNG pixels, parser and conservative fallback live in the
legacy recognizer. This module changes only the transport and its accounting.
No account token or credential file is opened by this adapter.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import psutil

from core.gemini_grounder import GeminiStageRecognizer


from core.codex_stage_policy import (
    _COUNTER_FIELDS, _MAX_EVENTS_BYTES, _REMOVED_ENVIRONMENT,
    TRANSPORT_FALLBACK_PREFIX, discover_disabled_skill_paths, policy_sha256, public_invocation_policy,
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


_MAX_DIAGNOSTIC_BYTES = 64 * 1024
_DIAGNOSTIC_PATTERNS = {
    "stream_disconnected": r"stream disconnected",
    "connection_reset": r"connection reset|broken pipe",
    "connection_refused": r"connection refused",
    "timeout": r"timed out|timeout",
    "dns_resolution": r"dns error|failed to resolve|name resolution",
    "tls_error": r"tls error|certificate verify failed|invalid peer certificate",
    "rate_limited": r"rate.limit|too many requests",
    "quota_exhausted": r"quota exceeded|quota exhausted|insufficient_quota|usage limit",
    "authentication_failed": r"unauthorized|authentication failed|invalid.api.key",
    "permission_denied": r"permission denied|forbidden",
    "service_unavailable": r"service unavailable|internal server error|bad gateway",
    "websocket": r"websocket",
    "transport_fallback": r"falling back|fallback",
}


def _safe_error_diagnostic(message):
    """Report text markers and hashes, never raw messages or inferred root causes."""
    if not isinstance(message, str):
        return {"message_present": False, "signals": [], "http_status_codes": []}
    encoded = message.encode(errors="replace")
    sample = encoded[:_MAX_DIAGNOSTIC_BYTES].decode(errors="replace")
    return {
        "message_present": True,
        "message_sha256": hashlib.sha256(encoded).hexdigest(),
        "message_length": len(message),
        "classification_truncated": len(encoded) > _MAX_DIAGNOSTIC_BYTES,
        "signals": [name for name, pattern in _DIAGNOSTIC_PATTERNS.items()
                    if re.search(pattern, sample, re.IGNORECASE)],
        "http_status_codes": sorted({int(match) for match in re.findall(
            r"(?:\bHTTP(?:/\d(?:\.\d)?)?\s+(?:error\s+)?|\bstatus(?:\s+code)?\s*[=:]?\s+)([45]\d{2})\b",
            sample, re.IGNORECASE)}),
    }


def _stderr_diagnostic(stream):
    stream.seek(0)
    raw = stream.read(_MAX_DIAGNOSTIC_BYTES + 1)
    sample = raw[:_MAX_DIAGNOSTIC_BYTES]
    result = _safe_error_diagnostic(sample.decode(errors="replace"))
    # The diagnostic is explicitly a bounded prefix, not the whole stderr.
    result.update(bytes_examined=len(sample), truncated=len(raw) > len(sample),
                  sample_sha256=hashlib.sha256(sample).hexdigest())
    return result


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
        self.output_format = config.get("output_format", "legacy_text")
        self.event_policy = config.get("event_policy", "strict_v1")
        self.timeout_seconds = float(config.get("timeout_seconds", 90))
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
            output_format=self.output_format,
            event_policy=self.event_policy,
            disabled_skill_paths=(config["disabled_skill_paths"] if config.get("disabled_skill_paths") is not None
                                  else discover_disabled_skill_paths()),
        )
        self.transport_metadata = {
            "diagnostics_version": "redacted_cli_v1",
            "backend": "codex_cli", "auth_mode": "chatgpt", "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "timeout_seconds": self.timeout_seconds, "cli_path": self.cli_path,
            "public_config_sha256": policy_sha256(self.public_policy),
            "disabled_skill_paths": self.public_policy["disabled_skill_paths"],
            "application_max_attempts": 1,
            "internal_http_retry_observation_available": False,
            "internal_retry_policy": "cli_managed_unknown",
        }
        self._call_transport = {}
        self._call_raw_response = None
        if self.output_format == "json_schema_v1":
            self.transport_metadata.update(output_format=self.output_format,
                output_schema_sha256=self.public_policy["output_schema_sha256"])
        if self.event_policy != "strict_v1":
            self.transport_metadata["event_policy"] = self.event_policy

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
        if self.output_format == "json_schema_v1":
            schema_path = directory / "stage-output.schema.json"
            schema_path.write_text(json.dumps(policy["output_schema"], sort_keys=True))
            command.extend(["--output-schema", str(schema_path)])
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
        errors = []
        diagnostics = []
        transport_fallbacks = []
        completed = False
        for event_index, event in enumerate(events):
            kind = event.get("type")
            event_types.append(kind if isinstance(kind, str) else "invalid")
            if kind == "turn.started":
                starts += 1
            elif kind == "turn.completed":
                if self.event_policy == "completed_transport_fallback_v1" and len(messages) != 1:
                    error_code = "codex_unexpected_event"
                completed = True
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
                message = item.get("message") if isinstance(item, dict) else None
                fallback = (self.event_policy == "completed_transport_fallback_v1"
                    and kind == "item.completed" and item_kind == "error"
                    and isinstance(message, str) and message.startswith(TRANSPORT_FALLBACK_PREFIX)
                    and len(TRANSPORT_FALLBACK_PREFIX) < len(message) <= 2048
                    and not any(char in message for char in ("\x00", "\r", "\n"))
                    and starts == 1 and not completed and not messages and not transport_fallbacks)
                if fallback:
                    transport_fallbacks.append({"event_index": event_index,
                        "classification": "websocket_to_https_fallback_notice",
                        "message_sha256": hashlib.sha256(message.encode()).hexdigest(),
                        "message_length": len(message)})
                if item_kind not in ("agent_message", "reasoning") and not fallback:
                    error_code = "codex_unexpected_item"
                if item_kind == "error":
                    diagnostics.append({"event_index": event_index, "source": "error_item",
                                        **_safe_error_diagnostic(item.get("message"))})
                if item_kind == "agent_message" and kind == "item.completed":
                    if self.event_policy == "completed_transport_fallback_v1" and completed:
                        error_code = "codex_unexpected_event"
                    text = item.get("text")
                    if not isinstance(text, str) or not text.strip():
                        error_code = "codex_empty_response"
                    else:
                        messages.append(text.strip())
            elif kind == "error":
                message = event.get("message")
                diagnostics.append({"event_index": event_index, "source": "error_event",
                                    **_safe_error_diagnostic(message)})
                match = re.fullmatch(
                    r"Reconnecting\.\.\. ([1-9][0-9]{0,2})/([1-9][0-9]{0,2})(?:[ \n][^\x00]*)?",
                    message,
                ) if isinstance(message, str) else None
                reconnect = bool(match and int(match[1]) <= int(match[2]))
                errors.append({
                    "event_index": event_index,
                    "classification": "numbered_reconnecting_notice" if reconnect else "unrecognized_error",
                    "message_sha256": hashlib.sha256(message.encode(errors="replace")).hexdigest() if isinstance(message, str) else None,
                    "message_length": len(message) if isinstance(message, str) else None,
                    "attempt": int(match[1]) if reconnect else None,
                    "maximum": int(match[2]) if reconnect else None,
                })
                if not (self.event_policy in {"completed_reconnect_v1", "completed_transport_fallback_v1"} and reconnect
                        and starts == 1 and not completed and not messages):
                    error_code = "codex_unexpected_event"
            elif kind not in ("thread.started",):
                error_code = "codex_unexpected_event"
                if kind == "turn.failed":
                    detail = event.get("error")
                    diagnostics.append({"event_index": event_index, "source": "turn_failed",
                                        **_safe_error_diagnostic(detail.get("message")
                                            if isinstance(detail, dict) else None)})
        complete_turns = sum(kind == "turn.completed" for kind in event_types)
        if len(messages) == 1:
            self._call_raw_response = messages[0]
        self._call_transport.update(
            event_types=event_types, item_types=item_types, observed_usage=usages,
            completed_turns=complete_turns,
            error_events=errors,
            error_diagnostics=diagnostics,
        )
        if self.event_policy == "completed_transport_fallback_v1":
            self._call_transport['transport_fallback_notices'] = transport_fallbacks
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
        return messages[0]

    def _normalize_structured_response(self, output):
        """Validate the raw JSON, then use the unchanged legacy decision parser."""
        def unique_pairs(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("duplicate field")
                value[key] = item
            return value
        try:
            value = json.loads(output, object_pairs_hook=unique_pairs)
            if (not isinstance(value, dict) or set(value) != {"stage", "guidance", "evidence"}
                    or type(value["stage"]) is not int or value["stage"] < 0
                    or value["guidance"] not in ("yes", "no")
                    or not isinstance(value["evidence"], str) or not value["evidence"].strip()):
                raise ValueError("invalid response")
        except (ValueError, TypeError):
            raise CodexStageError("codex_invalid_structured_response") from None
        evidence = " ".join(value["evidence"].splitlines())
        return f"stage {value['stage']}\nguidance: {value['guidance']}\nevidence: {evidence}"

    def _request_stage_response(self, content):
        self.api_request_counter.values["logical_call_attempts"] += 1
        self._call_transport = dict(self.transport_metadata)
        self._call_raw_response = None
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
                self._call_transport["request_fingerprint"] = {
                    "prompt_sha256": hashlib.sha256("\n\n".join(texts).encode()).hexdigest(),
                    "image_png_sha256": [hashlib.sha256(path.read_bytes()).hexdigest() for path in images],
                }
                command = self._command(directory, images)
                with (directory / "events.jsonl").open("w+b") as events_file, (
                    directory / "stderr.txt"
                ).open("w+b") as error_file:
                    process = subprocess.Popen(
                        command, stdin=subprocess.PIPE, stdout=events_file,
                        stderr=error_file, cwd=directory, env=child_env,
                        text=True, start_new_session=False,
                    )
                    try:
                        process.communicate(input="\n\n".join(texts), timeout=self.timeout_seconds)
                    except subprocess.TimeoutExpired:
                        _stop_owned_process(process)
                        self._call_transport.update(process_returncode=process.returncode,
                                                    process_timed_out=True)
                        events_file.seek(0)
                        partial = events_file.read(_MAX_EVENTS_BYTES + 1)
                        if len(partial) <= _MAX_EVENTS_BYTES:
                            try:
                                self._parse_events(partial)
                            except CodexStageError as exc:
                                self._call_transport["partial_event_validation_error"] = str(exc)
                        raise CodexStageError("codex_timeout") from None
                    except BaseException:
                        _stop_owned_process(process)
                        raise
                    finally:
                        try:
                            self._call_transport["stderr_diagnostic"] = _stderr_diagnostic(error_file)
                        except OSError:
                            self._call_transport["stderr_diagnostic"] = {"read_failed": True}
                    events_file.seek(0)
                    self._call_transport.update(process_returncode=process.returncode,
                                                process_timed_out=False)
                    raw_events = events_file.read(_MAX_EVENTS_BYTES + 1)
                    if len(raw_events) > _MAX_EVENTS_BYTES:
                        raise CodexStageError("codex_event_stream_too_large")
                    output = self._parse_events(raw_events)
                    if process.returncode != 0:
                        raise CodexStageError("codex_nonzero_exit")
                    if self.output_format == "json_schema_v1":
                        return self._normalize_structured_response(output)
                    return output
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
        if self.output_format == "json_schema_v1":
            self._last_result["normalized_response"] = self._last_result["raw_response"]
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
