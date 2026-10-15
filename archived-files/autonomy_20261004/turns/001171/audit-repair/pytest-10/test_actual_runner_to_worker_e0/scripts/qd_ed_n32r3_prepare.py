"""CPU manifest composition only. Never creates/adopts a release or runs a worker."""
import argparse
import json
from pathlib import Path
from scripts import qd_ed_n23_worker as w, qd_ed_n32r3_bridge as b
from scripts import qd_ed_n32r3_contract as c, qd_ed_n32r3_release as release
from scripts.qd_ed_n32r3_history import validate_mapping


def compose(plan_ref, destination):
    plan = w.read_ref(plan_ref)
    # A separate operational source approval precedes composition. The input is
    # still disabled; manifests alone cannot grant execution authority.
    w.require(plan['schema'] == 'n32r3-composition-input-v1' and plan['release_enabled'] is False
              and plan['episodes'] == c.expected_rows(plan['worktree']), 'disabled composition input required')
    validate_mapping(plan)
    release.verify_continuity(plan)
    w.verify_source(plan['worktree'], plan['source'])
    runtime = w.read_ref(plan['runtime'])
    destination = Path(destination).resolve()
    b.runner.owned(destination, plan['artifact_root'])
    w.require(not destination.exists(), 'manifest destination exists')
    # Compose everything before writing, and never reuse old config digests.
    manifests = [b.manifest(plan, runtime, row) for row in plan['episodes']]
    refs = {}
    for manifest in manifests:
        key = manifest['row']['episode_key']
        path = destination / (key + '.json')
        w.atomic_json(path, manifest)
        refs[key] = c.ref(path)
    w.atomic_json(destination / 'manifest-index.json', {'schema': 'n32r3-manifest-index-v1',
                  'plan': plan_ref, 'release_enabled': False, 'expected_manifests': refs})
    return refs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('plan', 'plan-sha256', 'destination'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    print(json.dumps(compose({'path': str(Path(args.plan).resolve()), 'sha256': args.plan_sha256}, args.destination)))


if __name__ == '__main__':
    main()
