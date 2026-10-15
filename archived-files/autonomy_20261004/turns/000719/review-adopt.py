import pathlib,json,hashlib,datetime,subprocess,sys,shutil,yaml,os
root=pathlib.Path.cwd();out=(root.parent/'autonomy_20261004/turns/000719').resolve();v=(root.parent/'variants/n34_observed_jaw_approach/recovery11-identity-repair-v1').resolve();sys.path.insert(0,str(root))
from scripts import qd_ed_final_runner as runner
def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,o):p.write_text(json.dumps(o,indent=2)+'\n')
def git(*a):return subprocess.check_output(['git',*a],text=True).strip()
now=datetime.datetime.now(datetime.timezone.utc).isoformat();authority=json.loads((v/'authority-v1.json').read_text());result=json.loads((v/'implementation-result-v1.json').read_text());candidate=result['commit'];before=git('rev-parse','HEAD');assert before==authority['owning_source']
assert not (root.parent/'autonomy_20261004/STOP').exists();assert now<'2026-10-11T11:13:13'
assert json.loads((v/'executor-exit-v1.json').read_text())['exit']==0
assert all(not pathlib.Path(f'/proc/{p}').exists() for p in [1295817,1295818,1236007,1238684])
for name,expected in authority['ledger_prefixes'].items():
 b=(root/'data'/name).read_bytes();assert {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}==expected
for name in ['authority','terminal_closure','runtime_preparation']:
 assert ref(authority[name]['path'])==authority[name]
handoff=json.loads((root.parent/'autonomy_20261004/handoff-v2.json').read_text())
for key in ['authorization','required_continuation_context','completion_contract']:
 assert ref(handoff[key]['path'])==handoff[key]
files=git('diff-tree','--no-commit-id','--name-only','-r',candidate).splitlines();assert files==result['changed_files'];assert git('diff','--name-only',before,candidate).splitlines()==files
assert not git('diff','--name-only','HEAD','--',*files);assert not git('diff','--cached','--name-only')
wt=v.parent/'production_worktree';assert subprocess.check_output(['git','status','--porcelain','-uno'],cwd=wt,text=True)==''
for f in files:assert subprocess.check_output(['git','show',f'{candidate}:{f}'])==(wt/f).read_bytes()
subprocess.run(['git','diff','--check',before,candidate],check=True)
review={'schema':'n34r11-identity-root-engineering-review-v1','at':now,'status':'PASS_CPU_ENGINEERING_REVIEW','commit':candidate,'implementation':ref(v/'implementation-result-v1.json'),'authority':ref(v/'authority-v1.json'),'executor_exit':ref(v/'executor-exit-v1.json'),'changed_files':files,'checks':['Source diff restricted to cohort identities, retained invalid history and exact turn715 closure binding','Scientific implementation, thresholds, caps, native audit and worker unchanged','All 30 rows fresh; 1 recovery/9 baseline/20 development; zero automatic recovery','Root independently ran all 12 focused recovery11 tests successfully'],'test_evidence':ref(v/'focused-tests-v1.log'),'root_tests_passed':12,'gpu_authorized':False,'limitations':['CPU tests do not establish native runtime validity or efficacy','Runtime regeneration and full public release validation remain pending'],'prior_incident_preserved':ref(out.parent/'000707/protected-read-incident-v1.json')}
write(out/'engineering-review-v1.json',review)
next_step='Regenerate N34R11 runtime closure and 30 fresh manifests on adopted source using turn716 corrected qualitative-image/video inventory. Freeze prospective accounting/protocol/root review/release and pass full public validation before idle GPU7 admission. Preserve eleven invalid N34 charges, unknown telemetry, protected reserves and scientific gates.'
intent={'schema':'n34r11-source-adoption-v1','at':now,'source_before':before,'candidate':candidate,'root_review':ref(out/'engineering-review-v1.json'),'ledger_prefixes':authority['ledger_prefixes'],'gpu_dispatch':False,'scientific_promotion':False,'next_step':next_step}
write(out/'source-adoption-intent-v1.json',intent)
cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';sp=root/'research-state.yaml';tp=cp.parent/'idea_tree.json'
with runner.locked(root/'data/qd-ed-state.lock'):
 s=runner.read_state(sp);c=json.loads(cp.read_text());t=json.loads(tp.read_text());assert s['active_controller'] is None and c['active_controller'] is None
 assert s['source_commit']==before and s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
 for p in [sp,cp,tp]:shutil.copyfile(p,out/(p.name+'.before'))
 pick=subprocess.run(['git','cherry-pick',candidate],text=True,capture_output=True);(out/'cherry-pick.log').write_text(pick.stdout+pick.stderr);assert pick.returncode==0,pick.stderr
 after=git('rev-parse','HEAD');assert not git('diff',after,candidate,'--',*files);assert git('diff','--name-only',before,after).splitlines()==files
 adoption={**intent,'source_after':after,'tree':git('rev-parse','HEAD^{tree}'),'identical_integrated_files':files};write(out/'source-adoption-v1.json',adoption)
 for d in [s,c]:
  rec=d['n34r11_identity_repair'];rec.update(status='CPU_REPAIR_ADOPTED_RUNTIME_RELEASE_PENDING',executor_exited=True,commit=candidate,integrated_source=after,root_review=ref(out/'engineering-review-v1.json'),source_adoption=ref(out/'source-adoption-v1.json'),executor_exit=ref(v/'executor-exit-v1.json'),next_step=next_step)
  d.update(status='N34R11_CPU_REPAIR_ADOPTED_RUNTIME_RELEASE_PENDING',source_commit=after,next_action=next_step,n34r11_source_adoption=ref(out/'source-adoption-v1.json'),in_flight_executor=None,in_flight_executors=[],automatic_gpu_dispatch_authorized=False,updated_at=now)
 n=t['nodes']['15.4'];n['n34r11_identity_repair']=s['n34r11_identity_repair'];n['result']='N34R11 operational identity repair reviewed and adopted; runtime/release preparation pending. No efficacy decision or promotion.'
 for p,obj,is_yaml in [(sp,s,True),(cp,c,False),(tp,t,False)]:
  tmp=p.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(obj,sort_keys=False,allow_unicode=True) if is_yaml else json.dumps(obj,indent=2)+'\n');tmp.replace(p)
