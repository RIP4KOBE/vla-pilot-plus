"""Fail-closed provider boundary for this study's Codex-only experiments."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.codex_stage_policy import _REMOVED_ENVIRONMENT


def worker_environment():
    from c0_trace_replay import process_env
    env = process_env()
    for name in (*_REMOVED_ENVIRONMENT, 'POE_API_KEY', 'POE_ACCESS_KEY'):
        env.pop(name, None)
    env['VLA_CODEX_ONLY'] = '1'
    return env


def validate_config(config):
    perception = config['perception']
    for name in ('gemini', 'vlm_agent'):
        item = perception[name]
        if item.get('backend') != 'codex_cli' or item.get('base_url') or item.get('api_key'):
            raise ValueError('Codex-only experiment requires managed-login Stage and reward backends')
    if any(perception.get(name, {}).get('enabled', False) for name in ('sam3', 'gemini_grounding')):
        raise ValueError('Codex-only experiment disables other remote perception clients')
    if config['main'].get('cached_functions_dir') or config['main'].get('cached_functions_root'):
        raise ValueError('This Codex-only cohort requires fresh per-task reward generation')

