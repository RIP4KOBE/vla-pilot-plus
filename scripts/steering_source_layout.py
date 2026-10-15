"""Resolve immutable flat-layout evidence and current packaged source identities.

Only paths are mapped. Archived bytes, hashes and receipts are never rewritten.
"""

CONTROL_PATH_MAP = {'core/stage_evidence.py': 'core/stage/controller.py',
 'core/stage_contact_handoff.py': 'core/stage/controller.py',
 'core/stage_observation_json.py': 'core/stage/contract.py',
 'core/stage_response_validation.py': 'core/stage/contract.py',
 'core/stage_identity_memory.py': 'core/stage/observation.py',
 'core/stage_target_marker.py': 'core/stage/observation.py',
 'core/stage_observation.py': 'core/stage/observation.py',
 'core/stage_robot_evidence.py': 'core/stage/grasp.py',
 'core/stage_grasp_guard.py': 'core/stage/grasp.py',
 'core/stage_carry_hold.py': 'core/stage/carry.py',
 'core/stage_fused_carry_hold.py': 'core/stage/carry.py',
 'core/stage_failed_contact_recheck.py': 'core/stage/recovery.py',
 'core/stage_release_guard.py': 'core/stage/recovery.py',
 'core/codex_stage.py': 'core/online/codex.py',
 'core/codex_vision.py': 'core/online/codex.py',
 'core/codex_stage_policy.py': 'core/online/policy.py',
 'core/stage_capture.py': 'core/online/capture.py',
 'core/trace_replay_stage.py': 'core/diagnostics/stage_replay.py',
 'core/stage_capture_trace_replay.py': 'core/diagnostics/stage_replay.py'}


LEGACY_PROOF_FILES = (
    'main.py', 'core/codex_vision.py', 'core/codex_stage.py', 'core/codex_stage_policy.py',
    'core/stage_grasp_guard.py', 'core/stage_target_marker.py', 'core/stage_observation.py',
    'core/env_adapters/libero_adapter.py', 'vlm_query/vlm_agent.py',
    'core/stage_identity_memory.py', 'core/stage_response_validation.py', 'core/stage_evidence.py',
    'vlm_query/stage_observation_v1.txt', 'core/target_distance_reward.py',
)
PACKAGE_INITIALIZERS = ('core/stage/__init__.py', 'core/online/__init__.py', 'core/diagnostics/__init__.py')


def evidence_layout(source_hashes):
    """Choose the recorded layout, rejecting ambiguous or partial hybrid inputs."""
    flat = any(path in source_hashes for path in CONTROL_PATH_MAP)
    packaged = any(path in source_hashes for path in CONTROL_PATH_MAP.values())
    if flat == packaged:
        raise ValueError('Missing or mixed control source layout')
    layout = 'flat' if flat else 'packaged'
    required = proof_files(layout)
    if any(path not in source_hashes for path in required):
        raise ValueError('Incomplete control source manifest')
    return layout


def source_path(path, layout):
    if layout not in {'flat', 'packaged'}:
        raise ValueError('Unknown control source layout')
    return CONTROL_PATH_MAP.get(path, path) if layout == 'packaged' else path


def proof_files(layout):
    required = [source_path(path, layout) for path in LEGACY_PROOF_FILES]
    if layout == 'packaged':
        required += list(CONTROL_PATH_MAP.values()) + list(PACKAGE_INITIALIZERS)
    return tuple(dict.fromkeys(required))
