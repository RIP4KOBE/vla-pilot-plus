import sys, pathlib, json, datetime, traceback, os
root=pathlib.Path.cwd();sys.path[:0]=[str(root),str(root/'scripts')]
from scripts import qd_ed_n32r3_runner as n, qd_ed_n32r3_contract as c
out=root.parent/'autonomy_20261004/turns/000469';status=out/'controller-status.json'
a=json.loads((out/'admission.json').read_text())
def write(obj):
 n.w.atomic_json(status,{'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'process':n.process_identity(os.getpid()),'plan':a['plan'],'release':a['release'],**obj})
write({'status':'WAITING_FOR_ROOT_GATE'})
assert sys.stdin.buffer.read(1)==b'G'
write({'status':'RUNNING_RELEASE_VALIDATION_AND_COHORT','note':'Consult owning ledger and per-attempt process.json for live worker progress; no automatic recovery.'})
try:
 result=n.launch(a['plan'],a['release'])
 summary={k:v for k,v in result.items() if k not in ['charged_events','terminal']}
 write(summary);n.w.atomic_json(out/'controller-exit.json',{'exit':0,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'result':summary})
except BaseException as e:
 write({'status':'STOPPED_EXCEPTION_RECONCILE_LEDGER','error':str(e),'exception':type(e).__name__})
 n.w.atomic_json(out/'controller-exit.json',{'exit':1,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'error':str(e),'exception':type(e).__name__})
 traceback.print_exc();raise
