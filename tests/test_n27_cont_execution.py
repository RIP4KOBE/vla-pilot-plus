import copy
import json
from pathlib import Path
from contextlib import contextmanager
import pytest
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w
from scripts import qd_ed_n27_cont_contract as c,qd_ed_n27_cont_history as h,qd_ed_n27_cont_prepare as prep
from scripts import qd_ed_n27_cont_report as report,qd_ed_n27_cont_supervise as sup,qd_ed_n27_cont_bridge as bridge
from n27_cont_fixtures import seal,write,group
from test_n27_continuation import fixture

@pytest.mark.parametrize('mode',['complete','reject','first_invalid','mid_invalid','abort','post_valid_error','status_write_error','missing_receipt'])
def test_supervisor_preserves_all_costs_and_no_retry(fixture,tmp_path,monkeypatch,mode):
    p=prep.build_plan(fixture,{'commit':'new','files':[]});write(c.PLAN,p)
    monkeypatch.setattr(sup,'ROOT',tmp_path);monkeypatch.setattr(sup.old,'device_check',lambda:None)
    events=[];calls=[];path=c.RUN_DIR/'execution/supervisor-status-v1.json'
    monkeypatch.setattr(r,'read_events',lambda _:copy.deepcopy(events))
    def run_plan(plan_path,*,split,iteration,episode_keys,root):
        assert split=='dev' and iteration==c.COHORT and root==tmp_path and len(episode_keys)==1
        row=next(x for x in p['episodes'] if x['episode_key']==episode_keys[0]);c.require_scope(p,root,vars(r),row)
        i=len(calls);calls.append(row);invalid=(mode=='first_invalid' and i==0) or (mode in {'mid_invalid','abort','missing_receipt'} and i==3)
        g=group(row,'new'+str(i),source='new',valid=not invalid,success=row['profile']=='N27' and row['task_id']<2 and mode!='reject')
        final=g[-1];out=tmp_path/'separate_attempt_volume'/final['attempt_id'];final['output_dir']=str(out)
        if mode=='abort' and invalid:g=g[:1]+[{**g[-1],'event':'aborted','outcome_valid':False}]
        events.extend(g);final=g[-1]
        for filename in ('attempt-result.json','n23-worker-context.json','eds_eval/decision-evidence-audit.json','eds_eval/in-worker-audit-receipt.json'):write(out/filename,final if filename=='attempt-result.json' else {})
        if invalid:raise r.GateError('original runner charged invalid')
        if mode=='post_valid_error' and i==3:raise RuntimeError('post-processing exception after valid journal')
        return [final]
    monkeypatch.setattr(r,'run_plan',run_plan)
    def accept(plan,row,ev,root,env):
        final=next(x for x in ev if x['episode_key']==row['episode_key'] and x['event'] in r.TERMINAL)
        w.require(final['outcome_valid'],'invalid/missing receipt');return final
    monkeypatch.setattr(c,'accepted_cell',accept);monkeypatch.setattr(c,'read_worker_report',lambda *a:{})
    monkeypatch.setattr(c.native,'from_output',lambda *a:({'guided_decisions':1,'parent_rounds_verified':10},{}))
    if mode=='status_write_error':
        original=r.durable_json;raised=False
        def durable(path,data):
            nonlocal raised
            if not raised and len(data['completed_keys'])==4:
                raised=True;raise OSError('status durable failure')
            return original(path,data)
        monkeypatch.setattr(r,'durable_json',durable)
    if mode in {'complete','reject'}:sup.execute(c.PLAN,p,path)
    else:
        with pytest.raises((ValueError,r.GateError,RuntimeError,OSError)):sup.execute(c.PLAN,p,path)
    result=json.loads((c.RUN_DIR/'result-v1.json').read_text())
    if mode=='complete':assert result['decision']=='ELIGIBLE_FOR_SEPARATELY_FROZEN_FULL_DEV' and result['audited_cells']==16
    elif mode=='reject':assert result['decision']=='REJECT_SCREEN' and len(calls)==13
    else:assert result['decision']=='INVALID_OR_INTERRUPTED' and not result['dev_gate_promoted'] and len(calls)<=4
    assert len(result['attempts'])==4+len(calls) and result['original_disposition']=='INVALID_OR_INTERRUPTED'
    assert result['unmeasured_token_call_attempts']==[h.FAILED]
    assert result['all_attempt_costs']['N27']['gpu_process_wall_seconds']['observed_total']>=7.231457023997791
    if mode=='post_valid_error':assert result['audited_cells']==7 and result['controller_evidence']['consistent'] is False
    assert all(x['source_commit']==h.BASE for x in result['accepted_cells'][:3])


