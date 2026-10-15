import ast,copy,datetime,hashlib,json,pathlib,subprocess,types
OUT=pathlib.Path(__file__).resolve().parent
A=json.loads((OUT/'authority-v1.json').read_text()); ROOT=pathlib.Path(A['source']['worktree']); G=pathlib.Path(A['report']['path']).parent
E={'schema':'n36-recovery-binding-direct-evidence-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reference_checks':[],'checks':{},'source_slices':[]}
def sha(b):return hashlib.sha256(b).hexdigest()
def load(p):return json.loads(pathlib.Path(p).read_text())
def canonical(x):return sha(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
def refcheck(r,label):
 p=pathlib.Path(r['path']);b=p.read_bytes();v={'label':label,'path':str(p),'bytes':len(b),'sha256':sha(b),'hash_matches':sha(b)==r['sha256']};v['size_matches']=len(b)==r['bytes'] if 'bytes'in r else None;E['reference_checks'].append(v);assert v['hash_matches'] and v['size_matches'] is not False;return b
def record(p,label):
 p=pathlib.Path(p);b=p.read_bytes();r={'path':str(p),'bytes':len(b),'sha256':sha(b)};refcheck(r,label);return r
def diff(a,b,p=''):
 if type(a)!=type(b):return [p]
 if isinstance(a,dict):return [z for k in sorted(a.keys()|b.keys()) for z in ([p+'/'+k] if k not in a or k not in b else diff(a[k],b[k],p+'/'+k))]
 return [] if a==b else [p]
def git(*args):return subprocess.check_output(['git','--no-replace-objects','-C',str(ROOT),*args],text=True).strip()
record(OUT/'authority-v1.json','review authority')
for k in ('standing_authority','terminal_reconciliation','report'):refcheck(A[k],k)
T=load(A['terminal_reconciliation']['path']);R=load(A['report']['path'])
for k in ('process_record','exit'):refcheck(T[k],k)
E['checks']['terminal']={'live_handles':T['live_handles'],'status':T['status'],'exit':load(T['exit']['path']),'basis':'Direct terminal reconciliation, no live provider/process probing'}
manifest=load(G/'outputs-manifest-final-v1.json');record(G/'outputs-manifest-final-v1.json','final manifest')
names=['deployment.prospective-disabled-v1.json','native-inventory.prospective-disabled-v1.json','recovery-identity.prospective-disabled-v1.json','source-record.prospective-disabled-v1.json','minimal-follow-on-canonical-source-pin.diff','specification.canonical-final.diff','commands-checks.final-v1.json']
for r in manifest['files']:
 if '.canonical-' in pathlib.Path(r['path']).name or pathlib.Path(r['path']).name in names:refcheck(r,'final canonical or reused artifact')
S=load(R['prospective_specification']['path']);P=load(R['prospective_policy']['path']);D=load(R['graph']['path']);I=load(D['identity']['path']);inputs=load(G/'inputs-manifest-v1.json')
def old(name):
 r=next(r for r in inputs['files'] if r['path'].endswith('/'+name));refcheck(r,'direct comparison baseline');return load(r['path'])
oldspec=old('engineering-r1-spec.prospective-disabled-v7.json');oldpolicy=old('preparation-policy.prospective-disabled-v2.json')
E['checks']['specification_changed_fields']=diff(oldspec,S);E['checks']['policy_changed_fields']=diff(oldpolicy,P)
for r,label in [(S['canonical_runtime'],'immutable disabled template'),(S['prospective_amendment'],'unchanged pinned amendment'),(S['full_audit_view']['immutable_original_plan'],'direct scientific audit baseline'),(S['runtime_binding']['amendment'],'direct readiness amendment'),(S['runtime_binding']['repair_authority'],'direct readiness authority'),(P['previous_specification'],'policy previous specification'),(S['runtime_binding']['accounting_contract'],'unchanged preparation contract')]:refcheck(r,label)
for k in ['scope','accounting_proposal','retained_ledger_prefixes','retained_snapshot','retained_snapshot_reference','canonical_runtime','full_audit_view','prospective_amendment','unchanged_files_and_rules']:assert S[k]==oldspec[k]
E['checks']['unchanged_specification_fields']=['scope','accounting_proposal','retained_ledger_prefixes','retained_snapshot','retained_snapshot_reference','canonical_runtime','full_audit_view','prospective_amendment','unchanged_files_and_rules']
B=load(S['canonical_runtime']['path']);runtime=load(D['runtime']['path']);source=load(D['source_record']['path']);audit=load(D['audit']['path']);plan=load(D['plan']['path']);orig=load(S['full_audit_view']['immutable_original_plan']['path'])
E['checks']['runtime_changes']=diff(B,runtime);assert E['checks']['runtime_changes']==['/preparation/source','/preparation/source_record']
E['checks']['runtime_provider']={k:runtime['frozen_stage_provider'][k] for k in ['backend','auth_mode','model']};E['checks']['gpu_mapping']=runtime['gpu_mapping']
for k in ['cohort','episodes','limits','worker_contract','deadline','protocol','protocol_review','accounting']:assert audit[k]==orig[k]
E['checks']['audit_science_equal_original']=['cohort','episodes','limits','worker_contract','deadline','protocol','protocol_review','accounting']
assert len(audit['episodes'])==40 and audit['stop_authority']==A['stop_authority']==plan['stop_authority']==I['stop_authority']
assert plan['source']==source==plan['scientific_source']==audit['source']==audit['scientific_source']
E['checks']['prospective_flags']={'audit_frozen':audit['frozen'],'audit_dispatch_authority':audit['dispatch_authority'],'audit_release_enabled':audit['release_enabled'],'plan_frozen':plan['frozen'],'plan_release_enabled':plan['release_enabled'],'runtime_ready':runtime['preparation']['runtime_ready'],'provider_ready':runtime['provider_ready'],'all40_count':len(audit['expected_manifests']),'engineering_manifest':plan['engineering_manifest'],'controller_semantics':plan['controller_semantics'],'scientific_equivalence':plan['scientific_equivalence']}
oldsource=old('prospective-final-source-v1.json');a={x['path']:x['sha256']for x in oldsource['files']};b={x['path']:x['sha256']for x in source['files']};assert a.keys()==b.keys();changed=[p for p in b if a[p]!=b[p]];git_changed=git('diff','--name-only',oldsource['commit'],source['commit'],'--').splitlines();assert changed==git_changed
for p in changed:assert sha((ROOT/p).read_bytes())==b[p] and sha(subprocess.check_output(['git','-C',str(ROOT),'show',source['commit']+':'+p]))==b[p]
assert canonical(source['files'])==source['sha256'];assert git('rev-parse','HEAD')==A['source']['commit']==source['commit'];assert git('rev-parse','HEAD^{tree}')==A['source']['tree'];assert git('diff','--name-only','HEAD','--')==''
E['checks']['source_projection']={'base_commit':oldsource['commit'],'commit':source['commit'],'tree':A['source']['tree'],'inventory_count':len(b),'same_path_inventory':True,'changed_paths':changed,'changed_bytes_match_commit_and_worktree':True,'inventory_canonical_digest_matches':True,'unmodified_entries_inherited':True,'poe_file_opened':False,'full_source_verification_run':False,'source_base_diff':git('diff','--name-only',S['runtime_binding']['source_base'],source['commit'],'--').splitlines()}
oldclosure=old('runtime-closure.disabled-v1.json');E['checks']['closure_changes']=diff(oldclosure,load(D['runtime_closure']['path']))
paths={k:v for k,v in P.items() if k.endswith('_path')};paths.update({k:S['runtime_binding'][k] for k in ('runtime_path','source_record_path')});E['checks']['fixed_slots']={k:{'path':v,'canonical':str(pathlib.Path(v).resolve())==v,'exists':pathlib.Path(v).exists(),'symlink':pathlib.Path(v).is_symlink()}for k,v in paths.items()};assert all(v['canonical'] and not v['symlink'] for v in E['checks']['fixed_slots'].values());assert len(set(paths.values()))==len(paths)
assert paths['source_record_path']==D['source_record']['path'];assert paths['disabled_runtime_path']==D['runtime']['path'];assert runtime['preparation']['source_record']==D['source_record']
E['checks']['source_pin_diff']={'reference':record(G/'minimal-follow-on-canonical-source-pin.diff','reviewed source pin diff'),'applies_without_write':subprocess.run(['git','-C',str(ROOT),'apply','--check',str(G/'minimal-follow-on-canonical-source-pin.diff')],capture_output=True,text=True).returncode==0}
code=(ROOT/'scripts/qd_ed_n36_engineering_r1.py').read_text();module=ast.parse(code);constants={n.targets[0].id:ast.literal_eval(n.value) for n in module.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('SPECIFICATION','AMENDMENT','HEALTH_ID','HEALTH_KIND','EPISODE_KEY','JOURNALS')}
assert constants['AMENDMENT']==S['prospective_amendment'];assert constants['SPECIFICATION']!=D['specification'];E['checks']['current_spec_pin']=constants['SPECIFICATION'];E['checks']['proposed_spec_pin']=D['specification']
ledger_data={};ledger_rows={};baseline={};E['checks']['ledger_bindings']=[]
for name,r in T['ledger_prefixes'].items():
 data=refcheck(r,'direct terminal ledger');ledger_data[name]=data;ledger_rows[name]=[json.loads(x)for x in data.splitlines()];anchor=S['retained_ledger_prefixes'][name];assert sha(data[:anchor['bytes']])==anchor['sha256'];baseline[name]=[json.loads(x)for x in data[:anchor['bytes']].splitlines()];E['checks']['ledger_bindings'].append({'name':name,'current_bytes':len(data),'retained_bytes':anchor['bytes'],'retained_prefix_matches':True,'new_identity_occurrences':sum(P['resource_id'] in [r.get(k)for k in ('resource_id','attempt_id','episode_key')] for r in ledger_rows[name])})
health=ledger_rows['gpu-healthcheck-ledger.jsonl'];suffix=health[len(baseline['gpu-healthcheck-ledger.jsonl']):];journal=pathlib.Path(S['retained_ledger_prefixes']['gpu-healthcheck-ledger.jsonl']['path']).parent/'readiness-preparation-ledger.jsonl';record(journal,'direct preparation journal');own=load(journal) if False else [json.loads(x)for x in journal.read_bytes().splitlines()];assert own==suffix;assert [r['event']for r in suffix]==['reserved','dispatched','aborted'];assert all(r['resource_id']==I['recovery_of']for r in suffix);assert suffix[-1]['gpu_process_wall_seconds']/3600==I['retained_charge_gpu_hours']==0.045194898711310494
E['checks']['retained_preparation']={'resource_id':I['recovery_of'],'events':[r['event']for r in suffix],'seconds':suffix[-1]['gpu_process_wall_seconds'],'gpu_hours':I['retained_charge_gpu_hours'],'own_journal_equals_global_suffix':True,'new_identity':P['resource_id'],'new_identity_in_own_journal':any(r['resource_id']==P['resource_id']for r in own),'first_strict_suffix_pair':[suffix[0]['resource_id'],suffix[0]['kind']],'allowed_pairs':[[P['resource_id'],'readiness_preparation'],[constants['HEALTH_ID'],constants['HEALTH_KIND']]]}
# Isolated execution of the exact relevant function AST; imports are replaced
# with supplied in-memory policy/journal dependencies. No production imports.
node=copy.deepcopy(next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='preparation_health_suffix'));node.body=[n for n in node.body if not isinstance(n,ast.ImportFrom)]
def require(ok,msg):
 if not ok:raise ValueError(msg)
