import os, sys, json, hashlib, copy, time, datetime as dt, resource, traceback
from pathlib import Path
OUT=Path(__file__).parent
A=json.loads((OUT/'authority-v1.json').read_text())
START=time.monotonic(); ART={}; CHECK={}; CHANGES=[]; REUSED={}
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
resource.setrlimit(resource.RLIMIT_CPU,(115,115))
def guard():
 assert not any(os.path.lexists(p) for p in A['STOP_paths']), 'STOP present'
 assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(A['deadline'].replace('Z','+00:00')), 'deadline'
 assert time.monotonic()-START<115, 'CPU check wall cap'
def ref(p,full=False):
 p=Path(p);b=p.read_bytes();r={'path':str(p),'sha256':hashlib.sha256(b).hexdigest()}
 if full:r['bytes']=len(b)
 return r
def read(r):
 b=Path(r['path']).read_bytes();assert hashlib.sha256(b).hexdigest()==r['sha256'],r['path']
 if 'bytes' in r:assert len(b)==r['bytes']
 return json.loads(b)
def write(n,d):
 guard();p=OUT/n;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:f.write(json.dumps(d,indent=2,allow_nan=False)+'\n')
 ART[n]=ref(p,True);return ref(p)
def delta(a,b,path=''):
 if type(a)!=type(b):return [path]
 if isinstance(a,dict):
  return [p for k in sorted(a.keys()|b.keys()) for p in ([path+'/'+k] if k not in a or k not in b else delta(a[k],b[k],path+'/'+k))]
 if isinstance(a,list):
  if len(a)!=len(b):return [path]
  return [p for i,(x,y) in enumerate(zip(a,b)) for p in delta(x,y,path+'/'+str(i))]
 return [] if a==b else [path]
def change(n,old,new,allowed):
 ds=delta(old,new);assert all(any(p==k or p.startswith(k+'/') for k in allowed) for p in ds),(n,ds)
 CHANGES.append({'artifact':n,'changed_fields':ds})
