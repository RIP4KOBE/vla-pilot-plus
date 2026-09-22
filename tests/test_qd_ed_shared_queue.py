import copy
import json
from pathlib import Path
import sys

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import qd_ed_available_gpu_queue as queue


def root_with_shared_journals(tmp_path):
    root = tmp_path / 'worktree'; shared = tmp_path / 'shared'
    (root/'data').mkdir(parents=True); shared.mkdir()
    for name in ('attempt-ledger.jsonl','gpu-healthcheck-ledger.jsonl',
                 'gpu-hour-reservation-ledger.jsonl','qd-ed-state.lock','qd-ed-runner.lock'):
        (shared/name).touch(); (root/'data'/name).symlink_to(shared/name)
    state = {'artifacts': str(tmp_path/'artifacts'), 'gpu_pool':[5], 'max_concurrent_gpu_workers':1,
             'authorized_gpu_selection':{'candidate_indices':[5], 'single_exclusive_worker':True,'rescan_if_unavailable':True},
             'execution_migration':{'same_study_budget':True,'shared_journal_root':str(shared)},
             'budget':{'dispatched':0,'gpu_hours_consumed':0,'max_episode_attempts':240,'max_gpu_hours':48,
                       'reserved':dict(queue.runner.BUCKETS)}, 'candidate':{'id':'N1','status':'CPU_READY_UNEVALUATED'}}
    (root/'research-state.yaml').write_text(yaml.safe_dump(state))
    row={'episode_key':'new','split':'dev','iteration':'SERIAL','profile':'C0','task_id':0,
         'env_seed':11,'policy_seed':11,'init_index':0,'budget_bucket':'development','timeout_seconds':1800}
    return root, shared, state, row


def external_events(row, terminal=False):
    identity=queue.runner.episode_identity({**row,'iteration':'EXTERNAL'})
    base={'attempt_id':'external','identity':identity,'budget_bucket':'recovery'}
    events=[{**base,'event':'reserved'},{**base,'event':'dispatched'}]
    if terminal:
        events.append({**base,'event':'aborted','gpu_process_wall_seconds':36,'retryable_infrastructure':True})
    return events


def write_events(path, events):
    path.write_text(''.join(json.dumps(event)+'\n' for event in events))


def test_refresh_finished_shared_costs_without_changing_authorization(tmp_path):
    root,shared,state,row=root_with_shared_journals(tmp_path)
    events=external_events(row,True); write_events(shared/'attempt-ledger.jsonl',events)
    refreshed,candidates=queue.pending_gate(root,row)
    assert refreshed['budget']['dispatched']==1
    assert refreshed['budget']['gpu_hours_consumed']==pytest.approx(.01)
    assert refreshed['budget']['max_episode_attempts']==240
    assert refreshed['budget']['reserved']==state['budget']['reserved']
    assert refreshed['candidate']==state['candidate'] and candidates==[5]
    assert queue.runner.read_events(shared/'attempt-ledger.jsonl')==events


def test_inflight_work_is_never_reconciled_by_waiter(tmp_path):
    root,shared,state,row=root_with_shared_journals(tmp_path)
    events=external_events(row);write_events(shared/'attempt-ledger.jsonl',events)
    before=(root/'research-state.yaml').read_bytes()
    with pytest.raises(queue.runner.GateError,match=queue.UNFINISHED_JOURNAL):
        queue.pending_gate(root,row)
    assert (root/'research-state.yaml').read_bytes()==before
    assert queue.runner.read_events(shared/'attempt-ledger.jsonl')==events


def test_false_shared_binding_rejected(tmp_path):
    root,shared,state,row=root_with_shared_journals(tmp_path)
    state['execution_migration']['shared_journal_root']=str(tmp_path/'elsewhere')
    (root/'research-state.yaml').write_text(yaml.safe_dump(state))
    with pytest.raises(queue.runner.GateError,match='binding changed'):
        queue.pending_gate(root,row)


def test_queue_waits_then_resumes_after_external_terminal_without_gpu_work(tmp_path,monkeypatch):
    root,shared,state,row=root_with_shared_journals(tmp_path)
    write_events(shared/'attempt-ledger.jsonl',external_events(row))
    plan={'episodes':[row],'phase_authorization':{'dev':True},'code_files':[{'path':'scripts/'+name+'.py'}
          for name in ('qd_ed_available_gpu_queue','qd_ed_gpu_probe','qd_ed_runtime_setup')]}
    plan_path=root/'plan.json';plan_path.write_text(json.dumps(plan))
    runtime={'gpu_mapping':{'physical_gpu':5}}
    monkeypatch.setattr(queue.runner,'validate_plan',lambda *a,**k:(copy.deepcopy(plan),{},runtime))
    monkeypatch.setattr(queue.runner,'verify_provider',lambda *a,**k:None)
    monkeypatch.setattr(queue.runner,'child_environment',lambda *a,**k:{})
    calls=[]
    def inventory():
        calls.append('inventory')
        return {5:{'physical_gpu':5,'uuid':'GPU-five','pci_bus_id':'0000:a1:00.0',
                   'memory_used_mib':8000,'compute_pids':[999],'reserving_pids':[]}}
    monkeypatch.setattr(queue,'inventory',inventory)
    def sleep(_):
        assert calls==[]
        status=json.loads((Path(state['artifacts'])/'runtime/available-gpu-queue-status.json').read_text())
        assert status['status']=='waiting_journal'
        write_events(shared/'attempt-ledger.jsonl',external_events(row,True))
    status=queue.run_queue(plan_path,['new'],root=root,max_polls=2,sleep=sleep)
    assert status['status']=='waiting' and calls==['inventory']
    assert status['completed_keys']==[]
    assert queue.runner.read_state(root/'research-state.yaml')['budget']['dispatched']==1