for name,expected in authority['ledger_prefixes'].items():
 b=(root/'data'/name).read_bytes();assert {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}==expected
entry=json.loads((out/'entry-reconciliation-v1.json').read_text())
write(out/'end-reconciliation-v1.json',{**entry,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':after,'source_adoption':ref(out/'source-adoption-v1.json'),'executor_exited':True,'active_controller':None,'target_met':False,'next_action':next_step,'controller_status':'N34R11_CPU_REPAIR_ADOPTED_RUNTIME_RELEASE_PENDING'})
(out/'operational-summary.md').write_text(f'''Turn719 — {now}

Current owning source: {after}; adopted isolated operational commit {candidate}. Scientific code/configuration unchanged.

Bound handoff, exact authorization, continuation and completion contract verified. Driver268073/start97715947 and coordinator1306564/start137412972 match boot2a1fa95f-ab0d-488c-a298-fc488ddd2af7. CPU wrapper1295817/executor1295818 exited normally (exit0); prior turn718 completed normally. Closed controller1236007/worker1238684 absent. No active GPU controller or worker. STOP absent; authorization deadline2026-10-11T11:13:13Z. Driver locks untouched.

Reviewed three-file identity/provenance repair, independently ran12 focused tests (PASS), adopted under owning state lock, updated state/checkpoint/node15.4 and cleared live executor index while preserving history. All three private ledgers unchanged:453 dispatches,64.81438003276922GPUh; eleven invalid N34 executions retained with unknown telemetry and original charges. No GPU dispatch, protected-result access or scientific promotion. Existing turn707 scope incident preserved.

Next bounded step: {next_step}

Unresolved: full native runtime validity, matched Dev efficacy, validation/formal/required ablation evidence. No completion record; local driver continues.
''')
print(json.dumps({'source_after':after,'review':'PASS_CPU_ENGINEERING','next_step':next_step}))
