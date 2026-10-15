#!/usr/bin/env python3
"""CPU-only draft builder. Never freezes, dispatches, probes or changes state.

The linked retry must still be unused. A consumed retry is an error, never a
reason to change iteration/key/identity. Existing runner checks remain decisive.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

WORKTREE = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
SOURCE_PLAN = Path('/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z/data/qd-ed-gpu6-c0-native-plan.json')
ORIGINAL_ATTEMPT_ID = 'rdt-qd-ed-final-20260921T093925Z__gpu6_native_c0_t00__6e57273c45b3'
OBSERVATION_FILES = {'main.py', 'core/render_phase_diagnostics.py',
                     'tests/test_episode_phase_timing.py', 'tests/test_render_phase_diagnostics.py'}
DROP_FIELDS = {'diagnostic_only', 'queue_contract', 'hardware_selection',
               'preflight_index', 'preflight_index_sha256', 'frozen_at',
               'native_probe_contract', 'candidate_profiles'}
HARDWARE_FIELDS = {'gpu_mapping', 'cuda_egl_verified', 'cuda_egl_probe',
                   'metadata_mapping_verified', 'egl_device_metadata_path', 'files'}


def load_runner(root):
    sys.path.insert(0, str(root / 'scripts'))
    spec = importlib.util.spec_from_file_location('c0_draft_runner', root / 'scripts/qd_ed_final_runner.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return runner


def recovery_row(source, runner, *, events, retry_of, episode_key):
    runner.require(len(source.get('episodes', [])) == 1, 'source C0 plan must contain exactly one row')
    row = copy.deepcopy(source['episodes'][0])
    expected = {'episode_key': 'gpu6_native_c0_t00', 'split': 'dev',
        'iteration': 'GPU6_NATIVE_C0', 'profile': 'C0', 'task_id': 0,
        'env_seed': 1969522881, 'policy_seed': 1969522881, 'init_index': 0,
        'seed_block': 'dev', 'timeout_seconds': 1800, 'budget_bucket': 'development'}
    runner.require(all(row.get(k) == v for k, v in expected.items()) and not row.get('retry_of'),
                   'original C0 scientific identity changed')
    groups = runner.event_groups(events)
    runner.require(retry_of in groups, 'explicit retry parent is absent from ledger')
    parent_identity = groups[retry_of][0]['identity']
    runner.require(all(event.get('identity') == parent_identity for event in groups[retry_of]),
                   'explicit parent identity is inconsistent across ledger events')
    runner.require(parent_identity == runner.episode_identity(row), 'explicit parent differs from original C0 scientific identity')
    runner.require(isinstance(episode_key, str) and re.fullmatch(r'gpu3_native_c0_t00_r[1-9][0-9]*', episode_key),
                   'new episode key must explicitly name a GPU3 C0 recovery')
    runner.require(not any(event.get('episode_key') == episode_key for event in events), 'episode key already present in ledger')
    row.update(parent_identity)
    row.update(episode_key=episode_key, retry_of=retry_of, budget_bucket='recovery')
    runner.check_retry(events, row)
    return row


def plan_skeleton(base, row):
    plan = copy.deepcopy(base)
    for key in DROP_FIELDS:
        plan.pop(key, None)
    plan.update(frozen=False, episodes=[copy.deepcopy(row)],
        phase_authorization={'dev': True, 'validation': False, 'formal': False},
        diagnostic_scope='One linked full C0 infrastructure recovery; excluded from N1 promotion and repaired cohort',
        recovery_note='Exact linked infrastructure recovery of the GPU6 C0 attempt; physical GPU3 only; unchanged scientific identity and 1800-second timeout.')
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worktree', type=Path, default=WORKTREE)
    parser.add_argument('--source-plan', type=Path, default=SOURCE_PLAN)
    parser.add_argument('--base-plan', type=Path, default=WORKTREE / 'data/qd-ed-native-gpu7-queue-v2-plan.json')
    parser.add_argument('--source-head', required=True)
    parser.add_argument('--retry-of', required=True, help='Exact infrastructure-aborted parent attempt; never inferred')
    parser.add_argument('--episode-key', required=True, help='Exact new unused recovery key; never inferred')
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--protocol', type=Path, required=True, help='Committed path relative to worktree, or absolute within it')
    parser.add_argument('--output', type=Path, required=True, help='New draft under this run artifact root')
    args = parser.parse_args(argv)
    root = args.worktree.resolve()
    r = load_runner(root)
    try:
        source = r.read_json(args.source_plan)
        base = r.read_json(args.base_plan)
        # First gate, before file creation or expensive validation. In particular,
        # another worktree reserving this retry consumes it even before dispatch.
        row = recovery_row(source, r, events=r.read_events(root / 'data/attempt-ledger.jsonl'),
                           retry_of=args.retry_of, episode_key=args.episode_key)
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
        r.require(head == args.source_head, 'requested source HEAD is not current committed HEAD')
        protocol = r.owned(args.protocol if args.protocol.is_absolute() else root / args.protocol, root)
        protocol_relative = str(protocol.relative_to(root))
        runtime_path = r.owned(args.runtime, base['artifact_root'])
        runtime = r.read_json(runtime_path)
        r.require(r.runtime_gpu(runtime) == 3, 'this draft authorizes physical GPU3 only')
        previous_runtime = r.read_json(base['runtime_manifest_path'])
        r.require(r.digest(base['runtime_manifest_path']) == base['runtime_manifest_sha256'], 'base runtime fingerprint changed')
        r.require({k: v for k, v in runtime.items() if k not in HARDWARE_FIELDS} ==
                  {k: v for k, v in previous_runtime.items() if k not in HARDWARE_FIELDS},
                  'nonhardware runtime/provider/cache identity changed')
        def nonhardware_files(item):
            return [record for record in item['files'] if record['path'] != item.get('egl_device_metadata_path')]
        r.require(nonhardware_files(runtime) == nonhardware_files(previous_runtime), 'nonhardware runtime file inventory changed')
        for label in ('profiles', 'runtime_inventory', 'seed_plan'):
            r.require(base[label + '_sha256'] == source[label + '_sha256'], label + ' differs from original C0')
            r.require(r.digest(base[label + '_path']) == base[label + '_sha256'], label + ' frozen input changed')
        r.require(base['stage_condition'] == source['stage_condition'], 'Stage scientific condition changed')
        r.require(base['input_contract_label'] == source['input_contract_label'], 'input repair contract changed')
        plan = plan_skeleton(base, row)
        scientific_files = set(base['scientific_config_files']) | {protocol_relative}
        code_paths = {item['path'] for item in base['code_files']} | r.REQUIRED_CODE | OBSERVATION_FILES | scientific_files
        baseline_fingerprints = {item['path']: item['sha256'] for item in base['code_files']}
        for relative in code_paths:
            path = r.owned(root / relative, root)
            if relative in baseline_fingerprints and relative not in OBSERVATION_FILES and not relative.startswith('experiments/'):
                r.require(r.digest(path) == baseline_fingerprints[relative],
                          'non-observation source/config changed: ' + relative)
            tracked = subprocess.run(['git', 'ls-files', '--error-unmatch', '--', relative], cwd=root,
                                     text=True, capture_output=True)
            r.require(tracked.returncode == 0, 'fingerprinted source is not committed: ' + relative)
            committed = subprocess.check_output(['git', 'show', head + ':' + relative], cwd=root)
            r.require(path.read_bytes() == committed, 'fingerprinted source differs from HEAD: ' + relative)
        plan.update(source_commit=head, runtime_manifest_path=str(runtime_path),
            runtime_manifest_sha256=r.digest(runtime_path), egl_mapping_verified=runtime.get('cuda_egl_verified') is True,
            scientific_config_files=sorted(scientific_files), resource_amendment=protocol_relative,
            recovery_protocol=protocol_relative,
            code_files=[{'path': relative, 'sha256': r.digest(root / relative)} for relative in sorted(code_paths)],
            recovery_provenance={'source_plan_path': str(args.source_plan.resolve()),
                'source_plan_sha256': r.digest(args.source_plan), 'base_plan_path': str(args.base_plan.resolve()),
                'base_plan_sha256': r.digest(args.base_plan), 'retry_of': args.retry_of,
                'parent_identity': r.episode_identity(row),
                'physical_gpu': 3, 'builder_path': str(Path(__file__).resolve()), 'builder_sha256': r.digest(__file__)})
        # Source/runtime inspection may take time; refresh the shared retry gate.
        r.check_retry(r.read_events(root / 'data/attempt-ledger.jsonl'), row)
        output = r.owned(args.output, base['artifact_root'])
        r.require(not output.exists(), 'refusing to overwrite an existing draft')
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x') as stream:
            json.dump(plan, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write('\n')
        # CPU structure/source/cache validation. No full checkpoint byte pass;
        # the final queue performs that once before resource admission.
        r.validate_plan(output, root=root, require_frozen=False)
        print(json.dumps({'draft': str(output), 'sha256': r.digest(output), 'frozen': False,
            'episode_key': args.episode_key, 'identity': r.episode_identity(row), 'physical_gpu': 3,
            'GPU_launches': 0, 'full_model_hash_passes': 0}, indent=2))
        return 0
    except (r.GateError, KeyError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        # Gate messages contain only public input identities, not provider state.
        print(json.dumps({'error': str(exc), 'frozen': False, 'GPU_launches': 0}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
