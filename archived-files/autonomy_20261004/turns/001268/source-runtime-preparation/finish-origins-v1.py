import os,sys,json,time,resource,datetime as dt,hashlib,importlib
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=Path.cwd().resolve();START=time.monotonic();resource.setrlimit(resource.RLIMIT_CPU,(30,30));os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);sys.path.insert(0,str(ROOT))
a=json.loads((OUT/'authority-v1.json').read_text());assert not any(os.path.lexists(p) for p in a['STOP_paths']);assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(a['deadline'].replace('Z','+00:00'));assert os.environ['CUDA_VISIBLE_DEVICES']==''
from scripts import qd_ed_n36_bridge as b,qd_ed_n34_source as s,qd_ed_n23_worker as w
from importlib.machinery import PathFinder
plan=json.loads((OUT/'plan.complete-disabled-v1.json').read_text());runtime=w.read_ref(plan['runtime']);source=plan['source'];os.environ['LIBERO_CONFIG_PATH']=runtime['environment']['LIBERO_CONFIG_PATH']
search=[str(ROOT)]+runtime['environment']['PYTHONPATH'].split(os.pathsep)+[p for p in sys.path if p and p!=str(ROOT)]
resolutions=[]
for name in ['lerobot','lerobot.processor','models.rdt_runner','configs.state_vec','libero','libero.libero','libero.libero.envs.env_wrapper','robosuite.controllers.osc']:
 path=search
 for i in range(1,len(name.split('.'))+1):
  full='.'.join(name.split('.')[:i]);spec=PathFinder.find_spec(full,path);assert spec is not None,full;path=spec.submodule_search_locations
 if spec.origin:
  p=Path(spec.origin).resolve();record={'path':str(p),'sha256':w.sha(p)}
  if name.startswith(('lerobot','libero','models','configs')):assert p.is_relative_to(ROOT)
 else:
  record={'namespace_locations':list(spec.submodule_search_locations)};assert all(Path(p).resolve().is_relative_to(ROOT) for p in record['namespace_locations'])
 resolutions.append({'module':name,'resolved_origin':record,'module_executed':False})
sys.path[:0]=runtime['environment']['PYTHONPATH'].split(os.pathsep);loaded={}
for name in ['lerobot','libero','libero.libero','configs.state_vec']:
 mod=importlib.import_module(name)
 if mod.__file__:
  p=Path(mod.__file__).resolve();assert p.is_relative_to(ROOT);loaded[name]={'path':str(p),'sha256':w.sha(p),'spec_origin':mod.__spec__.origin}
 else:
  paths=list(mod.__path__);assert paths and all(Path(p).resolve().is_relative_to(ROOT) for p in paths);loaded[name]={'namespace_locations':paths,'spec_origin':mod.__spec__.origin,'loader':type(mod.__loader__).__name__}
attested=s.attest_loaded(ROOT,source);assert not any(os.path.lexists(p) for p in a['STOP_paths'])
report={'status':'PASS','search_path':search,'resolved_only':resolutions,'actual_cpu_imports':loaded,'production_attest_loaded':attested,'source_commit':source['commit'],'runtime':plan['runtime'],'runtime_closure':plan['runtime_closure'],'process':{'pid':os.getpid(),'proc_start_ticks':Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19],'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()},'scope':'CPU preparation imports and passive resolution only. No simulator/model execution, no immutable worker runtime observation, no before/after worker receipt.','wall_seconds':time.monotonic()-START,'release_enabled':False}
p=OUT/'import-origins-v1.json';assert not p.exists();p.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':'PASS','actual_imports':list(loaded),'resolved':len(resolutions),'seconds':report['wall_seconds']}))
