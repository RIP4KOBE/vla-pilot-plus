import pathlib,sys,json,yaml,os,datetime,hashlib
root=pathlib.Path.cwd();sys.path[:0]=[str(root),str(root/'scripts')]
from scripts import qd_ed_n32r3_runner as n,qd_ed_n32r3_contract as c
t=root.parent/'autonomy_20261004/turns/000469';l=json.loads((t/'launch.json').read_text());a=json.loads((t/'admission.json').read_text())
with n.r.locked(root/'data/qd-ed-runner.lock',nonblocking=True),n.r.locked(root/'data/qd-ed-state.lock'):
 assert not pathlib.Path('/proc',str(l['controller']['pid'])).exists()
 assert n.journal_prefix(root/'data/attempt-ledger.jsonl')==a['ledger_prefix']
 p=c.read_ref(a['plan']);assert not n.continuation_handles(p,n.r.read_events(root/'data/attempt-ledger.jsonl'))
 rec={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'LAUNCHER_FAILED_BEFORE_RUNNER_ENTRY','launch':c.ref(t/'launch.json'),'log':c.ref(t/'controller.log'),'cause':'wrapper used immutable worker atomic_json for mutable status; second status write rejected before n.launch call','ledger_unchanged':a['ledger_prefix'],'controller_absent':True,'gpu_dispatched':False,'repair':'mutable status via fsync + os.replace; fresh launch directory; scientific and operational benchmark sources unchanged'}
 (t/'launch-failure-reconciliation.json').write_text(json.dumps(rec,indent=2)+'\n')
 for path in [root/'research-state.yaml',root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json']:
  obj=yaml.safe_load(path.read_text()) if path.suffix=='.yaml' else json.loads(path.read_text());assert obj['active_controller']['pid']==l['controller']['pid']
  obj['n32r3_failed_wrapper_launch']=c.ref(t/'launch-failure-reconciliation.json');obj['active_controller']=None;obj['status']='N32R3_RECONCILED_LAUNCHER_FAILURE_NO_DISPATCH'
  tmp=path.with_name(path.name+'.reconcile469.tmp');tmp.write_text(yaml.safe_dump(obj,sort_keys=False) if path.suffix=='.yaml' else json.dumps(obj,indent=2)+'\n');os.replace(tmp,path)
print(json.dumps(rec))
