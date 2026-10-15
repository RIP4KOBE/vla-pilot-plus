import json, hashlib, pathlib, subprocess, datetime, ast
O=pathlib.Path(__file__).parent
A=json.loads((O/'authority-v1.json').read_text())
inputs={}; checks=[]
def digest(b):return hashlib.sha256(b).hexdigest()
def read(ref):
 p=pathlib.Path(ref['path']); b=p.read_bytes(); assert digest(b)==ref['sha256'], str(p)
 if 'bytes' in ref:assert len(b)==ref['bytes'], str(p)
 inputs[str(p)]={'path':str(p),'sha256':digest(b),'bytes':len(b)}
 return json.loads(b)
def check(name,ok,detail=None):
 checks.append(dict(check=name,passed=bool(ok),detail=detail));assert ok,name
G=read(A['graph']); C=read(A['composition']); D=read(A['admission']); RC=read(A['root_controller_acceptance']);read(A['standing_authority'])
V={k:read(v) for k,v in G.items() if isinstance(v,dict) and 'sha256' in v and 'path' in v}
P=V['plan']; R=V['runtime']; S=V['specification']; CT=V['controller_semantics']; CL=V['runtime_closure']; IX=V['full40_manifests']; AU=V['audit']; EN=V['separate_engineering_manifest']; RP=V['recovery_prefix_contract']
check('source_HEAD_and_clean',subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==A['source']['commit'] and subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0)
check('exact_production_admission',D['status']=='PASS_STATIC_GRAPH_ADMISSION' and D['graph']['sha256']==A['graph']['sha256'] and D['source']==A['source'] and read(D['validator_input'])['graph']=={'plan':G['plan'],'runtime':G['runtime']})
check('disabled_graph',all(G[k] is False for k in ['gpu_authorized','release_enabled','provider_ready','runtime_ready','provider_measurement_authorized','frozen','independent_review_claimed']) and all(G[k] is None for k in ['authority','b5_review','root_acceptance']))
check('disabled_plan',P['release_enabled'] is False and P['frozen'] is False and P['authority'] is None and P['b5_review'] is None and P['phase_authorization']==dict(engineering=False,dev=False,validation=False,formal=False))
check('disabled_runtime',R['cuda_egl_verified'] is False and R['provider_ready'] is False and R['gpu_mapping']['cuda_egl_verified'] is False and R['preparation']['runtime_ready'] is False and R['preparation']['release_enabled'] is False and R['preparation']['historical_readiness_is_not_current'] is True)
check('canonical_source_runtime_closure_controller',P['source']==V['source_record'] and P['source']['commit']==A['source']['commit'] and R['preparation']['source_record']==G['source_record'] and R['preparation']['source']==A['source']['commit'] and CL['runtime']==G['runtime'] and CT['runtime']==G['runtime'] and CT['runtime_closure']==G['runtime_closure'] and CT['source']==CL['modules'][CT['module']])
for k in ['runtime','runtime_closure','controller_semantics','native_build','scientific_equivalence']:check('plan_binding_'+k,P[k]==G[k])
check('plan_audit_engineering_refs',P['audit_plan']==G['audit'] and P['engineering_manifest']==G['separate_engineering_manifest'])
for k in ['scope','accounting','deployment']:read(P[k])
prior=read(C['prior_graph'])
check('composition_graph_and_source',C['graph']['sha256']==A['graph']['sha256'] and C['source']==A['source'])
def diff(a,b,path=''):
 if type(a)!=type(b):return [path]
 if isinstance(a,dict):return sum((diff(a.get(k),b.get(k),path+'.'+k) for k in sorted(set(a)|set(b))),[])
 if isinstance(a,list):
  if len(a)!=len(b):return [path]
  return sum((diff(x,y,path+'.'+str(i)) for i,(x,y) in enumerate(zip(a,b))),[])
 return [] if a==b else [path]
replacements={x['old']['path']:x['new'] for x in C['replacements']}
def replace(x):
 if isinstance(x,dict):
  if 'path' in x and x['path'] in replacements and 'sha256' in x:return replacements[x['path']]
  return {k:replace(v) for k,v in x.items()}
 if isinstance(x,list):return [replace(v) for v in x]
 return x
