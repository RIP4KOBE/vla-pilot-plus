import pathlib,json,hashlib,datetime,subprocess,fcntl,os,copy,yaml
owner=pathlib.Path.cwd(); base=owner.parent/'autonomy_20261004'; out=base/'turns/001454'; review=base/'turns/001452/exact-b5-review'
def read(p): return json.loads(pathlib.Path(p).read_text())
def ref(p):
 p=pathlib.Path(p);b=p.read_bytes();return {'path':str(p),'sha256':hashlib.sha256(b).hexdigest()}
def verify(r):
 p=pathlib.Path(r['path']);assert '2026-08-10-eds-qd-stage-guidance-transition-design' not in str(p)
 assert ref(p)['sha256']==r['sha256'],str(p)
 if 'bytes' in r:assert p.stat().st_size==r['bytes']
 return read(p)
def write(p,d):
 assert not p.exists(),str(p)
 p.write_text(json.dumps(d,indent=2)+'\n');return ref(p)
def atomic(p,data):
 t=p.with_name(p.name+'.turn1454.tmp');t.write_text(data);os.replace(t,p)
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
assert not (base/'STOP').exists() and not (base.resolve()/'STOP').exists()
for n,h in [('handoff-v2.json','3d8267a367e40ba6a3b9fd307fc8371a335e21bbc92df6700d7ecc10fd9669de'),('user-authorization-v1.json','a8d4dfc38b1fd5e9895d5a78b8eab0d0334ef5cb2716ba6aeeb35a8140c5506c')]:assert ref(base/n)['sha256']==h
report=read(review/'report-v1.json');receipt=verify(report['consumer_receipt']);plan=verify(report['exact_plan']);verify(report['exact_bindings']);verify(report['authority'])
assert report['decision']=='PASS_PREPARATION_REQUIRES_ROOT_RELEASE' and not report['cpu_b5_blockers']
assert read(review/'executor-exit-v1.json')['exit']==0
process=read(review/'executor-process-v1.json')
for k in ['wrapper','executor']:assert not pathlib.Path('/proc',str(process[k]['pid'])).exists()
keys=report['admission_BINDINGS'];assert len(keys)==10
assert receipt=={'schema':'n36r3-independent-b5-review-v1','decision':'PASS_PREPARATION_REQUIRES_ROOT_RELEASE',**{k:plan[k] for k in keys},'worker_receipts_are_future':True,'release_enabled':False}
source=pathlib.Path(plan['resource_routing']['source_cwd']);assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()==plan['source']['commit']
for f in plan['source']['files']:assert ref(source/f['path'])['sha256']==f['sha256'],f['path']
for k in ['protocol','protocol_review','accounting','runtime','runtime_closure','native_build','controller_semantics']:verify(plan[k])
prev=read(base/'turns/001453/operational-summary-v1.json')
with (owner/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 prefixes={}
 for name,r in prev['ledger_prefixes'].items():
  p=owner/'data'/name;assert ref(p)['sha256']==r['sha256'];assert p.stat().st_size==r['bytes'];prefixes[name]={'path':str(p),'bytes':p.stat().st_size,'sha256':ref(p)['sha256']}
 adoption=write(out/'source-adoption-v1.json',{'schema':'n36r3-source-adoption-v1','approved':True,'owner_root':plan['resource_routing']['owner_root'],'source_cwd':str(source),**{k:plan[k] for k in keys},'independent_review':ref(review/'b5-review-v1.json')})
 next_action='Source/runtime 711602acc32031cfd977a2b3ec2e7ef0582e7377 accepted by turn001454 exact adoption. Next perform locked finite owning-accounting reconciliation/adoption against unchanged 505 attempts / 75.53335346582918 GPUh and all three prefixes; bind fresh authority to turn001454 source-adoption-v1.json and turn001452 b5-review-v1.json, then fresh charged health identity 001445, separate first-C0 release and mandatory G3 pause. No replay of historical health or release.'
 terminal=write(out/'terminal-reconciliation-v1.json',{'schema':'n36r3-b5-terminal-root-reconciliation-v1','at':now,'decision':'ACCEPT_EXACT_CPU_B5_AND_ISOLATED_SOURCE_RUNTIME','report':ref(review/'report-v1.json'),'receipt':ref(review/'b5-review-v1.json'),'exit':ref(review/'executor-exit-v1.json'),'process':ref(review/'executor-process-v1.json'),'source_adoption':adoption,'plan':report['exact_plan'],'ledger_prefixes':prefixes,'live_handles':[],'historical_review_assertion_failure_preserved':report['current_review_failures'],'accounting_adopted':False,'gpu_dispatched':False,'production_parent_attestation_executed':False,'goal_complete':False,'next_action':next_action})
 summary=write(out/'operational-summary-v1.json',{'schema':'arbor-operational-summary-v1','at':now,'turn':1454,'owning_source':prev['owning_source'],'candidate_source':plan['source']['commit'],'candidate_source_adopted':True,'source_adoption':adoption,'live_handles':[],'driver':read(base/'driver-status.json'),'current_controller_status':'NO_ACTIVE_GPU_CONTROLLER; EXACT_B5_ACCEPTED_SOURCE_RUNTIME_ADOPTED','completed_work':['Verified bound authority, isolation, driver PID/boot/start and private ledger prefixes','Reconciled terminal independent reviewer exit 0; no remaining CPU B5 blockers','Verified exact ten bindings, source bytes, runtime/protocol/controller reference hashes','Recorded exact isolated source/runtime adoption; preserved all historical charges and failed review assertion'],'terminal_reconciliation':terminal,'ledger_prefixes':prefixes,'retained_attempts':505,'retained_gpu_hours':75.53335346582918,'driver_stop_exists':False,'deadline':'2026-10-11T11:13:13Z','next_bounded_step':next_action,'unresolved_evidence':['Finite owning-accounting adoption','Fresh charged health 001445 and production attestation','First-C0 native receipts and G3','Original validation/formal/required ablations'],'goal_complete':False})
 sp=owner/'research-state.yaml';cp=owner/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
 for p,isyaml in [(sp,True),(cp,False)]:
  d=yaml.safe_load(p.read_text()) if isyaml else read(p)
  d['n36r3_source_runtime_adoption_prior_to_001454']=d.get('n36r3_source_runtime_adoption')
  d['n36r3_source_runtime_adoption']=adoption;d['n36r3_reconciled_accounting_exact_b5_terminal_reconciliation']=terminal
  r=d['n36r3_reconciled_accounting_exact_b5_review'];r.update(status='TERMINAL_EXIT_0_ROOT_ACCEPTED_SOURCE_RUNTIME_ADOPTED',live_handles=[],report=ref(review/'report-v1.json'),exit=ref(review/'executor-exit-v1.json'),terminal_reconciliation=terminal)
  d['in_flight_executor']=None;d['in_flight_executors']=[];d['status']='N36R3_SOURCE_RUNTIME_ACCEPTED_PENDING_FINITE_ACCOUNTING';d['phase']='N36R3_ACCOUNTING_ADOPTION_PENDING';d['next_action']=next_action;d['latest_operational_summary']=summary;d['automatic_gpu_dispatch_authorized']=False;d['updated_at']=now
  atomic(p,yaml.safe_dump(d,sort_keys=False,allow_unicode=True) if isyaml else json.dumps(d,indent=2)+'\n')
 tp=cp.parent/'idea_tree.json';tree=read(tp);ns=tree['nodes'];node=ns['15.6'] if isinstance(ns,dict) else next(x for x in ns if x['id']=='15.6');node['insight']=next_action;node['result']='EXACT_CPU_B5_ACCEPTED_SOURCE_RUNTIME_ADOPTED_PENDING_FINITE_ACCOUNTING';node['n36r3_b5_root_acceptance_001454']=terminal;atomic(tp,json.dumps(tree,indent=2)+'\n')
 print(json.dumps({'terminal':terminal,'source_adoption':adoption,'summary':summary}))
