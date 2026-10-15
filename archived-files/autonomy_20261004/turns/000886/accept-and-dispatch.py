import pathlib,json,hashlib,datetime,subprocess,sys,shutil,time,yaml
w=pathlib.Path.cwd();o=(w.parent/'autonomy_20261004/turns/000886').resolve();prev=o.parent/'000885';v=o/'n35-cpu-implementation';base='969d5fb57c90f61dfc93331346f0ea8158f4eaf1';sys.path.insert(0,str(w));from scripts import qd_ed_final_runner as runner
R=lambda p:json.loads(p.read_text())
def ref(p):return dict(path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def write(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
now=datetime.datetime.now(datetime.timezone.utc);ds=R(w.parent/'autonomy_20261004/driver-status.json');assert ds['turn']==886
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for key in ['driver','process']:
 h=ds[key];f=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(f[19])==h['start_ticks']
assert now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
assert not (w.parent/'autonomy_20261004/STOP').exists();assert R(prev/'receipt.json')['exit']==0
assert all(not pathlib.Path(f'/proc/{p}').exists() for p in [2303352,2464645,2464646])
report_path=prev/'n35-protocol-review/report-v1.json';report=R(report_path);assert report['disposition']=='PASS' and not report['blocking_issues'];assert R(prev/'n35-protocol-review/executor-exit-v1.json')['exit']==0
prior=R(prev/'n35-protocol-review/authority-v1.json')
for k in ['protocol','accounting','user_authority']:
 r=prior[k];assert ref(pathlib.Path(r['path']))['sha256']==r['sha256']
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==base
p=R(pathlib.Path(prior['protocol']['path']));old=R(o.parent/'000882/n35-prospective-protocol-v1.json')
for k in ['scientific_contract','decision','required_audits','episodes','limits','deadline']:assert p[k]==old[k]
a=R(pathlib.Path(prior['accounting']['path']));assert abs(a['cost_reconciliation']['total_retained_charge_gpu_hours']-(69.99568238388729+.23357169027961985))<1e-10
for n,r in prior['ledger_prefixes'].items():
 b=(w/'data'/n).read_bytes();assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256']
review=dict(schema='n35-protocol-root-acceptance-v1',at=now.isoformat(),source=base,disposition='PASS_CPU_IMPLEMENTATION_ONLY',independent_report=ref(report_path),executor_exit=ref(prev/'n35-protocol-review/executor-exit-v1.json'),protocol=prior['protocol'],accounting=prior['accounting'],scientific_fields_unchanged=True,ledger_prefixes=prior['ledger_prefixes'],live_reviewer_handles=[],review_obligations=report['nonblocking_implementation_obligations'],gpu_authorized=False,target_met=False)
write(o/'protocol-root-acceptance-v1.json',review)
v.mkdir(exist_ok=False)
work=(w.parent/'variants/n35_closure_intent/implementation_worktree').resolve();work.parent.mkdir(parents=True,exist_ok=True)
auth=dict(schema='n35-cpu-implementation-authority-v1',at=now.isoformat(),node_id='15.5',user_authority=prior['user_authority'],source=base,protocol=prior['protocol'],accounting=prior['accounting'],root_review=ref(o/'protocol-root-acceptance-v1.json'),independent_review=ref(report_path),worktree=str(work),branch='exp/n35-closure-intent-cpu-20261009',output_directory=str(v),scope='CPU implementation of frozen N35 mechanism, production wiring, mandatory native audits, controller and meaningful CPU tests. Commit only isolated branch. No GPU or actual experiment dispatch, source adoption, runtime release, protected outcomes or owning state/ledger writes.',gpu_authorized=False,source_edits_authorized=True,wall_cap_seconds=3600,ledger_prefixes=prior['ledger_prefixes'],implementation_obligations=report['nonblocking_implementation_obligations'])
write(v/'authority-v1.json',auth)
subprocess.run(['git','worktree','add','-b',auth['branch'],str(work),base],check=True,stdout=subprocess.DEVNULL)
shutil.copyfile(w/'AGENTS.md',work/'AGENTS.md')
prompt=f'''Continue the explicitly authorized Arbor task as a CPU implementation executor, node15.5. You are not coordinator. Work only in {work}, outputs {v}. Read authority {v/'authority-v1.json'} and verify its exact references. Follow frozen protocol v2, independent PASS review, root acceptance, hypothesis and CPU feasibility review referenced by protocol. These authorize CPU code/tests/commit ONLY. No GPU, training, native simulator runs, protected validation/formal results, source adoption, runtime release, external messages or state/ledger writes. No further delegation. Current source {base}. Use current official session only; no API-key/alternate provider/account, Poe or credential reads. Superpowers disabled. Never read prohibited untracked 2026-08-10-eds-qd-stage-guidance-transition-design.md. Do not recursively search study artifacts or historical results. Scope searches to source directories scripts/src/tests/configs and needed source dependencies, not data/docs/results. Exact bound CPU feasibility/hypothesis are sufficient scientific context; no new literature or hypothesis changes.

Implement the frozen N35 one-boundary executed-closure intent memory faithfully end to end, building on existing N34. Read scripts/qd_ed_n34_{{native,bridge,contract,controller,worker,source,runner,release,prepare}}.py and referenced active policy source as needed. Keep existing controls and old sources compatible. Add N35-specific modules where appropriate. Prove direct selected occurrence provenance through archive copies and deduplication: hash equality/ancestry alone insufficient; ambiguous equal-content origins and memory origins never rearm. Decoder and actual step-return acknowledgements must link all eight positive executed commands, immediate prior guided chunk, same target/Stage/tracker continuity and finite strictly decreasing jaw separation. Consume once on next boundary entry, latch across ten existing parent rounds using each current archive best, expire regardless of selection, reset every specified exception/change path. Only slot15 and native [:8,10]=+1; all other bytes/candidates/scoring/budgets unchanged. N34 fallback when ineligible; memory absent C0/Q0/N34. Distinguish missing trigger evidence (ineligible) from mandatory audit failure (invalid). Preserve native and decoded delta telemetry, including zero decoded deltas.

Build mandatory same-process N35 lifecycle/native audit and production wiring, exact source/runtime closure support, four-arm 40-cell fresh Dev controller under unchanged frozen protocol, complete-quadruple futility, invalidity stop, no retry/replay, atomic full1840s reservation and dual cumulative caps, separate bounded healthchecks, protected reserves, STOP/deadline drain. Do not create live releases or run any GPU worker. Implement CPU tests for scientifically meaningful invariants and adversarial origin/lifecycle/audit/controller paths, adapting pinned existing test infrastructure without broad repeated suites. Do not weaken audits to get tests green. CPU tests are not efficacy. If full integration cannot be completed within 3600 seconds, commit coherent partial work and report precise remaining blockers; do not invent PASS.

Commit only source/test changes on isolated branch (exclude copied AGENTS and any state/results). Preserve worktree after finishing for root review. Write report-v1.json and report-v1.md in output directory, including commit, changed files, test commands/results, protocol compliance, native occurrence chain, known blockers, exact next steps and target_met=false, gpu_authorized=false. No benchmark score is established by CPU work. Explicit authorization overrides skill defaults to run B_dev; do not run B_dev now.
'''
(v/'executor-prompt-v1.txt').write_text(prompt)
wrapper=(prev/'n35-protocol-review/executor-launch-v1.py').read_text().replace(str(w),str(work)).replace('n35-protocol-review-executor-process-v1','n35-cpu-implementation-executor-process-v1').replace('1200','3600')
(v/'executor-launch-v1.py').write_text(wrapper)
with runner.locked(w/'data/qd-ed-runner.lock',nonblocking=True):
 with runner.locked(w/'data/qd-ed-state.lock'):
  sp=w/'research-state.yaml';cp=w/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json'
  s=runner.read_state(sp);c=R(cp);t=R(tp)
  assert s['n35_protocol_review']['process_record']==ref(prev/'n35-protocol-review/executor-process-v1.json')
  assert not s.get('current_owned_workers')
  for path in [sp,cp,tp]:shutil.copyfile(path,o/(path.name+'.before'))
  closed=dict(s['n35_protocol_review']);closed.update(status='PASS_CPU_IMPLEMENTATION_ONLY',executor_exited=True,exit=ref(prev/'n35-protocol-review/executor-exit-v1.json'),report=ref(report_path),root_review=ref(o/'protocol-root-acceptance-v1.json'),live_handles=[])
  with open(v/'wrapper.log','ab') as log:proc=subprocess.Popen([sys.executable,str(v/'executor-launch-v1.py')],cwd=work,stdout=log,stderr=log,start_new_session=True)
  for _ in range(50):
   if (v/'executor-process-v1.json').exists():break
   time.sleep(.1)
  assert (v/'executor-process-v1.json').exists(),f'Reconcile wrapper {proc.pid} before any retry'
  pr=R(v/'executor-process-v1.json');rec=dict(status='CPU_IMPLEMENTATION_RUNNING',node_id='15.5',authority=ref(v/'authority-v1.json'),process_record=ref(v/'executor-process-v1.json'),handles={k:pr[k] for k in ['wrapper','executor']},worktree=str(work),output_directory=str(v),gpu_authorized=False,source_edits_authorized=True)
  next_step='Monitor exact N35 isolated CPU implementation executor; reconcile report/exit/commit and review frozen mechanism, native occurrence audit, controller and CPU tests before source adoption/runtime release. No GPU or protected-phase access yet.'
  for obj in [s,c]:obj.update(n35_protocol_review=closed,n35_protocol_root_acceptance=ref(o/'protocol-root-acceptance-v1.json'),n35_cpu_implementation=rec,in_flight_executor=rec,in_flight_executors=[rec],next_action=next_step,updated_at=now.isoformat())
  c.update(inflight_executor=rec,inflight_executors=[rec])
  t['nodes']['15.5'].update(status='running',result='CPU_IMPLEMENTATION_RUNNING_NO_GPU',protocol_review=closed,cpu_implementation=rec)
  tmp=sp.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(sp);write(cp,c);write(tp,t)
  write(o/'implementation-dispatch-v1.json',dict(at=now.isoformat(),driver=ds,review=review,executor=rec,ledger_prefixes=prior['ledger_prefixes'],next_step=next_step,target_met=False))
print(json.dumps(rec))
