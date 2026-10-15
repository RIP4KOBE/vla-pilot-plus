import ast, datetime, hashlib, json, pathlib, subprocess
OUT=pathlib.Path(__file__).parent
A=json.loads((OUT/'authority-v1.json').read_text())
ROOT=pathlib.Path(A['source']['worktree'])
checks=[]; inputs={}; excerpts=[]
def sha(b): return hashlib.sha256(b).hexdigest()
def check(name,ok,detail=None):
 checks.append({'check':name,'status':'PASS' if ok else 'FAIL','detail':detail})
def record(path):
 p=pathlib.Path(path); b=p.read_bytes(); r={'path':str(p),'bytes':len(b),'sha256':sha(b)}; inputs[str(p)]=r; return r

def read(ref,label):
 p=pathlib.Path(ref['path']); r=record(p)
 check(label+': exact reference',r['sha256']==ref['sha256'] and ('bytes' not in ref or ref['bytes']==r['bytes']) and not p.is_symlink(),{'expected':ref,'actual':r})
 return json.loads(p.read_text())
def git(*args): return subprocess.check_output(['git','--no-replace-objects',*args],cwd=ROOT)
def tracked(rel):
 p=ROOT/rel
 # Identify regular tracked bytes before opening: no credential/design/results inventory discovery.
 pin=A['source']['commit']; db=None; key=rel
 if rel.startswith('third_party/lerobot/'):
  meta=git('ls-tree',pin,'--','third_party/lerobot').decode().split()
  assert meta[:2]==['160000','commit'];pin=meta[2]
  common=pathlib.Path(git('rev-parse','--git-common-dir').decode().strip())
  db=(ROOT/common/'modules/third_party/lerobot').resolve();key=rel[len('third_party/lerobot/'):]
 args=['--git-dir='+str(db)] if db else []
 row=git(*args,'ls-tree',pin,'--',key).decode().strip();parts=row.split()
 if len(parts)<4 or parts[0] not in ('100644','100755') or parts[1]!='blob':
  check('tracked regular source '+rel,False,row);return
 if any((ROOT/pathlib.Path(*pathlib.Path(rel).parts[:i])).is_symlink() for i in range(1,len(pathlib.Path(rel).parts)+1)):
  check('unambiguous source '+rel,False,'symlink component');return
 data=p.read_bytes(); committed=git(*args,'cat-file','blob',parts[2]);r=record(p)
 check('tracked bytes '+rel,data==committed,{'pin':pin,'blob':parts[2],'record':r})
 expected=source_index.get(rel)
 check('source inventory '+rel,expected==r['sha256'],{'expected':expected,'actual':r['sha256']})
 for f in runtime['files']:
  if f['path']==str(p):check('runtime file '+rel,f['sha256']==r['sha256'] and f.get('size_bytes',len(data))==len(data) and f.get('resolved_path',str(p))==str(p),f)

def excerpt(path,ranges):
 p=pathlib.Path(path); r=record(p); lines=p.read_text().splitlines()
 for start,end in ranges:
  excerpts.append({'source':r,'start_line':start,'end_line':min(end,len(lines)),'text':'\n'.join(f'{i}: {lines[i-1]}' for i in range(start,min(end,len(lines))+1))})