replacement_diffs=[]
for pair in C['replacements']:
 old=read(pair['old']);new=read(pair['new']); ds=diff(replace(old),new)
 replacement_diffs.append({'new':pair['new'],'remaining_delta_paths':ds})
check('binding_only_composition_noncontroller',all(not x['remaining_delta_paths'] for x in replacement_diffs if 'controller-semantics' not in x['new']['path'] and 'relocation-map' not in x['new']['path']),replacement_diffs)
for ref in CT['review_evidence'].values():
 ev=read(ref);old=read(ev['prior_review']);check('controller_unchanged_findings_'+pathlib.Path(ref['path']).name,ev['findings']==old['findings'] and ev['sources']==old['sources'] and ev['runtime']==G['runtime'] and ev['runtime_closure']==G['runtime_closure'])
 for sr in ev['sources']:
  b=pathlib.Path(sr['path']).read_bytes();check('controller_source_hash_'+pathlib.Path(sr['path']).name,digest(b)==sr['sha256']);inputs[sr['path']]={**sr,'bytes':len(b)}
read(CT['historical_review']);read(RP['accepted_review']);ID=read(RP['identity'])
check('recovery_identity',ID['resource_id']==G['resource_id']==V['policy']['resource_id'] and ID['recovery_of']==G['recovery_of'] and [p['retained_charge_gpu_hours'] for p in RP['predecessors']]==G['retained_charge_gpu_hours'])
ledger_checks=[]
for name,ref in {**A['ledger_prefixes']}.items():
 b=pathlib.Path(ref['path']).read_bytes();check('current_ledger_'+name,len(b)==ref['bytes'] and digest(b)==ref['sha256']);ledger_checks.append(ref)
for name,ref in S['retained_ledger_prefixes'].items():
 with open(ref['path'],'rb') as f:b=f.read(ref['bytes'])
 check('retained_prefix_'+name,digest(b)==ref['sha256'])
for pred in RP['predecessors']:
 segs=[]
 for k in ['global_health_segment','own_journal']:
  ref=pred[k]
  with open(ref['path'],'rb') as f:f.seek(ref['start_inclusive']);b=f.read(ref['end_exclusive']-ref['start_inclusive'])
  check('recovery_segment_'+pred['resource_id']+'_'+k,digest(b)==ref['sha256']);segs.append(b)
 check('mirrored_history_'+pred['resource_id'],segs[0]==segs[1] and [json.loads(x) for x in segs[0].splitlines()]==pred['rows'] and pred['telemetry_complete'] is False and pred['consumed'] is True and pred['rows'][-1]['provider_calls']==1 and pred['rows'][-1]['gpu_process_wall_seconds']/3600==pred['retained_charge_gpu_hours'])
check('retained_reserves_deadline',S['accounting_proposal']['protected_remaining_gpu_hours']=={'formal':'12.0','validation':'24.2408240024308155'} and S['accounting_proposal']['retained_admission_margin_gpu_hours']=='0.23357169027962' and datetime.datetime.fromisoformat(P['deadline'].replace('Z','+00:00'))==datetime.datetime.fromisoformat(A['stop_authority']['deadline'].replace('Z','+00:00')))
print('INDEX_KEYS',list(IX));print('INDEX_TYPES',{k:type(v).__name__ for k,v in IX.items()});print('ENGINEERING_EXPECTED',P['expected_manifests'].keys());print('REPLACEMENT_DELTAS',[(x['new']['path'].split('/')[-1],x['remaining_delta_paths'][:25]) for x in replacement_diffs if x['remaining_delta_paths']]);print('RECOVERY_SUMMARY',{k:v for k,v in RP.items() if k not in ['predecessors']});print('IDENTITY',ID)
(O/'inspection-results-v1.json').write_text(json.dumps({'inputs':list(inputs.values()),'checks':checks,'ledger_checks':ledger_checks,'replacement_diffs':replacement_diffs},indent=2)+'\n')
