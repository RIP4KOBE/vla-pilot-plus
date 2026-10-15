#!/usr/bin/env python3
"""Describe only the two completed, digest-bound candidate reports; no bundles."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPECTED = {
    't00-c0-v1': 'f60ad2353dbc181e77d2fb8a01d67fdf71fa3f41a386512eee7f08bb096dbf68',
    't00-q0-v1': 'eb4619939885ec83f7744f6e39f1cd62214c8b0f98f15797373b84b8e4a44348',
}


def describe(rows):
    deltas = [row['summary']['best_known_quality_minus_actual_selected'] for row in rows]
    known_deltas = [value for value in deltas if value is not None]
    def distinct(row):
        known = any(c['tail_classification'] == 'not_flagged_robust_regression' and
                    c['fingerprint'] != row['selected_fingerprint'] for c in row['candidates'])
        return True if known else None if row['summary']['unknown_or_ineligible_occurrences'] else False
    fields = ['any_nonflagged', 'any_nonflagged_quality_ge_selected',
              'any_distinct_fingerprint_nonflagged_quality_ge_selected']
    return {
        'decisions': len(rows),
        'B_true_decisions': sum(row['original_actual_B'] is True for row in rows),
        'canonical_occurrences_with_repeats': sum(row['summary']['canonical_occurrences'] for row in rows),
        'unknown_or_ineligible_occurrences': sum(row['summary']['unknown_or_ineligible_occurrences'] for row in rows),
        'ambiguous_fingerprints': sum(len(row['ambiguous_fingerprints']) for row in rows),
        **{field: dict(Counter(str(row['summary'][field]) for row in rows)) for field in fields},
        'distinct_nonflagged': dict(Counter(str(distinct(row)) for row in rows)),
        'best_known_delta_counts': {
            'negative': sum(value < 0 for value in known_deltas),
            'zero': sum(value == 0 for value in known_deltas),
            'positive': sum(value > 0 for value in known_deltas),
            'Unknown': sum(value is None for value in deltas)},
        'best_known_delta_min': min(known_deltas, default=None),
        'best_known_delta_max': max(known_deltas, default=None),
    }


def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    episodes = []
    for name, expected in EXPECTED.items():
        path = ROOT / name / 'candidate-tail-availability.json'
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected
        report = json.loads(raw)
        assert report['promotion_status'] == 'NOT_EVALUATED' and report['cuda_initialized'] is False
        decisions = report['decisions']
        strata = {'all': decisions, 'A_true': [r for r in decisions if r['original_actual_A'] is True],
                  'A_false': [r for r in decisions if r['original_actual_A'] is False],
                  'A_Unknown': [r for r in decisions if r['original_actual_A'] is None]}
        episodes.append({
            'name': name, 'episode_key': report['episode_key'], 'attempt_id': report['attempt_id'],
            'report': {'path': str(path), 'sha256': expected}, 'original_success': report['original_success'],
            'eligible_decisions': report['eligible_decisions'], 'excluded_decisions': report['excluded_decision_count'],
            'strata': {key: describe(rows) for key, rows in strata.items()},
            'all_decision_summaries': [{key: row[key] for key in ['decision_id', 'global_step', 'stage',
                'original_actual_A', 'original_actual_B', 'selected_fingerprint', 'actual_selected_quality',
                'ambiguous_fingerprints', 'summary']} for row in decisions],
            'CPU_wall_seconds': report['CPU_wall_seconds'],
            'parent_ru_maxrss_before_kib': report['parent_ru_maxrss_before_kib'],
            'parent_ru_maxrss_after_kib': report['parent_ru_maxrss_after_kib'],
            'memory_scope': report['memory_scope'],
        })
    summary = {
        'schema': 'qd-ed-recorded-candidate-tail-summary-v1', 'episodes': episodes,
        'authorization_condition': 'post_data_identity_v3', 'promotion_status': 'NOT_EVALUATED',
        'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'limits': [
            'All eligible guided decisions from these two task0 episodes; A is descriptive stratification only.',
            'Counts of decisions and repeated occurrences are correlated within episodes, not independent trials.',
            'Nonflagged means only not exceeding the frozen projected native-ULP regression screen; no physical guarantee.',
            'Recorded canonical occurrences precede final selection; final-time archive/population availability Unknown.',
            'Original effective-quality deltas and all ties retained; no rescore or unexecuted outcome label.',
            'Only two observer=true task0 episodes; no claim about success-rate improvement or other tasks.',
        ],
    }
    with (ROOT / 'summary-v1.json').open('x') as stream:
        json.dump(summary, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'episodes': len(episodes), 'eligible': sum(e['eligible_decisions'] for e in episodes),
                      'promotion_status': 'NOT_EVALUATED'}))


if __name__ == '__main__':
    main()
