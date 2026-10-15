"""Read-only source verification and non-authorizing conditional-validation review."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
VI = HERE / 'validation_implementation'
sys.path.insert(0, str(VI))
from scripts import qd_ed_n23_validation_bridge as bridge

def read(path):
    return json.loads(path.read_text())

def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def main():
    packaging = read(HERE / 'cpu-validation-packaging-v2.json')
    for name in ('manifest', 'bridge', 'draft', 'review_template', 'promotion_template', 'authorization_template'):
        assert ref(Path(packaging[name]['path'])) == packaging[name], name
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=VI, text=True).strip() == '89aea3be3522a388484c6c65dd479c5d8174b290'
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=VI, text=True).strip()
    source, proof = bridge.source_record(VI, read(HERE / 'plan.frozen.v2.gpu7.json'),
        'b202e2bf03e13ea4d66fdd355f7959bbb40f264aeb3c9bd37f57959efdc63615')
    assert source == read(Path(packaging['manifest']['path']))
    assert proof == read(Path(packaging['bridge']['path']))
    assert len(source['files']) == 226
    draft = read(Path(packaging['draft']['path']))
    assert draft['frozen'] is False
    assert draft['n23_validation']['dev_review'] is None
    assert draft['n23_validation']['source_review'] is None
    log = HERE / 'cpu-validation-regression-v1.log'
    text = log.read_text()
    assert '474 passed' in text and '"blocked_reads": 0' in text and '"exitstatus": 0' in text
    torch = sys.modules.get('torch')
    assert torch is None or not torch.cuda.is_initialized()
    report = {
        'schema': 'n23-validation-root-cpu-prereview-v1',
        'disposition': 'CPU_PREPARATION_ACCEPTED_CONDITIONAL_ONLY',
        'source': packaging['manifest'], 'source_bridge': packaging['bridge'],
        'protocol': ref(HERE / 'protocol-validation-conditional-v1.md'),
        'executor_report': ref(HERE / 'cpu-validation-implementation-report-v1.md'),
        'test_log': ref(log), 'source_files_independently_verified': 226,
        'original_dev_source_files_bound': 214,
        'root_reviewed_modules': ['bridge', 'evidence', 'contract', 'recovery', 'prepare', 'supervise', 'report', 'identity'],
        'review_findings': [
            'Exact reversible worker/runner routing; remaining Dev scientific bytes preserved.',
            'Full forty-cell actual Dev promotion and real historical proof are required.',
            'Metadata-only first-unused whole cohort selection, protected aggregate-only steering.',
            'Sixty primary cells and at most two separately typed whole-episode recoveries.',
            'All failed attempts/costs retained, first-valid-only scientific denominators.',
            'Current Codex login, existing model/prompt/runtime/timeout and no Poe fallback preserved.'
        ],
        'limitations': [
            'Root read and checked the retained regression log; did not duplicate those tests.',
            'Synthetic tests and CPU source review do not establish actual validation execution or efficacy.',
            'Actual promotion, idle source integration, fresh identity/capacity checks and root execution release remain pending.'
        ],
        'cuda_initialized': False, 'gpu_or_api_execution': False,
        'protected_outcomes_inspected_by_this_review': False,
        'owning_source_modified': False, 'state_or_budget_modified': False,
        'validation_authorized': False, 'formal_authorized': False,
    }
    target = HERE / 'root-validation-cpu-prereview-v1.json'
    with target.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'review': ref(target), 'files_verified': 226, 'execution_authorized': False}))

if __name__ == '__main__':
    main()
