import json,pathlib,hashlib,datetime,decimal,fcntl,copy,subprocess,yaml
w=pathlib.Path.cwd(); a=w.parent/'autonomy_20261004'; o=(a/'turns/001151').resolve(); v=(a/'turns/001147/protocol-preparation').resolve()
def read(p):return json.loads(p.read_text())
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 q=p.with_name(p.name+'.tmp');q.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n');q.replace(p)
def verify(r):
 b=pathlib.Path(r['path']).read_bytes();assert hashlib.sha256(b).hexdigest()==r['sha256'],r['path']
 if 'bytes' in r:assert len(b)==r['bytes']
now=datetime.datetime.now(datetime.timezone.utc); deadline=datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00');assert now<deadline and not (a/'STOP').exists()
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert source=='52a87af0bf11f95b21ce17aba456dc98944d9774'
p=read(v/'protocol-v1.json');acct=read(v/'prospective-accounting-v1.json');report=read(v/'report-v1.json')
for r in report['outputs']:verify(r)
for r in acct['ledger_prefixes'].values():verify(r)
for key in ['authority','registered_ideation','accepted_feasibility','accepted_selection_review','prior_protocol','completion_contract','seed_plan']:verify(p[key])
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(); ds=read(a/'driver-status.json')
for h in [ds['driver'],ds['process']]:
 z=pathlib.Path(f"/proc/{h['pid']}/stat").read_text().rsplit(')',1)[1].split(); assert boot==h['boot_id'] and int(z[19])==h['start_ticks'] and z[0]!='Z'
for pid in [4063036,4063037,2632351]:assert not pathlib.Path(f'/proc/{pid}').exists()
assert read(a/'turns/001150/receipt.json')['exit']==0
assert len(p['episodes'])==40 and len({e['episode_key'] for e in p['episodes']})==40
old=read(pathlib.Path(p['prior_protocol']['path']))
for i,e in enumerate(p['episodes']):
 assert e['task_id']==i//4 and e['profile']==['C0','Q0','N34','N36'][i%4] and e['split']=='dev' and e['init_index']==0
 prior=next(x for x in old['episodes'] if x['task_id']==e['task_id'])
 for key in ['env_seed','policy_seed','init_index','init_row_sha256','init_file_sha256','bddl_sha256']:assert e[key]==prior[key]
assert 40*1840+1800+200==75600==21*3600
for row in acct['bucket_arithmetic']:
 assert row['retained']+row['proposed_addition']==row['after_max']<=row['cap']
