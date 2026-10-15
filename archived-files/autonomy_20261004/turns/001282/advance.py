import json,pathlib,hashlib,datetime,subprocess,fcntl,os
owner=pathlib.Path.cwd();root=owner.parent/'autonomy_20261004';turn=root/'turns/001282';prev=root/'turns/001281/independent-review';out=turn/'final-source-refresh';out.mkdir(exist_ok=True)
cp=owner/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
def ref(p):
 p=pathlib.Path(p);b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def write(p,d):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
def handle(pid):
 s=pathlib.Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1].split();return {'pid':pid,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':int(s[19]),'state':s[0]}
report=json.loads((prev/'report-v1.json').read_text());ex=json.loads((prev/'executor-exit-v1.json').read_text());assert ex['exit']==0
for pid in (669796,669797):assert not pathlib.Path(f'/proc/{pid}').exists()
for k in ['authority','preparation_report','prior_root_disposition','check_script','check_results','markdown']:
 r=report[k];assert ref(r['path'])['sha256']==r['sha256'],k
assert report['source_commit']=='30c6321715df86c5bab623db607bab2811aed56d'
a=json.loads((prev/'authority-v1.json').read_text());work=pathlib.Path(a['worktree'])
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=work,text=True).strip()==report['source_commit']
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=work,text=True).strip()
for p in a['STOP_paths']:assert not os.path.lexists(p)
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(a['deadline'].replace('Z','+00:00'))
old=json.loads((root/'turns/001280/terminal-reconciliation-v1.json').read_text())
for r in old['ledger_prefixes'].values():assert ref(r['path'])['sha256']==r['sha256']
rec={'schema':'n36r2-b5-root-reconciliation-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'report':ref(prev/'report-v1.json'),'exit':ref(prev/'executor-exit-v1.json'),'status':'CPU_PREPARATION_ACCEPTED_FINAL_SOURCE_REFRESH_REQUIRED','source_commit':report['source_commit'],'owner_source':report['owner_source'],'ledger_prefixes':old['ledger_prefixes'],'handles_absent':[669796,669797],'source_adopted':False,'gpu_authorized':False,'release_enabled':False,'target_met':False,'remaining_prerequisites':report['remaining_release_prerequisites']}
write(turn/'root-review-reconciliation-v1.json',rec)
a.update(schema='n36r2-final-source-refresh-authority-v1',at=rec['at'],output_directory=str(out),scope='Bounded CPU final-source binding refresh only; source frozen at30c63217; no adoption or release',root_acceptance=ref(turn/'root-review-reconciliation-v1.json'),review_report=ref(prev/'report-v1.json'),allowed=['Read exact preparation and accepted review inputs; write refreshed disabled bindings only under output_directory. Read isolated frozen source; no source edits.','Refresh only source-dependent manifests/runtime/closure/controller references/plan/contexts for all40 unchanged scientific identities. Reuse unchanged valid native/checkpoint evidence.','At most120 seconds focused CPU checks with2 threads; produce report-v1.json and report-v1.md with hashes, changed dependency graph and concrete remaining gates.'],deliverables=report['minimal_refresh_prerequisites'][:3],source_edits_authorized=False,scientific_edits_authorized=False)
a['forbidden'].append('Do not mint an independent B5 review or root production token; no child agents. Do not recursively rebuild provenance or rerun broad tests. If source defect is established, report exact blocker instead of modifying frozen source.')
write(out/'authority-v1.json',a)
prompt=f'''You are the bounded Arbor executor for existing node15.6 in the continuing authorized owning study, not a coordinator. Read and obey {out/'authority-v1.json'} and its exact accepted review {prev/'report-v1.json'}. Prior reviewer is terminal exit0; root accepted CPU preparation only. Your single task is final-source binding refresh as the three minimal_refresh_prerequisites in that report, freezing isolated HEAD30c6321715df86c5bab623db607bab2811aed56d. Complete this concrete package in output_directory, preserving original all40 scientific identities/configuration and all past costs. Source edits, GPU/Main/simulator/healthcheck/provider/network/package operations, owner state/ledger writes, protected validation/formal results, credentials/Poe and prohibited untracked design are forbidden. Do not activate release or mint independent/root review tokens. The disabled plan/contexts must remain disabled and final-source-consistent. Native build and checkpoint evidence can be reused if unchanged; runtime import-search evidence must correspond to the new isolation policy. No recursion through old provenance and no unnecessary broad test repeats. Bound CPU checks to120s/2threads, whole task900s. Produce report-v1.json and report-v1.md (score:null, target_met:false, release_enabled:false) with exact source/protocol/config/runtime/closure/manifest bindings and evidence for external final-source review. Future actual-worker before/after receipts are not a predispatch prerequisite and must never be fabricated. No child agents. Do not ask routine authorization questions. Owner source remains {report['owner_source']}; standalone official current-login Codex/gpt-6-astra only. Stop new work on either STOP alias or deadline. Preserve source clean. If concrete blocker prevents refresh, record it precisely. The next coordinator will handle external review, adoption and readiness/release in order.'''
(out/'executor-prompt-v1.txt').write_text(prompt+'\n')
launcher=(prev/'executor-launch-v1.py').read_text().replace('n36r2-b5-independent-review-process-v1','n36r2-final-source-refresh-process-v1');(out/'executor-launch-v1.py').write_text(launcher)
with open(owner/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 d=json.loads(cp.read_text());d['n36r2_b5_review']['status']=rec['status'];d['n36r2_b5_review']['terminal_reconciliation']=ref(turn/'root-review-reconciliation-v1.json');d['n36r2_b5_review']['report']=ref(prev/'report-v1.json');d['n36r2_b5_review']['historical_handles']=d['n36r2_b5_review'].pop('handles',{});d['n36r2_b5_review']['live_handles']=[]
 d['n36r2_final_source_refresh']={'status':'CPU_PREPARED_FOR_LAUNCH','authority':ref(out/'authority-v1.json'),'worktree':str(work),'output_directory':str(out),'gpu_authorized':False};d['next_action']='Monitor turn001282 bounded final-source refresh executor; no duplicate, source adoption or GPU release. On terminal exit reconcile package then obtain external final-source review.';d['updated_at']=rec['at'];write(cp,d)
with open(out/'wrapper.log','ab') as log:
 p=subprocess.Popen(['python',str(out/'executor-launch-v1.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,cwd=work)
write(out/'wrapper-launch-v1.json',{'wrapper':handle(p.pid),'authority':ref(out/'authority-v1.json'),'gpu_authorized':False});print(json.dumps({'wrapper':handle(p.pid),'output':str(out)}))
