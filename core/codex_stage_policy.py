"""Pure public Codex Stage invocation policy and deterministic freeze hash."""
import hashlib
import json
import os
from pathlib import Path

_DISABLED_FEATURES = (
    "shell_tool", "unified_exec", "plugins", "apps", "multi_agent", "hooks",
    "browser_use", "computer_use", "image_generation", "view_image",
    "skill_search", "unbounded_connection_retries", "shell_snapshot",
    "sleep_tool", "goals", "memories", "workspace_dependencies",
)
_DEVELOPER_INSTRUCTIONS = (
    "This invocation is a single image-based Stage recognition request. "
    "Answer the user's prompt directly, using only the attached images and text. "
    "The image attachments follow the label order in the user prompt: Initial "
    "Image (with keypoints), when supplied, then Current Image. "
    "Do not call tools, browse, read files, invoke skills, or perform other tasks. "
    "Return only the three lines requested by the user prompt."
)
# Remove provider/auth overrides only in the child. Saved CLI login stays under
# the original HOME/CODEX_HOME and remains managed entirely by the official CLI.
_REMOVED_ENVIRONMENT = (
    "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_ORG_ID", "OPENAI_ORGANIZATION",
    "OPENAI_PROJECT_ID", "OPENAI_API_TYPE", "OPENAI_API_VERSION",
    "CODEX_API_KEY", "CODEX_ACCESS_TOKEN", "GOOGLE_API_KEY",
    "GEMINI_API_KEY", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_BASE_URL", "AZURE_API_KEY", "CHATGPT_BASE_URL", "CODEX_MODEL_PROVIDER",
)
_MAX_EVENTS_BYTES = 4 * 1024 * 1024
_COUNTER_FIELDS = (
    "logical_call_attempts", "completed_turns", "failed_calls",
    "usage_complete_calls", "input_tokens", "cached_input_tokens",
    "output_tokens", "reasoning_output_tokens", "call_latency_s",
)

STAGE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "stage": {"type": "integer", "minimum": 0},
        "guidance": {"type": "string", "enum": ["yes", "no"]},
        "evidence": {"type": "string"},
    },
    "required": ["stage", "guidance", "evidence"],
    "additionalProperties": False,
}

# Literal present in the pinned 0.155.1 CLI binary. This is an opt-in proposal;
# the frozen N1V runner does not authorize this new acceptance policy.
TRANSPORT_FALLBACK_PREFIX = 'Falling back from WebSockets to HTTPS transport. '


