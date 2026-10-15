import os,sys,json,copy,time,resource
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=Path.cwd().resolve()
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);resource.setrlimit(resource.RLIMIT_CPU,(120,120));sys.path.insert(0,str(ROOT))
from scripts import qd_ed_n36_worker as worker, qd_ed_n34_source as closure, qd_ed_n23_worker as w
context_ref={'path':str(OUT/'cpu-context-v1.json'),'sha256':w.sha(OUT/'cpu-context-v1.json')};context=w.read_ref(context_ref)
assert not any(os.path.lexists(p) for p in context['stop_paths'])
receipt=json.loads((OUT/'cpu-receipt-v1.json').read_text());captured=json.loads((OUT/'bootstrap-parent-checks-v1.json').read_text())
assert receipt['process']==captured['process'] and receipt['context']==context_ref and captured['exit_code']==0
frozen=w.read_ref(context['runtime_closure']);checks=[];start=time.monotonic()
for phase in ('runtime_before','runtime_after'):
    binding=worker.runtime_receipt_binding(context_ref,context,receipt['process'],phase)
    closure.verify_runtime_receipt(frozen,receipt[phase],binding=binding,after=False)
    checks.append({'phase':phase,'runtime_v3':'PASS','module_aliases':receipt[phase]['module_aliases'],
                   'ordinary_module_count':len(receipt[phase]['modules']),'full_after_coverage':False})
for label,mutator in [
    ('process',lambda r:r['binding']['process'].update(pid=-1)),
    ('phase',lambda r:r['binding'].update(phase='wrong')),
    ('context',lambda r:r['binding']['context'].update(sha256='0'*64)),
    ('closure',lambda r:r['binding']['runtime_closure'].update(sha256='0'*64)),
    ('alias_identity',lambda r:r['module_aliases']['_cyutility'].update(same_module_object=False)),
    ('qualified_inventory',lambda r:r['modules'].pop(r['module_aliases']['_cyutility']['target']))]:
    bad=copy.deepcopy(receipt['runtime_after']);mutator(bad)
    try:closure.verify_runtime_receipt(frozen,bad,binding=worker.runtime_receipt_binding(context_ref,context,receipt['process'],'runtime_after'),after=False)
    except ValueError as error:checks.append({'negative':label,'status':'REJECTED','error':str(error)})
    else:raise AssertionError('accepted '+label)
result={'schema':'n36r2-captured-runtime-parent-checks-v1','receipt':{'path':str(OUT/'cpu-receipt-v1.json'),'sha256':w.sha(OUT/'cpu-receipt-v1.json')},
        'checks':checks,'full_worker_parent_verification':False,'source_execution_parent_gate':'BLOCKED: posixpath.py missing executable receipt',
        'source_failure_evidence':{'path':str(OUT/'bootstrap-parent-checks-v1.json'),'sha256':w.sha(OUT/'bootstrap-parent-checks-v1.json')},
        'worker_relaunched':False,'release_enabled':False,'wall_seconds':time.monotonic()-start,
        'cpu_seconds':sum((resource.getrusage(resource.RUSAGE_SELF).ru_utime,resource.getrusage(resource.RUSAGE_SELF).ru_stime))}
(OUT/'captured-runtime-parent-checks-v1.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
