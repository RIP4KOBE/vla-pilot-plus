import copy,json,math
from pathlib import Path
import pytest,torch
from scripts import qd_ed_n31_contract as c,qd_ed_n23_worker as w
from scripts.qd_ed_n31_reference import reconstruct,same
from test_n31_controller import write,CAPS


def authority(tmp_path,monkeypatch,weekly):
    proposal=tmp_path/'proposal.md';proposal.write_text('# UNADOPTED synthetic request\n')
    record={'schema':'n31-approved-budget-authority-v1','approved':True,'cohort_id':c.COHORT,
        'validation_authorized':False,'formal_authorized':False,'approval_basis':'synthetic fixture only','caps':copy.deepcopy(CAPS),
        'weekly_window':None,'amendment':{'approval':write(tmp_path/'approval.json',{'test':True}),
          'proposal':c.ref(proposal),'previous_authority':write(tmp_path/'previous.json',{'test':True}),
          'history_boundary':{'dispatched':403,'gpu_hours_consumed':53.80872756284531}}}
    if weekly:
        record['caps'].update(attempts=1800,gpu_hours=224.,buckets={'baseline':400,'development':1120,'validation':180,'formal':40,'recovery':60})
        record['weekly_window']={'origin_gpu_hours':53.08404692669838,'increment_gpu_hours':168.,'ends_at':'2026-10-10T17:42:00Z'}
    path=tmp_path/'authority.json';write(path,record);monkeypatch.setattr(c,'BUDGET_AUTHORITY',path)
    return path,record


@pytest.mark.parametrize('weekly',[False,True])
def test_exact_authority_markdown_and_effective_cap(tmp_path,monkeypatch,weekly):
    path,a=authority(tmp_path,monkeypatch,weekly);assert c.budget_authority()==a
    assert c.effective_hours(a)==(53.08404692669838+168. if weekly else 100.)


@pytest.mark.parametrize('fault',['draft','bucket','origin','end','increment','amendment','proposal_bytes','history'])
def test_authority_tamper(tmp_path,monkeypatch,fault):
    path,a=authority(tmp_path,monkeypatch,True)
    if fault=='draft':a['approved']=False
    elif fault=='bucket':a['caps']['buckets']['development']+=1
    elif fault=='origin':a['weekly_window']['origin_gpu_hours']=53.80872756284531
    elif fault=='end':a['weekly_window']['ends_at']='2026-10-11T17:42:00Z'
    elif fault=='increment':a['weekly_window']['increment_gpu_hours']=170
    elif fault=='amendment':a['amendment']='approved'
    elif fault=='proposal_bytes':Path(a['amendment']['proposal']['path']).write_text('changed')
    elif fault=='history':a['amendment']['history_boundary']['dispatched']=402
    write(path,a)
    with pytest.raises((ValueError,OSError)):c.budget_authority()


@pytest.mark.parametrize('left',[1840.01,1839.99])
def test_weekly_window_requires_whole_attempt(monkeypatch,left):
    import datetime as dt
    end=dt.datetime(2026,10,10,17,42,tzinfo=dt.timezone.utc)
    class Fixed(dt.datetime):
        @classmethod
        def now(cls,tz=None):return end-dt.timedelta(seconds=left)
    monkeypatch.setattr(c.dt,'datetime',Fixed)
    a={'weekly_window':{'ends_at':'2026-10-10T17:42:00Z'}}
    if left>=1840:c.require_window(a,1840)
    else:
        with pytest.raises(c.ResourceBudgetIncomplete):c.require_window(a,1840)


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
@pytest.mark.parametrize('axis,bound',[(0,-.008),(0,.008),(1,-.0195),(1,.0195),(2,-.0116),(2,.0044)])
def test_independent_inclusive_binary64_faces(dtype,axis,bound):
    plan=torch.ones((64,128),dtype=dtype);plan[:,10]=-1
    xyz=torch.zeros((8,3),dtype=dtype)
    target=torch.zeros(3,dtype=torch.float64);target[axis]=bound
    quat=torch.tensor([0.,0.,0.,2.],dtype=torch.float64);qpos=torch.tensor([.02,-.02],dtype=torch.float64)
    out,j,reason=reconstruct(plan,xyz,target,quat,qpos)
    assert j==0 and reason=='capture_dwell_proposal' and out is not None
    expected=plan.clone();expected[:8,10]=1;expected[1:8,39:45]=0
    assert same(out,expected)
    target[axis]=math.nextafter(bound,math.copysign(math.inf,bound))
    out,j,reason=reconstruct(plan,xyz,target,quat,qpos)
    assert out is None and j is None and reason=='no_projected_entry'
