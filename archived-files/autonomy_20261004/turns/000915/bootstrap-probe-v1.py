"""Single root-authorized operational readiness check; not a Dev release."""
import sys,os,json,time,subprocess,datetime as dt
from pathlib import Path
ROOT=Path.cwd().resolve(); sys.path.insert(0,str(ROOT))
from scripts import qd_ed_final_runner as r, qd_ed_gpu_probe as probe, qd_ed_available_gpu_queue as queue
from scripts import qd_ed_n35_runner as adapter, qd_ed_n35_healthcheck as health
from scripts import qd_ed_n35_accounting as accounting
D=Path(__file__).resolve().parent
A=D/'probe-authority-v1.json'
a=json.loads(A.read_text())
def ref(p): return {'path':str(Path(p).resolve()),'sha256':r.digest(p)}
def before():
    stop=Path(a['stop_path']);r.require(not stop.exists() and not stop.is_symlink(),'STOP')
    r.require(dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=160)<dt.datetime.fromisoformat(a['deadline'].replace('Z','+00:00')),'deadline')
    r.require(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==a['source_commit'],'source changed')
    for x in a['source_files']+[a['runtime'],a['operation'],a['user_authority']]: r.require(r.digest(x['path'])==x['sha256'],'bound file changed')
with r.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True):
    before()
    for name,x in a['ledger_prefixes'].items():
        p=ROOT/'data'/name;r.require(p.stat().st_size==x['bytes'] and r.digest(p)==x['sha256'],'ledger changed before preparation')
    events,resources=queue.no_unfinished(ROOT)
    snap=r.budget_snapshot(events,resources)
    margin=accounting.retained_margin(ROOT,a['accounting'])
    admission_budget=accounting.headroom(snap,r.budget_snapshot([],[]),retained_margin_hours=margin,protected_hours=a['protected_hours'],healthcheck=True,need=160)
    runtime=r.read_json(a['runtime']['path']);r.require(Path(runtime['worktree']).resolve()==ROOT,'owning runtime')
    admission=adapter.device_check(); before()
    out=D/'gpu-probe';out.mkdir(exist_ok=False)
    resource='n35_healthcheck_bootstrap_20261009_turn915'
    r.require(not any(e['resource_id']==resource for e in resources),'no replay')
    base={'resource_id':resource,'kind':'n35_resource_preparation_v1','physical_gpu':7,'budget_bucket':'recovery','episode_attempts':0,'reserved_gpu_seconds':160,'output_dir':str(out),'runtime_manifest_sha256':a['runtime']['sha256'],'source_script_sha256':r.digest(Path(probe.__file__)),'source_commit':a['source_commit'],'authority':ref(A),'queue_sha256':r.digest(Path(queue.__file__))}
    r.append_healthcheck_event(ROOT,{**base,'event':'reserved','time_unix':time.time(),'admission':admission,'accounting':admission_budget})
    p=None;started=None;result={};event='aborted'
    try:
        before();adapter.device_check()
        env=r.child_environment(runtime);env.update(QD_ED_GPU_PROBE_PARENT_PID=str(os.getpid()),QD_ED_GPU_PROBE_RESOURCE_ID=resource)
        command=[str(r.PYTHON),str(Path(probe.__file__).resolve()),'_child','--manifest',a['runtime']['path'],'--output',str(out),'--resource-id',resource]
        r.durable_json(out/'command.json',{'argv':command,'authority':ref(A)})
        before();r.append_healthcheck_event(ROOT,{**base,'event':'dispatched','time_unix':time.time(),'timeout_seconds':120})
        with (out/'probe.log').open('w') as log:
            started=time.monotonic();p=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            identity=adapter.process_identity(p.pid);r.durable_json(out/'process.json',identity)
            code=health.wait_probe(p,started,identity,120)
        r.require(code==0,'probe exit nonzero');result=r.read_json(out/'probe-evidence.json')
        r.require(result['resource_id']==resource,'resource mismatch');probe.validate_probe_evidence(result,runtime['gpu_mapping'])
        r.require(r.digest(out/'probe-frame.png')==result['frame_png_sha256'],'frame digest')
        r.require(r.digest(a['runtime']['path'])==a['runtime']['sha256'],'runtime changed')
        event='completed'
    except BaseException as exc:
        if p is not None and p.poll() is None: raise
        if isinstance(exc,(KeyboardInterrupt,SystemExit)):raise
        result={'failure':str(exc)}
    elapsed=0 if started is None else time.monotonic()-started
    terminal={**result,**base,'event':event,'time_unix':time.time(),'gpu_process_wall_seconds':elapsed,'cleanup_complete':p is None or p.poll() is not None,'cost_measurement_complete':True,'measurement':'whole exclusive child process wall through validation and cleanup'}
    r.append_healthcheck_event(ROOT,terminal);r.durable_json(out/'healthcheck-result.json',terminal)
    r.require(event=='completed' and elapsed<=160,'failed or exceeded bound; no automatic retry')
    runtime['cuda_egl_verified']=True;runtime['gpu_mapping']['cuda_egl_verified']=True
    runtime['cuda_egl_probe']={'resource_id':resource,'evidence_path':str(out/'probe-evidence.json'),'evidence_sha256':r.digest(out/'probe-evidence.json')}
    r.require(queue.reusable_probe(runtime,runtime['gpu_mapping'],r.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl'),root=ROOT) is not None,'new proof not reusable')
    r.durable_json(D/'runtime.gpu-ready-v1.json',runtime)
    r.durable_json(D/'probe-review-v1.json',{'status':'PASS','authority':ref(A),'runtime':ref(D/'runtime.gpu-ready-v1.json'),'terminal':ref(out/'healthcheck-result.json'),'gpu_seconds':elapsed,'dev_dispatch':False})
    print(json.dumps({'status':'PASS','gpu_seconds':elapsed,'runtime':ref(D/'runtime.gpu-ready-v1.json')}))
