import pathlib,json,hashlib,datetime,subprocess,fcntl,os,yaml
owner=pathlib.Path.cwd(); root=owner.parent/'autonomy_20261004'; turn=root/'turns/001284'; prev=root/'turns/001282/final-source-refresh'; out=turn/'independent-final-review';out.mkdir(exist_ok=True)
cp=owner/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
def ref(p):
 p=pathlib.Path(p);b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def write(p,d):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
def handle(pid):
 p=pathlib.Path(f'/proc/{pid}/stat')
 if not p.exists():return {'pid':pid,'absent':True}
 s=p.read_text().split(') ',1)[1].split();return dict(pid=pid,boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(s[19]),state=s[0])
def verify(d):
 n=0
 if isinstance(d,dict):
  if isinstance(d.get('path'),str) and 'sha256' in d:
   assert ref(d['path'])['sha256']==d['sha256'],d['path'];n+=1
  else:
   for v in d.values():n+=verify(v)
 elif isinstance(d,list):
  for v in d:n+=verify(v)
 return n
r=json.loads((prev/'report-v1.json').read_text());a=json.loads((prev/'authority-v1.json').read_text());e=json.loads((prev/'executor-exit-v1.json').read_text());assert e['exit']==0
assert all(handle(p).get('absent') for p in [678637,678638,391755])
assert handle(268073)['start_ticks']==97715947
assert handle(687906)['start_ticks']==146811582
assert not any(os.path.lexists(p) for p in a['STOP_paths'])
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(a['deadline'].replace('Z','+00:00'))
work=pathlib.Path(a['worktree']);assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=work,text=True).strip()==r['source_commit']
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=work,text=True).strip()
old=json.loads((root/'turns/001280/terminal-reconciliation-v1.json').read_text());verify(old['ledger_prefixes']);n=verify(r)
status=json.loads((root/'turns/001235/controller-status-v1.json').read_text())
rec=dict(schema='n36r2-final-refresh-terminal-reconciliation-v1',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),turn=1284,status='CPU_TERMINAL_RECONCILED_EXTERNAL_FINAL_REVIEW_PENDING',report=ref(prev/'report-v1.json'),exit=ref(prev/'executor-exit-v1.json'),source_commit=r['source_commit'],owner_source=r['owner_source'],handles_absent=[678637,678638,391755],driver=handle(268073),coordinator=handle(687906),controller_status=status,verified_report_references=n,ledger_prefixes=old['ledger_prefixes'],retained_attempts=504,retained_gpu_hours=75.49265038509455,gpu_dispatch=False,source_adopted=False,release_enabled=False,target_met=False)
write(turn/'entry-reconciliation-v1.json',rec);write(turn/'terminal-reconciliation-v1.json',rec)
a.update(schema='n36r2-independent-final-review-authority-v1',at=rec['at'],output_directory=str(out),scope='Independent CPU review of exact refreshed final-source package; no mutation/adoption/release',refresh_report=ref(prev/'report-v1.json'),terminal_reconciliation=ref(turn/'terminal-reconciliation-v1.json'),allowed=['Read exact refreshed package and prior accepted review; verify source/runtime/closure/manifest/context/protocol/accounting consistency and all40 scientific identities without changing artifacts.','Write independent report-v1.json and report-v1.md only in output_directory. At most120s focused CPU checks, two threads; reuse accepted evidence if inputs unchanged.'],deliverables=['Independent verdict on exact final source and bindings; concrete blockers or acceptance scoped to CPU predispatch package. Bind reviewed inputs by hashes.','Distinguish remaining owner adoption/readiness/final-plan/root-review/detached-release from future actual-worker evidence. Do not require future worker receipts before launch, and do not waive their postlaunch acceptance checks.'])
a['forbidden'].append('No modifications to reviewed files, no implementation, no root/production approval tokens or execution release. Review is independent evidence only.')
write(out/'authority-v1.json',a)
prompt=f'''You are the independent Arbor reviewer for existing node15.6, not the coordinator or implementer. Read {out/'authority-v1.json'} and exact refreshed report {prev/'report-v1.json'}; earlier accepted independent review is bound there. Review the final source30c6321715df86c5bab623db607bab2811aed56d and its refreshed disabled package. Verify all40 identity/config/source/runtime/closure/manifest/context joins, unchanged scientific semantics, private accounting/routing, and acyclic prospective approval chain. Do not recursively rebuild accepted provenance or repeat broad tests. CPU bootstrap evidence is not actual-worker evidence; future receipts must remain required for acceptance, not as impossible predispatch prerequisites. Report concrete blockers if any; otherwise explicitly accept only the final-source CPU package and enumerate exact remaining adoption/readiness/final-plan/root-review/release steps. Hash-bind reviewed input artifacts, source, plan, protocol and accounting in report-v1.json and report-v1.md. Do not mint production tokens. Score null,target_met false,release_enabled false. No source/artifact mutations outside output_directory, GPU, simulator, Main, healthcheck, provider probe, network, installation, credentials, protected validation/formal results, prohibited design, Superpowers, owner state or ledgers. No child agents. Whole task900s, focused CPU checks120s/two threads. Official current-login Codex gpt-6-astra only. Stop on STOP/deadline. Do not ask routine approvals.'''
(out/'executor-prompt-v1.txt').write_text(prompt+'\n')
launcher=(root/'turns/001281/independent-review/executor-launch-v1.py').read_text().replace('n36r2-b5-independent-review-process-v1','n36r2-independent-final-review-process-v1');(out/'executor-launch-v1.py').write_text(launcher)
with open(owner/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX);verify(old['ledger_prefixes'])
 d=json.loads(cp.read_text());s=yaml.safe_load((owner/'research-state.yaml').read_text())
 for x in [d,s]:
  item=x.setdefault('n36r2_final_source_refresh',dict(d['n36r2_final_source_refresh']));item['status']=rec['status'];item['terminal_reconciliation']=ref(turn/'terminal-reconciliation-v1.json');item['report']=ref(prev/'report-v1.json');item['historical_handles']=item.pop('handles',{});item['live_handles']=[]
  x['n36r2_independent_final_review']={'status':'CPU_PREPARED_FOR_LAUNCH','authority':ref(out/'authority-v1.json'),'worktree':str(work),'output_directory':str(out),'gpu_authorized':False}
  x['next_action']='Monitor turn001284 independent final-source review; on terminal reconcile exact verdict, then owner adoption and bounded readiness/final-plan/release only if gates pass. No duplicate or GPU dispatch during review.'
  x['updated_at']=rec['at']
 write(cp,d)
 t=owner/'research-state.yaml.tmp';t.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));t.replace(owner/'research-state.yaml')
with open(out/'wrapper.log','ab') as log:
 p=subprocess.Popen(['python',str(out/'executor-launch-v1.py')],cwd=work,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
write(out/'wrapper-launch-v1.json',{'wrapper':handle(p.pid),'authority':ref(out/'authority-v1.json'),'gpu_authorized':False})
print(json.dumps({'wrapper':handle(p.pid),'verified_references':n,'output':str(out)}))
