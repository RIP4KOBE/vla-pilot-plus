"""Inspect actual frozen inputs and build40 commands without dispatch or adoption."""
import copy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'implementation'
sys.path.insert(0, str(SOURCE))
from scripts import qd_ed_final_runner as runner
from scripts import qd_ed_n23_dev_contract as contract
from scripts import qd_ed_n23_worker as worker
import torch


def main():
    draft = HERE / 'plan.dev.draft-v2.json'
    plan = runner.read_json(draft)
    source = worker.source_record(SOURCE, [v['path'] for v in plan['code_files']])
    assert source['commit'] == plan['source_commit'] and source['files'] == plan['code_files']
    assert plan['frozen'] is False and plan['n23_cohort']['backend_proof'] is None
    manifest = runner.read_json(plan['profiles_path'])
    original = copy.deepcopy(manifest)
    assert set(manifest['profiles']) == {'C0', 'Q0'}
    assert worker.sha(plan['profiles_path']) == plan['profiles_sha256']
    for arm, reference in plan['candidate_profiles'].items():
        assert worker.sha(reference['path']) == reference['sha256']
        manifest['profiles'][arm] = runner.expand_candidate(arm, runner.read_json(reference['path']), manifest['profiles']['Q0'])
    assert all(manifest['profiles'][a] == original['profiles'][a] for a in ('C0','Q0'))
    n7 = manifest['profiles']['N7']['resolved_eds_config']
    n23 = manifest['profiles']['N23']['resolved_eds_config']
    assert n23 == {**n7, 'qd_quality_mode': 'actuator_clipped_provider_v1'}
    assert plan['episodes'] == contract.expected_rows()
    runtime = runner.read_json(plan['runtime_manifest_path'])
    assert worker.sha(plan['runtime_manifest_path']) == plan['runtime_manifest_sha256']
    commands = []
    for row in plan['episodes']:
        attempt = 'cpu_not_dispatched__' + row['episode_key']
        command, output = runner.build_command(plan, manifest, runtime, row, attempt)
        assert command[:2] == [str(runner.PYTHON), str(SOURCE/'main.py')]
        assert not output.exists()
        commands.append({'task_id': row['task_id'], 'profile': row['profile'],
                         'argv_sha256': worker.canonical_sha(command), 'argc': len(command)})
    assert len(commands) == 40
    assert not torch.cuda.is_initialized()
    report = {'schema': 'n23-root-real-profile-command-precheck-v1',
              'draft': {'path': str(draft), 'sha256': worker.sha(draft)},
              'reader_sha256': worker.sha(__file__), 'source_commit': source['commit'],
              'source_files': len(source['files']), 'source_manifest_sha256': source['sha256'],
              'commands': commands, 'exact_N7_to_N23_delta': {'qd_quality_mode': 'actuator_clipped_provider_v1'},
              'baseline_profiles_unchanged': True, 'original_dev_matrix': True,
              'cuda_initialized': False, 'dispatched': False,
              'limit': 'CPU composition of actual profile/input/argv only. Not a full owning-plan validation, Hydra execution, runtime admission or CUDA proof. Draft remains unfrozen with missing prerequisites; integration and actual backend preflight still required.'}
    output = HERE / 'root-profile-command-precheck-result-v1.json'
    with output.open('x') as f:
        json.dump(report, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps({k: report[k] for k in ('source_commit','source_files','baseline_profiles_unchanged','original_dev_matrix','cuda_initialized','dispatched')}))
    print(json.dumps({'result':str(output),'sha256':worker.sha(output),'commands_built':len(commands)}))


if __name__ == '__main__':
    main()
