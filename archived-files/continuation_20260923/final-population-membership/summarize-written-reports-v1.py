"""Describe two digest-bound final-membership outputs, without opening bundles."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORTS = {
    't00-c0-v1': 'fda61dee79c6df38e1772120b44fb24adf3ec0ff00bda791bc13e4a30cc107b8',
    't00-q0-v1': '40b319e2e41339cda84ba1f27cb61ff4dc71665dc4ee14ab6e46c64c0a6716b8',
}


def describe(rows):
    deltas = [d['summary']['best_known_quality_minus_actual_selected'] for d in rows]
    known = [v for v in deltas if v is not None]
    boolean_fields = ['any_nonflagged', 'any_distinct_nonflagged',
                      'any_nonflagged_quality_ge_selected', 'any_distinct_nonflagged_quality_ge_selected']
    return {'decisions': len(rows), 'final_slots': sum(d['summary']['final_slots'] for d in rows),
        **{field: dict(Counter(str(d['summary'][field]) for d in rows)) for field in boolean_fields},
        'best_nonflagged_quality_minus_selected': {
            'negative': sum(v < 0 for v in known), 'zero': sum(v == 0 for v in known),
            'positive': sum(v > 0 for v in known), 'Unknown': len(deltas)-len(known),
            'min': min(known, default=None), 'max': max(known, default=None)},
        'unknown_tail_slots': sum(d['summary']['unknown_tail_slots'] for d in rows),
        'unknown_quality_slots': sum(d['summary']['unknown_quality_slots'] for d in rows),
        'selected_slots_checked': sum(sum(s['selected'] for s in d['slots']) for d in rows)}


def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    episodes = []
    for label, expected in REPORTS.items():
        path = ROOT/label/'final-population-membership.json'; raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected
        r = json.loads(raw)
        assert r['cuda_initialized'] is False and r['promotion_status'] == 'NOT_EVALUATED'
        decisions = r['decisions']
        strata = {'all': decisions, 'A_true': [d for d in decisions if d['original_actual_A'] is True],
                  'A_false': [d for d in decisions if d['original_actual_A'] is False],
                  'A_Unknown': [d for d in decisions if d['original_actual_A'] is None]}
        episodes.append({'name': label, 'episode_key': r['episode_key'], 'attempt_id': r['attempt_id'],
            'report': {'path': str(path), 'sha256': expected}, 'original_success': r['original_success'],
            'strata': {key: describe(rows) for key, rows in strata.items()},
            'all_decision_summaries': [{key: d[key] for key in ['decision_id', 'global_step', 'stage', 'pool_kind',
                'original_actual_A', 'original_actual_B', 'selected_index', 'selected_fingerprint',
                'actual_selected_quality', 'summary']} for d in decisions],
            'excluded_decisions': r['excluded_decisions'], 'CPU_wall_seconds': r['CPU_wall_seconds'],
            'parent_ru_maxrss_before_kib': r['parent_ru_maxrss_before_kib'],
            'parent_ru_maxrss_after_kib': r['parent_ru_maxrss_after_kib'], 'memory_scope': r['memory_scope']})
    result = {'schema': 'qd-ed-final-membership-summary-v1', 'episodes': episodes,
        'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'promotion_status': 'NOT_EVALUATED', 'counterfactual_success': 'Unknown',
        'limits': ['Two observer=true task0 episodes only; correlated decisions/slots are not independent trials.',
            'Nonflagged means only the unchanged recorded projected native-ULP screen; no physical guarantee.',
            'Final slot membership is direct evidence; ambiguous original insertion occurrence is not reconstructed.',
            'Historical reports remain unchanged; final membership does not create a selection rule or success label.']}
    with (ROOT/'summary-v1.json').open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False); stream.write('\n')
    print(json.dumps({'episodes': len(episodes), 'eligible': sum(e['strata']['all']['decisions'] for e in episodes),
                      'promotion_status': 'NOT_EVALUATED'}))


if __name__ == '__main__': main()
