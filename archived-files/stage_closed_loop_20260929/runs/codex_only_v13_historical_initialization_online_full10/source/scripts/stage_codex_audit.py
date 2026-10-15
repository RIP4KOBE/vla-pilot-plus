"""Audit saved Codex completions without inventing HTTP-level counters."""
import json


def provider_checks(folder, config, events, compute, tasks):
    from codex_only_runtime import validate_config
    validate_config(config)
    queries = [r for r in events if r.get('query_status') in ('ok', 'error')]
    stage_paths = list((folder/'output/captured_stage_inputs').glob('request_*/response.json'))
    reward_paths = list((folder/'output').glob('episode_*/vlm_agent/codex_requests/request_*/response.json'))
    stage = [json.loads(p.read_text()) for p in stage_paths]
    rewards = [json.loads(p.read_text()) for p in reward_paths]
    records = stage+rewards
    policies = [json.loads(p.with_name('public-policy.json').read_text()) for p in stage_paths+reward_paths]
    checks = {
        'codex_only_resolved_provider': True,
        'all_requests_managed_chatgpt_login': bool(records) and all(
            r['backend']=='codex_cli' and r['auth_mode']=='chatgpt' and r['ok'] and
            r['transport']['backend']=='codex_cli' and r['transport']['auth_mode']=='chatgpt'
            for r in records),
        'all_child_policies_force_chatgpt_without_tools': bool(policies) and all(
            p['config_overrides'].get('forced_login_method')=='chatgpt' and
            p['config_overrides']['model_provider']=='openai' and
            p['output_format']=='requested_format_v1' and
            {'shell_tool','plugins','apps','multi_agent'} <= set(p['disabled_features']) for p in policies),
        'one_fresh_codex_reward_completion_per_task': len(rewards)==len(tasks) and all(
            r['counters']['completed_turns']==1 for r in rewards),
        'codex_http_counts_explicitly_unavailable': bool(queries) and all(
            q.get('api_request_attempts') is None and q.get('api_sdk_retry_attempts') is None and
            q.get('api_request_counter_available') is False for q in queries),
        'captured_codex_calls_match_stage_events': bool(stage) and all(
            sum((q.get('codex_'+k) or 0) for q in queries)==sum((r['counters'][k] or 0) for r in stage)
            for k in ('logical_call_attempts','completed_turns','usage_complete_calls','input_tokens','output_tokens')),
        'codex_reward_calls_match_episode_compute': len(compute)==len(tasks) and all(
            sum((r.get('guidance_codex_'+k) or 0) for r in compute)==sum((r['counters'][k] or 0) for r in rewards)
            for k in ('logical_call_attempts','completed_turns','usage_complete_calls','input_tokens','output_tokens')),
    }
    return checks
