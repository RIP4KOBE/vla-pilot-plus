"""Read-only N21-before/after-N22-integration parity on the completed task0 controls.

This diagnostic compares existing matched exposed-Dev paths. No simulation,
policy evaluation, source change, or candidate efficacy inference is performed.
"""
import hashlib
import json
from pathlib import Path
import torch

HERE = Path(__file__).resolve().parent
SESSION = HERE.parents[1]
OLD = 'rdt-qd-ed-final-20260921T093925Z__n21_dev_t00_n21_20260930__a4957aa45fc2'
NEW = 'rdt-qd-ed-final-20260921T093925Z__n22_dev_t00_n21_20260930__31c7a7b0fb11'
FIELDS = {
    'canonical_candidate_batch': ('candidates', 'effective_quality', 'raw_provider_quality', 'quality_mode', 'canonical_fingerprints'),
    'final_selection': ('population', 'selected_latent', 'selected_index', 'selected_quality', 'selected_cost', 'raw_provider_quality', 'selected_raw_provider_quality', 'selected_fingerprint', 'selection_rule'),
    'policy_action_decode': ('selected_latent', 'action_chunk', 'selected_canonical_fingerprint'),
    'terminal_population_stage_binding': ('selected_raw_reward', 'archive_cost_spread_scale', 'stage_init_reward', 'normalized_reward'),
}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(attempt):
    folder = SESSION / 'artifacts/attempts' / attempt
    result_path = folder / 'attempt-result.json'
    audit_path = folder / 'eds_eval/decision-evidence-audit.json'
    result, audit = json.loads(result_path.read_text()), json.loads(audit_path.read_text())
    assert result['outcome_valid'] and audit['accepted'] and audit['evidence_complete']
    ep = folder / 'eds_eval/decision_evidence/episode_000'
    grouped, refs = {name: [] for name in FIELDS}, []
    for line in (ep / 'events.jsonl').open():
        ref = json.loads(line)
        if not set(FIELDS).intersection(x['event'] for x in ref['events']):
            continue
        path = ep / ref['bundle']
        assert sha(path) == ref['sha256']
        refs.append({'path': str(path), 'sha256': ref['sha256']})
        for event in torch.load(path, map_location='cpu', weights_only=True)['events']:
            if event['event'] in FIELDS:
                grouped[event['event']].append((event['global_step'], event['values']))
    return grouped, {'attempt_id': attempt, 'result_sha256': sha(result_path),
                     'audit_sha256': sha(audit_path), 'event_index_sha256': sha(ep/'events.jsonl'),
                     'matched_identity': {k: result['identity'][k] for k in ('task_id','env_seed','policy_seed','init_index','profile','split')},
                     'verified_bundle_references': refs}


def equal(a, b):
    if isinstance(a, torch.Tensor) or isinstance(b, torch.Tensor):
        return isinstance(a, torch.Tensor) and isinstance(b, torch.Tensor) and a.dtype == b.dtype and a.shape == b.shape and torch.equal(a, b)
    return type(a) is type(b) and a == b


def main():
    torch.set_num_threads(1)
    target = HERE / 'n21-control-parity-result-v1.json'
    assert not target.exists()
    old, old_ref = read(OLD)
    new, new_ref = read(NEW)
    assert old_ref['matched_identity'] == new_ref['matched_identity']
    comparison = {}
    for name, fields in FIELDS.items():
        left, right = old[name], new[name]
        mismatches = []
        for ordinal, (a, b) in enumerate(zip(left, right)):
            if a[0] != b[0]:
                mismatches.append({'ordinal': ordinal, 'field': 'global_step', 'old': a[0], 'new': b[0]})
            for field in fields:
                if not equal(a[1].get(field), b[1].get(field)):
                    mismatches.append({'ordinal': ordinal, 'step_old': a[0], 'step_new': b[0], 'field': field})
        comparison[name] = {'old_count': len(left), 'new_count': len(right), 'fields': fields,
                            'exact_equal': len(left) == len(right) and not mismatches,
                            'mismatches': mismatches}
    result = {'schema': 'n21-control-parity-cpu-v1', 'sources': [old_ref, new_ref], 'reader_sha256': sha(__file__),
              'comparison': comparison, 'all_compared_fields_equal': all(x['exact_equal'] for x in comparison.values()),
              'interpretation': 'Only this repeated N21 task0 path is compared. Exact control trace parity does not imply N22 success, universal determinism, or independent replication.'}
    with target.open('x') as f:
        f.write(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'path': str(target), 'sha256': sha(target), 'comparison': comparison}))


if __name__ == '__main__':
    main()
