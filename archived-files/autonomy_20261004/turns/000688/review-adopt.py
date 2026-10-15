import pathlib,json,hashlib,datetime,subprocess,sys,shutil,yaml
root=pathlib.Path.cwd();out=(root.parent/'autonomy_20261004/turns/000688').resolve();v=(root.parent/'variants/n34_observed_jaw_approach/recovery8-identity-repair-v1').resolve();sys.path.insert(0,str(root))
from scripts import qd_ed_final_runner as runner
def ref(p):
 p=pathlib.Path(p).resolve();return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def write(p,o):p.write_text(json.dumps(o,indent=2)+'\n')
def git(*a):return subprocess.check_output(['git',*a],text=True).strip()
def handle(pid):
 p=pathlib.Path(f'/proc/{pid}/stat')
 if not p.exists():return dict(pid=pid,present=False)
 a=p.read_text().split(') ',1)[1].split();return dict(pid=pid,boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(a[19]),state=a[0])
now=datetime.datetime.now(datetime.timezone.utc).isoformat();authority=json.loads((v/'authority-v1.json').read_text());result=json.loads((v/'implementation-result-v1.json').read_text());candidate=result['commit'];before=git('rev-parse','HEAD');assert before==authority['owning_source']
assert not (root.parent/'autonomy_20261004'/'STOP').exists();assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
handles={k:handle(p) for k,p in [('driver',268073),('coordinator',1062161),('wrapper',1041530),('executor',1041531),('closed_controller',978678)]}
assert handles['driver']['start_ticks']==97715947 and handles['coordinator']['start_ticks']==136702068
assert all(not handles[k].get('present',True) for k in ['wrapper','executor','closed_controller'])
assert json.loads((v/'executor-exit-v1.json').read_text())['exit']==0
prefixes={}
for name,expected in authority['ledger_prefixes'].items():
 b=(root/'data'/name).read_bytes();prefixes[name]={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()};assert prefixes[name]==expected
for name in ['handoff-v2.json','user-authorization-v1.json']:
 expected={'handoff-v2.json':'3d8267a367e40ba6a3b9fd307fc8371a335e21bbc92df6700d7ecc10fd9669de','user-authorization-v1.json':'a8d4dfc38b1fd5e9895d5a78b8eab0d0334ef5cb2716ba6aeeb35a8140c5506c'}[name];assert ref(root.parent/'autonomy_20261004'/name)['sha256']==expected