def test_terminal_status_missing_keeps_valid_journal(fixture,tmp_path,monkeypatch):
    p=prep.build_plan(fixture,{'commit':'new','files':[]});write(c.PLAN,p)
    events=group(p['episodes'][0],'new',source='new');out=tmp_path/'attempt';events[-1]['output_dir']=str(out)
    for name in ('attempt-result.json','n23-worker-context.json','eds_eval/decision-evidence-audit.json','eds_eval/in-worker-audit-receipt.json'):write(out/name,{})
    monkeypatch.setattr(c,'accepted_cell',lambda *a:events[-1]);monkeypatch.setattr(c,'read_worker_report',lambda *a:{})
    monkeypatch.setattr(c.native,'from_output',lambda *a:({'guided_decisions':1,'parent_rounds_verified':10},{}))
    result=report.write_terminal(c.PLAN,p,c.RUN_DIR/'execution/supervisor-status-v1.json',tmp_path,{**vars(r),'read_events':lambda _:events})
    assert result['audited_cells']==4 and len(result['attempts'])==5 and result['decision']=='INVALID_OR_INTERRUPTED'
    assert result['terminal_status']['sha256'] is None


def test_launch_precreates_directory_no_retry_or_second_launch(fixture,tmp_path,monkeypatch):
    p=prep.build_plan(fixture,{'commit':'new','files':[]});write(c.PLAN,p)
    monkeypatch.setattr(sup,'ROOT',tmp_path);monkeypatch.setattr(r,'validate_plan',lambda *a,**kw:(p,{},{}))
    monkeypatch.setattr(sup,'release_check',lambda *a:None);monkeypatch.setattr(r,'read_events',lambda _:[]);monkeypatch.setattr(r,'read_state',lambda _: {})
    monkeypatch.setattr(c,'full_capacity',lambda *a:None);monkeypatch.setattr(w,'process_identity',lambda:{'pid':123,'proc_start_ticks':'456','boot_id':'synthetic'})
    @contextmanager
    def locked(path,**kw):
        if Path(path).name=='supervisor.lock':assert Path(path).parent.is_dir()
        yield
    monkeypatch.setattr(r,'locked',locked);calls=[];monkeypatch.setattr(sup,'execute',lambda *a:calls.append(a))
    write(tmp_path/'release',{})
    status=c.RUN_DIR/'execution/supervisor-status-v1.json';sup.launch(c.PLAN,tmp_path/'release',status);assert len(calls)==1
    with pytest.raises(ValueError):sup.launch(c.PLAN,tmp_path/'release',status)
    assert len(calls)==1

@pytest.mark.parametrize('fault',['wrongpath','source','keys','limits','disabled'])
def test_release_failclosed(fixture,tmp_path,fault):
    p=prep.build_plan(fixture,{'commit':'new','files':[]});write(c.PLAN,p)
    release=c.RUN_DIR/'execution-release-v1.json'
    data={'schema':'n27-hydra-execution-release-v1','plan':c.ref(c.PLAN),'source_commit':'new','cohort_id':c.COHORT,
        'authority':c.ref(c.AUTHORITY),'seal':c.ref(c.SEAL),'episode_keys':[x['episode_key'] for x in p['episodes']],
        'limits':c.LIMITS,'one_launch':True,'physical_gpu':7,'validation_authorized':False,'formal_authorized':False}
    write(release,data);sup.release_check(release,c.PLAN,p)
    if fault=='source':data['source_commit']='wrong'
    elif fault=='keys':data['episode_keys'].reverse()
    elif fault=='limits':data['limits']={**c.LIMITS,'new_dispatches':14}
    elif fault=='disabled':data['executable']=False
    write(release,data)
    with pytest.raises(ValueError):sup.release_check(tmp_path/'wrong' if fault=='wrongpath' else release,c.PLAN,p)



def test_source_reverse_exact_and_science_unchanged():
    root=Path(c.ROOT);files=[{'path':p,'sha256':w.sha(root/p)} for p in sorted(bridge.source_paths(root))]
    source={'commit':'synthetic','files':files,'sha256':w.canonical_sha(files)}
    old=bridge.reverse_source(root,source);assert old['commit']==h.BASE and len(old['files'])==345
    current=(root/'scripts/qd_ed_n23_worker.py').read_text();patch=json.loads((root/bridge.DOC/'reverse-source-v1.json').read_text())['files']['scripts/qd_ed_n23_worker.py']
    lines=current.splitlines(keepends=True)
    for edit in reversed(patch['edits']):lines[edit['new_start']:edit['new_end']]=edit['old'].splitlines(keepends=True)
    previous=''.join(lines);a,z=bridge.functions(previous),bridge.functions(current)
    assert a['run_worker']==z['run_worker'] and a['verify_receipt']==z['verify_receipt']
    assert 'n27_cohort' in z['run_worker'] and 'n27_cohort' in z['verify_receipt']


def test_reverse_rejects_source_hash_drift():
    root=Path(c.ROOT);files=[{'path':p,'sha256':w.sha(root/p)} for p in sorted(bridge.source_paths(root))]
    files[0]['sha256']='0'*64
    with pytest.raises(ValueError):bridge.reverse_source(root,{'commit':'synthetic','files':files})


def test_read_bounds_before_allocation(tmp_path):
    p=tmp_path/'big';p.touch()
    with p.open('r+b') as f:f.truncate(h.MAX_FILE+1)
    with pytest.raises(ValueError):h.read({'path':str(p),'sha256':'0'*64})
    with pytest.raises(ValueError):h.ref(p)
