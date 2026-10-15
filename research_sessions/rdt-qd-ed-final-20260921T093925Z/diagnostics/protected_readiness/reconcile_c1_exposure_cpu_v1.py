"""Prepare metadata-only C1 reconciliation; apply only after N22 is terminal."""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1] / 'study_worktree'
sys.path.insert(0, str(ROOT/'scripts'))
import qd_ed_final_runner as runner


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare():
    plan_path = ROOT/'data/frozen-seed-plan.json'
    plan = runner.read_json(plan_path)
    ledger_path = ROOT/'data/attempt-ledger.jsonl'
    blob = ledger_path.read_bytes()
    events = [json.loads(line) for line in blob.splitlines()]
    selected, records = [], []
    for name in ('validation_c1_b1', 'validation_c1_b2'):
        for cell in sorted(plan['blocks'][name], key=lambda x: x['task_id']):
            matches = [e for e in events if e['event'] == 'dispatched'
                       and e.get('identity', {}).get('split') == 'validation'
                       and (e['identity']['task_id'], e['identity']['env_seed']) == (cell['task_id'], cell['env_seed'])]
            runner.require(matches, 'C1 cell has no actual dispatch')
            runner.require(all(e['identity']['policy_seed'] == cell['policy_seed']
                               and e['identity']['init_index'] == cell['init_index']
                               and e['init_row_sha256'] == cell['init_row_sha256'] for e in matches),
                           'C1 frozen identity mismatch')
            ids = sorted({e['attempt_id'] for e in matches})
            selected.extend(ids)
            records.append({'schema':'qd-ed-exposure-registry-v1', 'run_name':plan['run_name'],
                'suite':'libero_object_swap', 'task_id':cell['task_id'], 'task_name':cell['task_name'],
                'episode_seed':cell['env_seed'], 'policy_seed':cell['policy_seed'],
                'init_identity':{'index':cell['init_index'],'file_sha256':cell['init_file_sha256'],
                                 'row_sha256':cell['init_row_sha256']},
                'study_role':'validation', 'seed_block':name, 'new_run_exposure':True,
                'counterfactual_or_new_holdout':False,
                'exposure_kind':'actual_dispatch_metadata_reconciled', 'attempt_ids':ids,
                'seed_plan_path':str(plan_path), 'seed_plan_sha256':sha(plan_path),
                'evidence_path':str(HERE/'c1-reconciliation-proof-v1.json'),
                'limitation':'Exposure is conservatively established from dispatch identity; no success or failure outcome is consulted. Two seed blocks share init layouts.',
                'outcomes_read':False})
    target=HERE/'pending-c1-exposure-records-v1.jsonl'
    with target.open('x') as f:
        for record in records:f.write(json.dumps(record,sort_keys=True)+'\n')
    proof={'schema':'c1-exposure-reconciliation-preparation-v1', 'prepared_at':datetime.now(timezone.utc).isoformat(),
           'ledger_prefix_bytes':len(blob),'ledger_prefix_sha256':hashlib.sha256(blob).hexdigest(),
           'seed_plan_sha256':sha(plan_path),'records_sha256':sha(target),'reader_sha256':sha(__file__),
           'records':len(records),'unique_dispatches':len(set(selected)),
           'outcomes_read':False,'applied':False}
    with (HERE/'c1-reconciliation-proof-v1.json').open('x') as f:f.write(json.dumps(proof,indent=2)+'\n')
    print(json.dumps(proof))


def apply():
    status=runner.read_json(ROOT.parent/'variants/n22_hold_conditioned_lift/execution/supervisor-status-gpu7-v1.json')
    runner.require(status['status'] in {'completed_all_forty_audited','rejected_numeric_futility','failed','interrupted'},
                   'N22 still running; no exposure journal mutation permitted')
    proof=runner.read_json(HERE/'c1-reconciliation-proof-v1.json')
    pending=HERE/'pending-c1-exposure-records-v1.jsonl'
    runner.require(sha(pending)==proof['records_sha256'] and sha(__file__)==proof['reader_sha256'], 'prepared bytes differ')
    with runner.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True), runner.locked(ROOT/'data/qd-ed-state.lock'):
        blob=(ROOT/'data/attempt-ledger.jsonl').read_bytes()
        runner.require(hashlib.sha256(blob[:proof['ledger_prefix_bytes']]).hexdigest()==proof['ledger_prefix_sha256'],
                       'historical ledger prefix changed')
        runner.require(sha(ROOT/'data/frozen-seed-plan.json')==proof['seed_plan_sha256'],'frozen seeds changed')
        snapshot=runner.budget_snapshot([json.loads(x) for x in blob.splitlines()],
                                        runner.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl'))
        runner.require(snapshot['running']==0 and snapshot['gpu_healthcheck_inflight']==0,'another owned attempt is active')
        registry=ROOT/'data/exposure-registry.jsonl'; old=registry.read_bytes()
        runner.require(old.endswith(b'\n'),'registry partial line')
        known={(x['task_id'],x['episode_seed']) for x in (json.loads(line) for line in old.splitlines())}
        add=[x for x in runner.read_events(pending) if (x['task_id'],x['episode_seed']) not in known]
        if add:
            temp=registry.with_name(registry.name+'.reconcile-'+uuid.uuid4().hex)
            with temp.open('xb') as f:
                f.write(old);f.write(''.join(json.dumps(x,sort_keys=True)+'\n' for x in add).encode())
                f.flush();os.fsync(f.fileno())
            os.replace(temp,registry)
        report={'applied_at':datetime.now(timezone.utc).isoformat(),'added':len(add),
                'proof_sha256':sha(HERE/'c1-reconciliation-proof-v1.json'),
                'registry_before_sha256':hashlib.sha256(old).hexdigest(),'registry_after_sha256':sha(registry),
                'outcomes_read':False,'budget_changed':False}
        report_path=HERE/'c1-reconciliation-applied-v1.json'
        with report_path.open('x') as f:f.write(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true')
    apply() if parser.parse_args().apply else prepare()
