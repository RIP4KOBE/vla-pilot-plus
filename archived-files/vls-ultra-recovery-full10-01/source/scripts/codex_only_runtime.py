"""Managed-login provider boundary shared by the online steering entrypoints."""
from __future__ import annotations

import os


def worker_environment(base=None):
    from core.codex_stage_policy import _REMOVED_ENVIRONMENT
    env = dict(os.environ if base is None else base)
    for name in (*_REMOVED_ENVIRONMENT, 'POE_API_KEY', 'POE_ACCESS_KEY',
                 'GOOGLE_API_KEY', 'GEMINI_API_KEY'):
        env.pop(name, None)
    env['VLA_CODEX_ONLY'] = '1'
    return env


def validate_config(config):
    perception = config['perception']
    for name in ('gemini', 'vlm_agent'):
        item = perception[name]
        if item.get('backend') != 'codex_cli' or item.get('base_url') or item.get('api_key'):
            raise ValueError('Online steering requires managed-login Codex Stage and reward backends')
    if any(perception.get(name, {}).get('enabled', False) for name in ('sam3', 'gemini_grounding')):
        raise ValueError('Online steering disables other remote perception clients')
    if config['main'].get('cached_functions_dir') or config['main'].get('cached_functions_root'):
        raise ValueError('Online evaluation requires fresh per-task reward generation')
