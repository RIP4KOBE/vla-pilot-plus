"""Read saved native Dev actions and their next observed origin; no execution."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import torch

HERE = Path(__file__).resolve().parent
SESSION = HERE.parents[1]
ROOT = SESSION / 'study_worktree'
CONFIG = Path('/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/robosuite/controllers/config/osc_pose.json')
PATTERNS = {'n17_n7_task0': '*n17_physics_t00_n7_*',
            'n17_n7_task9': '*n17_physics_t09_n7_*',
            'n21_task0': '*n21_dev_t00_n21_*'}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def tensor(value):
    return torch.as_tensor(value).double().reshape(-1)

def distribution(values):
    if not values:
        return {'count': 0}
    return {'count': len(values), 'mean': statistics.mean(values),
            'median': statistics.median(values), 'min': min(values), 'max': max(values)}

def analyze(label, pattern, scale):
    attempts = list((SESSION / 'artifacts/attempts').glob(pattern))
    assert len(attempts) == 1
    attempt = attempts[0]
    result = json.loads((attempt / 'attempt-result.json').read_text())
    audit_path = attempt / 'eds_eval/decision-evidence-audit.json'
    audit = json.loads(audit_path.read_text())
    assert result['outcome_valid'] and audit['accepted'] and audit['evidence_complete']
    ep = attempt / 'eds_eval/decision_evidence/episode_000'
    contexts, events, references = {}, {}, []
    for line in (ep / 'events.jsonl').open():
        ref = json.loads(line)
        path = ep / ref['bundle']
        assert sha(path) == ref['sha256']
        references.append({'path': str(path), 'sha256': ref['sha256']})
        for e in torch.load(path, map_location='cpu', weights_only=True)['events']:
            key = e.get('decision_id')
            if key is None:
                continue
            events.setdefault(key, []).append(e)
            if e['event'] == 'decision_context':
                assert e['global_step'] not in contexts
                contexts[e['global_step']] = e
    paired, excluded = [], Counter()
    origins = {}
    for step, ctx in contexts.items():
        ev = events[ctx['decision_id']]
        sent = [e for e in ev if e['event'] == 'executed_action']
        if not sent:
            continue
        before = [e for e in ev if e['event'] == 'projection_origin'
                  and ctx['sequence'] < e['sequence'] < sent[0]['sequence']]
        if before:
            origins[step] = (tensor(before[0]['values']['source_eef_position']), before[0])
    for step, ctx in sorted(contexts.items()):
        ev = events[ctx['decision_id']]
        nxt = contexts.get(step + 8)
        if nxt is None:
            excluded['no_next_eight_step_context'] += 1
            continue
        if (ctx['episode'], ctx['reset_sequence']) != (nxt['episode'], nxt['reset_sequence']):
            excluded['episode_or_reset_changed'] += 1
            continue
        if step not in origins or step + 8 not in origins:
            excluded['missing_preexecution_source_origin'] += 1
            continue
        sent = [e for e in ev if e['event'] == 'executed_action']
        returned = [e for e in ev if e['event'] == 'step_returned']
        if len(sent) != 8 or len(returned) != 8:
            excluded['not_eight_actions_and_returns'] += 1
            continue
        assert [e['global_step'] for e in sent] == list(range(step, step + 8))
        actual_actions = torch.stack([tensor(e['values']['action_numpy']) for e in sent])
        decoded = next(e for e in ev if e['event'] == 'policy_action_decode')
        actions = tensor(decoded['values']['action_chunk']).reshape(8, 7)
        assert torch.equal(actions, actual_actions)
        start, origin_event = origins[step]
        end, next_origin_event = origins[step + 8]
        actual_delta = end - start
        sums = actions[:, :3].sum(0)
        clipped_sums = actions[:, :3].clamp(-1, 1).sum(0)
        predictions = {'raw_001': sums * .01, 'clipped_001': clipped_sums * .01,
                       'controller_clipped': clipped_sums * scale}
        finals = [e for e in ev if e['event'] == 'final_selection']
        if finals and finals[0]['values'].get('terminal_population'):
            f = finals[0]['values']
            sid = f['terminal_population']['scoring_batch_id']
            score = next(e for e in ev if e['sequence'] == sid)
            xyz = score['values']['projected_xyz'][int(f['selected_index'])].double()
            predictions['stored_native'] = xyz[-1] - start
        row = {'step': step, 'decision_id': ctx['decision_id'],
               'guided': ctx['values']['use_guidance'],
               'origin_sequence': origin_event['sequence'],
               'next_origin_sequence': next_origin_event['sequence'],
               'start_eef_m': start.tolist(), 'next_eef_m': end.tolist(),
               'actual_displacement_m': actual_delta.tolist(),
               'actual_displacement_norm_m': float(actual_delta.norm()),
               'raw_translation_sum': sums.tolist(), 'clipped_translation_sum': clipped_sums.tolist(),
               'saturated_translation_components': int((actions[:, :3].abs() > 1).sum()),
               'errors_m': {name: float((pred - actual_delta).norm()) for name, pred in predictions.items()},
               'predicted_displacements_m': {name: pred.tolist() for name, pred in predictions.items()}}
        paired.append(row)
    stats = {}
    for group in ('all', 'guided', 'unguided'):
        subset = [x for x in paired if group == 'all' or x['guided'] == (group == 'guided')]
        stats[group] = {'chunks': len(subset),
                        'actual_displacement_m': distribution([x['actual_displacement_norm_m'] for x in subset]),
                        'errors_m': {name: distribution([x['errors_m'][name] for x in subset if name in x['errors_m']])
                                     for name in ('raw_001', 'clipped_001', 'controller_clipped', 'stored_native')},
                        'saturated_translation_components': sum(x['saturated_translation_components'] for x in subset)}
    return {'label': label, 'attempt_id': attempt.name, 'source_success': result['success'],
            'native_audit_sha256': sha(audit_path), 'contexts': len(contexts),
            'source_origins_available': len(origins), 'excluded': dict(excluded),
            'summary': stats, 'paired_records': paired, 'verified_bundles': references}

def main():
    torch.set_num_threads(1)
    cfg = json.loads(CONFIG.read_text())
    assert cfg['input_min'] == -1 and cfg['input_max'] == 1
    assert cfg['output_max'][:3] == [.05] * 3 and cfg['output_min'][:3] == [-.05] * 3
    sources = [CONFIG, CONFIG.parents[1] / 'base_controller.py', CONFIG.parents[1] / 'osc.py',
               ROOT / 'core/env_adapters/libero_adapter.py', ROOT / 'core/rdt_policy_steer.py',
               ROOT / 'third_party/libero_pro/libero/libero/envs/env_wrapper.py',
               HERE / 'protocol-readonly-v1.md']
    report = {'schema': 'readonly-executed-projection-audit-v1',
              'source_refs': [{'path': str(p), 'sha256': sha(p)} for p in sources],
              'paths': [], 'controller_scale_m': .05,
              'caveat': 'Three correlated exposed Dev paths; predictions are analytic proxies, not alternate-action outcomes. No fitted model, simulation or source changes. Installed controller target scale does not guarantee realized displacement.'}
    for label, pattern in PATTERNS.items():
        path = analyze(label, pattern, cfg['output_max'][0])
        report['paths'].append(path)
        print(json.dumps({'label': label, 'contexts': path['contexts'], 'excluded': path['excluded'],
                          'summary': path['summary']}), flush=True)
    out = HERE / 'audit-result-v1.json'
    assert not out.exists()
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')

if __name__ == '__main__':
    main()
