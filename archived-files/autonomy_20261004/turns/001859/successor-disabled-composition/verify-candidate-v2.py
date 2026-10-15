"""Read-only bounded production checks. No gate issuance or owner snapshot."""
import sys,os,json,hashlib,datetime as dt
from pathlib import Path
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent
a=json.loads((O/'authority-v1.json').read_text())
assert all(not os.path.lexists(p) for p in a['stop_authority']['paths'])
assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(a['stop_authority']['deadline'].replace('Z','+00:00'))
g=json.loads((O/'graph.complete-disabled-v1.json').read_text())
os.environ.update(QD_ED_N36_R1_SPECIFICATION=json.dumps(g['specification']),CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1')
sys.path.insert(0,a['worktree'])
def hook(event,args):
 if event=='open' and isinstance(args[0],(str,bytes)):
  name=os.fsdecode(args[0]);mode,flags=args[1:3]
  if Path(name).name in ('auth.json','credentials.json','.env','state.json','checkpoint.json') or '2026-08-10-eds-qd-stage-guidance-transition-design.md' in name or '/dev/nvidia' in name:raise PermissionError('prohibited read')
  if name!='/dev/null' and ((isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))):raise PermissionError('read-only verifier')
 if event in ('socket.connect','socket.bind'):raise PermissionError('network prohibited')
 if event=='subprocess.Popen' and Path(str(args[0])).name not in ('git','uname','ldconfig'):raise PermissionError('bounded CPU subprocess only')
sys.addaudithook(hook)
from scripts import qd_ed_n36_engineering_r1 as e,qd_ed_n36_readiness_prepare as p
s=e.read(g['specification']);contract=e.read(g['recovery_prefix_contract']);root=Path(a['ledger_prefixes'][e.JOURNALS[0]]['path']).parent
p.policy(s);parsed,tail,current=e._recovery_capture(contract,root);assert not tail and not current
snapshot=e.r.budget_snapshot(parsed[e.JOURNALS[0]],parsed[e.JOURNALS[1]])
results={'policy':'PASS','four_predecessor_raw_capture':'PASS','budget_snapshot':snapshot}
for name,fn in [('specification',e.specification),('recovery_contract',lambda:e._recovery_contract(s))]:
 try:fn();results[name]='UNEXPECTED_PASS'
 except Exception as ex:results[name]={'status':'EXPECTED_BLOCK','error':str(ex)}
print(json.dumps(results,sort_keys=True))
