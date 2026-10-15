import os,sys,json,pathlib,datetime,traceback
P=pathlib.Path;O=P('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001867');g=json.loads((O.parent/'001864/canonical-v2/graph.complete-disabled-v1.json').read_text());os.environ['QD_ED_N36_R1_SPECIFICATION']=json.dumps(g['specification']);sys.path.insert(0,g['production_required_worktree']);os.chdir(g['production_required_worktree'])
from scripts import qd_ed_n36_readiness_prepare as m
from scripts.qd_ed_n36_runner import process_identity
v=json.loads((O.parent/'001866/release-validation-v1.json').read_text())
def put(n,d):
 with (O/n).open('x') as f:json.dump(d,f,indent=2);f.write('\n')
put('measurement-process-v1.json',dict(process=process_identity(os.getpid()),release=v['release'],started_at=datetime.datetime.now(datetime.timezone.utc).isoformat()))
try:
 result=m.execute_preparation(v['release']);status='RETURNED';error=None
except BaseException as ex:
 result=None;status='FAILED';error=dict(type=type(ex).__name__,message=str(ex));traceback.print_exc()
put('measurement-exit-v1.json',dict(status=status,result=result,error=error,finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat()))
