import json,subprocess,time,resource,os,datetime
from pathlib import Path
out=Path(__file__).resolve().parent; prev=json.loads((out/'parent-timing-v1.json').read_text());cmd=prev['command'][:-1]+['closure_probe_v2'];env=prev['environment']; cpus=prev['affinity']
def limits():
 os.sched_setaffinity(0,cpus);resource.setrlimit(resource.RLIMIT_CPU,(700,700))
before=resource.getrusage(resource.RUSAGE_CHILDREN);t=time.monotonic();at=datetime.datetime.now(datetime.timezone.utc).isoformat()
with open(out/'closure-v2.log','w') as log:
 p=subprocess.run(cmd,cwd=prev['cwd'],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=750,preexec_fn=limits)
after=resource.getrusage(resource.RUSAGE_CHILDREN)
r={'command':cmd,'cwd':prev['cwd'],'environment':env,'started_at':at,'finished_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit_code':p.returncode,'complete_parent_wall_seconds':time.monotonic()-t,'child_cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'peak_rss_kib':after.ru_maxrss,'includes_interpreter_bootstrap_import_hash_attestation':True,'threads':2}
(out/'closure-parent-timing-v2.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='environment'},indent=2))
