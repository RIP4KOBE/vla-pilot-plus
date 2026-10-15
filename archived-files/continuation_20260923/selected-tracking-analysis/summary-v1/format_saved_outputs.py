"""Descriptive aggregation of all30 frozen outputs; never reads source episodes."""
from collections import Counter
from pathlib import Path
import hashlib
import json

BASE = Path(__file__).resolve().parent.parent
READ = BASE/'read-v1'
OUT = Path(__file__).resolve().parent
INDEX_SHA = 'd0ed98c7b8dfd4c3c1fd1a584368b5b33a3ff91383dc0e6beb90d04f941fada7'
PROVENANCE_SHA = 'b76e99c0d1985a93ce285c84f0068a04519f09973388082f7aac7aeba3395ba6'
STATUS_SHA = '263f930a951ba98a540255a7d2ff469b37d812c268493aa713d2a1010574d13e'
inputs = {}

def load(path, expected):
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == expected
    inputs[str(path)] = expected
    return json.loads(data)

def avg(values): return sum(values)/len(values) if values else None

index = load(READ/'index.json', INDEX_SHA)
prov = load(READ/'inputs-and-source-hashes.json', PROVENANCE_SHA)
status = load(READ/'status.json', STATUS_SHA)
assert index['complete'] is prov['complete'] is status['complete'] is True
assert [c['cell'] for c in index['cells']] == [f't{t:02d}-{a}' for t in range(10) for a in ('c0', 'q0', 'n2')]
rows = []; total_pairs = Counter(); projection_dtypes = Counter(); origin_dtypes = Counter(); eef_dtypes = Counter()
for cell in index['cells']:
    value = load(READ/cell['path'], cell['sha256'])
    assert value['attempt_id'] == cell['attempt_id'] and value['summary'] == cell['summary']
    known = [d for d in value['decisions'] if d['tracking'] is not None]
    pairs = [p for p in value['temporal_pairs'] if p['status'] == 'retrospective_predictive_check']
    relation = Counter('lower' if p['transported_mse'] < p['zero_mse'] else 'higher'
                       if p['transported_mse'] > p['zero_mse'] else 'equal' for p in pairs)
    total_pairs.update(relation)
    for d in known:
        projection_dtypes[d['projected']['native']['dtype']] += 1
        origin_dtypes[d['projected']['origin_native']['dtype']] += 1
    for d in value['decisions']:
        for a in d['actual_prefix']: eef_dtypes[a['eef_native']['dtype']] += 1
    rows.append({'cell': cell['cell'], 'attempt_id': cell['attempt_id'],
        'actions': value['summary']['observed_actions'], 'decisions': value['summary']['decisions'],
        'guided': value['summary']['guided'], 'known_selected_tracking': len(known),
        'actual_prefix_lengths': dict(Counter(str(d['m']) for d in value['decisions'])),
        'guided_prefix_lengths': dict(Counter(str(d['m']) for d in known)),
        'tracking_status_counts': value['summary']['tracking_status_counts'],
        'pair_status_counts': value['summary']['pair_status_counts'], 'eligible_pairs': len(pairs),
        'transport_vs_zero_counts': dict(relation),
        'mean_of_pair_zero_mse': avg([p['zero_mse'] for p in pairs]),
        'mean_of_pair_transported_mse': avg([p['transported_mse'] for p in pairs]),
        'by_step': [{'i': s['i'], 'n': s['n'], 'e_abs_mean': s['e_abs_mean'], 'e_disp_mean': s['e_disp_mean'],
                     'mean_abs_l2': avg(s['abs_l2_values']), 'mean_disp_l2': avg(s['disp_l2_values'])}
                    for s in value['summary']['by_step']],
        'guided_sent_decode_changed_steps': sum(d['summary']['sent_decode_changed_steps'] for d in known),
        'guided_sent_outside_source_declared_unit_bounds_components':
            sum(d['summary']['sent_outside_declared_unit_bounds_components'] for d in known)})

report = {'schema': 'selected-tracking-all30-descriptive-summary-v1', 'complete': True,
    'formatter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'input_hashes': inputs,
    'scope': 'All30 existing frozen outputs only; existing per-step errors and per-pair MSE summarized; no episode reread or new scientific metric/formula.',
    'counting_convention': 'Pair mean is unweighted mean of already recorded per-pair MSE within its episode. lower/higher/equal are exact recorded-value comparisons, not significance or precision-aware physical improvement.',
    'cells': rows, 'totals': {'cells': len(rows), 'decisions': sum(r['decisions'] for r in rows),
        'actions': sum(r['actions'] for r in rows), 'guided': sum(r['guided'] for r in rows),
        'known_selected_tracking': sum(r['known_selected_tracking'] for r in rows),
        'eligible_pairs': sum(r['eligible_pairs'] for r in rows), 'transport_vs_zero_counts': dict(total_pairs)},
    'native_dtypes': {'selected_projection_decisions': dict(projection_dtypes), 'controller_origin_decisions': dict(origin_dtypes), 'actual_eef_actions': dict(eef_dtypes)},
    'limits': ['Correlated chunks/pairs are not independent episode evidence.', 'No task outcome, cause, contact, target progress, controller clipping or deployment benefit is inferred.',
               'Unit-bound counts use the source-declared adapter bounds and guided-prefix summary fields only.',
               'Unguided projections remain Unknown; neither thresholds nor hypothesis parameters are fitted.']}
with (OUT/'all30-summary-v1.json').open('x') as f:
    json.dump(report, f, indent=2, sort_keys=True, allow_nan=False); f.write('\n')
with (OUT/'all30-tables-v1.md').open('x') as f:
    f.write('# All30 fixed selected-tracking descriptives\n\nEvery cell is included. Errors use stored selected projections and actual executed EEF, not target progress or counterfactual outcomes. MSE has units m²; L2 has units m. Exact lower/equal/higher counts do not establish physical or task benefit.\n\n')
    f.write('| Cell | Guided / mapped | Pairs | Lower / equal / higher MSE | Zero mean pair MSE | Transport mean pair MSE |\n|---|---:|---:|---:|---:|---:|\n')
    for r in rows:
        c = r['transport_vs_zero_counts']
        f.write(f"| {r['cell']} | {r['guided']}/{r['known_selected_tracking']} | {r['eligible_pairs']} | {c.get('lower',0)}/{c.get('equal',0)}/{c.get('higher',0)} | {r['mean_of_pair_zero_mse']:.9g} | {r['mean_of_pair_transported_mse']:.9g} |\n")
    f.write('\n| Cell | Step1 n | Mean absolute L2 at1 | Step8 n | Mean absolute L2 at8 | Mean displacement L2 at8 | Guided sent changed steps | Guided source-unit-bound components |\n|---|---:|---:|---:|---:|---:|---:|---:|\n')
    for r in rows:
        a, b = r['by_step'][0], r['by_step'][7]
        f.write(f"| {r['cell']} | {a['n']} | {a['mean_abs_l2']:.9g} | {b['n']} | {b['mean_abs_l2']:.9g} | {b['mean_disp_l2']:.9g} | {r['guided_sent_decode_changed_steps']} | {r['guided_sent_outside_source_declared_unit_bounds_components']} |\n")
    f.write('\nAll i=1..8 vector means and support remain in all30-summary-v1.json. All individual pairs, origins and exact native references remain in immutable read-v1 cell outputs. No outcomes were joined.\n')
for path, expected in inputs.items(): assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected
print(json.dumps({'totals': report['totals'], 'native_dtypes': report['native_dtypes']}, indent=2))
