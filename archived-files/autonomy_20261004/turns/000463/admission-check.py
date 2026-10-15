import pathlib,json,datetime,traceback
from scripts import qd_ed_n32r3_runner as runner,qd_ed_n32r3_release as release,qd_ed_n32r3_contract as c,qd_ed_n23_worker as w
root=pathlib.Path.cwd();out=root.parent/'autonomy_20261004/turns/000463';v=json.loads((out/'release-validation-after-storage-repair.json').read_text());assert v['status']=='PASS'
p=w.read_ref(v['plan']);rt=w.read_ref(p['runtime']);a=w.read_ref(p['authority'])
try:
 with runner.r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
  with runner.r.locked(root/'data/qd-ed-state.lock'):
   state,events,resources,reservations=runner.snapshot(root,a)
   handles=runner.continuation_handles(p,events);assert not handles
   runner.check_probe(rt,resources,root);device=runner.device_check()
   snap=release.admission(p,a,state,events,resources,reservations,p['episodes'][0],now=datetime.datetime.now(datetime.timezone.utc),gpu_idle=True)
 result={'status':'PASS','device':device,'live_handles':handles,'snapshot':snap,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'gpu_dispatched':False}
except Exception as e:result={'status':'FAIL','error':str(e),'traceback':traceback.format_exc(),'gpu_dispatched':False}
w.atomic_json(out/'admission-check.json',result);print(json.dumps(result))
