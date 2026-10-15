import pathlib,json,hashlib,datetime,subprocess,os,time,fcntl,yaml
W=pathlib.Path.cwd();A=W.parent/'autonomy_20261004';T=A/'turns/001579';O=T/'g7-affected-graph-refresh';C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def put(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
def ident(h):
 p=pathlib.Path('/proc')/str(h['pid'])/'stat';o=dict(h)
 if p.exists():
  s=p.read_text().rsplit(')',1)[1].split();o.update(observed_start_ticks=int(s[19]),state=s[0],identity_matches=int(s[19])==h['start_ticks'] and h['boot_id']==pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip());o['live']=o['identity_matches'] and s[0]!='Z'
 else:o.update(live=False,identity_matches=False,state=None)
 return o
old=json.loads((A/'turns/001578/operational-summary-v1.json').read_text());review=json.loads((A/'turns/001578/terminal-review-v1.json').read_text());report=json.loads(pathlib.Path(review['report']['path']).read_text());E=pathlib.Path(report['worktree']);now=datetime.datetime.now(datetime.timezone.utc).isoformat()
assert not os.path.lexists(A/'STOP') and not os.path.lexists(pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/STOP'))
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(old['deadline'].replace('Z','+00:00'))
assert ident(old['driver'])['live'];assert not any(ident(h)['live'] for h in old['prior_cohort_handles'].values());assert not any(ident(h)['live'] for h in old['reviewer_terminal_handles'].values())
for v in old['ledger_prefixes'].values():assert ref(pathlib.Path(v['path']))==v
assert ref(pathlib.Path(review['report']['path']))==review['report']
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=E,text=True).strip()==review['source']
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=E,text=True).strip()
assert not O.exists();O.mkdir()
auth=dict(schema='n36-g7-affected-graph-refresh-authority-v1',at=now,node_id='15.6',source=review['source'],worktree=str(E),standing_authority=ref(A/'user-authorization-v1.json'),accepted_source_review=ref(A/'turns/001578/terminal-review-v1.json'),independent_source_review=review['report'],prior_graph_report=ref(A/'turns/001555/graph-rebinding/report-v1.json'),scope=review['remaining_obligations'][:3],gpu_authorized=False,source_edits_authorized=False,release_enabled=False,timeout_seconds=1200,deadline=old['deadline'])
put(O/'authority-v1.json',auth)
(O/'prompt.txt').write_text(f'''Continue explicitly authorized Arbor node 15.6 as bounded CPU artifact executor. Read {O/'authority-v1.json'}, accepted source review and its exact independent source report. Immutable candidate {E} at {review['source']}. Complete the current next step: refresh only G7-source-affected operational scientific-equivalence proof, source/scientific_source inventories, manifests (all40 audit view and engineering manifest), audit plan, disabled plan and transitive disabled graph roots. Prior accepted graph and reusable helpers: {A/'turns/001555/graph-rebinding'}. Its prior source was dcd890474b733743414d2a7711069bb0d2b0337e, so assess all intervening G7 changes, not only the last repair. Reuse unchanged runtime/runtime-closure/native/controller/scope/accounting/deployment evidence only with explicit compatibility rationale, regenerate content/hash-affected records only. Preserve source, scientific algorithm/configuration/thresholds/cohort rows and all old records/failed tests. No recursive provenance reconstruction or broad test repeats. Execute necessary bounded passive exact-source validators without model/native/provider/GPU execution. Do not bypass audits; report concrete blockers rather than falsify compatibility. Source has G7 conditional lifecycle now; do not restore obsolete unconditional veto assumptions. All prepared roots must stay release_enabled false, b5_review null, no authority grant/adoption. Write NEW files only under {O}; no owner state/tree/ledger writes, no source edits/commits. Produce hash-bound report-v1.json, independent-b5-inputs-v1.json, refreshed root references and explicit changed/reused evidence matrix. Prior B5 does not approve current source; independent B5 is a later coordinator operation. No scientific success claim. Check STOP/deadline before work and before finalization; deadline {old['deadline']}. CPU-only 1200s limit, CUDA_VISIBLE_DEVICES empty. Use only this current-login official gpt-6-astra session; no delegation, alternate accounts/API/Poe, credential access, protected validation/formal results, prohibited untracked 2026-08-10-eds-qd-stage-guidance-transition-design.md or Superpowers. If blocked, preserve partial outputs and exact blocker. Keep focused and complete concrete graph work instead of expanding review scope.''')
(O/'run-executor.py').write_text((A/'turns/001576/independent-g7-r1-review/run-executor.py').read_text())
with (O/'wrapper.log').open('wb') as log:
 p=subprocess.Popen(['/home/hynx/miniconda3/envs/vla-pilot/bin/python',str(O/'run-executor.py')],cwd=E,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
put(O/'wrapper-launch-v1.json',dict(pid=p.pid,at=now))
for _ in range(30):
 if (O/'process-v1.json').exists():break
 time.sleep(.1)
h=json.loads((O/'process-v1.json').read_text());op=dict(status='CPU_AFFECTED_GRAPH_REFRESH_RUNNING',source=review['source'],worktree=str(E),authority=ref(O/'authority-v1.json'),output_directory=str(O),process_record_path=str(O/'process-v1.json'),exit_path=str(O/'exit-v1.json'),wrapper=h['wrapper'],executor=h['executor'],gpu_authorized=False,source_edits_authorized=False,release_enabled=False)
nextstep='Monitor turn001579 G7 affected graph refresh by boot/start identity; reconcile its exact-source passive artifact checks, then obtain independent B5 review before any source adoption or detached GPU release.'
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for path,is_yaml in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  d=yaml.safe_load(path.read_text()) if is_yaml else json.loads(path.read_text());d['n36_engineering_g7_affected_graph_refresh']=op;d['next_action']=nextstep;d['updated_at']=now
  if is_yaml:
   tmp=path.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));tmp.replace(path)
  else:put(path,d)
 tree=json.loads((C/'idea_tree.json').read_text());tree['nodes']['15.6'].update(result='G7_SOURCE_ACCEPTED_AFFECTED_GRAPH_REFRESH_RUNNING',insight='Bounded artifact executor refreshing G7-affected exact-source proof and disabled graph on b8d6b981; prior accepted provenance reused only when compatible. B5 and GPU release remain pending.');put(C/'idea_tree.json',tree)
summary=dict(old);summary.update(at=now,turn=1579,live_handles={k:ident(h[k]) for k in ['wrapper','executor']},driver=ident(old['driver']),executor_authority=ref(O/'authority-v1.json'),completed_work=['Verified handoff/authority hashes, driver identity, inactive prior cohort/reviewer handles and unchanged owning ledger prefixes.','Confirmed current isolated source b8d6b981 and prior accepted G7 source review.','Launched one official gpt-6-astra CPU artifact executor for affected proof/graph refresh; owning state/checkpoint/tree updated.'],next_bounded_step=nextstep,unresolved_evidence=['Affected graph refresh and exact-source independent B5 pending.','No owner adoption, GPU release, scientific promotion or original validation/formal/ablation completion established.']);put(T/'operational-summary-v1.json',summary);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'\n');print(json.dumps(op,indent=2))
