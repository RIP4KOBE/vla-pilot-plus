import pathlib,json,hashlib,datetime,subprocess,sys,shutil,yaml
root=pathlib.Path.cwd();out=(root.parent/'autonomy_20261004/turns/000707').resolve();v=(root.parent/'variants/n34_observed_jaw_approach/recovery10-identity-repair-v1').resolve();sys.path.insert(0,str(root))
from scripts import qd_ed_final_runner as runner
def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,o):p.write_text(json.dumps(o,indent=2)+'\n')
def git(*a):return subprocess.check_output(['git',*a],text=True).strip()
now=datetime.datetime.now(datetime.timezone.utc).isoformat();authority=json.loads((v/'authority-v1.json').read_text());result=json.loads((v/'implementation-result-v1.json').read_text());candidate=result['commit'];before=git('rev-parse','HEAD');assert before==authority['owning_source']
assert not (root.parent/'autonomy_20261004/STOP').exists();assert now<'2026-10-11T11:13:13'
assert json.loads((v/'executor-exit-v1.json').read_text())['exit']==0
assert all(not pathlib.Path(f'/proc/{p}').exists() for p in [1217477,1217478])
for name,expected in authority['ledger_prefixes'].items():
 b=(root/'data'/name).read_bytes();assert {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}==expected
files=git('diff-tree','--no-commit-id','--name-only','-r',candidate).splitlines();assert files==result['changed_files'];assert git('diff','--name-only',before,candidate).splitlines()==files
assert not git('diff','--name-only','HEAD','--',*files);assert not git('diff','--cached','--name-only')
wt=v.parent/'production_worktree';assert subprocess.check_output(['git','status','--porcelain'],cwd=wt,text=True)==''
for f in files:assert subprocess.check_output(['git','show',f'{candidate}:{f}'])==(wt/f).read_bytes()
subprocess.run(['git','diff','--check',before,candidate],check=True)
incident={'schema':'protected-read-scope-incident-v1','at':now,'source':ref(v/'report-v1.md'),'scope':'Executor reports broad identity search emitted tracked historical validation rows. Root did not open that event content or protected results.','executor_claim':'No result values used in implementation or scientific decisions.','root_assessment':'Four-file diff is operational identity/provenance only, no scientific changes. This engineering review makes no efficacy or promotion decision.','disposition':'Preserve disclosure; exclude exposed values from scientific decisions. Future executor searches must specify source/test/config files and exclude all data/results. No scientific promotion authorized.'}
write(out/'protected-read-incident-v1.json',incident)
review={'schema':'n34r10-identity-root-engineering-review-v1','at':now,'status':'PASS_CPU_ENGINEERING_REVIEW','commit':candidate,'implementation':ref(v/'implementation-result-v1.json'),'authority':ref(v/'authority-v1.json'),'executor_exit':ref(v/'executor-exit-v1.json'),'changed_files':files,'checks':['Reviewed source and test diffs: exact turn704 provenance, 30 fresh identities and ten invalid histories retained','Only authorized four files differ from owning source; isolated committed bytes match','1 recovery/9 baseline/20 development; no automatic recovery; scientific thresholds and native audits unchanged'],'test_evidence':ref(v/'focused-tests-v1.log'),'reported_tests_passed':556,'tests_repeated':False,'gpu_authorized':False,'scope_incident':ref(out/'protected-read-incident-v1.json'),'limitations':['CPU tests do not establish native runtime validity or efficacy','Runtime regeneration, full public release validation and scientific promotion remain pending']}
write(out/'engineering-review-v1.json',review)
next_step='Regenerate composed N34R10 runtime closure and 30 fresh manifests on adopted source using turn705 corrected import inventory. Freeze prospective accounting/protocol/root review/release and pass full public validation before idle GPU7 admission. Preserve ten invalid charges, unknown telemetry and scientific gates. Restrict executor searches to explicit source/test/config paths; preserve turn707 protected-read incident.'
resolution=json.loads((out.parent/'000697/source-adoption-v1.json').read_text())['scientific_source_resolution'];assert ref(resolution['basis']['path'])==resolution['basis']
intent={'schema':'n34r10-source-adoption-v1','at':now,'source_before':before,'candidate':candidate,'root_review':ref(out/'engineering-review-v1.json'),'ledger_prefixes':authority['ledger_prefixes'],'gpu_dispatch':False,'scientific_promotion':False,'scientific_source_resolution':resolution,'next_step':next_step}
write(out/'source-adoption-intent-v1.json',intent)
cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';sp=root/'research-state.yaml';tp=cp.parent/'idea_tree.json'
with runner.locked(root/'data/qd-ed-state.lock'):
 s=runner.read_state(sp);c=json.loads(cp.read_text());t=json.loads(tp.read_text());assert s['active_controller'] is None and c['active_controller'] is None
 assert s['source_commit']==before and s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
 for p in [sp,cp,tp]:shutil.copyfile(p,out/(p.name+'.before'))
 pick=subprocess.run(['git','cherry-pick',candidate],text=True,capture_output=True);(out/'cherry-pick.log').write_text(pick.stdout+pick.stderr);assert pick.returncode==0,pick.stderr
 after=git('rev-parse','HEAD');assert not git('diff',after,candidate,'--',*files);assert git('diff','--name-only',before,after).splitlines()==files
 adoption={**intent,'source_after':after,'tree':git('rev-parse','HEAD^{tree}'),'identical_integrated_files':files,'test_evidence':ref(v/'focused-tests-v1.log'),'tests_repeated':False};write(out/'source-adoption-v1.json',adoption)
 for d in [s,c]:
  rec=d['n34r10_identity_repair'];rec.update(status='CPU_REPAIR_ADOPTED_RUNTIME_RELEASE_PENDING',executor_exited=True,commit=candidate,integrated_source=after,root_review=ref(out/'engineering-review-v1.json'),source_adoption=ref(out/'source-adoption-v1.json'),executor_exit=ref(v/'executor-exit-v1.json'),next_step=next_step)
  d.update(status='N34R10_CPU_REPAIR_ADOPTED_RUNTIME_RELEASE_PENDING',source_commit=after,next_action=next_step,n34r10_source_adoption=ref(out/'source-adoption-v1.json'),n34r10_protected_read_incident=ref(out/'protected-read-incident-v1.json'),in_flight_executor=None,in_flight_executors=[],automatic_gpu_dispatch_authorized=False,updated_at=now)
 n=t['nodes']['15.4'];n['n34r10_identity_repair']=s['n34r10_identity_repair'];n['result']='N34R10 operational identity repair reviewed and adopted; runtime/release preparation pending. Scope-read incident preserved; no efficacy decision or promotion.'
 for p,obj,is_yaml in [(sp,s,True),(cp,c,False),(tp,t,False)]:
  tmp=p.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(obj,sort_keys=False,allow_unicode=True) if is_yaml else json.dumps(obj,indent=2)+'\n');tmp.replace(p)
