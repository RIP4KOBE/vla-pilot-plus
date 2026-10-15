import pathlib,sys,json,datetime,traceback,os
root=pathlib.Path.cwd();out=root.parent/'autonomy_20261004/turns/000572'
# Parent records PID/boot/start and owning state before releasing this gate.
if sys.stdin.read(1)!='G': raise SystemExit('parent gate absent')
prep=json.loads((out/'n34-authority-adoption-v1.json').read_text());plan=json.loads(pathlib.Path(prep['plan']['path']).read_text());runtime=json.loads(pathlib.Path(plan['runtime']['path']).read_text())
os.environ.update(runtime['environment']);sys.path[:0]=[str(root)]+runtime['environment']['PYTHONPATH'].split(':')
from scripts import qd_ed_n34_runner as runner, qd_ed_n23_worker as w
status=out/'controller-status-v1.json';result=out/'controller-result-v1.json'
w.atomic_json(status,{'status':'RUNNING_RELEASE_REVALIDATION_AND_LOCKED_ADMISSION','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pid':os.getpid(),'plan':prep['plan'],'release':prep['release']})
try:
 value=runner.launch(prep['plan'],prep['release']);w.atomic_json(result,{'status':'RETURNED','result':value,'at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
except BaseException as e:
 w.atomic_json(result,{'status':'ERROR_REQUIRES_ROOT_RECONCILIATION','error':repr(e),'traceback':traceback.format_exc(),'at':datetime.datetime.now(datetime.timezone.utc).isoformat()});raise
finally:
 if result.exists():w.atomic_json(status,{'status':'TERMINAL_REQUIRES_ROOT_RECONCILIATION','result':str(result),'at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
