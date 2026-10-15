import os,sys,json,pathlib,hashlib,datetime,subprocess,copy,traceback
sys.dont_write_bytecode=True
O=pathlib.Path(__file__).absolute().parent;T=O.parent.parent;P=T/'001632/runtime-binding-refresh'
ROOT=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_r1_001617/implementation_worktree')
sys.path.insert(0,str(ROOT));os.chdir(ROOT)
from scripts import qd_ed_n36_engineering_r1 as e,qd_ed_n36_stop as stop
stop.check(need=1)
def rec(p):
 p=pathlib.Path(p);return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
def ref(p):return {k:v for k,v in rec(p).items() if k!='bytes'}
def load(p):return json.loads(pathlib.Path(p).read_text())
def save(n,d):
 p=O/n
 with p.open('x') as f:json.dump(d,f,indent=2,sort_keys=True,allow_nan=False)
 return rec(p)
a=load(O/'authority-v1.json');g=load(O/'generation-results-v1.json');plan=load(O/'engineering-plan.draft-disabled-v1.json');audit=load(O/'audit-view.disabled-v1.json')
inputs={r['path']:r for r in g['inputs']}
def read(r):
 actual=rec(r['path']);assert actual['sha256']==r['sha256'];inputs[r['path']]=actual;return load(r['path'])
prior_report=read(inputs[str(P/'report-v1.json')]);old_index={x['path']:x for x in prior_report['outputs']}
oldplan=read(old_index[str(P/'engineering-plan.draft-disabled-v1.json')]);oldaudit=read(old_index[str(P/'audit-view.disabled-v1.json')])
newhead=plan['source']['commit'];oldhead=oldplan['source']['commit'];supp=[]
def check(n,fn):
 try:result=fn();r={'check':n,'status':'PASS','details':result}
 except Exception as ex:r={'check':n,'status':'FAIL','message':str(ex),'traceback':traceback.format_exc()}
 supp.append(r);return r

def exact_equivalence():
 changed=subprocess.check_output(['git','diff','--name-only',e.BASE,newhead,'--'],cwd=ROOT,text=True).splitlines()
 assert set(changed)<=e.OPERATIONAL_FILES
 assert subprocess.run(['git','merge-base','--is-ancestor',e.BASE,newhead],cwd=ROOT).returncode==0
 evidence=read(plan['scientific_equivalence'])
 e.exact(evidence,{'schema':'n36-engineering-scientific-equivalence-v1','base_commit':e.BASE,'source':plan['source'],'changed_paths':sorted(changed),'scientific_changes':False},'exact reviewed variant scientific equivalence')
 return {'changed_paths':changed,'source_location':str(ROOT),'source':newhead,'corrected_supplemental_comparison':'splitlines before sorting git output; initial character-sorting failure retained, production validator unchanged'}
check('Corrected supplemental exact variant scientific equivalence',exact_equivalence)

def science():
 outcomes=[]
 pairs=[(read(oldaudit['expected_manifests'][row['episode_key']]),read(audit['expected_manifests'][row['episode_key']])) for row in audit['episodes']]
 pairs.append((read(oldplan['engineering_manifest']),read(plan['engineering_manifest'])))
 for old,new in pairs:
  assert old['row']==new['row'] and old['output_dir']==new['output_dir']
  oldcfg=copy.deepcopy(old['resolved_config']);newcfg=copy.deepcopy(new['resolved_config'])
  changes=[]
  for key in ('n34_runtime_binding','n36_runtime_binding'):
   if oldcfg[key] is not None:
    assert oldcfg[key]['source_commit']==oldhead and newcfg[key]['source_commit']==newhead
    oldcfg[key]['source_commit']=newhead;changes.append(key)
  assert oldcfg==newcfg
  normalized=[arg.replace('source_commit:'+oldhead,'source_commit:'+newhead) for arg in old['argv']]
  assert normalized==new['argv']
  if not changes:assert old['composed_config_sha256']==new['composed_config_sha256']
  if old['expected_runtime'] is not None:
   er=copy.deepcopy(old['expected_runtime']);er['binding']['source_commit']=newhead;er['config_sha256']=new['expected_runtime']['config_sha256']
   assert er==new['expected_runtime']
  else:assert new['expected_runtime'] is None
  outcomes.append({'row':new['row']['episode_key'],'scientific_config_preserved':True,'source_commit_binding_fields':changes})
 assert len(outcomes)==41 and audit['episodes']==oldaudit['episodes']
 return outcomes
