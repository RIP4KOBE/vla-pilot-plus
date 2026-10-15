import json,hashlib,pathlib,subprocess,time,os,resource,ast,collections
O=pathlib.Path(__file__).parent; A=json.load(open(O/'authority-v1.json')); P=pathlib.Path(A['preparation_report']['path']).parent
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);resource.setrlimit(resource.RLIMIT_CPU,(180,180));t=time.monotonic();cpu=time.process_time()
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for x in iter(lambda:f.read(8*1024*1024),b''):h.update(x)
 return h.hexdigest()
def read(p):return json.load(open(p))
refs=[]
def verify(r):
 h=sha(r['path']);assert h==r['sha256'],r['path'];refs.append({'path':r['path'],'sha256':h,'bytes':pathlib.Path(r['path']).stat().st_size});return read(r['path']) if r['path'].endswith('.json') else None
for v in A.values():
 if isinstance(v,dict) and 'path' in v:verify(v)
R=read(A['preparation_report']['path']);D=read(A['draft']['path']);PR=read(A['protocol']['path'])
for v in R['artifacts'].values():verify(v)
for v in R['reused_tests']:verify(v)
for c in R['commands']:
 for k in ['receipt','environment_receipt']:
  if k in c:verify(c[k])
for f in ['prepare-artifacts-result-v2.json','prepare_artifacts_v2.py','runpy-diagnostic-v1.json','runtime-inventory-delta-v2.json']:
 p=P/f;refs.append({'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size})
root=pathlib.Path(A['owning_worktree']);src=D['source'];assert src==D['scientific_source'];assert subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()==A['source']
source_bad=[]
for row in src['files']:
 p=root/row['path']
 if sha(p)!=row['sha256']:source_bad.append(row['path'])
assert not source_bad,source_bad
# Compare every selected source to exact Git blobs, including pinned submodule databases.
def git(*args):return subprocess.check_output(['git','--no-replace-objects','-C',str(root),*args])
common=pathlib.Path(git('rev-parse','--git-common-dir').decode().strip());common=(root/common).resolve();groups=collections.defaultdict(list)
for row in src['files']:
 s=next((s for s in ['third_party/rdt','third_party/lerobot'] if row['path'].startswith(s+'/')),None);groups[s].append(row)
for sub,rows in groups.items():
 prefix=['git','--no-replace-objects','-C',str(root)];commit=A['source']
 if sub:
  commit=git('ls-tree',A['source'],sub).decode().split()[2];prefix+=['--git-dir='+str(common/'modules'/sub)]
 names=[r['path'][len(sub)+1:] if sub else r['path'] for r in rows]
 raw=subprocess.check_output(prefix+['cat-file','--batch'],input=('\n'.join(commit+':'+n for n in names)+'\n').encode());i=0
 for r in rows:
  e=raw.index(b'\n',i);head=raw[i:e].split();assert head[1]==b'blob';size=int(head[2]);blob=raw[e+1:e+1+size];i=e+size+2;assert hashlib.sha256(blob).hexdigest()==r['sha256'],r['path']
 assert i==len(raw)
CL=verify(D['runtime_closure']);N=verify(D['native_build']);C=verify(D['controller_semantics']);RT=verify(D['runtime']);assert CL['runtime']==C['runtime']==D['runtime']
# Hash unique executable inventory bytes, no model weights or historical tensors.
files={r['path']:r['sha256'] for r in CL['modules'].values()};files.update({r['path']:r['sha256'] for r in N['libraries']});files[CL['interpreter']['path']]=CL['interpreter']['sha256']
for p,h in files.items():assert sha(p)==h,p
for v in C['review_evidence'].values():
 e=verify(v);assert e['runtime']==D['runtime'] and e['source_commit']==A['source']
 for r in e['sources']:assert sha(r['path'])==r['sha256']
M=read(P/'native-cpu-mapped-v2.json');assert M['manifest']==D['native_build'];idx={r['path']:r['sha256'] for r in N['libraries']};assert all(idx[r['path']]==r['sha256'] for r in M['libraries']);assert [r['path'] for r in M['libraries']]==read(P/'native-mapping-diagnostic-v2.json')['actual_mapped_paths']
SE=read(P/'source-execution-post-compose-v1.json');RR=read(P/'runtime-execution-frozen-v2.json');ix={str(root/r['path']):r['sha256'] for r in src['files']};ix.update({r['path']:r['sha256'] for r in CL['modules'].values()});gen={k:v['sha256'] for k,v in CL['generated_modules'].items()}
assert all(ix.get(r['path'],gen.get(r['module']))==r['sha256'] for r in SE['compiled']+SE['startup_source_only'])
assert {r['module'] for r in SE['startup_source_only']}=={'encodings','encodings.aliases','encodings.utf_8'}
assert all(CL['modules'].get(k)==v for k,v in RR['modules'].items() if k not in ('__main__','__mp_main__'))
for k,v in RR['generated_modules'].items():assert hashlib.sha256(v['source_utf8'].encode()).hexdigest()==gen[k]
assert D['episodes']==PR['episodes'];assert len(D['episodes'])==40
T={k:verify(v)['resolved_config'] for k,v in PR['scientific_contract']['matched_controls']['profile_templates'].items()}
def norm(config):
 x=json.loads(json.dumps(config));x.setdefault('closure_intent_mode','off');x.setdefault('n35_runtime_binding',None);x.setdefault('nonprogress_tangent_mode','off');x.setdefault('n36_runtime_binding',None)
 x['mechanism_pretest'].pop('output_dir');x['mechanism_pretest'].pop('run_id');x['n34_runtime_binding']=None;x['n36_runtime_binding']=None
 return x
manifest_checks=[]
for row in D['episodes']:
 m=verify(D['expected_manifests'][row['episode_key']]);assert m['row']==row
 for k in ['source','scientific_source','runtime','runtime_closure','native_build','controller_semantics']:assert m[k]==D[k]
 cfg=m['resolved_config'];base=norm(T['N34' if row['profile']=='N36' else row['profile']]);got=norm(cfg)
 if row['profile']=='N36':base['nonprogress_tangent_mode']='nonprogress_tangent_v1'
 assert got==base,(row['episode_key'],{k:(got.get(k),base.get(k)) for k in got.keys()|base.keys() if got.get(k)!=base.get(k)})
 bind={'task_id':row['task_id'],'source_commit':A['source'],'run_id':row['episode_key']}
 assert cfg['n34_runtime_binding']==(bind if row['profile'] in ['N34','N36'] else None)
 assert cfg['n36_runtime_binding']==(bind if row['profile']=='N36' else None)
 assert pathlib.Path(m['output_dir']).is_relative_to(D['artifact_root']);assert m['argv'][1]==str(root/'main.py')
 task=RT['tasks'][str(row['task_id'])];rf={r['path']:r['sha256'] for r in RT['files']};assert rf[task['init_path']]==row['init_file_sha256'] and rf[task['bddl_path']]==row['bddl_sha256']
 manifest_checks.append({'episode_key':row['episode_key'],'config_sha256':m['composed_config_sha256'],'manifest_sha256':D['expected_manifests'][row['episode_key']]['sha256']})
for key in ['runtime_inventory','seed_plan']:assert sha(D[key+'_path'])==D[key+'_sha256']
old=subprocess.check_output(['git','show','68c341ef6357887c4ae33ddafad00fab17582302:core/env_adapters/libero_adapter.py'])
new=(root/'core/env_adapters/libero_adapter.py').read_bytes()
def funcs(raw):return {n.name:ast.dump(n,include_attributes=False) for n in ast.walk(ast.parse(raw)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
f1,f2=funcs(old),funcs(new);changed=[k for k in f1.keys()|f2.keys() if f1.get(k)!=f2.get(k)];assert changed==['delta_actions_to_ee_trajectory'],changed
out={'status':'PASS','direct_and_focused_references':refs,'source_commit':A['source'],'exact_git_and_owning_source_files':len(src['files']),'unique_executable_and_native_files_hashed':len(files),'static_native_count':len(N['libraries']),'cpu_mapped_count':len(M['libraries']),'source_execution_records':len(SE['compiled']),'runtime_receipt_modules':len(RR['modules']),'diagnostic_only_aliases':['__main__','__mp_main__'],'all40_exact_protocol':True,'all40_template_config_comparisons':manifest_checks,'controller_adapter_changed_functions':changed,'wall_seconds':time.monotonic()-t,'cpu_seconds':time.process_time()-cpu,'release_enabled':False}
(O/'checks-v1.json').write_text(json.dumps(out,indent=2)+'\n');print({k:v for k,v in out.items() if k not in ['direct_and_focused_references','all40_template_config_comparisons']})