for name,expected in authority['ledger_prefixes'].items():
 b=(root/'data'/name).read_bytes();assert {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}==expected
write(out/'end-reconciliation-v1.json',{'at':now,'source':after,'ledger_prefixes':authority['ledger_prefixes'],'source_adoption':ref(out/'source-adoption-v1.json'),'executor_exited':True,'active_controller':None,'target_met':False,'next_action':next_step})
(out/'operational-summary.md').write_text(f'''Turn 707 — {now}

Current owning source: {after}; adopted isolated operational commit {candidate}. Scientific implementation 71ffff1a0f70d9874b309db9ef1843c02bf17ebf unchanged; historical reference discrepancy resolved by turn524 adoption, without rewriting history.

Bound handoff, authority, continuation and completion contract verified. Driver268073/start97715947 remains live on boot2a1fa95f-ab0d-488c-a298-fc488ddd2af7. Existing CPU wrapper1217477/executor1217478 identities initially matched, then both exited normally (exit0). Prior turn706 completed normally. No active GPU controller or worker; no duplicate launch. STOP absent, deadline2026-10-11T11:13:13Z. Driver locks untouched.

Reviewed four-file identity/provenance repair and 556 passing focused CPU tests, adopted under owning state lock, updated state/checkpoint/node15.4 and cleared live executor index while preserving history. Tests not unnecessarily repeated. All three private ledgers unchanged:452 dispatches,64.57233985826672GPUh; ten invalid N34 executions retained with unknown telemetry and original charges. No GPU dispatch or scientific promotion.

Executor disclosed an out-of-scope search emitting historical validation rows. Incident is hash-bound in protected-read-incident-v1.json; root did not inspect those rows. No scientific edits or decisions adopted; future searches must be path-restricted. Disclosure retained as a limitation, not erased.

Next bounded step: {next_step}

Unresolved: full native runtime validity, matched Dev efficacy, validation/formal/required ablation evidence. No completion record; local driver continues.
''')
print(json.dumps({'source_after':after,'review':'PASS_CPU_ENGINEERING','next_step':next_step}))
