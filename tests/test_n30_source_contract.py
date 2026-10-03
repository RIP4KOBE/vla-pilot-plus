"""Synthetic source/review/terminal identity boundaries; no closed history reads."""
import copy,hashlib,json
from pathlib import Path
import pytest
from scripts import qd_ed_n30_bridge as b,qd_ed_n30_contract as c,qd_ed_n23_worker as w,qd_ed_final_runner as r
from test_n30_controller import rows,write


def test_reverse_complete_source_and_pinned_json(tmp_path,monkeypatch):
    monkeypatch.setattr(b,'CHANGED',{'main.py'})
    before=b'old\n';after=b'new\n';base={'commit':b.BASE,'files':[{'path':'main.py','sha256':hashlib.sha256(before).hexdigest()}]}
    write(tmp_path/b.DOC/'base-source-v1.json',base)
    (tmp_path/'main.py').write_bytes(after)
    write(tmp_path/'tests/n30_original_control_functions.json',{'synthetic':'pinned'})
    write(tmp_path/b.DOC/'reverse-source-v1.json',{'base_commit':b.BASE,'files':{'main.py':{'old_sha256':hashlib.sha256(before).hexdigest(),
        'new_sha256':hashlib.sha256(after).hexdigest(),'hunks':[{'start':0,'end':1,'new':['new\n'],'old':['old\n']}]}}})
    paths=b.source_paths(tmp_path);assert 'tests/n30_original_control_functions.json' in paths
    source={'files':[{'path':p,'sha256':w.sha(tmp_path/p)} for p in sorted(paths)]}
    assert b.reverse_source(tmp_path,source)==base
    with pytest.raises(ValueError):b.reverse_source(tmp_path,{'files':[x for x in source['files'] if not x['path'].endswith('control_functions.json')]})
    (tmp_path/'main.py').write_bytes(b'drift\n')
    with pytest.raises(ValueError):b.reverse_source(tmp_path,source)


def test_closed_schema_and_no_nested_payload_follow(tmp_path):
    source={'commit':b.BASE,'files':[{'path':f'f{i}','sha256':'x'} for i in range(411)],'sha256':'record'}
    runtime={'path':'/forbidden/no-runtime-read','sha256':'runtime'}
    plan={'code_files':source['files'],'source_commit':b.BASE,'frozen':True,
        'episodes':[{'task_id':t,'profile':a,'split':'dev','seed_block':'dev'} for t in range(10) for a in ('C0','Q0','N28','N29')],
        'runtime_manifest_path':runtime['path'],'runtime_manifest_sha256':runtime['sha256']}
    refs={'source_plan':write(tmp_path/'old-plan.json',plan),'source_record_sha256':'record','runtime':runtime,
        'caps':c.BASE_CAPS,'closed_result':{'counts':{a:{'audited':6,'success':0} for a in ('C0','Q0','N28','N29')}}}
    review={'schema':'n29-root-terminal-review-v1','decision':'REJECT_NUMERIC_DEV_FUTILITY','source_commit':b.BASE,'source_files_rehashed':411,
        'audited_cells':24,'dispatched':24,'invalid_attempts':[],'controller_original_process_exited':True,
        'worker_original_processes_exited':[f'a{i}' for i in range(24)],'plan':refs['source_plan'],'counts':refs['closed_result']['counts']}
    refs['closed_review']=write(tmp_path/'review.json',review)
    refs['source_review']=write(tmp_path/'source-review.json',{'schema':'n29-source-runtime-review-v1','disposition':'accepted','source':source,'runtime':runtime,
        'proof':{'path':'/forbidden/no-proof-read','sha256':'no'}})
    refs['budget_authority']=write(tmp_path/'budget.json',{'caps':c.BASE_CAPS})
    write(tmp_path/b.DOC/'base-source-v1.json',source);write(tmp_path/b.DOC/'historical-input-bindings-v1.json',refs)
    assert b.closed_records(tmp_path)['source_plan']==plan
    review['decision']='INVALID_OR_INTERRUPTED';refs['closed_review']=write(tmp_path/'review.json',review)
    write(tmp_path/b.DOC/'historical-input-bindings-v1.json',refs)
    with pytest.raises(ValueError):b.closed_records(tmp_path)