def exact(a,b,msg):require(canonical(a)==canonical(b),msg)
ns={**constants,'specification':lambda:S,'preparation':types.SimpleNamespace(policy=lambda s:P,journal_rows=lambda root:own),'exact':exact,'w':types.SimpleNamespace(require=require),'owner_root':lambda p:None}
exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'isolated-production-function','exec'),ns)
try:ns['preparation_health_suffix'](plan,baseline,health);raise AssertionError('expected strict suffix rejection')
except ValueError as x:E['checks']['isolated_suffix_reproduction']={'result':'BLOCK','message':str(x),'method':'Exact production function AST with import removed and direct data supplied; no production import, native or provider invocation'}
for file,ranges in {'scripts/qd_ed_n36_engineering_r1.py':[(37,38),(86,137),(266,301),(321,346),(554,594)],'scripts/qd_ed_n36_engineering_api.py':[(1,17)],'scripts/qd_ed_n36_readiness_prepare.py':[(46,80),(82,128),(423,447),(479,527)],'scripts/qd_ed_n34_source.py':[(339,377)],'scripts/qd_ed_n36_contract.py':[(23,41)],'scripts/qd_ed_n36_stop.py':[(10,24)]}.items():
 lines=(ROOT/file).read_text().splitlines();r=record(ROOT/file,'relevant production source');E['source_slices'].append({'source':r,'slices':[{'first_line':lo,'last_line':hi,'text':'\n'.join(lines[lo-1:hi])}for lo,hi in ranges]})
E['limits']=['No recursive provenance validation','No full source inventory payload verification; unchanged metadata inherited from direct baseline','No model/native/provider calls or imports; no broad tests','No active cohort per direct terminal reconciliation; no owning state read or modified','No protected results or prohibited design/Poe files opened','No writes outside this review directory']
with (OUT/'direct-evidence-v1.json').open('x')as f:json.dump(E,f,indent=2,sort_keys=True);f.write('\n')
print(json.dumps({'reference_checks':len(E['reference_checks']),'failed_reference_checks':sum(not x['hash_matches'] or x['size_matches'] is False for x in E['reference_checks']),'suffix_reproduction':E['checks']['isolated_suffix_reproduction'],'source_projection':E['checks']['source_projection'],'evidence_sha256':sha((OUT/'direct-evidence-v1.json').read_bytes())},indent=2))