check('All41 scientific settings identities output routes and argv preservation',science)

def controller():
 proof=read(plan['controller_semantics']);out=[]
 for name,r in proof['review_evidence'].items():
  d=read(r);prior=read(d['reference_refresh_lineage']['prior_evidence'])
  assert d['findings']==prior['findings'] and d['sources']==prior['sources']
  assert d['status']=='PENDING_INDEPENDENT_AND_ROOT_REVIEW' and d['source_commit']==newhead
  assert d['runtime']==plan['runtime'] and d['runtime_closure']==plan['runtime_closure']
  for s in d['sources']:
   rr=rec(s['path']);assert rr['sha256']==s['sha256'];inputs[s['path']]=rr
   p=pathlib.Path(s['path'])
   if p.is_relative_to(pathlib.Path(plan['worktree'])):
    rel=p.relative_to(plan['worktree']);assert rec(ROOT/rel)['sha256']==s['sha256'];inputs[str(ROOT/rel)]=rec(ROOT/rel)
  out.append({'kind':name,'static_sources_hash_verified':True,'findings_preserved':True,'acceptance':'PENDING'})
 return out
check('Controller proposal static sources and unchanged semantic findings',controller)

ledgers={}
for name,r in a['ledger_prefixes'].items():
 p=pathlib.Path(r['path']);data=p.read_bytes();actual=rec(p)
 ledgers[name]={'anchor':r,'after':actual,'prefix_preserved':hashlib.sha256(data[:r['bytes']]).hexdigest()==r['sha256'],'whole_file_unchanged':actual['sha256']==r['sha256'] and actual['bytes']==r['bytes']}
assert all(x['prefix_preserved'] and x['whole_file_unchanged'] for x in ledgers.values())
unchanged=[{'before':r,'after':rec(p),'unchanged':r==rec(p)} for p,r in inputs.items()]
assert all(x['unchanged'] for x in unchanged)
status=subprocess.check_output(['git','--no-optional-locks','status','--porcelain=v1','--untracked-files=no'],cwd=ROOT,text=True);assert not status
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==a['source_base']
stop.check(need=1)
save('supplemental-verification-v1.json',{'checks':supp,'ledgers':ledgers,'input_preservation':unchanged,'source_status':status,'stop_paths':[{'path':p,'absent':not os.path.lexists(p)} for p in stop.STOP_PATHS],'deadline':stop.DEADLINE,'no_dispatch':True})
checks=g['checks']+supp
helper=load(O/'helper-certification-v1.json')
assert helper['all_helper_checks_pass'] and len(helper['audit_manifests'])==40
outputs=[]
# Enumerate only known executor-created artifacts; avoid live outer wrapper files.
names=list(g['outputs'])+['prepare-disabled-v1.py','prepare-disabled-v1.log','generation-results-v1.json','finalize-report-v1.py','supplemental-verification-v1.json']
for n in sorted(set(names)):outputs.append(rec(O/n))
remaining=[
 {'gate':'owner deployment/source location adoption','status':'PENDING','detail':'Pinned lexical deployment retains prior adapter checkout; exact reviewed source is verified only at isolated R1 variant. No source placement or route-policy amendment performed.'},
 {'gate':'independent/root controller semantics review','status':'PENDING','detail':'Refreshed controller chain is proposal-only; existing validator rejects missing ROOT_REVIEWED status.'},
 {'gate':'readiness-bearing runtime policy','status':'SEPARATE_PROSPECTIVE_REVIEWED_AMENDMENT_REQUIRED','detail':'Exact pinned runtime remains disabled. Current runtime binding rejects readiness flag changes; helper certificates cannot establish readiness.'},
 {'gate':'independent final B5 on exact final graph','status':'PENDING'},
 {'gate':'root source/accounting/protocol adoption and frozen prospective plan','status':'PENDING'},
 {'gate':'fresh separately released health/readiness then distinct episode review/release','status':'PENDING'}]
