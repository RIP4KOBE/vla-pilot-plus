import pathlib,json,hashlib,datetime,os,subprocess,fcntl,yaml,time
root=pathlib.Path.cwd();base=root.parent/'autonomy_20261004';out=base/'turns/001452';v=out/'exact-b5-review';prior=base/'turns/001433/exact-b5-review'
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def write(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');os.replace(t,p)
def handle(pid):
 s=pathlib.Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1].split();return dict(pid=pid,boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(s[19]),state=s[0])
now=datetime.datetime.now(datetime.timezone.utc);assert now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00');assert not (base/'STOP').exists()
prev=json.loads((base/'turns/001451/operational-summary-v1.json').read_text());receipt=json.loads((base/'turns/001451/receipt.json').read_text());assert receipt['exit']==0
for r in prev['ledger_prefixes'].values():assert ref(pathlib.Path(r['path']))['sha256']==r['sha256']
driver=json.loads((base/'driver-status.json').read_text())
for k in ['driver','process']:
 h=handle(driver[k]['pid']);assert all(h[x]==driver[k][x] for x in ['pid','boot_id','start_ticks'])
assert not v.exists();v.mkdir()
a=json.loads((prior/'authority-v1.json').read_text());a.update(at=now.isoformat(),source='711602acc32031cfd977a2b3ec2e7ef0582e7377')
for key,name in [('plan','plan.draft.json'),('bindings','bindings.disabled-v1.json')]:a[key]=ref(base/'turns/001451/manifest-refresh'/name)
assert a['plan']['sha256']=='b3d75d399d1953e1e3f3f230a92c4960d0ce6e700714598d0d8cedd603047103'
a['terminal_reconciliation']=ref(base/'turns/001451/terminal-reconciliation-v1.json');a['controller_review']=ref(base/'turns/001451/controller-semantics.root-reviewed-v1.json');write(v/'authority-v1.json',a)
prompt=(prior/'executor-prompt-v1.txt').read_text().split('Focus on accepted accounting-health repair')[0]
prompt=prompt.replace('001433','001452').replace('001432','001451').replace('d01bc1e2e7acc876653a43ddf157d0b4a641f88a',a['source'])
prompt+='\nFocus on accepted reconciled-accounting health repair turn 001445, root reconciliation 001447 and refreshed bindings 001448/001451. Prior accepted exact B5 turn 001433 and root disposition 001437 provide continuity. Review only current binding delta and consumers, especially accounting verification against refreshed accounting and distinct preparation health identity n36_healthcheck_n36r3_preparation_001445; include retained lexical-reference repair. Preserve accepted tests; run only necessary bounded CPU verification. Production parent attestation remains unexecuted pending real governance; do not synthesize governance or replay old health. Distinguish future finite accounting/health/G3 requirements from CPU B5 blockers. Require schema n36r3-independent-b5-review-v1, exact admission.BINDINGS, worker_receipts_are_future=true, release_enabled=false; emit PASS_PREPARATION_REQUIRES_ROOT_RELEASE only if warranted. Preserve failures and unknowns.\n'
(v/'executor-prompt-v1.txt').write_text(prompt);(v/'executor-launch-v1.py').write_text((prior/'executor-launch-v1.py').read_text())
with (root/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 state=yaml.safe_load((root/'research-state.yaml').read_text());assert not state.get('in_flight_executor') and not state.get('in_flight_executors')
 assert not (base/'STOP').exists()
 with (v/'wrapper.log').open('wb') as log:p=subprocess.Popen(['/home/hynx/miniconda3/envs/vla-pilot/bin/python','-I','-B',str(v/'executor-launch-v1.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 h=handle(p.pid);write(v/'wrapper-launch-v1.json',h)
 active=dict(status='RUNNING_CPU_EXACT_B5_REVIEW',node_id='15.6',authority=ref(v/'authority-v1.json'),wrapper=h,source=a['source'],worktree='/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree',output_directory=str(v),process_record_path=str(v/'executor-process-v1.json'),gpu_authorized=False,release_enabled=False,source_edits_authorized=False)
 next_action='Monitor turn 001452 exact independent B5 reviewer by boot/start identity; reconcile exit and hash-bound report before source/runtime adoption. Then locked finite accounting and fresh charged preparation health identity, separate first-C0 release and G3 pause. Do not dispatch duplicate reviewer or GPU worker.'
 for path,is_yaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  d=yaml.safe_load(path.read_text()) if is_yaml else json.loads(path.read_text());d.update(n36r3_reconciled_accounting_exact_b5_review=active,in_flight_executor=active,in_flight_executors=[active],status='N36R3_RECONCILED_ACCOUNTING_EXACT_B5_RUNNING',phase='N36R3_EXACT_B5_RUNNING',next_action=next_action,updated_at=now.isoformat())
  if is_yaml:
   t=path.with_suffix('.tmp');t.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));os.replace(t,path)
  else:write(path,d)
 tp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/idea_tree.json';tree=json.loads(tp.read_text());tree['nodes']['15.6'].update(n36r3_reconciled_accounting_exact_b5_review=active,result='CURRENT_EXACT_B5_REVIEW_RUNNING');write(tp,tree)
summary=dict(prev);summary.update(at=now.isoformat(),turn=1452,live_handles=[h],live_executor_handles=[h],driver=driver,current_controller_status='NO_ACTIVE_GPU_CONTROLLER; CPU_EXACT_B5_REVIEW_RUNNING',completed_work=['Verified bound handoff and authority, driver PID/boot/start identity and STOP/deadline','Reconciled successful prior turn; all three owning ledger prefixes unchanged','Launched one official current-login gpt-6-astra CPU-only independent exact B5 review of source 711602ac and exact current disabled manifests'],next_bounded_step=next_action,review_authority=ref(v/'authority-v1.json'))
write(out/'operational-summary-v1.json',summary);(out/'operational-summary-v1.sha256').write_text(ref(out/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n')
print(json.dumps({'wrapper':h,'next_action':next_action}))
