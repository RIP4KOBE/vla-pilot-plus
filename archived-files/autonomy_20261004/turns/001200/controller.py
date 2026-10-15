"""Operational monitor only; frozen bootstrapped runner owns all dispatch gates."""
import pathlib,json,hashlib,datetime,os,sys,subprocess,traceback
out=pathlib.Path(__file__).resolve().parent
root=pathlib.Path.cwd()
def write(name,value):
 p=out/name;t=p.with_suffix('.tmp');t.write_text(json.dumps(value,indent=2)+'\n');t.replace(p)
def read(ref):
 p=pathlib.Path(ref['path']);b=p.read_bytes();assert hashlib.sha256(b).hexdigest()==ref['sha256'];return json.loads(b)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def identity(pid):
 a=pathlib.Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split();return {'pid':pid,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':int(a[19]),'state':a[0]}
if sys.stdin.read(1)!='G':raise SystemExit('parent start gate absent')
refs=json.loads((out/'release-refs-v1.json').read_text());plan=read(refs['plan']);runtime=read(plan['runtime']);authority=read(plan['authority'])
try:
 assert not pathlib.Path(plan['stop_path']).exists() and not pathlib.Path(plan['stop_path']).is_symlink()
 assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(authority['coordinator_ends_at'].replace('Z','+00:00'))
 manifest=read(next(iter(plan['expected_manifests'].values())))
 env=os.environ.copy();env.update(runtime['environment']);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
 argv=[manifest['argv'][0],'-I','-S','-B','-X','pycache_prefix=/dev/null',str(root/'scripts/qd_ed_n36_bootstrap.py'),'scripts.qd_ed_n36_runner','--plan',refs['plan']['path'],'--plan-sha256',refs['plan']['sha256'],'--release',refs['release']['path'],'--release-sha256',refs['release']['sha256']]
 with (out/'runner.log').open('ab',buffering=0) as log:
  p=subprocess.Popen(argv,cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
  child=identity(p.pid);write('runner-process-v1.json',{'at':now(),'handle':child,'argv':argv,**refs})
  write('controller-status-v1.json',{'status':'RUNNING_FROZEN_BOOTSTRAPPED_RUNNER','at':now(),'runner':child,**refs})
  code=p.wait()
 write('controller-result-v1.json',{'status':'RETURNED' if code==0 else 'ERROR_REQUIRES_ROOT_RECONCILIATION','exit_code':code,'at':now(),'runner':child,'log':str(out/'runner.log'),**refs})
except BaseException as exc:
 write('controller-result-v1.json',{'status':'ERROR_REQUIRES_ROOT_RECONCILIATION','error':repr(exc),'traceback':traceback.format_exc(),'at':now()});raise
finally:
 if (out/'controller-result-v1.json').exists():write('controller-status-v1.json',{'status':'TERMINAL_REQUIRES_ROOT_RECONCILIATION','at':now(),'result_path':str(out/'controller-result-v1.json')})