record(OUT/'authority-v1.json')
for key in ('standing_authority','boundary_diagnosis'):read(A[key],key)
prior=read(A['prior_root_acceptance'],'prior root acceptance')
D=pathlib.Path(A['proposed_artifact_directory'])
report=json.loads((D/'report-v2.json').read_text());record(D/'report-v2.json')
manifest=read(report['generated_artifact_manifest'],'proposal manifest')
manifest_index={pathlib.Path(r['path']).name:r for r in manifest['files']}
controller=read(manifest_index['controller-semantics.json'],'proposed controller')
proposals={k:read(ref,'proposal '+k) for k,ref in controller['review_evidence'].items()}
runtime=read(controller['runtime'],'runtime');closure=read(controller['runtime_closure'],'closure')
source=read(runtime['preparation']['source_record'],'source record');source_index={r['path']:r['sha256'] for r in source['files']}
check('source record canonical inventory digest',sha(json.dumps(source['files'],sort_keys=True,separators=(',',':'),allow_nan=False).encode())==source['sha256'],{'entries':len(source['files']),'full_inventory_files_verified':False})
old_controller=read(prior['controller'],'prior accepted controller')
old_runtime=read(prior['runtime'],'prior accepted runtime')
old_closure=read(prior['runtime_closure'],'prior accepted closure')
old_proposals={k:read(ref,'prior accepted evidence '+k) for k,ref in old_controller['review_evidence'].items()}
check('final Git identities',git('rev-parse','HEAD','HEAD^{tree}').decode().splitlines()==[A['source']['commit'],A['source']['tree']])
check('tracked clean',all(subprocess.run(['git','diff',*args,'--quiet','HEAD','--'],cwd=ROOT).returncode==0 for args in [[],['--cached']]))
changes=git('diff','--name-only',prior['current_source']['commit'],A['source']['commit'],'--').decode().splitlines()
check('controller continuity through operational source changes',set(changes)=={'scripts/qd_ed_n36_engineering_r1.py','scripts/qd_ed_n36_readiness_prepare.py','tests/test_n36_engineering_r1.py','tests/test_n36_readiness_prepare.py'},changes)
check('runtime continuity: only preparation source bindings changed',{k for k in set(runtime)|set(old_runtime) if runtime.get(k)!=old_runtime.get(k)}=={'preparation'} and {k for k in set(runtime['preparation'])|set(old_runtime['preparation']) if runtime['preparation'].get(k)!=old_runtime['preparation'].get(k)}=={'source','source_record'})
check('closure continuity: only runtime reference changed',{k for k in set(closure)|set(old_closure) if closure.get(k)!=old_closure.get(k)}=={'runtime'})
check('runtime/closure/controller agree',closure['runtime']==controller['runtime'] and controller['source']==closure['modules'][controller['module']] and controller['module'] in closure['required_after'])
check('final source bindings agree',source['commit']==runtime['preparation']['source']==controller['source_commit']==A['source']['commit'] and runtime['worktree']==str(ROOT))
check('runtime disabled',runtime['preparation']['release_enabled'] is False and runtime['preparation']['runtime_ready'] is False and runtime['provider_ready'] is False and runtime['cuda_egl_verified'] is False and runtime['provider_evidence'] is None and runtime['preparation']['historical_readiness_is_not_current'] is True)
for k,p in proposals.items():
 check(k+': final binding and pending status',p['runtime']==controller['runtime'] and p['runtime_closure']==controller['runtime_closure'] and p['source_commit']==A['source']['commit'] and p['status']=='PENDING_INDEPENDENT_AND_ROOT_REVIEW' and p['fixture_only'] is False and p['kind']=='deployed_source_review' and p['release_enabled'] is False and p['native_execution_observed'] is False)
 check(k+': accepted semantic continuity',p['findings']==old_proposals[k]['findings'] and p['sources']==old_proposals[k]['sources'])
 for ref in p['sources']:
  rr=record(ref['path']);check(k+': deployed source hash '+ref['path'],rr['sha256']==ref['sha256'])
 for field in ['preparation_authority','prior_evidence']:
  # One-hop referenced projection continuity; no recursive history traversal.
  read(p['reference_refresh_lineage'][field],k+' refresh '+field)
check('controller stays pending',controller['status']=='PENDING_INDEPENDENT_AND_ROOT_REVIEW' and controller['reference_refresh_lineage']['new_root_approval'] is False and controller['physical_gain_certified'] is False and controller['release_enabled'] is False)
expected={'control_delta':True,'control_ori':True,'control_dim':6,'impedance_mode':'fixed','input_min':[-1]*6,'input_max':[1]*6,'output_min':[-.05]*3+[-.5]*3,'output_max':[.05]*3+[.5]*3,'policy_freq':20,'uncouple_pos_ori':True,'interpolator_pos':None,'interpolator_ori':None}
check('all twelve expected instance fields',controller['instance']==expected and old_controller['instance']==expected,expected)
check('semantic contract continuity',all(controller[k]==old_controller[k] for k in ('schema','class','module','source','semantics','physical_gain_certified')))
rels=['core/env_adapters/libero_adapter.py','third_party/libero_pro/libero/libero/envs/env_wrapper.py','third_party/lerobot/src/lerobot/processor/pipeline.py','third_party/lerobot/src/lerobot/processor/converters.py','third_party/lerobot/src/lerobot/processor/core.py','third_party/lerobot/src/lerobot/utils/constants.py','scripts/qd_ed_n34_controller.py','scripts/qd_ed_n34_source.py','scripts/qd_ed_n23_worker.py','scripts/qd_ed_n36_engineering_r1.py']
for rel in rels:tracked(rel)
module_names=['robosuite.controllers.osc','robosuite.controllers.base_controller','robosuite.utils.control_utils','robosuite.controllers.controller_factory','robosuite.controllers','robosuite.robots.single_arm','robosuite.robots.manipulator','robosuite.environments.robot_env','robosuite.models.robots.manipulators.panda_robot','robosuite.models.grippers.panda_gripper']
for name in module_names:
 ref=closure['modules'][name];rr=record(ref['path']);check('closure deployed module '+name,ref['sha256']==rr['sha256'] and not pathlib.Path(ref['path']).is_symlink(),rr)
