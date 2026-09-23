#!/usr/bin/env python3
"""Reproduce the bounded task0/task5 source review without importing/executing providers.

Only compile and marshal CodeType values. No tensor, simulator, network or runtime
episode imports/reads. Expected source hashes deliberately make this review fail
if the reviewed source has changed.
"""
import argparse
import hashlib
import json
import marshal
from pathlib import Path
import sys
import types

EXPECTED = {
    1: 'd374557f569b8c69f898a1596dfefd32a21774929511bb969d5d27e0050d4830',
    2: 'ca058cc1dcf87ce5910181800bb2f65b8cd4d92788b27f3b10b1e33dbc103f84',
}
LOADER_SHA = 'b0fe9d6d5fc014143f5877918de9bd0986b1688b4a6a90980847b7d15cab0c82'


def digest(value):
    return hashlib.sha256(value).hexdigest()


def nested(code):
    yield code
    for constant in code.co_consts:
        if isinstance(constant, types.CodeType):
            yield from nested(constant)


def loader_text(raw):
    # Exact string replacement order in the SHA-bound load_functions_from_txt.
    text = raw.replace('np.array(', 'torch.tensor(').replace('numpy.array(', 'torch.tensor(')
    for original, replacement in {
        'np.zeros': 'torch.zeros', 'np.ones': 'torch.ones', 'np.linalg.norm': 'torch.norm',
        'np.sum': 'torch.sum', 'np.mean': 'torch.mean', 'np.max': 'torch.max',
        'np.min': 'torch.min', 'np.sqrt': 'torch.sqrt', 'np.abs': 'torch.abs',
        'np.exp': 'torch.exp', 'np.log': 'torch.log',
    }.items():
        text = text.replace(original, replacement)
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--production-worktree', required=True, type=Path)
    parser.add_argument('--artifact-root', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    assert sys.version_info[:2] == (3, 12) and sys.flags.optimize == 0
    worktree = args.production_worktree.resolve()
    loader = worktree / 'utils/guidance_utils.py'
    raw_loader = loader.read_bytes()
    assert digest(raw_loader) == LOADER_SHA, 'loader differs from reviewed source'
    module = compile(raw_loader.decode('utf-8'), str(loader), 'exec', flags=0, dont_inherit=True, optimize=0)
    wrapped = next(code for code in nested(module)
                   if code.co_qualname == 'wrap_guidance_function_with_device_fix.<locals>.wrapped')
    wrapper_sha = digest(marshal.dumps(wrapped))
    reviews, targets = [], []
    files = {str(loader): digest(raw_loader)}
    for task in (0, 5):
        directory = args.artifact_root.resolve() / 'runtime/guidance' / f'task_{task}'
        metadata_path = directory / 'metadata.json'
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        files[str(metadata_path)] = digest(metadata_path.read_bytes())
        assert metadata['qd_ed_task_identity']['task_id'] == task
        for stage in (1, 2):
            path = directory / f'stage{stage}_guidance.txt'
            raw = path.read_bytes()
            assert digest(raw) == EXPECTED[stage], 'cached source differs from reviewed source'
            source = path.read_text(encoding='utf-8')
            transformed = loader_text(source)
            assert transformed == source, 'reviewed files must have unchanged loader text'
            compiled = compile(transformed, '<string>', 'exec', flags=0, dont_inherit=True, optimize=0)
            original = next(code for code in compiled.co_consts
                            if isinstance(code, types.CodeType) and code.co_name == f'stage{stage}_guidance')
            identity = {'original_code_sha256': digest(marshal.dumps(original)),
                        'source_text_sha256': digest(transformed.encode('utf-8')),
                        'source_path': str(path), 'source_sha256': digest(raw)}
            files[str(path)] = digest(raw)
            reviews.append({**identity, 'task_id': task, 'stage': stage,
                'original_function_name': original.co_name, 'static_compile_filename': original.co_filename,
                'target_kind': 'fixed_keypoint_0' if stage == 1 else 'none_constant_reward',
                'keypoint_metadata_label': metadata['key_points_objects_map']['0'] if stage == 1 else None,
                'objective': 'negative normalized positive-weight squared EEF distance over provider input'
                             if stage == 1 else 'constant 0 on trajectory device; no keypoint read',
                'runtime_identity_status': 'NOT_OBSERVED; pending exact original-code/text/path match'})
            if stage == 1:
                targets.append({**identity, 'source_text_transform': 'identity',
                    'target_selection': 'fixed_keypoint_index', 'keypoint_index': 0,
                    'target_expression': 'target_idx = torch.tensor([0], ...); target_pos = keypoints[target_idx][0]',
                    'reviewed_against_frozen_provider_source': True,
                    'distance_progress_interpretation': 'approach_proxy',
                    'approach_review_basis': 'reward = -(all_dists ** 2 * weights).sum(dim=1); all weights are positive and normalized; all_dists = torch.norm(action_sequence - target_pos, dim=-1)',
                    'objective_limit': 'weighted whole scored prefix, not endpoint-only, grasp, contact or live-object success',
                    'task_id_for_review_only': task, 'stage_for_review_only': stage,
                    'keypoint_metadata_label': metadata['key_points_objects_map']['0'],
                    'expected_shared_wrapper_code_sha256': wrapper_sha,
                    'static_original_hash_status': 'pending exact runtime identity match',
                    'loader_source_path': str(loader), 'loader_source_sha256': LOADER_SHA})
    report = {'schema': 'qd-ed-static-provider-source-review-v1',
        'python': sys.version, 'marshal_version': marshal.version, 'optimize': sys.flags.optimize,
        'compile_flags': 0, 'compile_dont_inherit': True, 'compile_optimize': 0,
        'provider_function_executions': 0, 'runtime_episodes_read': 0,
        'torch_imported': 'torch' in sys.modules,
        'wrapper_code_sha256_static_candidate': wrapper_sha,
        'wrapper_limitation': 'same wrapper bytecode for every captured original function; insufficient target identity',
        'reviews': reviews, 'reviewed_file_sha256': files,
        'generator_sha256': digest(Path(__file__).read_bytes())}
    assert not report['torch_imported']
    args.output_dir.mkdir(parents=True, exist_ok=False)
    for name, data in [('review.json', report), ('provider-target-map-v2.json',
            {'schema': 'qd-ed-provider-target-map-v2', 'entries': targets})]:
        with (args.output_dir / name).open('x') as stream:
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write('\n')
    print(json.dumps({'output': str(args.output_dir), 'source_reviews': len(reviews),
                      'target_entries': len(targets), 'provider_executions': 0, 'torch_imported': False}))


if __name__ == '__main__':
    main()
