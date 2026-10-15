#!/usr/bin/env python3
"""Freeze the four-cell passive N7 diagnostic without dispatching a GPU."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2] / 'study_worktree'
sys.path.insert(0, str(ROOT / 'scripts'))
import qd_ed_final_runner as runner
import qd_ed_n7_passive_diagnostic as diagnostic


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    source = diagnostic.SOURCE_PLAN
    runner.require(sha(source) == diagnostic.SOURCE_PLAN_SHA,
                   'historical N7 plan hash changed')
    output = diagnostic.RUN_DIR / 'plan.frozen.v2.json'
    runner.require(not output.exists(), 'passive plan already frozen')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                   text=True).strip()
    runner.require(head == 'dbe65b6e1db1d23b4ce8a68368dfbd7278c80a13',
                   'diagnostic admission source HEAD changed')
    plan = copy.deepcopy(runner.read_json(source))
    code = {r['path'] for r in plan['code_files']}
    code |= runner.REQUIRED_CODE
    code |= {'main.py', 'core/keypoint_tracker.py', 'core/decision_evidence.py',
             'scripts/qd_ed_final_runner.py',
             'scripts/qd_ed_n7_passive_diagnostic.py',
             'tests/test_keypoint_tracking_evidence.py'}
    records = []
    for relative in sorted(code):
        actual = (ROOT / relative).read_bytes()
        committed = subprocess.check_output(['git', 'show', head + ':' + relative],
                                            cwd=ROOT)
        runner.require(actual == committed, 'uncommitted frozen source: ' + relative)
        records.append({'path': relative,
                        'sha256': hashlib.sha256(actual).hexdigest()})
    plan.pop('n7_cohort')
    plan.update(source_commit=head, worktree=str(ROOT), code_files=records,
                episodes=diagnostic.expected_rows(),
                phase_authorization={'dev': True, 'validation': False,
                                     'formal': False})
    plan['n7_passive_diagnostic'] = {
        'schema': 'n7-passive-diagnostic-v1',
        'cohort_id': diagnostic.COHORT,
        'limits': diagnostic.LIMITS,
        'source_plan_sha256': diagnostic.SOURCE_PLAN_SHA,
        'run_dir': str(diagnostic.RUN_DIR),
        'protocol_path': str(diagnostic.PROTOCOL),
        'protocol_sha256': sha(diagnostic.PROTOCOL),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    runner.durable_json(output, plan)
    runner.validate_plan(output, root=ROOT)
    print(json.dumps({'plan': str(output), 'sha256': sha(output),
                      'source_commit': head,
                      'episode_keys': [r['episode_key'] for r in plan['episodes']],
                      'status': 'frozen_validated_no_dispatch'}, sort_keys=True))


if __name__ == '__main__':
    main()
