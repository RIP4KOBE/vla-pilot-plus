"""Read-only checks downstream of the pending controller gate, without bypassing it."""
import sys,os,json,time,traceback
from pathlib import Path
sys.dont_write_bytecode=True
O=Path(__file__).absolute().parent
A=json.loads((O/'authority-v1.json').read_text());root=Path(A['source']['worktree'])
sys.path.insert(0,str(root));os.chdir(root)
from scripts import qd_ed_n36_engineering_r1 as e,qd_ed_n36_stop as stop
checks=[]
def check(name,fn):
 stop.check();start=time.monotonic()
 try:fn();r=dict(check=name,status='PASS')
 except Exception as ex:r=dict(check=name,status='FAIL',message=str(ex),traceback=traceback.format_exc())
 r['elapsed_seconds']=time.monotonic()-start;checks.append(r);print(name,r['status'],r.get('message',''),flush=True)
plan=json.loads((O/'engineering-plan.draft-disabled-v1.json').read_text());runtime=e.read(plan['runtime']);audit=e.read(plan['audit_plan'])
check('exact disabled runtime projection and file hashes',lambda:e.validate_runtime_binding(plan))
check('frozen stage configuration',lambda:e.r.stage_overrides(runtime))
def cache():
 fingerprints={str(Path(x['path']).resolve()) for x in runtime['files']}
 for task in runtime['tasks'].values():
  actual={str(p.resolve()) for p in Path(task['cache_dir']).rglob('*') if p.is_file()}
  e.w.require(actual and actual<=fingerprints,'task cache inventory')
check('all ten task cache inventories',cache)
check('frozen model checkpoint task and seed inputs',lambda:e.r.validate_runtime_inputs(audit,runtime,e.b.profiles(root),root,{'artifacts':runtime['artifact_root']}))
from scripts.qd_ed_n36_dino import DinoSources
def dino():
 d=DinoSources(plan['runtime'])
 for name,path in d.names.items():d.check_file(name,path)
check('DINO fixed runtime source bindings',dino)
with (O/'input-checks-v1.json').open('x') as f:json.dump(dict(schema='n36-disabled-graph-input-checks-v1',checks=checks,release_enabled=False,measurement_invocations=0,full_graph_accepted=False),f,indent=2);f.write('\n')
