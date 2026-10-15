"""Read only frozen provider sources, without executing provider/model/simulator."""
import ast
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'implementation'))
from core.qd_executed_quality import _template_index
import torch

MANIFEST = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260929/n18-close-then-lift-dev-v1/gpu7-rebind/runtime-manifest.gpu7.frozen.v3.json')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    manifest = json.loads(MANIFEST.read_text())
    rows = []
    for task, item in sorted(manifest['tasks'].items(), key=lambda x: int(x[0])):
        cache = Path(item['cache_dir'])
        metadata = json.loads((cache / 'metadata.json').read_text())
        for stage in range(1, metadata['num_stages'] + 1):
            path = cache / f'stage{stage}_guidance.txt'
            source = path.read_text()
            try:
                _, _, target = _template_index(source)
                supported, reason = target == 0, 'recognized_weighted_distance_template'
            except (ValueError, SyntaxError, TypeError) as exc:
                supported, reason, target = False, str(exc), None
            rows.append({'task_id': int(task), 'stage': stage, 'path': str(path),
                         'sha256': sha(path), 'supported_target0_contract': supported,
                         'target_index': target, 'recognition_reason': reason,
                         'ast_sha256': hashlib.sha256(ast.dump(ast.parse(source), include_attributes=False).encode()).hexdigest()})
    assert len(rows) == 20
    assert all(r['supported_target0_contract'] for r in rows if r['stage'] == 1)
    assert all(not r['supported_target0_contract'] for r in rows if r['stage'] == 2)
    assert not torch.cuda.is_initialized()
    report = {'schema': 'n23-static-provider-compatibility-v1', 'rows': rows,
              'manifest': {'path': str(MANIFEST), 'sha256': sha(MANIFEST)},
              'reader_sha256': sha(__file__),
              'recognizer_sha256': sha(HERE / 'implementation/core/qd_executed_quality.py'),
              'supported_stage1_tasks': 10, 'unsupported_stage2_tasks': 10,
              'provider_executed': False, 'cuda_initialized': False,
              'interpretation': 'All ten frozen task Stage1 sources match target0 weighted distance. All Stage2 sources are constant zero, outside N23 contract. Loader preserves these functions and Stage recognition has no hard Stage2 guidance-off override. If Stage2 guidance activates, the existing N23 unsupported-provider guard must invalidate the attempt; this audit does not authorize a fallback or Stage change. No claim of all-stage compatibility.'}
    output = HERE / 'provider-compatibility-result-v1.json'
    with output.open('x') as f:
        json.dump(report, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps({'path': str(output), 'sha256': sha(output), 'supported_stage1_tasks': 10,
                      'unsupported_stage2_tasks': 10, 'cuda_initialized': False}))

if __name__ == '__main__':
    main()
