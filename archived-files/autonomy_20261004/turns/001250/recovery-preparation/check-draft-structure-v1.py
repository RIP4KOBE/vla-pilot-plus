import json,copy,os,sys,resource,time,hashlib
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=Path.cwd().resolve();sys.path.insert(0,str(ROOT));resource.setrlimit(resource.RLIMIT_CPU,(120,120));os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
from scripts import qd_ed_n36_contract as c, qd_ed_n36r2_draft as r2, qd_ed_n23_worker as w
from scripts import qd_ed_n36_release as release
plan=json.loads((OUT/'draft/plan.partial.draft-v1.json').read_text())
c.validate_draft(plan);checks=[{'check':'actual disabled draft','result':'PASS'}]
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);assert not path.exists();path.write_text(json.dumps(value,indent=2)+'\n');return c.ref(path)
def reject(label,fn):
    try:fn()
    except (ValueError,KeyError) as e:checks.append({'check':label,'result':'REJECTED','error':str(e)})
    else:raise AssertionError('accepted '+label)
for label,field,value in [('release enabled','release_enabled',True),('frozen','frozen',True),('authority','authority',{}),('root review','root_review',{})]:
    bad=copy.deepcopy(plan);bad[field]=value;reject(label,lambda:c.validate_draft(bad))
for label,section,field,value in [
    ('allocation extra authority','allocation','approved',True),
    ('allocation automatic retry','allocation','automatic_recoveries',1),
    ('allocation wrong cohort','allocation','cohort',c.RECOVERY_COHORT),
    ('accounting old charge changed','accounting','preserved_attempts',[]),
    ('new budget authority','accounting','new_budget_authority',True),
    ('ledger count changed','snapshot','dispatched',503),
    ('ledger hours changed','snapshot','gpu_hours_consumed',75.0),
    ('protected reserves changed','snapshot','protected_gpu_hours',{'validation':0.,'formal':0.}),
    ('scientific changes','protocol','scientific_changes',True),
    ('protocol auto recovery','protocol','automatic_recoveries',1),
    ('protocol extra science','protocol','threshold',0)]:
    bad=copy.deepcopy(plan);protocol=w.read_ref(bad['protocol']);accounting=w.read_ref(bad['accounting']);allocation=w.read_ref(accounting['allocation']);snapshot=w.read_ref(accounting['ledger_snapshot'])
    objects={'protocol':protocol,'accounting':accounting,'allocation':allocation,'snapshot':snapshot};objects[section][field]=value
    directory=OUT/'negative-fixtures'/label.replace(' ','-')
    accounting['allocation']=write(directory/'allocation.json',allocation)
    accounting['ledger_snapshot']=write(directory/'snapshot.json',snapshot)
    bad['accounting']=write(directory/'accounting.json',accounting)
    protocol['accounting']=bad['accounting'];protocol['allocation']=accounting['allocation']
    bad['protocol']=write(directory/'protocol.json',protocol)
    reject(label,lambda:r2.validate_protocol(bad))
reject('production release stays disabled',lambda:release.validate_plan(plan))
receipt=json.loads((OUT/'cpu-receipt-v1.json').read_text());runtime=receipt['runtime_before'];execution=receipt['execution_runtime_before']
frozen_evidence={'observed_os_path':runtime['modules'].get('os.path'),'observed_posixpath':runtime['modules'].get('posixpath'),
     'frozen_names':[n for n in execution['frozen_modules'] if n in ('os.path','posixpath')],
     'compiled_names':[r['module'] for r in execution['compiled'] if r['module'] in ('os.path','posixpath')],
     'interpretation':'Parent filters frozen exceptions by inventory key; os.path aliases frozen posixpath but remains in executable-source coverage. No validator or exception changed.'}
assert frozen_evidence['observed_os_path']==frozen_evidence['observed_posixpath'] and frozen_evidence['frozen_names']==['posixpath']
result={'checks':checks,'frozen_alias_failure_analysis':frozen_evidence,'release_enabled':False,
        'cpu_seconds':resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime}
(OUT/'draft-negative-checks-v1.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
