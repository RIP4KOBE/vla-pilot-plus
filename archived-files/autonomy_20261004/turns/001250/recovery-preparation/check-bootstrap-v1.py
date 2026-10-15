import os,sys,resource,subprocess,time,json,hashlib,copy,traceback
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=Path.cwd().resolve()
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);resource.setrlimit(resource.RLIMIT_CPU,(300,300))
sys.path.insert(0,str(ROOT))
from scripts import qd_ed_n36_source as execution
from scripts import qd_ed_n36_worker as worker, qd_ed_n34_source as closure
from scripts import qd_ed_n23_worker as w
context_ref={'path':str(OUT/'cpu-context-v1.json'),'sha256':w.sha(OUT/'cpu-context-v1.json')}
context=w.read_ref(context_ref)
assert not any(os.path.lexists(p) for p in context['stop_paths'])
argv=execution.command(sys.executable,ROOT,'scripts.qd_ed_n36_cpu_receipt',context_ref['path'],context_ref['sha256'])
env={**os.environ,'CUDA_VISIBLE_DEVICES':'','PYTHONPATH':'','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'}
start=time.monotonic()
with (OUT/'bootstrap-stdout-v1.log').open('x') as stdout,(OUT/'bootstrap-stderr-v1.log').open('x') as stderr:
    process=subprocess.Popen(argv,stdout=stdout,stderr=stderr,env=env)
    identity={'pid':process.pid,'proc_start_ticks':int(Path(f'/proc/{process.pid}/stat').read_text().rsplit(')',1)[1].split()[19]),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
    try:code=process.wait(timeout=180)
    except subprocess.TimeoutExpired:
        process.kill();code=process.wait()
usage=resource.getrusage(resource.RUSAGE_CHILDREN)
result={'argv':argv,'exit_code':code,'process':identity,'wall_seconds':time.monotonic()-start,'cpu_seconds':usage.ru_utime+usage.ru_stime,
        'CUDA_VISIBLE_DEVICES':'','cpu_affinity':sorted(os.sched_getaffinity(0)),'full_worker_parent_verification':False,
        'full_after_coverage':False,'release_enabled':False,'source_coverage_complete':False,'parent_checks':[]}
try:
    assert code==0,'source-only bootstrap failed; see stderr'
    receipt=json.loads((OUT/'cpu-receipt-v1.json').read_text());assert receipt['context']==context_ref and receipt['process']==identity
    frozen=w.read_ref(context['runtime_closure']);source=w.read_ref(context['source'])
    for phase in ('runtime_before','runtime_after'):
        binding=worker.runtime_receipt_binding(context_ref,context,identity,phase)
        closure.verify_runtime_receipt(frozen,receipt[phase],binding=binding,after=False)
        execution.verify_receipt(receipt['execution_'+phase],ROOT,source,frozen,
                                 loaded=receipt['loaded_'+phase],runtime_receipt=receipt[phase])
        assert receipt[phase]['schema']=='n34-runtime-receipt-v3' and receipt[phase]['module_aliases']['_cyutility']['same_module_object'] is True
        result['parent_checks'].append({'phase':phase,'runtime_v3':'PASS','compiled_source':'PASS','alias':receipt[phase]['module_aliases'],
                                        'ordinary_modules':len(receipt[phase]['modules'])})
    for label,mutator in [
        ('process',lambda r:r['binding']['process'].update(pid=-1)),
        ('phase',lambda r:r['binding'].update(phase='wrong')),
        ('closure',lambda r:r['binding']['runtime_closure'].update(sha256='0'*64)),
        ('alias_identity',lambda r:r['module_aliases']['_cyutility'].update(same_module_object=False)),
        ('qualified_inventory',lambda r:r['modules'].pop(r['module_aliases']['_cyutility']['target']))]:
        bad=copy.deepcopy(receipt['runtime_after']);mutator(bad)
        try:closure.verify_runtime_receipt(frozen,bad,binding=worker.runtime_receipt_binding(context_ref,context,identity,'runtime_after'),after=False)
        except ValueError as error:result['parent_checks'].append({'negative':label,'status':'REJECTED','error':str(error)})
        else:raise AssertionError('parent accepted '+label)
    result['status']='PASS_LIMITED_CPU_BOOTSTRAP_AND_PRODUCTION_PARENT_ATTESTORS'
except Exception as error:
    result.update(status='BLOCKED',error=repr(error),traceback=traceback.format_exc())
finally:
    result['stops_absent_at_end']=not any(os.path.lexists(p) for p in context['stop_paths'])
    (OUT/'bootstrap-parent-checks-v1.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