def main():
 guard();assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
 inputs={k:read(v) for k,v in A['inputs'].items()};CHECK['authority_inputs_hashes']='PASS'
 accepted=inputs['accepted_package'];base=Path(A['inputs']['accepted_package']['path']).parent
 def old(n):return read(accepted['artifacts'][n])
 plan0=old('plan.complete-disabled-v1.json');runtime0=old('runtime.isolated.draft-v1.json')
 assert inputs['runtime_ready']==runtime0
 ready=inputs['readiness_review'];adoption=inputs['source_accounting_adoption']
 assert ready['status']=='PASS_READINESS_ONLY_NOT_RELEASE' and ready['source']==A['base_source']
 assert ready['runtime']['sha256']==ready['disabled_runtime']['sha256']==A['inputs']['runtime_ready']['sha256']
 assert ready['changed_fields']==[] and adoption['source_after']==A['base_source']
 authority=read(adoption['authority']);assert ready['accounting_authority']==adoption['authority']
 sys.path.insert(0,A['worktree'])
 from scripts import qd_ed_n36_bridge as b, qd_ed_n36_contract as c, qd_ed_n34_source as s, qd_ed_n34_controller as ctrl, qd_ed_n23_worker as w, qd_ed_n36_release as release
 # Reuse accepted inventory; verify it, never refresh source or historical evidence.
 s.verify_source(A['worktree'],plan0['source'],commit=A['base_source'])
 CHECK['accepted_source_verification']='PASS'
 for k in ['source','scientific_source','source_files_sha256','import_search','native_build','protocol','accounting','full_config_comparison']:
  if k in accepted['bindings']:
   read(accepted['bindings'][k]);REUSED[k]=accepted['bindings'][k]
 runtime=copy.deepcopy(runtime0)
 prep=runtime['preparation']
 prep.update(runtime_ready=True,status='EXTERNAL_READINESS_BOUND_CANDIDATE_REQUIRES_B5',readiness_review=A['inputs']['readiness_review'],source_accounting_adoption=A['inputs']['source_accounting_adoption'],runtime_ready_scope='Preparation only: accepted source/import inventory and external turn001289 provider/CUDA/EGL readiness; unchanged native/checkpoint evidence reused. Not live admission, actual-worker attestation, B5 approval or release.')
 assert prep['release_enabled'] is False and prep['no_provider_or_device_probe'] is True
 change('runtime.readiness-bound-v1.json',runtime0,runtime,['/preparation'])
 rr=write('runtime.readiness-bound-v1.json',runtime)
 closure0=old('runtime-closure.isolated.draft-v1.json');closure=copy.deepcopy(closure0);closure['runtime']=rr
 change('runtime-closure.readiness-bound-v1.json',closure0,closure,['/runtime'])
 cr=write('runtime-closure.readiness-bound-v1.json',closure)
 s.verify_runtime(closure,rr);CHECK['runtime_closure_verifier']='PASS'
 proof0=old('controller-semantics.isolated.draft-v1.json');proof=copy.deepcopy(proof0)
 proof.update(runtime=rr,runtime_closure=cr)
 for k,v in proof0['review_evidence'].items():
  before=read(v);after=copy.deepcopy(before);after.update(runtime=rr,runtime_closure=cr)
  n='controller-'+k+'.readiness-bound-v1.json';change(n,before,after,['/runtime','/runtime_closure']);proof['review_evidence'][k]=write(n,after)
 change('controller-semantics.readiness-bound-v1.json',proof0,proof,['/runtime','/runtime_closure','/review_evidence'])
 pr=write('controller-semantics.readiness-bound-v1.json',proof)
 ctrl.verify_semantics(pr,rr,closure);CHECK['controller_semantics_verifier']='PASS_INHERITED_EVIDENCE_BINDINGS_ONLY'
 plan=copy.deepcopy(plan0);plan.update(runtime=rr,runtime_closure=cr,controller_semantics=pr,authority={k:v for k,v in adoption['authority'].items() if k!='bytes'},source_binding_status='ACCEPTED_SOURCE_EXTERNAL_READINESS_BOUND_B5_PENDING')
 plan.pop('root_review');plan.pop('execution_release')
 assert not plan['frozen'] and not plan['release_enabled'] and plan['b5_review'] is None and not any(plan['phase_authorization'].values())
 c.validate_stop_binding(plan);assert c.plan_rows(plan)==plan['episodes']
 # No recursive historical protocol reconstruction: accepted protocol/accounting unchanged.
 assert plan['protocol']==plan0['protocol'] and plan['accounting']==plan0['accounting']
 assert authority['protocol']==plan['protocol'] and authority['accounting']==authority['amendment']==plan['accounting']
 assert authority['caps']==c.CAPS;release.validate_caps(authority['caps'])
 CHECK['adopted_authority_protocol_accounting_caps']='PASS'
 assert runtime['provider_ready'] and runtime['cuda_egl_verified'] and runtime['gpu_mapping']['uuid']==c.GPU_UUID
 assert b.runner.runtime_gpu(runtime)==7 and runtime['gpu_mapping']['egl_device_index']==4
 b.runner.stage_overrides(runtime)
 CHECK['runtime_preparation_requirements']={'result':'PASS_WITH_ACCEPTED_UNCHANGED_EVIDENCE','ready_flag_is_not_authorization':True,'external_readiness':A['inputs']['readiness_review'],'native_checkpoint_rehashed':False,'future_worker_receipts_required_before_dispatch':False}
 joins=[];comparisons=[]
 for row in plan['episodes']:
  guard();key=row['episode_key'];previous=read(plan0['expected_manifests'][key]);m=b.manifest(plan,runtime,row)
  change('expected/'+key+'.json',previous,m,['/runtime','/runtime_closure','/controller_semantics'])
  assert not Path(m['output_dir']).exists(), 'used output: '+key
  config,resolved=b.compose_launch(m['argv'],A['worktree'])
  assert w.canonical_sha(config)==previous['composed_config_sha256'] and resolved==previous['resolved_config']
  mr=write('expected/'+key+'.json',m);plan['expected_manifests'][key]=mr
  comparisons.append({'episode_key':key,'prior_manifest':plan0['expected_manifests'][key],'manifest':mr,'full_composed_config_sha256':w.canonical_sha(config),'resolved_config_sha256':w.canonical_sha(resolved),'full_config_exact':True,'argv_exact':True,'row_exact':True,'output_absent':True})
  joins.append({'episode_key':key,'manifest':mr,'runtime':rr,'runtime_closure':cr,'controller_semantics':pr})
 assert len(joins)==len({r['episode_key'] for r in joins})==40
 change('plan.candidate-nonreleased-v1.json',plan0,plan,['/runtime','/runtime_closure','/controller_semantics','/expected_manifests','/authority','/source_binding_status','/root_review','/execution_release'])
 planref=write('plan.candidate-nonreleased-v1.json',plan)
 for row in joins:
  key=row['episode_key'];before=old('contexts/'+key+'.disabled.json');ctx=copy.deepcopy(before);ctx.update(plan=planref,expected_manifest=plan['expected_manifests'][key])
  assert ctx['release'] is None
  change('contexts/'+key+'.disabled.json',before,ctx,['/plan','/expected_manifest'])
  row['context']=write('contexts/'+key+'.disabled.json',ctx)
 try:release.validate_plan(plan)
 except (ValueError,KeyError) as e:CHECK['disabled_plan_rejection']={'result':'PASS','reason':str(e)}
 else:raise AssertionError('candidate accepted as released')
 CHECK['all40_scientific_configs_and_context_joins']='PASS'
 CHECK['unchanged_runtime_payload']='PASS_EXACT_EXCEPT_PREPARATION'
 write('all40-joins-v1.json',{'count':40,'plan':planref,'rows':joins,'release_enabled':False})
 write('full-scientific-config-comparison-v1.json',{'count':40,'rows':comparisons,'normalization':None,'release_enabled':False})
 write('changes-v1.json',{'changes':CHANGES,'scope':'Only preparation/readiness bindings, adopted authority reference, downstream hashes and removal of null downstream approval keys.'})
 write('reused-evidence-v1.json',{'accepted_package':A['inputs']['accepted_package'],'independent_review':A['inputs']['independent_review'],'references':REUSED,'runtime_payload_unchanged':True,'closure_payload_unchanged':True,'controller_semantics_unchanged':True,'no_historical_provenance_rebuild':True,'no_future_receipts_created':True})
 keys=('source','scientific_source','protocol','accounting','runtime','runtime_closure','native_build','controller_semantics','resource_routing')
 b5=write('next-independent-b5-inputs-v1.json',{'schema':'n36r2-b5-review-input-package-v1','candidate_plan':planref,'review_inputs':{k:plan[k] for k in keys},'supporting_evidence':{**A['inputs'],'all40_joins':ART['all40-joins-v1.json'],'full_config_comparison':ART['full-scientific-config-comparison-v1.json'],'changes':ART['changes-v1.json'],'reused_evidence':ART['reused-evidence-v1.json']},'verifier':ref(Path(A['worktree'])/'scripts/qd_ed_n36r2_admission.py',True),'required_external_record_schema':'n36r2-independent-b5-review-v1','required_external_decision':'PASS_PREPARATION_REQUIRES_ROOT_RELEASE','required_external_additional_fields':{'worker_receipts_are_future':True,'release_enabled':False},'is_approval_token':False,'release_enabled':False,'instructions':'External reviewer must independently assess these exact inputs. Only after its input-bound B5 record may coordinator freeze final plan, omitting root_review/execution_release keys. External root production review then detached release then regenerated contexts. No worker receipts required before dispatch; mandatory before acceptance.'})
 write('dependency-graph-v1.json',{'direction':'accepted inputs + external readiness/adoption -> runtime -> closure -> controller evidence -> controller semantics -> 40 manifests -> nonreleased candidate plan -> disabled contexts -> review input package','topological_outputs':list(ART.values()),'release_enabled':False})
 # Validate all newly generated immediate references without traversing historical provenance.
 def refs(x):
  if isinstance(x,dict):
   if 'path' in x and 'sha256' in x and str(x['path']).startswith(str(OUT)+'/'):read(x)
   for v in x.values():refs(v)
  elif isinstance(x,list):
   for v in x:refs(v)
 for v in ART.values():refs(read(v))
 CHECK['new_hash_reference_graph']='PASS'
 guard();return b5
