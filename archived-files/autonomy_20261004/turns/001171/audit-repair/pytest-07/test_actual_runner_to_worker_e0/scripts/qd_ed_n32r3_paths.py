"""Explicit prospective path amendment; the original preparation stays immutable.

The disabled amendment is evidence only. Adoption requires a new plan, composed
manifests and detached root review/release committing its exact reference.
"""
from pathlib import Path
from scripts import qd_ed_n23_worker as w, qd_ed_n32r3_contract as c

OUTPUT_FIELDS = {'hydra.run.dir': '', 'main.eds_eval.output_dir': '/eds_eval',
                 'main.eds_mechanism_pretest.output_dir': '/mechanism'}
IDENTITY_FIELDS = set(OUTPUT_FIELDS) | {'main.eds_eval.job_id',
    'main.eds_mechanism_pretest.run_id', 'main.eds_config.n32_runtime_binding'}


def changes(before, after):
    w.require(len(before) == len(after), 'command length changed')
    return [{'index': i, 'old': a, 'new': b}
            for i, (a, b) in enumerate(zip(before, after)) if a != b]


def verify_original(candidate):
    """Check the original parent/old argv and exact prepared delta, even amended."""
    parent = c.read_ref(candidate['parent_expected_manifest'])
    w.require(candidate['old_argv'] == parent['argv'], 'parent command anchor')
    delta = changes(parent['argv'], candidate['proposed_argv'])
    w.require(delta == candidate['exact_changes'] and all(
        x['old'].split('=', 1)[0] == x['new'].split('=', 1)[0] in IDENTITY_FIELDS
        for x in delta), 'non-identity command change')
    return parent


def expected_amendment(plan):
    """Derive the sole permissible amendment, after validating the old map/review."""
    from scripts.qd_ed_n32r3_history import validate_mapping
    from scripts.qd_ed_final_runner import owned
    mapping, parent = validate_mapping(plan)
    commands = c.read_ref(plan['command_candidates'])['commands']
    rows = c.expected_rows(plan['worktree'])
    w.require(plan['episodes'] == rows and len(commands) == 16
              and [x['new_attempt_id'] for x in commands] == [r['episode_key'] for r in rows],
              'exact16 original command cells')
    root = Path(plan['artifact_root'])
    runtime = c.read_ref(plan['runtime'])
    owned(root, runtime['artifact_root'])
    w.require(root.resolve() != Path(runtime['artifact_root']).resolve(), 'distinct amendment artifact root')
    pairs = []
    for candidate, entry, row in zip(commands, mapping['proposed_cells'], rows):
        original = verify_original(candidate)
        w.require(candidate['old_attempt_id'] == entry['old_attempt_id']
                  and candidate['parent_expected_manifest'] == entry['parent_expected_manifest']
                  and original['row'] == entry['old_row']
                  and original['source'] == parent['source']
                  and original['runtime'] == parent['runtime'], 'amendment parent identity')
        output = candidate['proposed_output_dir']
        resolved = Path(output).resolve()
        owned(resolved, root)
        w.require(Path(output).is_absolute()
                  and resolved == (root / 'attempts' / row['episode_key']).resolve(),
                  'amendment intended output')
        argv = list(candidate['proposed_argv'])
        for field, suffix in OUTPUT_FIELDS.items():
            indices = [i for i, token in enumerate(argv) if token.split('=', 1)[0] == field]
            w.require(len(indices) == 1, 'unique output-directory field')
            i = indices[0]
            w.require(argv[i] == field + '=' + output + suffix, 'original output-directory layout')
            target = Path(output + suffix).resolve()
            owned(target, root)
            w.require(target == Path(str(resolved) + suffix), 'output subdirectory redirected')
            argv[i] = field + '=' + str(target)
        delta = changes(candidate['proposed_argv'], argv)
        w.require(len(delta) == 3, 'exactly three resolved output-directory changes')
        pairs.append({'old_attempt_id': candidate['old_attempt_id'], 'new_attempt_id': row['episode_key'],
                      'row': row, 'parent_expected_manifest': candidate['parent_expected_manifest'],
                      'original_argv': candidate['proposed_argv'], 'amended_argv': argv,
                      'original_output_dir': output, 'amended_output_dir': str(resolved),
                      'exact_changes': delta})
    return {'schema': 'n32r3-command-path-amendment-v1', 'release_enabled': False,
            **{k: plan[k] for k in ('parent_plan', 'parent_release', 'parent_review',
                'preparation_review', 'carry_forward_map', 'command_candidates',
                'scientific_source', 'runtime', 'worktree', 'artifact_root')}, 'pairs': pairs}


def verify_amendment(plan):
    amendment = c.read_ref(plan['command_path_amendment'])
    w.require(amendment == expected_amendment(plan), 'exact prospective command-path amendment')
    return amendment
