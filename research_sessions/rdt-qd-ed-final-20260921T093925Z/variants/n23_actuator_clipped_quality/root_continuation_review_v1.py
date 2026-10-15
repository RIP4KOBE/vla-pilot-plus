"""Root CPU/source/actual-prefix review; no execution or private state mutation."""
import datetime
import json
import subprocess
import n23_continuation_contract as x

def main():
    owned=x.load_owned();r=owned.r
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=x.EXTERNAL,text=True).strip()=='dd27e77edd5e8d67aba998c1d0441c2b8e48713c'
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=x.EXTERNAL,text=True).strip()
    with r.locked(owned.root/'data/qd-ed-runner.lock',nonblocking=True),r.locked(owned.root/'data/qd-ed-state.lock'):
        plan,manifest,runtime=r.validate_plan(x.PLAN,root=owned.root)
        failure=x.immutable_inputs(owned);source=x.source_record();owning=x.owning_source(plan,owned)
        source_path=x.HERE/'continuation-source-manifest-v1.json'
        assert x.sha(source_path)=='ced23d5abf8949621ccb5cdbccbb557f75d19e116b85b9deb8461a6a043ac4e4'
        assert source==json.loads(source_path.read_text())
        events=r.read_events(owned.root/'data/attempt-ledger.jsonl')
        resources=r.read_events(owned.root/'data/gpu-healthcheck-ledger.jsonl')
        prefix=x.prefix_gate(plan,failure,events,owned,x.acceptor(plan,manifest,owned),initial=True)
        state=r.read_state(owned.root/'research-state.yaml')
        owned.c.full_capacity(state,events,resources,vars(r));x.no_owned_worker(owned.root)
        log=x.HERE/'cpu-continuation-v2.log';log_text=log.read_text()
        assert '88 passed' in log_text and '"blocked_reads": 0' in log_text and '"exitstatus": 0' in log_text
        assert len(prefix)==3 and prefix[2][2]=={'guided_decisions':15,'parent_rounds_verified':150}
        review=x.review_payload(plan,source,owning,owned)
        owned.w.atomic_json(x.REVIEW,review)
        report={
            'schema':'n23-root-continuation-review-v1','recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'review':x.ref(x.REVIEW),'external_manifest':x.ref(source_path),'test_log':x.ref(log),
            'original_source_files_verified':len(owning['files']),'external_source_files_verified':len(source['files']),
            'module_origins':x.module_origins(owned.root),'original_runtime_and_inputs_validated':True,
            'original_prefix':[{'attempt_id':item[0]['attempt_id'],'outcome_valid':item[0]['outcome_valid'],
                'success':item[0]['success'],'gpu_process_wall_seconds':item[0]['gpu_process_wall_seconds'],
                'native_counts':item[2],'evidence_refs':item[1]} for item in prefix],
            'prefix_gpu_seconds':sum(item[0]['gpu_process_wall_seconds'] for item in prefix),
            'budget_snapshot':r.budget_snapshot(events,resources),
            'cpu_tests_reexecuted_by_root':False,'gpu_or_api_dispatched':False,
            'state_changed':False,'adopted':False,'target_met':False,
            'conclusion':'Real three-cell native evidence supports legacy-provider interpretation. Exact original source/plan/runtime retained; only untouched suffix may execute after separate locked adoption.'}
        target=x.HERE/'root-continuation-review-v1.json';owned.w.atomic_json(target,report)
        print(json.dumps({'review':x.ref(target),'source_review':x.ref(x.REVIEW),'prefix_cells':3,
            'original_source_files':214,'external_source_files':len(source['files']),'adopted':False}))

if __name__=='__main__':main()
