"""Read-only CPU verification and immutable DISABLED continuation candidates.

This command never creates an approved release, adopts state or dispatches.
Root must separately freeze the new operational/runtime closure and release.
"""
import argparse
import json
from pathlib import Path

from scripts import qd_ed_n23_worker as w, qd_ed_n34_contract as c
from scripts import qd_ed_n34_continuation as cc, qd_ed_n34_bridge as b

LEDGERS = {'attempt-ledger.jsonl', 'gpu-healthcheck-ledger.jsonl', 'gpu-hour-reservation-ledger.jsonl'}


def validate_candidate(plan, *, ledger_directory):
    design, original, terminal = cc.load_design(plan['design'])
    cc.validate_shape(plan, design, original)
    w.require(plan['schema'] == 'n34-continuation-draft-v1' and plan['frozen'] is False
              and plan['release_enabled'] is False
              and plan['phase_authorization'] == {'dev': False, 'validation': False, 'formal': False}
              and all(plan[k] is None for k in ('authority', 'root_review', 'execution_release', 'source',
                                               'runtime', 'runtime_closure', 'controller_semantics', 'scientific_equality'))
              and all(v is None for v in plan['expected_manifests'].values()), 'candidate cannot confer release')
    authority = w.read_ref(plan['implementation_authority'])
    w.require(authority['schema'] == 'n34-continuation-cpu-implementation-authority-v1'
              and authority['status'] == 'CPU_ONLY_NO_GPU_RELEASE' and authority['gpu_authorized'] is False
              and authority['source'] == cc.BASE and authority['design'] == plan['design'], 'CPU authority differs')
    anchors = plan['ledger_prefixes']
    w.require(set(anchors) == LEDGERS and anchors == authority['ledger_prefixes']
              and anchors['attempt-ledger.jsonl'] == design['ledger_prefix']
              and all(anchors[k] == {a: terminal['ledger_prefixes'][k][a] for a in ('bytes', 'sha256')}
                      for k in LEDGERS), 'candidate prefix anchors differ')
    for name, anchor in anchors.items():
        raw = cc.read_prefix(Path(ledger_directory) / name, anchor)
        if name == 'gpu-healthcheck-ledger.jsonl':
            w.require(plan['resource_prefix_event_count'] == len(raw.splitlines()), 'resource prefix count differs')
    retained = cc.verify_retained(design, original, terminal, Path(ledger_directory) / 'attempt-ledger.jsonl')
    w.require(plan['retained_outcomes'] == retained and plan['scientific_source'] == original['scientific_source'],
              'candidate retained/scientific source differs')
    return cc.summarize(retained, 'CPU_PREPARATION_ONLY_NOT_EXECUTION_RELEASE')


def prepare(directory, authority_ref, *, root=c.ROOT):
    directory, root = Path(directory).resolve(), Path(root).resolve()
    w.require(not directory.exists(), 'immutable candidate directory already exists')
    authority = w.read_ref(authority_ref)
    design, original, terminal = cc.load_design(authority['design'], root)
    ledger_directory = Path(original['worktree']) / 'data'
    retained = cc.verify_retained(design, original, terminal, ledger_directory / 'attempt-ledger.jsonl')
    resources = cc.read_prefix(ledger_directory / 'gpu-healthcheck-ledger.jsonl',
                               authority['ledger_prefixes']['gpu-healthcheck-ledger.jsonl'])
    plan = {'schema': 'n34-continuation-draft-v1', 'label': cc.LABEL, 'frozen': False,
        'release_enabled': False, 'worktree': str(root), 'artifact_root': None,
        'implementation_authority': authority_ref, 'design': authority['design'],
        'predecessor_plan': design['predecessor_plan'], 'terminal_reconciliation': design['terminal_reconciliation'],
        'retained_episode_keys': design['retained_valid_episode_keys'], 'retained_outcomes': retained,
        'episodes': design['unobserved_original_rows'], 'identity_mapping': cc.mapping(design),
        'ledger_prefixes': authority['ledger_prefixes'], 'resource_prefix_event_count': len(resources.splitlines()),
        'limits': cc.LIMITS, 'gates': cc.GATES, 'worker_contract': c.WORKER_CONTRACT,
        'scientific_interpretation': design['scientific_interpretation'], 'scientific_source': original['scientific_source'],
        'deadline': c.DEADLINE, 'stop_path': original['stop_path'],
        'source': None, 'runtime': None, 'runtime_closure': None, 'controller_semantics': None,
        'scientific_equality': None, 'authority': None, 'root_review': None, 'execution_release': None,
        'phase_authorization': {'dev': False, 'validation': False, 'formal': False},
        'automatic_promotion': False, 'root_scientific_review_required': True,
        'expected_manifests': {r['episode_key']: None for r in design['unobserved_original_rows']},
        'required_root_steps': [
            'Review outcome-aware amendment and exact retained evidence equivalence.',
            'Adopt reviewed operational commit; attest exact scientific equality to base.',
            'Freeze runtime, same-worker/provider/source closure and only missing11 manifests.',
            'Bind separate root authority, review and detached continuation release; preserve old plan.',
            'Reconcile all costs and protected reserves under normal runner/state locks.',
            'After amended Dev screen, explicit root scientific review before fresh matched validation.']}
    summary = validate_candidate(plan, ledger_directory=ledger_directory)
    w.atomic_json(directory / 'plan.DISABLED-v1.json', plan)
    w.atomic_json(directory / 'summary.DISABLED-v1.json', summary)
    return plan


def prepare_manifests(plan, directory):
    """Root freeze helper: new missing11 manifests only; creates no approval.

    Caller supplies a populated disabled draft with new committed source/runtime.
    Full released validation remains mandatory, including retained verification.
    """
    from scripts import qd_ed_n34_continuation_release as release
    design, original, _ = cc.load_design(plan['design'])
    cc.validate_shape(plan, design, original)
    w.require(plan['schema'] == 'n34-continuation-draft-v1' and plan['release_enabled'] is False
              and plan['frozen'] is False and plan['phase_authorization'] ==
              {'dev': False, 'validation': False, 'formal': False}, 'manifest preparation stays disabled')
    directory = Path(directory).resolve()
    w.require(not directory.exists(), 'immutable manifest directory exists')
    equality = release.source_equivalence(plan['worktree'], original, plan['source'])
    w.require(plan['scientific_source'] == original['scientific_source'], 'science identity differs')
    runtime = w.read_ref(plan['runtime'])
    b.closure.verify_runtime(w.read_ref(plan['runtime_closure']), plan['runtime'])
    from scripts.qd_ed_n34_controller import verify_semantics
    verify_semantics(plan['controller_semantics'], plan['runtime'], w.read_ref(plan['runtime_closure']))
    b.runner.stage_overrides(runtime)
    w.require(runtime['frozen_stage_provider'] == w.read_ref(original['runtime'])['frozen_stage_provider'],
              'frozen provider differs')
    result = {}
    for row in plan['episodes']:
        path = directory / (row['episode_key'] + '.json')
        w.atomic_json(path, b.manifest(plan, runtime, row))
        result[row['episode_key']] = c.ref(path)
    w.atomic_json(directory / 'scientific-equality-v1.json', equality)
    return result, c.ref(directory / 'scientific-equality-v1.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authority', required=True)
    parser.add_argument('--authority-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    plan = prepare(args.output, {'path': str(Path(args.authority).resolve()), 'sha256': args.authority_sha256})
    print(json.dumps({'label': plan['label'], 'release_enabled': False, 'gpu_dispatched': False}))


if __name__ == '__main__':
    main()
