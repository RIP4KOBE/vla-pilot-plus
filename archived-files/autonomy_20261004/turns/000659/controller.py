"""Operational N34 wrapper repair; frozen release owns all scientific admission."""
import pathlib, sys, json, datetime, traceback, os, hashlib
root=pathlib.Path.cwd(); out=root.parent/'autonomy_20261004/turns/000659'
if sys.stdin.read(1)!='G': raise SystemExit('parent gate absent')
def read_ref(ref):
 p=pathlib.Path(ref['path']); raw=p.read_bytes()
 assert hashlib.sha256(raw).hexdigest()==ref['sha256']
 return json.loads(raw)
def status(value):
 p=out/'controller-status-v1.json';tmp=p.with_suffix('.tmp')
 tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(p)
prep=json.loads((out/'release-preparation-v1.json').read_text());plan=read_ref(prep['plan']);runtime=read_ref(plan['runtime'])
os.environ.update(runtime['environment'])
# Script-style helpers use absolute sibling imports. This is coordinator-only:
# do not alter the frozen child environment, runtime, manifests, or source.
sys.path[:0]=[str(root),str(root/'scripts')]+runtime['environment']['PYTHONPATH'].split(':')
from scripts import qd_ed_n34_runner as runner, qd_ed_n23_worker as w
result=out/'controller-result-v1.json'
status({'status':'RUNNING_RELEASE_REVALIDATION_AND_LOCKED_ADMISSION','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pid':os.getpid(),'plan':prep['plan'],'release':prep['release']})
try:
 value=runner.launch(prep['plan'],prep['release'])
 w.atomic_json(result,{'status':'RETURNED','result':value,'at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
except BaseException as e:
 w.atomic_json(result,{'status':'ERROR_REQUIRES_ROOT_RECONCILIATION','error':repr(e),'traceback':traceback.format_exc(),'at':datetime.datetime.now(datetime.timezone.utc).isoformat()});raise
finally:
 if result.exists():status({'status':'TERMINAL_REQUIRES_ROOT_RECONCILIATION','result':str(result),'at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