def public_invocation_policy(*, model, reasoning_effort, timeout_seconds, cli_path,
                             disabled_skill_paths=(), output_format="legacy_text",
                             event_policy="strict_v1"):
    """Credential-free, deterministic full wrapper policy for freeze hashes."""
    if output_format not in {"legacy_text", "json_schema_v1"}:
        raise ValueError("Unknown Codex Stage output format")
    if event_policy not in {"strict_v1", "completed_reconnect_v1", "completed_transport_fallback_v1"}:
        raise ValueError("Unknown Codex Stage event policy")
    if event_policy != "strict_v1" and output_format != "json_schema_v1":
        raise ValueError("Reconnect policy requires structured output")
    policy = {
        "backend": "codex_cli", "auth_mode": "chatgpt", "model": str(model),
        "reasoning_effort": str(reasoning_effort),
        "timeout_seconds": float(timeout_seconds), "cli_path": str(cli_path),
        "fixed_arguments": [
            "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
            "--skip-git-repo-check", "--sandbox", "read-only", "--json",
            "--color", "never",
        ],
        "config_overrides": {
            "model_provider": "openai", "model_reasoning_effort": str(reasoning_effort),
            "web_search": "disabled", "approval_policy": "never",
            "project_doc_max_bytes": 0, "mcp_servers": {},
            "developer_instructions": _DEVELOPER_INSTRUCTIONS,
            # CLI 0.155.1 matches SKILL.md file paths, verified using its local
            # debug prompt-input. Directory paths silently leave skills active.
            "skills.config": [{"path": str(Path(path) / "SKILL.md"), "enabled": False}
                              for path in sorted(disabled_skill_paths)],
        },
        "disabled_skill_paths": sorted(str(path) for path in disabled_skill_paths),
        "skill_disable_path_semantics": "folder_metadata_to_SKILL.md_file_for_cli_0.155.1",
        "disabled_features": list(_DISABLED_FEATURES),
        "enabled_features": [],
        "removed_child_environment": list(_REMOVED_ENVIRONMENT),
        "image_policy": "original_png_bytes_in_original_content_order",
        "prompt_policy": "unchanged_content_text_parts_joined_with_two_newlines_stdin",
        "output_policy": "one_turn_one_agent_message_required_usage_no_tools",
        "working_directory": "owned_temporary_directory",
        "log_directory": "owned_temporary_directory/log",
        "application_max_attempts": 1,
        "internal_http_retry_observation_available": False,
        "internal_retry_policy": "cli_managed_unknown",
        "maximum_event_bytes": _MAX_EVENTS_BYTES,
        "process_group": "inherit_outer_runner_group",
    }
    if output_format == "json_schema_v1":
        policy["output_format"] = output_format
        policy["output_schema"] = json.loads(json.dumps(STAGE_OUTPUT_SCHEMA))
        policy["output_schema_sha256"] = policy_sha256(STAGE_OUTPUT_SCHEMA)
        policy["output_policy"] = "one_turn_one_schema_json_message_required_usage_no_tools"
        policy["config_overrides"]["developer_instructions"] = _DEVELOPER_INSTRUCTIONS.replace(
            "Return only the three lines requested by the user prompt.",
            "Apply the same Stage decision rules in the user prompt. Return only a JSON object "
            "conforming to the supplied output schema: stage is the nonnegative stage number, "
            "guidance is yes or no, and evidence is a brief nonempty observation. "
            "This JSON format supersedes the three-line output format in the user prompt.")
    if event_policy != "strict_v1":
        policy["event_policy"] = event_policy
        policy["reconnect_acceptance"] = (
            "explicit_numbered_reconnecting_notice_inside_single_turn_then_"
            "one_complete_usage_one_schema_message_exit_zero_no_other_error"
        )
    if event_policy == "completed_transport_fallback_v1":
        policy["transport_fallback_acceptance"] = {
            "exact_notice_prefix": TRANSPORT_FALLBACK_PREFIX,
            "maximum_notice_characters": 2048,
            "maximum_notice_count": 1,
            "event_type": "item.completed",
            "item_type": "error",
            "position": "inside_single_turn_before_agent_message_and_completion",
            "required_completion": "one_schema_message_then_one_usage_exit_zero_no_other_error",
            "new_application_invocations": 0,
        }
    return policy


def policy_sha256(policy):
    return hashlib.sha256(json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def discover_disabled_skill_paths(codex_home=None, user_home=None):
    """List active installation folders by metadata only; never read skill files.

    Paths are lexical installation directories. The invocation policy maps
    them to SKILL.md file paths for the installed CLI. Inactive artifacts and
    disabled plugin copies are intentionally outside the discovery roots.
    """
    user_home = Path(user_home or os.environ.get("HOME") or Path.home())
    codex_home = Path(codex_home or os.environ.get("CODEX_HOME") or user_home / ".codex")
    roots = (codex_home / "skills", codex_home / "skills" / ".system",
             user_home / ".agents" / "skills")
    paths = set()
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.iterdir():
            if (path.name.startswith(".") or path.name == "disabled-skills"
                    or "superpowers" in path.name.lower()):
                continue
            if path.is_dir() and (path / "SKILL.md").is_file():
                paths.add(str(path.absolute()))
    return sorted(paths)
