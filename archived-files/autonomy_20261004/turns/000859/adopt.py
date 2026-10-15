import pathlib,json,hashlib,datetime,subprocess,sys,shutil,yaml,os
r=pathlib.Path.cwd();o=(r.parent/'autonomy_20261004/turns/000859').resolve();v=(r.parent/'variants/n34_observed_jaw_approach/continuation11-implementation-v1').resolve();sys.path.insert(0,str(r))
from scripts import qd_ed_final_runner as runner
def ref(p):
 p=pathlib.Path(p).resolve();return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
a=json.loads((v/'authority-v1.json').read_text());review=json.loads((o.parent/'000858/engineering-review-v1.json').read_text());before=git('rev-parse','HEAD');candidate=review['commit'];now=datetime.datetime.now(datetime.timezone.utc).isoformat()
assert before==a['source']==review['base'];assert not os.path.lexists(r.parent/'autonomy_20261004/STOP');assert now<'2026-10-11T11:13:13'
for p in [1322966,2244802,2244805]:assert not pathlib.Path(f'/proc/{p}').exists()
assert json.loads((v/'executor-exit-v1.json').read_text())['exit']==0
for k in ['implementation','executor_exit']:assert ref(review[k]['path'])==review[k]
h=json.loads((r.parent/'autonomy_20261004/handoff-v2.json').read_text())
for k in ['authorization','required_continuation_context','completion_contract']:assert ref(h[k]['path'])==h[k]
def ledgers():
 for name,e in a['ledger_prefixes'].items():
  b=(r/'data'/name).read_bytes();assert dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())==e
ledgers();files=git('diff','--name-only',before,candidate).splitlines();assert files==review['changed_files'];assert not git('diff','HEAD','--',*files);assert not git('diff','--cached','--name-only');subprocess.run(['git','diff','--check',before,candidate],check=True)
next_step='Prepare separate continuation11 runtime and source closure on adopted operational source using existing pinned dependencies; verify exact scientific equality, generate missing11-only manifests, freeze prospective accounting/protocol/root release and pass public validation before idle GPU7 admission. Preserve original19/R11 and all charges; no replay or automatic promotion.'
intent=dict(schema='n34-continuation-source-adoption-v1',at=now,source_before=before,candidate=candidate,root_review=ref(o.parent/'000858/engineering-review-v1.json'),authority=ref(v/'authority-v1.json'),ledger_prefixes=a['ledger_prefixes'],gpu_dispatch=False,scientific_promotion=False,next_step=next_step)
write(o/'source-adoption-intent-v1.json',intent)
sp=r/'research-state.yaml';cp=r/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json'
with runner.locked(r/'data/qd-ed-state.lock'):
 s=runner.read_state(sp);c=json.loads(cp.read_text());t=json.loads(tp.read_text());assert s['source_commit']==before;assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS';assert s['active_controller']['terminal_status']=='BUDGET_CAPPED_PARTIAL_COHORT_NO_PROMOTION'
 for p in [sp,cp,tp]:shutil.copyfile(p,o/(p.name+'.before'))
 p=subprocess.run(['git','cherry-pick',candidate],text=True,capture_output=True);(o/'cherry-pick.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
 after=git('rev-parse','HEAD');assert not git('diff',after,candidate,'--',*files);assert git('diff','--name-only',before,after).splitlines()==files
 write(o/'source-adoption-v1.json',{**intent,'source_after':after,'tree':git('rev-parse','HEAD^{tree}'),'identical_integrated_files':files})
 for d in [s,c]:
  rec=d['n34_continuation_implementation'];rec.update(status='CPU_REVIEWED_ADOPTED_RUNTIME_RELEASE_PENDING',executor_exited=True,commit=candidate,integrated_source=after,root_review=intent['root_review'],source_adoption=ref(o/'source-adoption-v1.json'),executor_exit=ref(v/'executor-exit-v1.json'),next_step=next_step)
  d.update(status='N34_CONTINUATION_ADOPTED_RUNTIME_RELEASE_PENDING',source_commit=after,next_action=next_step,n34_continuation_source_adoption=ref(o/'source-adoption-v1.json'),in_flight_executor=None,in_flight_executors=[],automatic_gpu_dispatch_authorized=False,updated_at=now)
 t['nodes']['15.4']['n34_continuation_implementation']=s['n34_continuation_implementation'];t['nodes']['15.4']['result']='Operational continuation implementation reviewed/adopted; runtime and distinct release pending. R11 retains six matched triples C0=0/6,Q0=0/6,N34=1/6; no promotion.'
 for p,x,y in [(sp,s,True),(cp,c,False),(tp,t,False)]:
  tmp=p.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(x,sort_keys=False,allow_unicode=True) if y else json.dumps(x,indent=2)+'\n');tmp.replace(p)
ledgers()
write(o/'end-reconciliation-v1.json',dict(at=now,source=after,live_experiment_handles=[],driver_pid=268073,driver_start_ticks=97715947,coordinator_pid=2283002,coordinator_start_ticks=139898274,boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),ledger_prefixes=a['ledger_prefixes'],budget_snapshot=s['budget_snapshot'],source_adoption=ref(o/'source-adoption-v1.json'),next_step=next_step,goal_complete=False))
(o/'operational-summary.md').write_text(f'''Turn859 — {now}\n\nCurrent owning source {after}; adopted reviewed operational commit {candidate}. Scientific files unchanged. Driver268073/start97715947 and coordinator2283002/start139898274 verified on current boot. Closed controller1322966 and CPU wrapper2244802/executor2244805 absent; executor exit0. STOP absent; deadline2026-10-11T11:13:13Z.\n\nCompleted: verified prior normal turn and hash-bound CPU review, adopted six scoped files under owning state lock, reconciled state/checkpoint/node15.4 executor completion. Three private ledgers unchanged;472 attempts/69.38354303190809 GPUh retained. Existing terminal controller record preserved. No GPU dispatch or protected evaluation; no driver locks acquired. Prior64 focused tests and retained19 audit PASS reused without redundant reruns.\n\nNext bounded step: {next_step}\n\nUnresolved: production source/runtime closure and fresh release, missing11 outcomes, scientific promotion, validation20/formal10/required ablations. No completion claim; local driver continues.\n''')
print(json.dumps(dict(source_after=after,next_step=next_step)))