@pytest.mark.parametrize('fault',['none','context_episode','context_attempt','context_source','terminal_source','terminal_plan','terminal_runtime','terminal_input','terminal_profile','receipt','retry'])
def test_accepted_cell_binds_real_runner_terminal_shape(tmp_path,monkeypatch,fault):
    row={**rows()[2],'init_row_sha256':'row'};output=tmp_path/'artifacts/attempts/a';output.mkdir(parents=True)
    plan={'source_commit':'s','code_files':[],'profiles_sha256':'profiles','runtime_manifest_sha256':'runtime',
        'runtime_inventory_sha256':'inventory','artifact_root':str(tmp_path/'artifacts')}
    planref=write(tmp_path/'plan.json',plan)
    receiptref=write(output/'eds_eval/in-worker-audit-receipt.json',{'accepted':True})
    context={'plan':planref,'attempt_id':'a','episode_key':row['episode_key'],'profile':'N30','output_dir':str(output),'source':{'commit':'s','files':[]}}
    final={'event':'valid','attempt_id':'a','episode_key':row['episode_key'],'identity':r.episode_identity(row),'source_commit':'s',
        'plan_sha256':planref['sha256'],'profile_manifest_sha256':'profiles','runtime_manifest_sha256':'runtime','runtime_inventory_sha256':'inventory',
        'init_row_sha256':'row','physical_gpu':7,'output_dir':str(output),'n23_worker_receipt':receiptref,'outcome_valid':True,
        'required_cost_telemetry_complete':True,'guided_chunks':0,'success':False}
    if fault=='context_episode':context['episode_key']='other'
    elif fault=='context_attempt':context['attempt_id']='other'
    elif fault=='context_source':context['source']['commit']='other'
    elif fault.startswith('terminal_'):
        key={'terminal_source':'source_commit','terminal_plan':'plan_sha256','terminal_runtime':'runtime_manifest_sha256',
             'terminal_input':'init_row_sha256','terminal_profile':'profile_manifest_sha256'}[fault];final[key]='other'
    elif fault=='receipt':final['n23_worker_receipt']={'path':'/other','sha256':'other'}
    elif fault=='retry':final['retry_of']='old'
    write(output/'n23-worker-context.json',context);write(output/'attempt-result.json',final)
    events=[{**final,'event':event} for event in ('reserved','dispatched','valid')]
    monkeypatch.setattr(c,'read_worker_report',lambda *a:{'accepted':True})
    monkeypatch.setattr(c.native,'from_output',lambda *a:({},{}))
    if fault=='none':assert c.accepted_cell(plan,row,events,tmp_path,vars(r))==final
    else:
        with pytest.raises(ValueError):c.accepted_cell(plan,row,events,tmp_path,vars(r))


def test_future_qd_off_worker_route_closed(tmp_path):
    row=rows()[2];runtime={'gpu_mapping':{'physical_gpu':7,'uuid':c.GPU7_UUID}}
    plan={'frozen':True,'worktree':str(tmp_path),'artifact_root':str(tmp_path/'artifacts'),'episodes':[row],
        'source_commit':'s','code_files':[],'candidate_profiles':{'N30':{}},'n30_cohort':{'worker_audit':c.WORKER_CONTRACT},
        'runtime_manifest_path':'/synthetic-runtime','runtime_manifest_sha256':'runtime'}
    output=tmp_path/'artifacts/attempts/a';context={'attempt_id':'a','episode_key':row['episode_key'],'profile':'N30',
        'runtime':{'path':'/synthetic-runtime','sha256':'runtime'},'source':{'commit':'s','files':[]}}
    with pytest.raises(ValueError,match='future QD-off'):
        c.validate_worker_context(context,['main.py','main.eds_config.executed_progress_continuation_control=qd_off_v1'],tmp_path,output,plan,runtime)
