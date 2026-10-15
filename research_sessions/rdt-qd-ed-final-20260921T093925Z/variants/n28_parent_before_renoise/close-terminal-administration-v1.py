import copy, datetime, fcntl, hashlib, json, pathlib, time, yaml
start=time.process_time()
N=pathlib.Path(__file__).resolve().parent
W=N.parent.parent/'study_worktree'
C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(p): return json.loads(p.read_text())
def ref(p): return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def new(p,d):
    with p.open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2);f.write('\n')
def atomic(p,text):
    q=p.with_name(p.name+'.n28-close.tmp')
    with q.open('x') as f:f.write(text)
    q.replace(p)
result=read(N/'result-v1.json'); review=read(N/'root-terminal-review-v1.json')
assert ref(N/'result-v1.json')==review['result']
assert result['decision']==review['decision']=='REJECT_SCREEN'
assert result['audited_cells']==review['audited_cells']==16
assert review['controller_original_process_exited'] is True
assert review['observed_valid_stage_logical_calls']==246 and review['observed_valid_stage_failed_calls']==0
assert review['stage_bindings']==[{'backend':'codex_cli','auth_mode':'chatgpt','model':'gpt-6-astra','calls':246}]
assert not review['poe_allowed'] and not review['protected_authorized']
ledgerpath=pathlib.Path(result['ledger_snapshot']['path'])
assert ref(ledgerpath)==result['ledger_snapshot']
ledger=read(ledgerpath)
assert len(ledger)==48
# Keep all historical operational material before correcting stale current pointers.
out=N/'terminal-admin-v1';out.mkdir(exist_ok=False)
lock=(W/'data/qd-ed-runner.lock').open('a')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
sp=W/'research-state.yaml';cp=C/'checkpoint.json';tp=C/'idea_tree.json';cfgp=W/'research_config.yaml'
s=yaml.safe_load(sp.read_text());c=read(cp);t=read(tp);cfg=yaml.safe_load(cfgp.read_text())
assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
budget=copy.deepcopy(s['budget'])
assert budget['dispatched']==371 and budget['running']==0
assert abs(budget['gpu_hours_consumed']-49.99373352883483)<1e-8
beforekeys=['study','budget','current_iteration','active_iteration','active_plan','next_action','prospective_iteration','current_owned_workers','worktree','canonical_worktree']
new(out/'state-selected-before-v1.json',{k:s.get(k) for k in beforekeys})
new(out/'checkpoint-before-v1.json',c)
new(out/'tree-before-v1.json',t)
new(out/'config-task-before-v1.json',{'task':cfg.get('task')})
summary={'candidate_id':'N28','cohort_id':result['cohort_id'],'status':'CLOSED_REJECT_SCREEN','scientific_decision':'REJECT_SCREEN','source_commit':result['source_commit'],'counts':result['counts'],'result':ref(N/'result-v1.json'),'root_review':ref(N/'root-terminal-review-v1.json'),'closed_at':now,'target_achieved':False,'execution_authorized':False,'validation_authorized':False,'formal_authorized':False}
status='N28_REJECTED_LINKAGE_REVIEW_COMPLETE_TARGET_NOT_MET'
next_action='Closed CPU linkage audit accepted with disclosed field-output deviation; identify a distinct falsifiable next hypothesis from existing evidence. No GPU dispatch or protected phase released.'
s['closed_candidates']['N28']=summary
s['study']['status']=status
s['current_iteration'].update(summary)
s['active_iteration']=None;s['active_plan']=None
s['last_completed_iteration']=result['cohort_id'];s['last_completed_plan']=review['plan']
s['next_action']=next_action;s['current_owned_workers']=[]
s['prospective_iteration'].update({'status':'CLOSED_REJECT_SCREEN','gpu_execution_authorized':False})
s['current_cpu_task']={'status':'CLOSED_ACCEPTED_WITH_DISCLOSED_DEVIATION','agent':'/root/n22_cpu_executor','scope':ref(N/'closed-linkage-availability-cpu-scope-v1.md'),'release':ref(N/'closed-linkage-availability-cpu-release-v1.json'),'review':ref(N/'root-closed-linkage-review-v1.json')}
s['updated_at']=now
assert s['budget']==budget
c['n28_closed_controller']=copy.deepcopy(c.get('active_controller'))
c.update({'status':status,'updated_at':now,'active_node':'12.2','active_controller':None,'execution_tool_session':None,'automatic_gpu_dispatch_authorized':False,'automatic_gpu_dispatch_scope':None,'owned_gpu_workers':[],'pending_human_gate':None,'next_action':next_action,'plan':None,'status_path':str(N/'execution/supervisor-status-v1.json'),'source_commit':result['source_commit'],'n28_terminal_review':ref(N/'root-terminal-review-v1.json'),'n28_result':ref(N/'result-v1.json'),'latest_closed_provider_audit':ref(N/'root-terminal-review-v1.json')})
for k in ['achieved','goal_achieved','target_achieved','target_met']:c[k]=False
# Reconcile the pre-dispatch cumulative snapshot with all 16 original journal events.
snapshot=copy.deepcopy(c['budget_snapshot'])
assert snapshot['dispatched']==355
for x in ledger:
    if x['event']=='dispatched':snapshot['by_bucket'][x['budget_bucket']]+=1
    if x['event']=='valid':snapshot['gpu_hours_by_bucket'][x['budget_bucket']]+=x['gpu_process_wall_seconds']/3600
