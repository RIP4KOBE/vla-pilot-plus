"""Audited visual inference through the CLI's existing ChatGPT account only."""
import json
import time

from core.codex_stage import CodexStageRecognizer
from core.codex_stage_policy import _COUNTER_FIELDS


class CodexVisionTransport(CodexStageRecognizer):
    def __init__(self, config):
        config = dict(config, backend="codex_cli", output_format="requested_format_v1")
        super().__init__(config)
        self.context = {}
        self._last_completion_metadata = None

    @property
    def cursor(self):
        return self._capture_index

    def set_trace_context(self, state, trigger_reason):
        self.context = {key: state.get(key) for key in
                        ('episode_id', 'task_id', 'episode_seed', 'global_step', 'chunk_id')}
        self.context['trigger_reason'] = trigger_reason

    def _request_stage_response(self, content):
        started = time.perf_counter()
        before = self.api_request_counter.snapshot()
        capture_index = self._capture_index
        output = None
        error = None
        self._last_completion_metadata = None
        try:
            output = super()._request_stage_response(content)
            if not isinstance(output, str) or not output.strip():
                raise ValueError("empty Codex response")
            self._last_completion_metadata = {
                "backend": "codex_cli", "auth_mode": "chatgpt",
                "response_model": self.model, "reasoning_effort": self.reasoning_effort,
                "finish_reason": "validated_turn_completed",
                "usage": self._call_transport.get("observed_usage", []),
            }
            return output
        except Exception as exc:
            error = type(exc).__name__
            self.api_request_counter.values["failed_calls"] += 1
            raise
        finally:
            self.api_request_counter.values["call_latency_s"] += time.perf_counter() - started
            if self.capture_dir is not None:
                folder = self.capture_dir / f"request_{capture_index:04d}"
                if folder.exists():
                    after = self.api_request_counter.snapshot()
                    record = dict(backend="codex_cli", auth_mode="chatgpt", context=self.context,
                        ok=error is None, error_type=error, raw_response=output,
                        transport=self._call_transport, completion_metadata=self._last_completion_metadata,
                        counters={k: after[k]-before[k] if after[k] is not None and before[k] is not None else None
                                  for k in _COUNTER_FIELDS})
                    (folder / "response.json").write_text(json.dumps(record, ensure_ascii=False, indent=2)+"\n")
                    (folder / "public-policy.json").write_text(json.dumps(self.public_policy, indent=2)+"\n")

    def _record_transport_result(self, counter_before):
        # Per-request transport accounting above includes identity and every bounded
        # syntax/transport retry. Do not count their latency twice at query level.
        after = self.api_request_counter.snapshot()
        self._last_result.update(api_request_attempts=None, api_sdk_retry_attempts=None,
            api_request_counter_available=False, transport=dict(self._call_transport))
        for key in _COUNTER_FIELDS:
            a, b = after[key], counter_before[key]
            self._last_result["codex_"+key] = a-b if a is not None and b is not None else None

