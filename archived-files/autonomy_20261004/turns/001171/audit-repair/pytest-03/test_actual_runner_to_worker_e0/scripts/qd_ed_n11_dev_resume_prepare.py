#!/usr/bin/env python3
"""Freeze the remaining twelve N11 Dev cells after a proven audit-only correction."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess

import qd_ed_final_runner as runner
import qd_ed_n11_dev_contract as contract
import qd_ed_n11_dev_prepare as original_prepare

ROOT = Path(__file__).resolve().parents[1]
SESSION = ROOT.parent
PRIOR_PLAN = contract.RUN_DIR/'plan.frozen.v1.json'
PRIOR_PLAN_SHA = 'ec2f0f15f51ded24022ffd9cc39ca184813a4c53ef5f4334ca76ddf6a1ebc879'
PRIOR_STATUS = contract.RUN_DIR/'status.json'
CORRECTION = SESSION/'variants/n11_parent_survival/audit_correction_20260928'
CORRECTED_AUDIT = CORRECTION/'task0_reaudit.json'
CORRECTED_AUDIT_SHA = '975c520454f4d030257456ee60976382ff7fbf506015c704e6ccfb0ed8e10e9c'
ORIGINAL_AUDIT_SHA = 'ba8d0ad5fb5af48ece88f6ec5ed1d8f140767186974e15dd2e68e98f7ebaa814'
PRIOR_KEYS = [row['episode_key'] for row in contract.expected_rows()[:4]]
REMAINING_KEYS = [row['episode_key'] for row in contract.expected_rows()[4:]]


def prior_evidence():
    runner.require(runner.digest(PRIOR_PLAN) == PRIOR_PLAN_SHA,
                   'N11 original frozen plan differs')
    prior = runner.read_json(PRIOR_PLAN)
    runner.require(prior['episodes'] == contract.expected_rows(),
                   'N11 original matched matrix differs')
    status = runner.read_json(PRIOR_STATUS)
    runner.require(status.get('status') == 'failed'
                   and status.get('completed_keys') == PRIOR_KEYS[:3]
                   and status.get('reason') == 'GateError',
                   'N11 original supervisor stop differs')
    correction = runner.read_json(CORRECTED_AUDIT)
    runner.require(runner.digest(CORRECTED_AUDIT) == CORRECTED_AUDIT_SHA
                   and correction.get('accepted') is True
                   and correction.get('evidence_complete') is True
                   and correction.get('errors') == []
                   and correction.get('n11_parent_survival_audit',{}).get('checked_decisions') == 43
                   and correction['n11_parent_survival_audit']['survivor_rounds_verified'] == 430,
                   'N11 independent audit correction differs')
    events = runner.read_events(ROOT/'data/attempt-ledger.jsonl')
    for row in contract.expected_rows():
        related = [event for event in events if event.get('episode_key') == row['episode_key']]
        if row['episode_key'] in PRIOR_KEYS:
            runner.require([event['event'] for event in related] ==
                           ['reserved','dispatched','valid']
                           and all(event.get('plan_sha256') == PRIOR_PLAN_SHA
                                   for event in related)
                           and related[-1].get('outcome_valid') is True
                           and related[-1].get('success') is False
                           and related[-1].get('physical_gpu') == 3,
                           'N11 original task0 attempt provenance differs')
            audit = Path(related[-1]['output_dir'])/'eds_eval/decision-evidence-audit.json'
            if row['profile'] == 'N11':
                runner.require(runner.digest(audit) == ORIGINAL_AUDIT_SHA
                               and runner.read_json(audit).get('errors') ==
                               ['n4_selected_parent_cell_mismatch'],
                               'N11 original failed audit differs')
            else:
                record = runner.read_json(audit)
                runner.require(record.get('accepted') is True
                               and record.get('evidence_complete') is True,
                               'N11 original control audit differs')
        else:
            runner.require(not related, 'N11 continuation identity already attempted')
    return prior


def main():
    prior = prior_evidence()
    head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    plan_path = contract.RUN_DIR/'plan.frozen.v2.json'
    release_path = contract.RUN_DIR/'execution-release.v2.json'
    runner.require(not plan_path.exists() and not release_path.exists(),
                   'N11 continuation already frozen')
    plan = copy.deepcopy(prior)
    code = {record['path'] for record in plan['code_files']}
    code |= {'scripts/qd_ed_n11_dev_resume_prepare.py',
             'scripts/qd_ed_n11_dev_resume.py'}
    plan['code_files'] = [original_prepare.committed_record(relative,head)
                          for relative in sorted(code)]
    plan['source_commit'] = head
    plan['n11_continuation'] = {
        'schema':'n11-audit-correction-continuation-v2',
        'prior_plan':{'path':str(PRIOR_PLAN),'sha256':PRIOR_PLAN_SHA},
        'prior_status':{'path':str(PRIOR_STATUS),'sha256':runner.digest(PRIOR_STATUS)},
        'correction_memo':{'path':str(CORRECTION/'audit-correction-v1.md'),
                           'sha256':runner.digest(CORRECTION/'audit-correction-v1.md')},
        'corrected_audit':{'path':str(CORRECTED_AUDIT),'sha256':CORRECTED_AUDIT_SHA},
        'original_failed_audit_sha256':ORIGINAL_AUDIT_SHA,
        'completed_episode_keys':PRIOR_KEYS,
        'remaining_episode_keys':REMAINING_KEYS,
        'policy_change_since_v1':False,
    }
    runner.durable_json(plan_path,plan)
    runner.validate_plan(plan_path,root=ROOT)
    release = {
        'schema':'n11-dev-continuation-release-v2',
        'plan_path':str(plan_path.resolve()),
        'plan_sha256':runner.digest(plan_path),
        'source_commit':head,
        'cohort_id':contract.COHORT,
        'completed_episode_keys':PRIOR_KEYS,
        'remaining_episode_keys':REMAINING_KEYS,
        'physical_gpu':3,
        'validation_authorized':False,
        'formal_authorized':False,
    }
    runner.durable_json(release_path,release)
    print(json.dumps({'plan_path':str(plan_path),'plan_sha256':runner.digest(plan_path),
                      'release_path':str(release_path),'source_commit':head,
                      'remaining_episode_keys':REMAINING_KEYS,'gpu_dispatched':False},sort_keys=True))


if __name__ == '__main__':
    main()