site=pathlib.Path('/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/robosuite')
config=json.loads((site/'controllers/config/osc_pose.json').read_text())
check('config exact scales and modes',config['type']=='OSC_POSE' and config['control_delta'] is True and config['uncouple_pos_ori'] is True and config['impedance_mode']=='fixed' and config['interpolation'] is None and config['input_min']==-1 and config['input_max']==1 and config['output_min']==expected['output_min'] and config['output_max']==expected['output_max'] and config['position_limits'] is None and config['orientation_limits'] is None)
validator_ast=ast.parse((ROOT/'scripts/qd_ed_n34_controller.py').read_text())
constants={n.targets[0].id:ast.literal_eval(n.value) for n in validator_ast.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('FIELDS','INSTANCE_ATTRIBUTES')}
check('validator exact fields and attribute adapter',set(constants['FIELDS'])==set(expected) and constants['INSTANCE_ATTRIBUTES']=={'control_delta':'use_delta','control_ori':'use_ori','control_dim':'control_dim','impedance_mode':'impedance_mode','input_min':'input_min','input_max':'input_max','output_min':'output_min','output_max':'output_max','policy_freq':'control_freq','uncouple_pos_ori':'uncoupling','interpolator_pos':'interpolator_pos','interpolator_ori':'interpolator_ori'},constants)
for p,rs in [(site/'controllers/osc.py',[(108,200),(218,266),(367,381)]),(site/'controllers/base_controller.py',[(104,123)]),(site/'controllers/config/osc_pose.json',[(1,25)]),(site/'utils/control_utils.py',[(114,147),(150,177)]),(site/'controllers/controller_factory.py',[(63,91),(113,129)]),(site/'models/grippers/panda_gripper.py',[(38,66)]),(site/'robots/single_arm.py',[(118,135),(231,256)]),(site/'robots/manipulator.py',[(16,31)]),(site/'environments/robot_env.py',[(558,584),(198,210)]),(site/'models/robots/manipulators/panda_robot.py',[(25,31)]),(ROOT/rels[0],[(41,75),(718,726),(809,815),(1011,1015),(1710,1729)]),(ROOT/rels[1],[(13,80),(87,88),(152,162)]),(ROOT/rels[2],[(270,316),(1436,1436)]),(ROOT/rels[3],[(179,209),(326,389)]),(ROOT/rels[4],[(24,49)]),(ROOT/rels[5],[(26,32)]),(ROOT/'scripts/qd_ed_n34_controller.py',[(13,111)]),(ROOT/'scripts/qd_ed_n34_source.py',[(339,377),(380,425)]),(ROOT/'scripts/qd_ed_n36_engineering_r1.py',[(100,143)])]:excerpt(p,rs)
check('STOP absent',not any(pathlib.Path(p).exists() for p in A['stop_authority']['paths']))
check('deadline live',datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(A['stop_authority']['deadline'].replace('Z','+00:00')))
result={'schema':'n36-controller-static-checks-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'method':'stdlib JSON/hash/AST and read-only Git only; no production imports or validator execution','checks':checks,'source':A['source'],'input_files':list(inputs.values()),'failure_count':sum(c['status']=='FAIL' for c in checks),'full_source_inventory_verified':False,'full_runtime_closure_verified':False,'loaded_instance_observed':False}
for name,obj in [('static-checks-v1.json',result),('source-excerpts-v1.json',{'schema':'n36-controller-source-excerpts-v1','excerpts':excerpts})]:
 with (OUT/name).open('x') as f:json.dump(obj,f,indent=2);f.write('\n')
print(json.dumps({'checks':len(checks),'failures':[x for x in checks if x['status']=='FAIL'],'inputs':len(inputs),'excerpts':len(excerpts)},indent=2))
