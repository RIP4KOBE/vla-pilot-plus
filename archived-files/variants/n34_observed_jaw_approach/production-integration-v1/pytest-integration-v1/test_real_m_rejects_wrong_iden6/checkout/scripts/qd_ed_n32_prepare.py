"""Create immutable prospective manifests and a disabled draft, never freeze/adopt."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import qd_ed_n32_bridge as b, qd_ed_n32_contract as c, qd_ed_n23_worker as w


def prepare(directory, runtime_ref, *, root=ROOT):
    root, directory = Path(root).resolve(), Path(directory).resolve()
    w.require(not directory.exists(), 'immutable draft directory already exists')
    source = w.source_record(root, b.source_paths(root))
    runtime = w.read_ref(runtime_ref)
    w.require(runtime['stage_recovered_error_condition'] == b.runner.E2_STAGE_CONDITION
              and runtime['frozen_stage_provider']['backend'] == 'codex_cli', 'official recovered Codex runtime only')
    b.runner.stage_overrides(runtime)
    plan = {'schema': 'n32-release-draft-v1', 'frozen': False, 'release_enabled': False,
            'worktree': str(root), 'artifact_root': str(directory / 'prospective-artifacts'),
            'source': source, 'runtime': runtime_ref, 'episodes': c.expected_rows(root),
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--runtime-sha256', required=True)
    args = parser.parse_args()
    plan = prepare(args.output, {'path': str(args.runtime.resolve()), 'sha256': args.runtime_sha256})
    print(json.dumps({'draft': str(args.output / 'plan.draft.json'), 'source_commit': plan['source']['commit'], 'release_enabled': False}))


if __name__ == '__main__':
    main()
