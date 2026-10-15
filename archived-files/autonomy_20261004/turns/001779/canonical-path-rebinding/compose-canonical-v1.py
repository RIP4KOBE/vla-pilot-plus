"""CPU artifact composition using unmodified production APIs; no release creation."""
import os,sys,json,hashlib,datetime as dt,time,copy,subprocess,traceback,signal
from pathlib import Path
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent; A=json.loads((O/'authority-v1.json').read_text()); ROOT=Path(A['worktree']); A['deadline']=A['stop_authority']['deadline']
START=time.monotonic(); INPUTS={}; OUTPUTS={}; CHECKS=[]; COMMANDS=[]; BLOCKERS=[]; COUNTS={'audit':0,'engineering':0}; graphref=None; verified=False
os.environ.update(TMPDIR=str(O/'tmp'),CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0',GIT_NO_LAZY_FETCH='1')
def guard():
 assert time.monotonic()-START<960,'CPU executor time boundary'
 assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(A['deadline'].replace('Z','+00:00')),'deadline'
 assert all(not os.path.lexists(p) for p in A['stop_authority']['paths']),'STOP present'
def record(p):
 p=Path(p);data=p.read_bytes();return dict(path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def ref(r):return {k:r[k] for k in ('path','sha256')}
def read(r):
 guard();v=record(r['path']);assert all(v[k]==r[k] for k in ('sha256','bytes') if k in r),'input hash '+r['path'];INPUTS[v['path']]=v;return json.loads(Path(v['path']).read_text())
def save(name,value):
 p=O/name;assert p.is_relative_to(O) and not os.path.lexists(p),'fresh output required '+str(p)
 p.parent.mkdir(parents=True,exist_ok=True)
 data=value.encode() if isinstance(value,str) else json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
 with p.open('xb') as f:f.write(data)
 OUTPUTS[str(p)]=record(p);return ref(OUTPUTS[str(p)])
def check(name,fn):
 guard();print('BEGIN',name,flush=True);t=time.monotonic()
 try:result=fn()
 except Exception as ex:
  CHECKS.append(dict(check=name,status='BLOCKED',error=str(ex),elapsed_seconds=time.monotonic()-t));BLOCKERS.append(dict(check=name,detail=str(ex)));print('BLOCKED',name,str(ex),flush=True);return None
 CHECKS.append(dict(check=name,status='PASS',elapsed_seconds=time.monotonic()-t));print('PASS',name,flush=True);return result

def git(*args):
 q=subprocess.run(['git','--no-replace-objects','-C',str(ROOT),*args],capture_output=True,text=True,check=True,timeout=60);COMMANDS.append(dict(argv=q.args,stdout=q.stdout,stderr=q.stderr,returncode=q.returncode));return q.stdout.strip()
def source_check():
 assert git('rev-parse','HEAD')==A['source'];assert git('diff','--name-only')==git('diff','--cached','--name-only')==''
# This guard restricts I/O and dispatch, never changes validator results.
physical_output=str(O.resolve())
def hook(event,args):
 if event=='open' and isinstance(args[0],(str,bytes)):
  name=os.fsdecode(args[0]);low=name.lower();base=Path(low).name
  if ('poe' in base and base!='qd_ed_poe_launch.py') or '2026-08-10' in low or base in ('auth.json','credentials.json','.env') or '/.ssh/' in low or '/dev/nvidia' in low:
   raise PermissionError('prohibited input '+name)
  if any(x in low for x in ('/protected-results/','/validation/results/','/formal/results/')):raise PermissionError('protected result '+name)
  mode,flags=args[1:3];writing=(isinstance(mode,str) and any(x in mode for x in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
  if writing and name != '/dev/null' and not (str(Path(name).resolve()).startswith(physical_output+'/')):raise PermissionError('out-of-scope write '+name)
 if event=='import' and ('poe' in args[0].lower()):raise PermissionError('Poe import prohibited')
 if event in ('socket.connect','socket.bind'):raise PermissionError('network prohibited')
 if event=='subprocess.Popen':
  executable,argv=args[0],args[1]
  if Path(str(executable)).name not in ('git','uname','ldconfig'):raise PermissionError('non-audit subprocess prohibited '+str(argv))
  COMMANDS.append(dict(event=event,argv=argv,cwd=str(ROOT)))
sys.addaudithook(hook)
def alarm(*_):raise TimeoutError('bounded composition timeout')
signal.signal(signal.SIGALRM,alarm);signal.alarm(960)
try:
 guard();read(record(O/'authority-v1.json'));check('immutable source before',source_check)
 read(A['standing_authority']);read(A['source_deployment']);review=read(A['root_scoped_review']);prior=read(A['prior_bindings'])
 spec=read(review['specification']);contract=read(review['recovery_prefix_contract']);controller=read(review['controller_semantics'])
 read(review['recovery_review']);read(review['recovery_reconciliation'])
 A['canonical_specification']=review['specification'];A['canonical_contract']=review['recovery_prefix_contract'];A['controller']=review['controller_semantics'];A['root_controller_acceptance']=A['root_scoped_review']
 A['fresh_resource_id']=prior['resource_id'];A['recovery_of']=prior['recovery_of']
 A['retained_charge_gpu_hours']=[p['retained_charge_gpu_hours'] for p in contract['predecessors']]
 slots=read(spec['downstream_slots']);S=slots['slots'];A['downstream_slots']=spec['downstream_slots']
 for r in A['ledger_prefixes'].values():
  v=record(r['path']);assert all(v[k]==r[k] for k in ('path','bytes','sha256'));INPUTS[r['path']]=v
 oldspec=copy.deepcopy(spec)
 oldpolicy=read(spec['runtime_binding']['preparation'])
 oldsr=prior['source_record']; source=read(oldsr)
 sr=save('source-record.json',source)
 oldrr=prior['runtime']; runtime=read(oldrr)
 runtime['preparation']['source_record']=sr
 rr=save('disabled-runtime.json',runtime)
 oldcr=prior['runtime_closure']; closure=read(oldcr)
 closure['runtime']=rr
 cr=save('runtime-closure.prospective-disabled-v1.json',closure)
 policy=copy.deepcopy(oldpolicy)
 policy['disabled_runtime_path']=rr['path']
 for key in policy:
  if key.endswith('_path') and key!='disabled_runtime_path':
   policy[key]=str(O/Path(policy[key]).name)
 polref=save('preparation-policy.prospective-disabled-v1.json',policy)
 spec['runtime_binding']['preparation']=polref
 spec['runtime_binding']['source_record_path']=sr['path']
 spec['runtime_binding']['runtime_path']=str(O/'measured-runtime.json')
 spec_ref=save('specification.prospective-disabled-v1.json',spec)
 A['canonical_specification']=spec_ref
 # Changed bindings carry no inherited controller approval.
 oldcontroller=copy.deepcopy(controller)
 controller['runtime']=rr; controller['runtime_closure']=cr
 controller['status']='PENDING_ROOT_REVIEW'
 controller.pop('reviewer',None);controller.pop('at',None)
 controller['review_scope']='Prospective binding only; prior exact review retained as historical evidence, no approval transferred.'
 controller['historical_review']=review['controller_semantics']
 controller['review_evidence']=oldcontroller['review_evidence']
 A['controller']=save('controller-semantics.prospective-disabled-v1.json',controller)
 A['root_controller_acceptance']=None
 prior.update(source_record=sr,runtime=rr,runtime_closure=cr)
 os.environ['QD_ED_N36_R1_SPECIFICATION']=json.dumps(spec_ref,sort_keys=True)
 save('specification-selector-v1.json',{'environment_variable':'QD_ED_N36_R1_SPECIFICATION','value':spec_ref,'release_enabled':False})
 sys.path.insert(0,str(ROOT));os.chdir(ROOT)
 from scripts import qd_ed_n36_engineering_r1 as e, qd_ed_n36_bridge as b, qd_ed_n36_readiness_prepare as prep, qd_ed_n36_build as native
 from scripts.qd_ed_n34_controller import verify_semantics
 check('canonical specification and raw recovery prefix admission',lambda:e.exact(e.specification(),spec,'pinned canonical specification'))
 policy=prep.policy(spec)
 assert policy['resource_id']==A['fresh_resource_id']==contract['successor']['resource_id']=='n36_readiness_preparation_recovery_001771'
 assert [p['resource_id'] for p in contract['predecessors']]==A['recovery_of']==['n36_readiness_preparation_001651','n36_readiness_preparation_recovery_001723']
 assert spec['retained_ledger_prefixes']==contract['original_ledger_prefixes']
 sr=prior['source_record'];source=read(sr);rr=prior['runtime'];runtime=read(rr);cr=prior['runtime_closure'];closure=read(cr)
 assert source['commit']==A['source'] and rr['path']==policy['disabled_runtime_path'] and sr['path']==spec['runtime_binding']['source_record_path']
 assert controller['runtime']==rr and controller['runtime_closure']==cr
 template=O.parent.parent/'001776/disabled-graph-composition/composition-v3'
 historical={'plan':ref(record(template/'engineering-plan.disabled-v1.json')),'audit':ref(record(template/'all40-audit.immutable-disabled-v1.json'))}
 read(record(template.parent/'final-result/report-v1.json'))
 oldplan=read(historical['plan']);oldaudit=read(historical['audit']);baseline=read(spec['canonical_runtime'])
 current_binding={**oldplan,'source':source,'scientific_source':source,'runtime':rr,'runtime_closure':cr,'controller_semantics':ref(A['controller'])}
 check('complete final-source inventory verification',lambda:b.verify_sources(current_binding))
 check('final source exact runtime derivation and input file hashes',lambda:e.validate_runtime_binding(current_binding))
 check('runtime closure installed file hashes and interpreter',lambda:b.closure.verify_runtime(closure,rr))
 check('prospective controller semantics exact production admission',lambda:verify_semantics(ref(A['controller']),rr,closure))
 read(oldplan['native_build'])
 nativevalue=check('native library inventory binary hashes',lambda:native.manifest(oldplan['native_build']))
 nr=save('native-build.disabled-v1.json',nativevalue)
 scope=save('scope.disabled-v1.json',e.disabled_scope());accounting=save('accounting.disabled-v1.json',e.disabled_accounting());deployment=save('deployment.disabled-v1.json',read(oldplan['deployment']))
 changed=git('diff','--name-only',e.BASE,source['commit'],'--').splitlines()
 eq=save('scientific-equivalence-v1.json',dict(schema='n36-engineering-scientific-equivalence-v1',base_commit=e.BASE,source=source,changed_paths=sorted(changed),scientific_changes=False))
 fields=dict(source=source,scientific_source=source,runtime=rr,runtime_closure=cr,native_build=nr,scope=scope,deployment=deployment,controller_semantics=ref(A['controller']))
 audit=copy.deepcopy(oldaudit);audit.update(fields,expected_manifests={},frozen=True,release_enabled=False,dispatch_authority=False)
 plan=copy.deepcopy(oldplan);plan.update(fields,accounting=accounting,scientific_equivalence=eq,expected_manifests={},engineering_manifest=None,frozen=False,release_enabled=False,authority=None,b5_review=None)
 check('scientific equivalence production validator',lambda:e.scientific_equivalence(plan))
 check('audit precomposition production validator',lambda:e.validate_audit_view(audit,require_manifests=False))
 mapping=[]
 replacements=[(oldplan[k],plan[k]) for k in ('source','scientific_source','runtime','runtime_closure','native_build','scope','deployment','controller_semantics','accounting')]
 def rebind(value):
  for old,new in replacements:
   if value==old:return copy.deepcopy(new)
  if isinstance(value,dict):return {k:rebind(v) for k,v in value.items()}
  if isinstance(value,list):return [rebind(v) for v in value]
  if isinstance(value,str):return value.replace(oldplan['source']['commit'],source['commit'])
  return value
 def recompose_config(m):
  config,resolved=b.compose_launch(m['argv'],str(ROOT))
  m['composed_config_sha256']=e.w.canonical_sha(config);m['resolved_config']=resolved
  if m['expected_runtime'] is not None:
   m['expected_runtime']['config_sha256']=hashlib.sha256(json.dumps(resolved,sort_keys=True,allow_nan=False).encode()).hexdigest()
   files={x['path']:x['sha256'] for x in source['files']}
   m['expected_runtime']['source_hashes']={k:files[k] for k in m['expected_runtime']['source_hashes']}
  return m
 for i,row in enumerate(audit['episodes']):
  original=oldaudit['expected_manifests'][row['episode_key']]
  m=recompose_config(rebind(read(original)))
  mr=save('audit-manifests/%02d.json'%i,m);COUNTS['audit']+=1;audit['expected_manifests'][row['episode_key']]=mr
  mapping.append(dict(original=original,new=mr,row=row,composition='template_rebinding_and_production_Hydra_recomposition',production_admission='SEE_EXACT_STATIC_CONSUMERS'))
 ar=save('all40-audit.immutable-disabled-v1.json',audit);plan['audit_plan']=ar
 check('complete all40 audit production validator',lambda:e.validate_audit_view(audit))
 replacements.append((oldplan['audit_plan'],ar))
 replacements.extend((oldaudit['expected_manifests'][r['episode_key']],audit['expected_manifests'][r['episode_key']]) for r in audit['episodes'])
 em=recompose_config(rebind(read(oldplan['engineering_manifest'])))
 er=save('engineering-manifest.disabled-v1.json',em);COUNTS['engineering']=1;plan['engineering_manifest']=er;plan['expected_manifests']={e.EPISODE_KEY:er}
 check('separate engineering manifest production consumer',lambda:b.verify_engineering_manifest(er,plan,runtime,e.row(),audit=audit))
 pr=save('engineering-plan.disabled-v1.json',plan)
 index=save('full40-manifest-index-v1.json',dict(schema='n36-full40-manifest-index-v1',audit=ar,manifests=mapping,release_enabled=False))
 relocated={'audit_view':ar,'engineering_plan':pr,'engineering_manifest':er,'full40_manifest_index':index,'native_build':nr,'scope':scope,'accounting':accounting,'deployment':deployment,'scientific_equivalence':eq,'controller_semantics':ref(A['controller'])}
 relocation=save('disabled-relocation-map-v1.json',dict(schema='n36-disabled-graph-relocation-v1',original_specification=A['canonical_specification'],original_contract=A['canonical_contract'],original_slots=A['downstream_slots'],original_specification_content=spec,original_slot_content=slots,relocations={k:dict(original=S[k],new=v) for k,v in relocated.items()},full40=mapping,reused_exact={'source_record':sr,'runtime':rr,'runtime_closure':cr,'controller':ref(A['controller'])},scientific_parameters_preserved=True,active_specification_changed=False,release_enabled=False,adoption_authorized=False,resource_id=A['fresh_resource_id'],recovery_of=A['recovery_of'],retained_charge_gpu_hours=A['retained_charge_gpu_hours']))
 # verify_graph consumes only graph. This input is explicitly not a release or approval.
 validator_input=save('disabled-graph-validator-input-v1.json',dict(graph=dict(plan=pr,runtime=rr),release_enabled=False,approved=False))
 for row in audit['episodes']:
  check('production audit manifest consumer '+row['episode_key'],lambda row=row:b._verify_manifest_bound(audit['expected_manifests'][row['episode_key']],audit,runtime,row))
 check('production complete disabled graph verify_graph all41',lambda:prep.verify_graph(read(validator_input),source,baseline))
 check('final scientific equivalence',lambda:e.scientific_equivalence(plan))
 check('exact final source and loaded production modules',lambda:(source_check(),b.attest_loaded(ROOT,source)))
 def preserve():
  assert all(v is False for v in plan['phase_authorization'].values()) and all(v is False for v in audit['phase_authorization'].values())
  assert runtime['preparation']['runtime_ready'] is False and runtime['provider_ready'] is False and runtime['cuda_egl_verified'] is False and runtime['gpu_mapping']['cuda_egl_verified'] is False
  assert plan['stop_authority']==audit['stop_authority']==oldplan['stop_authority']
  assert audit['stop_authority']['paths']==A['stop_authority']['paths']
  assert dt.datetime.fromisoformat(audit['stop_authority']['deadline'].replace('Z','+00:00'))==dt.datetime.fromisoformat(A['deadline'].replace('Z','+00:00'))
  assert spec['accounting_proposal']==oldspec['accounting_proposal'] and spec['scope']==oldspec['scope']
  assert read(sr)==read(oldsr)
  oldruntime=read(oldrr); oldruntime['preparation']['source_record']=sr
  assert runtime==oldruntime
  oldclosure=read(oldcr);oldclosure['runtime']=rr
  assert closure==oldclosure
  for k in ('episodes','limits','worker_contract','deadline','protocol','protocol_review','accounting'):assert audit[k]==oldaudit[k]
  for p,r in INPUTS.items():assert record(p)==r,p
  assert len(audit['episodes'])==40 and COUNTS=={'audit':40,'engineering':1}
  assert audit['limits']['physical_gpu']==7
 check('science budget reserves original offsets journals and disabled authorization preservation',preserve)
 preservation=save('preservation-evidence-v1.json',dict(checks=CHECKS[-3:],all_inputs_unchanged=all(record(p)==r for p,r in INPUTS.items()),ledger_prefixes=A['ledger_prefixes'],scientific_scope=spec['scope'],accounting_proposal=spec['accounting_proposal'],stop_authority=A['stop_authority'],resource_id=A['fresh_resource_id'],recovery_of=A['recovery_of'],retained_charge_gpu_hours=A['retained_charge_gpu_hours'],source_record_unchanged=source==read(oldsr),runtime_changes=['preparation.source_record'],closure_changes=['runtime'],approval_transferred=False))
 verified=not BLOCKERS
 graphref=save('graph.complete-disabled-v1.json',dict(schema='n36-readiness-recovery-prospective-graph-v1',status='COMPOSED_DISABLED_CANDIDATE_BLOCKED_STATIC_ADMISSION',specification=ref(A['canonical_specification']),recovery_prefix_contract=ref(A['canonical_contract']),relocation_map=relocation,policy=spec['runtime_binding']['preparation'],resource_id=A['fresh_resource_id'],recovery_of=A['recovery_of'],retained_charge_gpu_hours=A['retained_charge_gpu_hours'],source_record=sr,runtime=rr,runtime_closure=cr,native_build=nr,controller_semantics=ref(A['controller']),root_controller_acceptance=None,independent_review_claimed=False,review_status='PENDING_INDEPENDENT_REVIEW_OF_NEW_GRAPH',scientific_equivalence=eq,audit=ar,plan=pr,full40_manifests=index,separate_engineering_manifest=er,graph_complete=True,graph_verified=verified,release_enabled=False,frozen=False,runtime_ready=False,provider_ready=False,gpu_authorized=False,provider_measurement_authorized=False,authority=None,b5_review=None,root_acceptance=None))
except Exception as ex:
 BLOCKERS.append(dict(id='PRODUCTION_COMPOSITION_BLOCK',detail=str(ex),traceback=traceback.format_exc()));print(traceback.format_exc(),flush=True)
finally:
 signal.alarm(0)
 ce=save('command-evidence-v1.json',dict(schema='n36-focused-cpu-command-evidence-v1',invocation=[sys.executable,'-B',str(Path(__file__).absolute())],environment={k:os.environ[k] for k in ('CUDA_VISIBLE_DEVICES','OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','PYTHONDONTWRITEBYTECODE','GIT_OPTIONAL_LOCKS','QD_ED_N36_R1_SPECIFICATION')},commands=COMMANDS,checks=CHECKS,builder_counts=COUNTS,production_sources_unmodified=True,validator_bypass=False,recursive_provenance_rebuilt=False,model_loading_inference_native_build_provider_gpu_invocations=0))
 ir=save('inputs-manifest-v1.json',dict(schema='direct-input-bindings-v1',files=list(INPUTS.values()),recursive_provenance_rebuilt=False))
 am=save('generated-artifact-manifest-v1.json',dict(schema='n36-generated-artifact-manifest-v1',files=[record(Path(__file__).absolute())]+list(OUTPUTS.values()),graph_complete=verified,excludes=['report-v1.json','report-v1.sha256','outputs-manifest-v1.json','builder-stdout-v1.log','command-receipt-v1.json']))
 report=dict(schema='n36-disabled-graph-composition-report-v1',node_id='15.6',at=dt.datetime.now(dt.timezone.utc).isoformat(),status='PASS_COMPLETE_DISABLED_GRAPH' if verified else 'COMPOSED_DISABLED_CANDIDATE_BLOCKED_STATIC_ADMISSION',authority=ref(record(O/'authority-v1.json')),source=A['source'],graph=graphref,command_evidence=ce,input_manifest=ir,generated_artifact_manifest=am,blockers=BLOCKERS,checks=CHECKS,generated_audit_manifest_count=COUNTS['audit'],generated_engineering_manifest_count=COUNTS['engineering'],resource_id=A['fresh_resource_id'],recovery_of=A['recovery_of'],retained_charge_gpu_hours=A['retained_charge_gpu_hours'],stop_authority=A['stop_authority'],deadline=A['deadline'],elapsed_builder_seconds=time.monotonic()-START,maximum_executor_seconds=1200,graph_complete=COUNTS=={'audit':40,'engineering':1},graph_verified=verified,source_edits=False,source_adopted=False,active_specification_adopted=False,owning_state_mutation=False,ledger_writes=False,release_enabled=False,frozen=False,audit_snapshot_frozen=True if COUNTS['audit']==40 else None,runtime_ready=False,provider_ready=False,production_readiness=False,gpu_authorized=False,provider_measurement_authorized=False,health_authorized=False,episode_authorized=False,phase_authorization={'engineering':False,'dev':False,'validation':False,'formal':False},scientific_success=False,b5_review=None,release=None,root_acceptance=None,independent_review_claimed=False,next_bounded_step='Owning root must independently review controller semantics and deployed-source review evidence against the new exact runtime and closure bindings, then rerun focused production consumers and verify_graph before B5 and graph/accounting adoption. No source changes or measurements are authorized.',poe_credentials_opened=False,poe_launcher_execution=False,prohibited_design_or_protected_results_read=False,future_gates=['Independent B5 and owning-root accounting/adoption of exact composed graph.','Separately authorized finite preparation release, fresh measured readiness and external acceptance.','Distinct health and episode releases with current budget/reserves, STOP/deadline and GPU7 checks.'],limitations=['Candidate manifests were structurally rebound from historical templates and production Hydra recomposed; exact consumer outcomes are recorded individually; pending controller review is not approval. No validator bypass or production admission is claimed.','CPU disabled composition only; no live native/controller receipt, measurement, readiness, release or production adoption.','Exact source and narrow historical evidence reused; changed controller bindings are pending review; no recursive provenance rebuilding.'])
 rr=save('report-v1.json',report);save('report-v1.sha256',rr['sha256']+'  report-v1.json\n')
 save('outputs-manifest-v1.json',dict(files=[record(Path(__file__).absolute())]+list(OUTPUTS.values()),excludes=['outputs-manifest-v1.json','builder-stdout-v1.log','command-receipt-v1.json']))
 print(json.dumps(dict(status=report['status'],report=rr,blockers=BLOCKERS,counts=COUNTS)),flush=True)
