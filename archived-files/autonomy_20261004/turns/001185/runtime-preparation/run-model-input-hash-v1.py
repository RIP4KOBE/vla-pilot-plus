import subprocess,time,resource,json,sys
from pathlib import Path
out=Path(__file__).resolve().parent;cmd=[sys.executable,'-I','-S','-B',str(out/'hash-model-inputs-v1.py')];t=time.monotonic()
with (out/'model-input-hash-v1.log').open('w') as log:p=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=600)
r=resource.getrusage(resource.RUSAGE_CHILDREN);record={'command':cmd,'parent_wall_seconds':time.monotonic()-t,'child_cpu_seconds':r.ru_utime+r.ru_stime,'peak_rss_kib':r.ru_maxrss,'exit_code':p.returncode,'scope':'Byte hashing only, no framework/model/provider imports or execution'}
(out/'model-input-parent-timing-v1.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