error=None;b5=None
try:b5=main()
except BaseException as e:error={'type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()}
report={'schema':'n36r2-readiness-binding-report-v1','node_id':'15.6','at':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'READINESS_BOUND_CANDIDATE_REQUIRES_EXTERNAL_B5' if error is None else 'BLOCKED','authority':ref(OUT/'authority-v1.json',True),'inputs':A['inputs'],'source_commit':A['base_source'],'score':None,'target_met':False,'release_enabled':False,'root_token_minted':False,'b5_token_minted':False,'final_plan_frozen':False,'worker_receipts_are_future':True,'future_worker_receipts_required_before_dispatch':False,'future_worker_receipts_required_before_attempt_acceptance':True,'future_worker_receipts_fabricated':False,'retained_attempts':504,'retained_gpu_hours':75.49265038509455,'checks':CHECK,'blocker':error,'outputs':ART,'next_independent_b5_inputs':b5,'preparation_script':ref(__file__,True),'cpu_checks':{'wall_seconds':time.monotonic()-START,'cpu_seconds':resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime,'threads':2,'affinity':sorted(os.sched_getaffinity(0)),'cap_seconds':120,'broad_tests_repeated':False},'remaining_obligations':['Independent input-bound B5 review; no implementer token.','Coordinator final frozen plan after B5; omit root_review/execution_release keys entirely.','External root production review, detached execution release, regenerated release-bearing contexts.','Locked STOP/deadline, live private ACTIVE/PASS assignment, exclusive GPU7 UUID/CUDA0/EGL4, provider, fresh IDs, accounting and protected headroom rechecks before reservation/launch.','Full frozen model/runtime/native byte checks at production release/admission; unchanged accepted evidence reused here.','Actual admitted worker before/after process-bound receipts and controller/native arithmetic audits; parent validation before acceptance. Missing evidence retains costs and stops.'],'limits':['No source edits, source refresh, historical provenance rebuild, broad tests, device/provider/network/credential/protected result access, owner writes, child agents or old-artifact overwrites.','Readiness is externally evidenced at turn001289, not a new live observation or dispatch authority. Inherited controller ROOT_REVIEWED status refers only to unchanged historical semantics.','Canonical STOP owner_source is an immutable source constant and is preserved, not changed to adopted HEAD.']}
md='Node15.6 readiness binding\n\n'+report['status']+'\n\nScore: null; target_met: false; release_enabled: false.\n\n'+('External turn001289 readiness and turn001288 adoption are hash-bound. Runtime changes are limited to preparation metadata; closure/controller bindings, all40 manifests, nonreleased plan and disabled contexts follow acyclic dependency order. Full composed configs, original fresh IDs/output paths, source/owner routing, GPU7 UUID, protocol/accounting, caps/reserves and future native-worker obligations are preserved. Focused source, closure, controller, all40 config/join and disabled-rejection checks passed. Accepted native/checkpoint evidence is reused. No B5/root token, final frozen plan, release or worker receipt was created.\n\nExact next independent B5 inputs: next-independent-b5-inputs-v1.json. Hash-bound outputs/checks: report-v1.json. Changes: changes-v1.json. After external input-bound B5, coordinator freezes final plan with root_review/execution_release keys absent; external root review and detached release follow. Future actual-worker receipts remain acceptance obligations, not predispatch prerequisites.\n' if error is None else 'Blocker: '+json.dumps(error)+'\n')
with (OUT/'report-v1.md').open('x') as f:f.write(md)
report['markdown']=ref(OUT/'report-v1.md',True)
with (OUT/'report-v1.json').open('x') as f:f.write(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':report['status'],'blocker':error,'cpu_checks':report['cpu_checks'],'report':ref(OUT/'report-v1.json',True)}))
