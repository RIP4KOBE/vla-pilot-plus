import sys
__file__=sys.argv[1]
sys.argv=[__file__,'scripts.qd_ed_n36_source']
exec(compile(open(__file__,'rb').read(),__file__,'exec'))
import json
from pathlib import Path
from importlib.machinery import PathFinder
from scripts import qd_ed_n36_source as policy
state=policy.active()
rows=[]
for name in ['lerobot','lerobot.processor','models.rdt_runner','configs.state_vec','libero','libero.libero','libero.libero.envs.env_wrapper','robosuite.controllers.osc']:
 search=sys.path
 for i in range(1,len(name.split('.'))+1):
  full='.'.join(name.split('.')[:i]);spec=PathFinder.find_spec(full,search);assert spec is not None,full;search=spec.submodule_search_locations
 rows.append({'module':name,'origin':spec.origin,'sha256':policy.sha(spec.origin) if spec.origin else None,'module_executed':False})
rejected=[]
for search in [sys.path+[''],sys.path+['/home/hynx/VLA-Pilot++']]:
 try:policy.validate_search_path(state.root,search,sys.prefix)
 except ValueError as e:rejected.append(str(e))
 else:raise AssertionError('foreign search accepted')
print(json.dumps({'schema':'n36r2-isolated-import-search-evidence-v1','search_path':sys.path,'search_prefix':sys.prefix,'interpreter':policy.interpreter_identity(),'bootstrap_sha256':state.bootstrap_digest,'source_only_active':True,'resolved_only':rows,'negative_rejections':rejected,'actual_worker_receipt':False,'scope':'Frozen bootstrap executed by CPU harness; no worker/Main/simulator imports or execution; finder resolution only.'}))
