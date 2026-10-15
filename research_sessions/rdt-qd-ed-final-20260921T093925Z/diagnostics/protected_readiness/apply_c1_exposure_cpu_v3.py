"""Apply immutable v2 metadata preparation using actual N22 v1 terminal path.

The v2 preparation and its source hash remain intact. Its apply function had
an unexecuted v2-status filename typo; v3 corrects only this release-time path
and records its own reader hash. No outcomes are used to select exposure rows.
"""
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


def apply():
    status=runner.read_json(ROOT.parent/'variants/n22_hold_conditioned_lift/execution/supervisor-status-gpu7-v1.json')
    runner.require(status['status'] in {'completed_all_forty_audited','rejected_numeric_futility','failed','interrupted'},
                   'N22 still running; no exposure journal mutation permitted')
    runner.require(not (HERE/'c1-reconciliation-applied-v3.json').exists(), 'v3 reconciliation already applied')
    proof=runner.read_json(HERE/'c1-reconciliation-proof-v2.json')
    pending=HERE/'pending-c1-exposure-records-v2.jsonl'
    runner.require(sha(pending)==proof['records_sha256'] and sha(HERE/'reconcile_c1_exposure_cpu_v2.py')==proof['reader_sha256'], 'prepared bytes differ')
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
                'proof_sha256':sha(HERE/'c1-reconciliation-proof-v2.json'),
                'registry_before_sha256':hashlib.sha256(old).hexdigest(),'registry_after_sha256':sha(registry),
                'outcomes_read':False,'budget_changed':False, 'apply_reader_sha256':sha(__file__), 'terminal_status_path':str(ROOT.parent/'variants/n22_hold_conditioned_lift/execution/supervisor-status-gpu7-v1.json')}
        report_path=HERE/'c1-reconciliation-applied-v3.json'
        with report_path.open('x') as f:f.write(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report))


if __name__ == '__main__':
    apply()
