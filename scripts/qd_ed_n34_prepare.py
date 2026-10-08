"""Create immutable prospective manifests and a disabled draft, never freeze/adopt."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import qd_ed_n34_bridge as b, qd_ed_n34_contract as c, qd_ed_n23_worker as w


def prepare(directory, runtime_ref, *, runtime_closure_ref, controller_semantics_ref, root=ROOT):
    root, directory = Path(root).resolve(), Path(directory).resolve()
    w.require(not directory.exists(), 'immutable draft directory already exists')
    source = b.closure.source_record(root, b.source_paths(root))
    scientific_source = b.closure.source_record(root, b.scientific_paths(root), commit=b.SCIENTIFIC_COMMIT)
    b.closure.verify_runtime(w.read_ref(runtime_closure_ref), runtime_ref)
    from scripts.qd_ed_n34_controller import verify_semantics
    verify_semantics(controller_semantics_ref, runtime_ref, w.read_ref(runtime_closure_ref))
    runtime = w.read_ref(runtime_ref)
    w.require(runtime['stage_recovered_error_condition'] == b.runner.E2_STAGE_CONDITION
              and runtime['frozen_stage_provider']['backend'] == 'codex_cli', 'official recovered Codex runtime only')
    b.runner.stage_overrides(runtime)
    plan = {'schema': 'n34-release-draft-v1', 'frozen': False, 'release_enabled': False,
            'worktree': str(root), 'artifact_root': str(directory / 'prospective-artifacts'),
            'source': source, 'scientific_source': scientific_source, 'runtime': runtime_ref,
            'runtime_closure': runtime_closure_ref, 'controller_semantics': controller_semantics_ref, 'episodes': c.expected_rows(root),
            'limits': c.LIMITS, 'worker_contract': c.WORKER_CONTRACT, 'deadline': c.DEADLINE, 'stop_path': c.stop_path(root),
            'root_review': None, 'protocol': None, 'authority': None, 'execution_release': None,
            'phase_authorization': {'dev': False, 'validation': False, 'formal': False},
            'expected_manifests': {}, 'http_counters': 'Unknown'}
    for row in plan['episodes']:
        path = directory / 'expected' / (row['episode_key'] + '.json')
        w.atomic_json(path, b.manifest(plan, runtime, row))
        plan['expected_manifests'][row['episode_key']] = c.ref(path)
    c.validate_draft(plan)
    w.atomic_json(directory / 'plan.draft.json', plan)
    return plan


def prepare_candidates(directory, *, root=ROOT):
    """Write explicitly incomplete, disabled candidates without runtime access."""
    root, directory = Path(root).resolve(), Path(directory).resolve()
    w.require(not directory.exists(), 'immutable candidate directory already exists')
    rows = c.expected_rows(root)
    protocol = {'schema': 'n34-production-protocol-CANDIDATE-v1', 'release_enabled': False,
                'cohort': c.COHORT, 'episodes': rows, 'limits': c.LIMITS,
                'worker_contract': c.WORKER_CONTRACT, 'attempt_identity': 'episode_key',
                'deadline': c.DEADLINE,
                'promotion': {'all_valid_cells': 30, 'n34_min_successes': 5,
                              'at_least_both_controls': True, 'matched_controls_required': True},
                'futility': 'complete_valid_triples_only', 'validation_authorized': False,
                'formal_authorized': False, 'carried_control_outcomes': [],
                'dev_gate_is_necessary_not_automatic_promotion': True}
    w.atomic_json(directory / 'protocol.CANDIDATE-v1.json', protocol)
    plan = {'schema': 'n34-production-plan-CANDIDATE-v1', 'frozen': False, 'release_enabled': False,
            'worktree': str(root), 'artifact_root': None, 'episodes': rows,
            'limits': c.LIMITS, 'worker_contract': c.WORKER_CONTRACT,
            'deadline': c.DEADLINE, 'stop_path': c.stop_path(root),
            'operational_commit_candidate': w._source_git(root, 'rev-parse', 'HEAD').decode().strip(),
            'scientific_source_commit': b.SCIENTIFIC_COMMIT,
            'source': None, 'scientific_source': None, 'runtime': None,
            'runtime_closure': None, 'controller_semantics': None, 'authority': None,
            'root_review': None, 'execution_release': None, 'expected_manifests': {},
            'protocol_candidate': c.ref(directory / 'protocol.CANDIDATE-v1.json'),
            'task_definition': c.ref(root / 'configs/qd_ed_final/n31_dev_task_identities.json'),
            'phase_authorization': {'dev': False, 'validation': False, 'formal': False},
            'outcomes': {r['episode_key']: 'Unknown' for r in rows}, 'carried_control_outcomes': [],
            'http_counters': 'Unknown',
            'required_root_steps': ['reconcile current accounting and protected reserves; retain all historical charges',
                'verify fresh attempt IDs against complete owning journal',
                'materialize and verify pinned RDT sources without substituting another revision',
                'review deployed runtime, module closure and actual controller delta semantics',
                'freeze both source identities and all30 external resolved-config manifests',
                'review protocol and official current-login gpt-6-astra condition',
                'wire closed release boundary only after detached root review and release']}
    w.atomic_json(directory / 'plan.CANDIDATE-v1.json', plan)
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--runtime-sha256', required=True)
    parser.add_argument('--runtime-closure', required=True, type=Path)
    parser.add_argument('--controller-semantics', required=True, type=Path)
    args = parser.parse_args()
    plan = prepare(args.output, {'path': str(args.runtime.resolve()), 'sha256': args.runtime_sha256},
                   runtime_closure_ref=c.ref(args.runtime_closure), controller_semantics_ref=c.ref(args.controller_semantics))
    print(json.dumps({'draft': str(args.output / 'plan.draft.json'), 'source_commit': plan['source']['commit'], 'release_enabled': False}))


if __name__ == '__main__':
    main()