assert sum(r['after_max'] for r in acct['bucket_arithmetic'])==542
D=decimal.Decimal
cap=D('53.08404692669838')+D(168); charge=D('75.24379311215873')+D('0.23357169027962');reserve=D(32)-D('7.7591759975691845')+D(12)
next_action='Dispatch one bounded CPU implementation executor in an isolated N36 variant worktree from source52a87af0bf11f95b21ce17aba456dc98944d9774, using this reviewed protocol. Implement independent nonprogress memory/path plus complete native audit/controller negatives; then independent source review and prospective source/runtime/accounting release. No GPU dispatch or protected access until those gates pass.'
r={'schema':'n36-root-protocol-accounting-review-v1','at':now.isoformat(),'node_id':'15.6','status':'PASS_PROTOCOL_DESIGN_FOR_ISOLATED_CPU_IMPLEMENTATION_ONLY','reviewer':'Current root coordinator; independent of completed protocol-drafting executor. No second-agent review claimed.','source':source,'protocol':ref(v/'protocol-v1.json'),'accounting_draft':ref(v/'prospective-accounting-v1.json'),'draft_report':ref(v/'report-v1.json'),'terminal_reconciliation':ref(a/'turns/001150/protocol-terminal-reconciliation-v1.json'),'authority':ref(a/'user-authorization-v1.json'),'ledger_prefixes':acct['ledger_prefixes'],'checks':{'direct_bound_references':'PASS','fresh_unique_task_major_episode_identities':'PASS_40_CELLS_DEV_ONLY','same_matched_seeds_bddl_init_rows':'PASS_AGAINST_PREVIOUS_DEV_PROTOCOL','attempt_bucket_arithmetic':'PASS_502_PLUS_40_EQUALS_542','gpu_seconds':'PASS_40_TIMES_1840_PLUS_1800_PLUS_200_EQUALS_75600','source_head':'UNCHANGED','controller_and_drafting_handles':'ABSENT','driver_and_current_coordinator_boot_start':'MATCH','STOP':'ABSENT'},'scientific_decisions':[
'Accept the once-per-adjacent-decision eligibility latch across ten ordinary offspring updates. Registered proposal inherits N34 insertion schedule; source ObservedJawDecision.prepare binds each actual current archive best. This is a prospective lifecycle decision, not evidence that first-insertion CPU plausibility survives later competition. Do not replay later historical offspring or force a direct competitor/selection.',
'Accept fresh C0/Q0/N34/N36 task-major design and N36>=N34 path-removal comparator in addition to original complete10, >=5, >=C0 and >=Q0. This stricter local gate does not replace required final QD/ED ablations or protected validation/formal gates.',
'Futility is sound only at complete valid quadruples: remaining N36 maximum below5 or any already observed comparator total makes final gate impossible. Invalid/missing mandatory audit stops admission; unrun outcomes remain Unknown.',
'Accept independent N36 memory with N35 disabled, exact occurrence rather than byte-alias origin, full8 acknowledgement, identity continuity, fixed-order binary64 dot predicate and one-decision expiry. Inside-box close remains unchanged; inactive fallback remains N34.',
'Accept deterministic tangent path, current observed geometry, native once-cast encoding, other15/remainder preservation and unchanged scoring/archive/176 evaluations/11 batches. Clipping breaks nominal endpoint cancellation; no collision avoidance or contact inference is licensed.',
'All-round native evidence must establish actual loaded code/build, arithmetic, origin, archive, decode, commit, acknowledgements and physical response. CPU scan model and first-insertion results cannot substitute. Auditor negatives must independently reject corrupted/missing required telemetry; producer PASS flags alone are insufficient.'
],'accounting_review':{'caps_adopted':False,'reservation_adopted':False,'exact_decimal_effective_cap':str(cap),'exact_decimal_conservative_charge':str(charge),'exact_decimal_protected_remaining':str(reserve),'exact_decimal_unprotected_after_21h':str(cap-charge-D(21)-reserve),'float_serialization_note':'Draft binary64 effective cap 221.08404692669836 differs by roundoff from source decimal221.08404692669838. Later adoption must use the authority decimal string, preserving current exact cap; not a budget extension.','wall_hours_remaining':(deadline-now).total_seconds()/3600,'wall_feasibility':'21h worst-case occupancy fits current window, but implementation/review/release and idle wait still consume time. Recompute at release and each admission; no guarantee of all40 completion.','healthchecks':'41 is invocation upper bound;1800s aggregate reservation overrides41*60, including cleanup. No retries or disguised episode probes.','historical_n31_deadline_unchanged':'2026-10-10T17:42:00Z'},'limitations':['No deployed N36 implementation or native audit yet.','First-insertion-only overlapping selected Dev windows; final selection and physical benefit Unknown.','No cumulative budget amendment, GPU release, protected access, scientific promotion or goal completion.'],'next_action':next_action,'gpu_authorized':False,'target_met':False}
write(o/'protocol-root-review-v1.json',r)
with open(w/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 sp=w/'research-state.yaml';cp=w/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json'
 s=yaml.safe_load(sp.read_text());c=read(cp);t=read(tp)
 assert s['active_controller'] is None and c['active_controller'] is None and not s.get('current_owned_workers')
 assert s['n36_protocol_preparation']['handles']['executor']['pid']==4063037
 for r0 in acct['ledger_prefixes'].values():verify(r0)
 assert s['budget_snapshot']==acct['retained_snapshot']
 for f in [sp,cp,tp]:(o/(f.name+'.before-review')).write_bytes(f.read_bytes())
 rec=copy.deepcopy(s['n36_protocol_preparation']);rec.update(status='CPU_PROTOCOL_DRAFT_COMPLETED_REVIEWED',executor_exited=True,live_handles=[],report=ref(v/'report-v1.json'),exit=ref(v/'executor-exit-v1.json'),root_review=ref(o/'protocol-root-review-v1.json'))
 for obj in [s,c]:
  obj.update(n36_protocol_preparation=rec,n36_protocol_root_review=ref(o/'protocol-root-review-v1.json'),in_flight_executor=None,phase='N36_PROTOCOL_REVIEWED_CPU_IMPLEMENTATION_NEXT',next_action=next_action,updated_at=now.isoformat())
 c['inflight_executor']=None
 t['nodes']['15.6'].update(status='pending',result='PROTOCOL_REVIEWED_NO_GPU_RELEASE',protocol_preparation=rec,protocol_root_review=ref(o/'protocol-root-review-v1.json'))
 q=sp.with_suffix('.tmp');q.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));q.replace(sp);write(cp,c);write(tp,t)
summary={'schema':'autonomy-bounded-operation-summary-v1','at':now.isoformat(),'source':source,'driver':ds['driver'],'coordinator':ds['process'],'live_research_handles':[],'active_controller':None,'completed':'Reconciled drafting executor exit and previous successful turn; independently reviewed protocol/accounting, verified40 matched identities, bounds and ledger prefixes; recorded design acceptance and cleared stale in-flight drafting state under owning lock.','review':ref(o/'protocol-root-review-v1.json'),'ledger_prefixes':acct['ledger_prefixes'],'retained_attempts':502,'retained_gpu_hours':75.24379311215873,'next_action':next_action,'unresolved':r['limitations']+['Fresh Dev, validation/formal and required ablation evidence remain outstanding.'],'target_met':False,'new_gpu_dispatches':0,'stop_present':False,'deadline':deadline.isoformat()}
write(o/'operational-summary.json',summary)
(o/'operational-summary.md').write_text(f"# Turn1151 operational summary\n\nSource `{source}` unchanged. Driver268073/start97715947 and current coordinator4078358/start144573474 verified on boot{boot}. Drafting wrapper4063036/executor4063037 and N35 controller2632351 absent. No live research worker; STOP absent; deadline2026-10-11T11:13:13Z.\n\nCompleted independent root review of completed N36 draft: all40 identities, scientific gates, ten-update latch versus first-insertion-only evidence, native audits and budget arithmetic. Protocol design accepted for isolated CPU implementation only. Hash-bound review: protocol-root-review-v1.json. Stale drafting handles closed in owning state/checkpoint/tree under state lock. No code, budget, ledger, GPU or scientific threshold change. Retained502 attempts/75.24379311215873 GPUh; attempt ledger7513934 bytes/SHA256 aff9bf3e50b5d82b06cbb54f067746e3eeb6c27e499235519b903f42957ac368.\n\nNext: {next_action}\n\nUnresolved: implementation/source/runtime/native audit review, fresh Dev outcomes, validation/formal/required ablation evidence. Goal remains unmet.\n")
print(json.dumps({'review':ref(o/'protocol-root-review-v1.json'),'summary':ref(o/'operational-summary.json'),'phase':s['phase']}))
