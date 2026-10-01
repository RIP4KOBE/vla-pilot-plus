import copy,json
from pathlib import Path
import pytest
from scripts import qd_ed_final_runner as r,qd_ed_n28_contract as c,qd_ed_n28_native as n,qd_ed_n28_supervise as sup,qd_ed_n28_report as report
from test_n28_execution import rows,journal
from test_n28_metering import write

@pytest.mark.parametrize('mode',['reject','promote','invalid','after_terminal'])
def test_controller_closes_exact_prefix_and_costs(tmp_path,monkeypatch,mode):
    plan={'episodes':rows(),'source_commit':'synthetic'};path=tmp_path/'plan.json';write(path,plan)
    monkeypatch.setattr(c,'RUN_DIR',tmp_path);monkeypatch.setattr(c,'BRIDGE',tmp_path/'bridge.json');write(c.BRIDGE,{})
    write(tmp_path/'scripts/qd_ed_n28_report.py',{})
    monkeypatch.setattr(sup,'ROOT',tmp_path);monkeypatch.setattr(sup,'device_check',lambda:None)
    events=[];calls=[];monkeypatch.setattr(r,'read_events',lambda _:copy.deepcopy(events))
    def attempt(_p,p,row):
        index=p['episodes'].index(row);calls.append(index)
        group=journal(successes=(3,7) if mode=='promote' else (),invalid=3 if mode=='invalid' else None,count=index+1)[-3:]
        output=tmp_path/f'a{index}'
        for event in group:event['output_dir']=str(output)
        for name in ('attempt-result.json','n23-worker-context.json','eds_eval/in-worker-audit-receipt.json','eds_eval/decision-evidence-audit.json'):write(output/name,{})
        events.extend(group)
        if mode=='after_terminal' and index==3:raise RuntimeError('postprocessing failed after terminal')
        return group[-1]
    monkeypatch.setattr(sup,'one_attempt',attempt)
    def accept(p,row,ev,*_):
        final=next(e for e in ev if e['event']=='valid' and e['episode_key']==row['episode_key'])
        if not final['outcome_valid']:raise ValueError('invalid')
        return final
    monkeypatch.setattr(c,'accepted_cell',accept);monkeypatch.setattr(c,'read_worker_report',lambda *a:{})
    monkeypatch.setattr(n,'from_output',lambda *a:({'guided_decisions':1,'parent_rounds_verified':10},{}))
    if mode in {'invalid','after_terminal'}:
        with pytest.raises((RuntimeError,ValueError)):sup.execute(path,plan,{}, {},tmp_path/'status.json')
    else:sup.execute(path,plan,{}, {},tmp_path/'status.json')
    result=json.loads((tmp_path/'result-v1.json').read_text());want=4 if mode in {'invalid','after_terminal'} else 16
    assert len(calls)==result['dispatched']==want
    assert sum(x['gpu_process_wall_seconds']['observed_total'] for x in result['all_attempt_costs'].values())==want*10
    assert result['dev_gate_promoted']==(mode=='promote')
    if mode=='reject':assert result['decision']=='REJECT_SCREEN'
    if mode=='after_terminal':
        assert result['decision']=='INVALID_OR_INTERRUPTED' and result['audited_cells']==4
        assert result['controller_evidence']['completed_keys']==[x['episode_key'] for x in rows()[:3]]
        assert len(result['controller_evidence']['journal_accepted_keys'])==4
    with pytest.raises(ValueError):report.write_terminal(path,plan,tmp_path/'status.json',tmp_path,vars(r))

@pytest.mark.parametrize('fault',['none','identity','source','plan','runtime','profile','init','receipt','second','native'])
def test_accepted_terminal_real_schema_binding(tmp_path,monkeypatch,fault):
    row={**rows()[0],'init_row_sha256':'row'};plan={'episodes':[row],'source_commit':'source','artifact_root':str(tmp_path),
        'profiles_sha256':'profile','runtime_manifest_sha256':'runtime','runtime_inventory_sha256':'inventory'}
    planref=write(tmp_path/'plan.json',plan);output=tmp_path/'attempts/a0';receipt=write(output/'eds_eval/in-worker-audit-receipt.json',{})
    write(output/'n23-worker-context.json',{'plan':planref})
    ev=journal(count=1)
    for e in ev:e.update(identity=r.episode_identity(row),output_dir=str(output))
    final=ev[-1];final.update(source_commit='source',plan_sha256=planref['sha256'],profile_manifest_sha256='profile',
      runtime_manifest_sha256='runtime',runtime_inventory_sha256='inventory',init_row_sha256='row',physical_gpu=7,
      n23_worker_receipt=receipt,guided_chunks=0)
    field={'identity':'identity','source':'source_commit','plan':'plan_sha256','runtime':'runtime_manifest_sha256','profile':'profile_manifest_sha256','init':'init_row_sha256','receipt':'n23_worker_receipt'}.get(fault)
    if field:final[field]={**r.episode_identity(row),'task_id':9} if fault=='identity' else 'wrong'
    if fault=='second':ev.extend([{**e,'attempt_id':'again'} for e in ev[:]])
    write(output/'attempt-result.json',final)
    monkeypatch.setattr(c,'read_worker_report',lambda *a:{'accepted':True})
    seen=[]
    def native(*args):
        seen.append(args)
        if fault=='native':raise ValueError('missing mandatory zero-guided N28 gate')
        return {},{}
    monkeypatch.setattr(n,'from_output',native)
    if fault=='none':assert c.accepted_cell(plan,row,ev,tmp_path,vars(r))==final and len(seen)==1
    else:
        with pytest.raises(ValueError):c.accepted_cell(plan,row,ev,tmp_path,vars(r))
