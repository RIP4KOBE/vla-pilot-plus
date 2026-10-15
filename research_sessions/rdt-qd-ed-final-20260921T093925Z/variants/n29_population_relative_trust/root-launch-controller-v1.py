"""Launch the single reviewed N29 controller and retain its exact process identity."""
from pathlib import Path
import datetime,json,os,subprocess,sys
V=Path(__file__).resolve().parent
ROOT=V.parents[1]/'study_worktree'
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from scripts import qd_ed_n23_worker as w, qd_ed_n29_contract as c, qd_ed_n29_supervise as sup
plan=V/'plan.frozen.v1.gpu7.json';release=V/'execution-release-v1.json'
sup.release_check(release,plan,w.read_ref(c.ref(plan)))
out=V/'execution';out.mkdir(exist_ok=False)
command=[sys.executable,'-B',str(ROOT/'scripts/qd_ed_n29_supervise.py'),'--plan',str(plan),'--release',str(release),'--status',str(out/'supervisor-status-v1.json')]
with (out/'controller.log').open('x') as log:
    proc=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    record={'schema':'n29-root-controller-process-v1','recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pid':proc.pid,'proc_start_ticks':Path(f'/proc/{proc.pid}/stat').read_text().rsplit(')',1)[1].split()[19],'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'argv':command,'plan':c.ref(plan),'release':c.ref(release),'maximum_live_gpu_workers':1,'provider':'codex_cli/chatgpt/current managed login','poe_allowed':False}
    w.atomic_json(out/'controller-process-v1.json',record)
    print(json.dumps({'controller_pid':proc.pid,'physical_gpu':7,'maximum_primary_cells':40,'status_path':str(out/'supervisor-status-v1.json')}),flush=True)
    code=proc.wait()
w.atomic_json(out/'root-launch-result-v1.json',{'schema':'n29-root-controller-exit-v1','recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'controller':c.ref(out/'controller-process-v1.json'),'exit_code':code})
print(json.dumps({'controller_exit_code':code}),flush=True)
sys.exit(code)
