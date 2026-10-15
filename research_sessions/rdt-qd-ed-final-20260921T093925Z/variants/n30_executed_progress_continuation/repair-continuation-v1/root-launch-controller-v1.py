"""Launch one detached N30 controller with a persistent exit witness."""
from pathlib import Path
import datetime,json,os,subprocess,sys,time
V=Path(__file__).resolve().parent;ROOT=V.parent.parents[1]/'study_worktree'
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from scripts import qd_ed_n23_worker as w,qd_ed_n30_r1_contract as c,qd_ed_n30_r1_supervise as sup
plan=V/'plan.frozen.v1.gpu7.json';release=V/'execution-release-v1.json';out=V/'execution'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def pid_identity(pid):
 return {'pid':pid,'proc_start_ticks':Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19],
   'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
sup.release_check(release,plan,w.read_ref(c.ref(plan)))
if sys.argv[1:]==['--monitor']:
 command=[sys.executable,'-B',str(ROOT/'scripts/qd_ed_n30_r1_supervise.py'),'--plan',str(plan),
   '--release',str(release),'--status',str(out/'supervisor-status-v1.json')]
 with (out/'controller.log').open('x') as log:
  proc=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
  w.atomic_json(out/'controller-process-v1.json',{'schema':'n30-r1-root-controller-process-v1','recorded_at':now(),
    **pid_identity(proc.pid),'argv':command,'plan':c.ref(plan),'release':c.ref(release),'maximum_live_gpu_workers':1,
    'provider':'codex_cli/chatgpt/current managed login','poe_allowed':False,'monitor_pid':os.getpid()})
  code=proc.wait()
 w.atomic_json(out/'root-launch-result-v1.json',{'schema':'n30-r1-root-controller-exit-v1','recorded_at':now(),
   'controller':c.ref(out/'controller-process-v1.json'),'exit_code':code})
 sys.exit(code)
assert sys.argv[1:]==[]
out.mkdir(exist_ok=False)
command=[sys.executable,'-B',str(Path(__file__).resolve()),'--monitor']
with (out/'monitor.log').open('x') as log:
 monitor=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
w.atomic_json(out/'monitor-process-v1.json',{'schema':'n30-r1-root-detached-exit-monitor-v1','recorded_at':now(),
 **pid_identity(monitor.pid),'argv':command,'plan':c.ref(plan),'release':c.ref(release)})
for _ in range(50):
 if (out/'controller-process-v1.json').exists():break
 if monitor.poll() is not None:raise RuntimeError('N30 monitor ended before controller record; inspect retained monitor.log')
 time.sleep(.1)
assert (out/'controller-process-v1.json').is_file()
record=w.read_ref(c.ref(out/'controller-process-v1.json'))
print(json.dumps({'controller_pid':record['pid'],'monitor_pid':monitor.pid,'physical_gpu':7,
 'maximum_new_cells':10,'status_path':str(out/'supervisor-status-v1.json'),'persistent_exit_witness':str(out/'root-launch-result-v1.json')}))

