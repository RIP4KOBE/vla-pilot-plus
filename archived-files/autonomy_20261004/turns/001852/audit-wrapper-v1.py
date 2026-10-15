from pathlib import Path
import subprocess,json,datetime,os
O=Path(__file__).resolve().parent
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def h(pid):
 s=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split();return dict(pid=pid,boot_id=boot,start_ticks=int(s[19]),state=s[0])
with (O/'audit.stdout.log').open('wb') as out,(O/'audit.stderr.log').open('wb') as err:
 p=subprocess.Popen(['/home/hynx/miniconda3/envs/vla-pilot/bin/python','-B','-X','pycache_prefix=/dev/null',str(O/'audit-measured-graph-v1.py')],stdout=out,stderr=err,stdin=subprocess.DEVNULL)
 (O/'cpu-operation-process-v1.json').write_text(json.dumps(dict(wrapper=h(os.getpid()),child=h(p.pid),gpu_authorized=False),indent=2)+'\n')
 rc=p.wait()
 (O/'audit-exit-v1.json').write_text(json.dumps(dict(returncode=rc,at=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2)+'\n')