for k in ['dispatched','aborted','valid','invalid','completed','running','gpu_hours_consumed']:snapshot[k]=budget[k]
snapshot['reserved_attempts']+=16
assert snapshot['by_bucket']=={'baseline':66,'development':232,'validation':60,'formal':0,'recovery':13}
assert abs(sum(snapshot['gpu_hours_by_bucket'].values())-budget['gpu_hours_consumed'])<1e-8
c['budget_snapshot']=snapshot
c['in_flight_executor']=None;c['in_flight_executors']=[]
c['n28_closed_linkage_review']=ref(N/'root-closed-linkage-review-v1.json')
c['executor_task']=next_action
c['n28_progress']={'completed_cells':16,'counts':result['counts'],'stage_logical_calls':246,'stage_failed_calls':0,'closed':True,'active_attempts':[]}
t['meta'].update({'study_status':status,'target_achieved':False,'automatic_dispatch_authorized':False,'best_effective_candidate':None})
t['meta']['resource_checkpoint']={'timestamp':now,'status':status,'owned_gpu_workers':[],'current_root_adopted_attempt_cap':538,'last_explicit_user_numeric_attempt_cap':395,'gpu_hours_cap':100,'budget_snapshot':snapshot,'authority':s['current_iteration']['budget_authority'],'authority_interpretation':'Finite root adoption under subsequent autonomy delegation; not a separate user approval of 538.'}
t['nodes']['12.1'].update({'status':'pruned','scientific_decision':'REJECT_SCREEN','result':summary['result'],'review':summary['root_review'],'counts':result['counts'],'insight':'All 16 valid. N28 0/4 versus C0 0/4, Q0 0/4 and fresh N27 1/4. Native arithmetic and placement active; task benefit not established. Historical N27 0/4 rejection remains unchanged.'})
if '12.2' not in t['nodes']['12']['children_ids']:t['nodes']['12']['children_ids'].append('12.2')
t['nodes']['12.2']={'id':'12.2','parent_id':'12','children_ids':[],'depth':2,'status':'done','kind':'closed_metadata_diagnostic','hypothesis':'Which existing identity links connect parent mutation to selected executable prefix, and which numerical/causal links remain unobserved?','scope':s['current_cpu_task']['scope'],'release':s['current_cpu_task']['release'],'review':s['current_cpu_task']['review'],'insight':'All four first-guided identity chains join; numerical preservation and causal task effects remain unknown. Field-output scope deviation disclosed; no tensor reads.','gpu_execution_authorized':False}
cfg['task']='Continue original RDT/QD/ED target: N28 valid screen rejected; closed CPU linkage audit reviewed. Identify a distinct justified next hypothesis. Current Codex login only; no new GPU release.'
body=f"""# N28 terminal conclusion

Closed {now}; original research target remains **TARGET_NOT_MET**.

All 16 frozen task-major Dev cells are valid; no retries, invalid attempts or unrun cells.

| Task | C0 | Q0 | N27 | N28 |
|---|---|---|---|---|
| 0 | Fail | Fail | Fail | Fail |
| 1 | Fail | Fail | Fail | Fail |
| 2 | Fail | Fail | Success | Fail |
| 3 | Fail | Fail | Fail | Fail |
| Total | 0/4 | 0/4 | 1/4 | 0/4 |

Decision: **REJECT_SCREEN**. N28 has no paired gain over C0/Q0, and 0 gains / 1 loss versus fresh N27. Four tasks do not establish a statistically reliable ranking. This N27 control result does not rewrite its earlier 0/4 cohort.

N28 moved selected-parent feasible EEF mutation before the original renoise/denoise operation. Original same-worker CUDA audits establish active arithmetic and the observed entry binding: 115 guided decisions, 1,150 parent rounds, 1,610 call summaries, 44 witness calls and 40 parent boundaries. Root independently reconciled metadata, journals, 383 source files, 64 evidence references and process exits without replaying tensors. Ancestry and operator activity do not establish numerical transport through denoising, action-level causal effect or task benefit. N28 has 14 RBF calls per guided decision versus N27's 19, and actual guided counts differ 115 versus 28; equal total compute is not claimed.

All **246 logical online Stage calls succeeded through codex_cli / chatgpt / gpt-6-astra**, using the current managed Codex login. Poe and alternate-account fallback are disabled; saved Poe credentials are preserved. Observed tokens: 2,655,707 input, including 1,273,088 cached input, and 14,114 output. Internal HTTP request/retry counts are unknown.

Episode GPU process time: 6,749.600166862132 seconds. Separate native proof: 14.794140067999251 seconds. Combined local cost: 1.878998418591703 GPU hours. Cumulative ledger: 371 attempts and 49.99373352883483 GPU hours, no running GPU worker. Cumulative cap 538 attempts is a finite root adoption under later autonomy delegation, not a separately user-approved numeric amendment; last explicit numeric approval was 395 attempts / 100 GPU hours. The 100-hour ceiling and protected reserves remain unchanged.

Baseline/development primary slots are currently exhausted (66/66 and 232/232); protected validation/formal and recovery reserves are not a new development allocation. No further GPU dispatch is released. A bounded CPU-only metadata audit of all four N28 first-guided segments has identified existing links and missing observations. It cannot nominate a successful algorithm or claim causal transport by itself.

The CPU linkage audit is now closed and independently reviewed: all four first-guided identity chains are joinable; tensor contents were not read. Numerical preservation and causal action effects remain unknown. A disclosed schema-inspection output included audit numeric vectors outside the intended identity-only field scope; they were not used for quantitative conclusions or sample selection. The original scope and deviation are retained. This does not justify a new algorithm by itself.

Evidence: [result](result-v1.json), [independent terminal review](root-terminal-review-v1.json), [frozen plan](plan.frozen.v1.gpu7.json), [CPU scope](closed-linkage-availability-cpu-scope-v1.md), [CPU review](root-closed-linkage-review-v1.json).
"""
with (N/'terminal-conclusion-v1.md').open('x') as f:f.write(body)
entry=f"""
## {now} — N28 terminal: valid rejection, target unmet

16/16 valid; C0 0/4, Q0 0/4, N27 1/4 (task2), N28 0/4. REJECT_SCREEN; no protected-phase promotion. Native operator activity is verified, task benefit and causal transport are not. 246/246 online Stage calls used current Codex login; no Poe/fallback. Local GPU cost 1.878998418591703 h; cumulative 371 attempts / 49.99373352883483 h. CPU-only closed linkage audit is complete and root-reviewed, with a disclosed field-output deviation. Full conclusion: {N/'terminal-conclusion-v1.md'}; independent review: {N/'root-terminal-review-v1.json'}.
"""
paths=[W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md']
# Operational documents must not be source-manifest-bound.
manifest=read(N/'source-manifest-execution-v1.json')
for p in paths+[sp,cp,tp,cfgp]:
    assert str(p.relative_to(W)) not in json.dumps(manifest['files'])
atomic(sp,yaml.safe_dump(s,sort_keys=False,allow_unicode=True))
atomic(cp,json.dumps(c,ensure_ascii=False,indent=2)+'\n')
atomic(tp,json.dumps(t,ensure_ascii=False,indent=2)+'\n')
atomic(cfgp,yaml.safe_dump(cfg,sort_keys=False,allow_unicode=True))
for p in paths:
    old=p.read_text();(out/(p.name+'.before')).write_text(old)
    atomic(p,old+entry)
mp=C/'idea_tree.md'
old=mp.read_text();(out/'idea_tree.md.before').write_text(old)
atomic(mp,f"# Current status — {now}\n\nN28 node 12.1 is pruned: C0 0/4, Q0 0/4, N27 1/4, N28 0/4, all16 valid. Node12.2 is the completed CPU-only closed-linkage audit. No active GPU controller. Target unmet. The JSON tree is authoritative.\n\nHistorical render below is retained verbatim; its RUNNING labels are historical.\n\n---\n\n"+old)
new(out/'completion-v1.json',{'schema':'n28-terminal-admin-closure-v1','at':now,'result':summary['result'],'review':summary['root_review'],'conclusion':ref(N/'terminal-conclusion-v1.md'),'budget_unchanged':budget==yaml.safe_load(sp.read_text())['budget'],'frozen_source_unchanged':True,'no_new_gpu_dispatch':True,'target_achieved':False,'cpu_seconds':time.process_time()-start,'operational_after':[ref(p) for p in [sp,cp,tp,cfgp,*paths,mp]]})
print(json.dumps({'status':status,'budget_unchanged':True,'conclusion':str(N/'terminal-conclusion-v1.md'),'cpu_seconds':time.process_time()-start}))