handoff=json.loads((root.parent/'autonomy_20261004'/'handoff-v2.json').read_text())
for k in ['required_continuation_context','completion_contract']:assert ref(handoff[k]['path'])['sha256']==handoff[k]['sha256']
entry=dict(schema='autonomy-turn-entry-reconciliation-v1',at=now,source=before,handles=handles,ledger_prefixes=prefixes,stop_exists=False,prior_turn_receipt=ref(out.parent/'000687/receipt.json'),prior_turn_summary=ref(out.parent/'000687/operational-summary.md'),active_controller=None,executor_terminal=True)
write(out/'adoption-reconciliation-v1.json',entry)
files=git('diff-tree','--no-commit-id','--name-only','-r',candidate).splitlines();assert files==result['changed_files']
assert git('diff','--name-only',before,candidate).splitlines()==files
assert not git('diff','--name-only','HEAD','--',*files);assert not git('diff','--cached','--name-only')
wt=v.parent/'production_worktree';assert subprocess.check_output(['git','status','--porcelain'],cwd=wt,text=True)==''
for f in files:assert subprocess.check_output(['git','show',f'{candidate}:{f}'])==(wt/f).read_bytes()
review=dict(schema='n34r8-identity-root-engineering-review-v1',at=now,status='PASS_CPU_ENGINEERING_REVIEW',commit=candidate,implementation=ref(v/'implementation-result-v1.json'),authority=ref(v/'authority-v1.json'),executor_exit=ref(v/'executor-exit-v1.json'),changed_files=files,checks=['Reviewed complete two-source-file diff and changed identity/history/release tests; lifecycle unchanged','Exact four-file scope and clean isolated committed bytes','All eight invalid charges retained in original buckets; no outcome carry-forward','Fresh30 identities, one recovery/nine baseline/twenty development; no automatic retries','Scientific source/thresholds/native audits unchanged'],test_evidence=ref(v/'focused-tests-v1.log'),reported_tests_passed=471,tests_repeated=False,ledger_prefixes=prefixes,gpu_authorized=False,limitations=['CPU tests do not certify native runtime completeness or scientific efficacy','Runtime regeneration and detached release verification pending'])
write(out/'engineering-review-v1.json',review)
next_step='Regenerate composed N34R8 runtime closure and30 fresh manifests on adopted source using turn685 corrected import inventory. Freeze fresh prospective accounting/protocol/root review/release; pass full public validation before idle GPU7 admission. Preserve eight invalid charges, unknown telemetry, scientific thresholds and protected gates.'
intent=dict(schema='n34r8-source-adoption-v1',at=now,source_before=before,candidate=candidate,root_review=ref(out/'engineering-review-v1.json'),ledger_prefixes=prefixes,gpu_dispatch=False,scientific_promotion=False,next_step=next_step,scientific_source_resolution={'current_n34_implementation':'71ffff1a0f70d9874b309db9ef1843c02bf17ebf','historical_state_field':'1065f38122379a515b60a9a424f574330405b66f','basis':ref(out.parent/'000524/n34-cpu-source-adoption-v1.json'),'historical_field_preserved':True})
assert intent['scientific_source_resolution']['basis']['sha256']=='7c7b06e50013fccea43a6a61e3c29f5da7e79396525751a817218ef91c1f4f88'
write(out/'source-adoption-intent-v1.json',intent)
cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';sp=root/'research-state.yaml';tp=cp.parent/'idea_tree.json'
with runner.locked(root/'data/qd-ed-state.lock'):
 s=runner.read_state(sp);c=json.loads(cp.read_text());t=json.loads(tp.read_text());assert s['active_controller'] is None and c['active_controller'] is None
 assert s['source_commit']==before and s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
 for p in [sp,cp,tp]:shutil.copyfile(p,out/(p.name+'.before'))
 pick=subprocess.run(['git','cherry-pick',candidate],text=True,capture_output=True);(out/'cherry-pick.log').write_text(pick.stdout+pick.stderr);assert pick.returncode==0,pick.stderr
 after=git('rev-parse','HEAD');assert not git('diff',after,candidate,'--',*files)
 assert git('diff','--name-only',before,after).splitlines()==files
 adoption={**intent,'source_after':after,'tree':git('rev-parse','HEAD^{tree}'),'identical_integrated_files':files,'test_evidence':ref(v/'focused-tests-v1.log'),'tests_repeated':False};write(out/'source-adoption-v1.json',adoption)
 for d in [s,c]:
  rec=d['n34r8_identity_repair'];rec.update(status='CPU_REPAIR_ADOPTED_RUNTIME_RELEASE_PENDING',executor_exited=True,commit=candidate,integrated_source=after,root_review=ref(out/'engineering-review-v1.json'),source_adoption=ref(out/'source-adoption-v1.json'),executor_exit=ref(v/'executor-exit-v1.json'),next_step=next_step)
  d.update(status='N34R8_CPU_REPAIR_ADOPTED_RUNTIME_RELEASE_PENDING',source_commit=after,next_action=next_step,n34r8_source_adoption=ref(out/'source-adoption-v1.json'),in_flight_executor=None,in_flight_executors=[],automatic_gpu_dispatch_authorized=False,updated_at=now)
 n=t['nodes']['15.4'];n['n34r8_identity_repair']=s['n34r8_identity_repair'];n['result']='N34R8 operational identity repair independently reviewed and adopted; runtime/release preparation pending. No accepted Dev evidence or promotion.'
 for p,obj,is_yaml in [(sp,s,True),(cp,c,False),(tp,t,False)]:
  tmp=p.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(obj,sort_keys=False,allow_unicode=True) if is_yaml else json.dumps(obj,indent=2)+'\n');tmp.replace(p)
for name,expected in prefixes.items():
 b=(root/'data'/name).read_bytes();assert {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}==expected
write(out/'end-reconciliation-v1.json',dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),source=after,handles=handles,ledger_prefixes_unchanged=True,source_adoption=ref(out/'source-adoption-v1.json'),target_met=False,gpu_dispatches=0,next_action=next_step))
(out/'operational-summary.md').write_text(f'''Turn688 — {now}

Owning source {before} -> {after}; adopted isolated operational commit {candidate}. Scientific source71ffff1a0f70d9874b309db9ef1843c02bf17ebf unchanged. Handoff, exact authorization, continuation and completion-contract hashes verified. STOP absent; deadline2026-10-11T11:13:13Z.

Live handles verified on boot{handles['driver']['boot_id']}: driver268073/start97715947, coordinator1062161/start136702068. CPU wrapper1041530/executor1041531 and closed controller978678 absent. No active GPU controller. Prior turn exited normally; its terminal executor side effects reconciled. No duplicate launch, restart or process signal.

Reviewed complete four-file R8 repair and471 passing focused CPU tests; clean committed executor bytes matched. Adoption changed only those four files; state/checkpoint/node15.4 updated under owning state lock. CPU executor live index cleared with historical handle records preserved. No broad tests repeated. All450 dispatches and64.17769137431843GPUh retained; all three private ledger prefixes byte/hash unchanged. No driver locks, foreign study, protected results or credentials accessed.

Next bounded step: {next_step}

Unresolved: native runtime completeness, fresh matched Dev efficacy, promotion, original validation20/formal10/required matched ablation evidence and hash-bound completion record. Goal not complete. Local driver owns continuation.
''')
print(json.dumps({'review':'PASS','source_before':before,'source_after':after,'ledger_unchanged':True,'next_step':next_step}))