report={
 'schema':'n36-engineering-r1-affected-binding-refresh-report-v1','node_id':'15.6','status':'DISABLED_BINDINGS_PREPARED_PRODUCTION_ACCEPTANCE_BLOCKED',
 'source_hash':newhead,'source_commit':newhead,'source_inventory_sha256':plan['source']['sha256'],'worktree':str(ROOT),'source_unchanged':True,
 'started_at':g['started_at'],'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'timeout_seconds':1200,'deadline':stop.DEADLINE,
 'authority':rec(O/'authority-v1.json'),'source_review':rec(T/'001640/independent-source-review/review-v1.json'),'root_reconciliation':rec(T/'001642/terminal-reconciliation-v1.json'),
 'prepared':{'specification_reused_exact':e.SPECIFICATION,'source_inventory_reused_exact':load(plan['runtime']['path'])['preparation']['source_record'],'runtime_reused_exact':plan['runtime'],'runtime_regenerated':False,'scope':plan['scope'],'accounting':plan['accounting'],'scientific_equivalence':plan['scientific_equivalence'],'deployment_reused':plan['deployment'],'runtime_closure':plan['runtime_closure'],'controller_proposal':plan['controller_semantics'],'audit':plan['audit_plan'],'audit_rows':40,'helper_certified_audit_manifests':40,'distinct_task0_c0_engineering_manifest':plan['engineering_manifest'],'helper_certified_engineering_manifests':1,'plan':ref(O/'engineering-plan.draft-disabled-v1.json'),'bindings':ref(O/'bindings.disabled-v1.json')},
 'validator_outcomes':checks,'validator_totals':{k:sum(x['status']==k for x in checks) for k in ['PASS','BLOCKED','FAIL']},
 'supplemental_failure_retained':{'check':'Scientific equivalence at exact reviewed variant','reason':'Executor supplemental comparison sorted raw git output characters instead of split lines. Corrected external comparison passes; production helper was unmodified and its scientific-equivalence validator passed. Initial failure/log remain immutable.'},
 'retained_ledger_prefixes':ledgers,'inputs':list(inputs.values()),'outputs':outputs,
 'remaining_review_readiness_adoption_gates':remaining,
 'next_bounded_action':'Independent CPU review of this exact prepared graph and controller proposal, with explicit deployment/source-location reconciliation by the owning root. Before readiness or execution, separately authorize and review a prospective readiness-bearing policy amendment; then final B5, root adoption/frozen protocol, and separately released health/episode. No dispatch from this report.',
 'preservation':{'all40_scientific_rows':True,'task0_c0_identity':True,'scientific_settings_and_protocol':True,'accounting_values_charges_failures_unknown_telemetry_protected_reserves':True,'historical_001632_outputs':True,'exact_inputs_unchanged':True,'source_edits':False,'source_commits':False,'source_placement':False,'owner_peer_state_checkpoint_tree_ledger_writes':False,'evaluators_launched':0,'gpu_model_provider_calls':0,'installs':0,'delegation':False,'protected_validation_formal_access':False,'credential_reads':False,'policy_changes':False},
 'stop_checks':{'paths':list(stop.STOP_PATHS),'absent_at_final':True,'deadline_checked':True,'new_dispatch':False},
 'evidence_limits':'Helper-generated and helper-certified disabled preparation only. Full production closure rejected the imported/deployment checkout mismatch before downstream readiness admission. Explicit controller validation is blocked. Runtime CUDA/EGL/provider/runtime_ready remain false. No root, independent, adoption or readiness acceptance was fabricated.',
 'prepared_bindings_complete':True,'final_production_acceptance':False,'source_adopted':False,'production_ready':False,'gpu_authorized':False,'release_enabled':False,'goal_complete':False,'scientific_success':False,
 'hash_scope':'All executor-created immutable artifacts listed before this report. Report self-hash in report-v1.sha256.json. Preexisting authority and live executor-wrapper artifacts are not outputs.'}
save('report-v1.json',report);save('report-v1.sha256.json',rec(O/'report-v1.json'))
print(json.dumps({'status':report['status'],'validators':report['validator_totals'],'helper_certified':41,'report':rec(O/'report-v1.json')}))
