"""Accept completed bounded archive pool screen; release no further calculation."""
from pathlib import Path
import copy,datetime,hashlib,importlib.util,json,os,sys,yaml
V=Path(__file__).resolve().parent;Q=V.parent;P=Q.parent;W=P.parents[1]/'study_worktree'
def raw(p):
 p=Path(p);assert p.suffix not in {'.pt','.mp4','.png','.jpg'}
 return p.read_bytes()
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(raw(p)).hexdigest()}
def check(x):
 b=raw(x['path']);assert hashlib.sha256(b).hexdigest()==x['sha256']
 if 'bytes' in x:assert len(b)==x['bytes']
out=V/'output-manifest-v2.json';assert ref(out)['sha256']=='d2bb9510b70bf5b914bbd3b9905a787b226db975e87c4d0a1017eb6cdc917c67'
m=json.loads(raw(out))
for x in m['files']:check(x)
for k in ['original_input_manifest','prior_failure_delivery','prior_failure_resource']:check(m[k])
res=json.loads(raw(V/'resource-v1.json'));ext=json.loads(raw(V/'external-execution-v2.json'));data=json.loads(raw(V/'result-v1.json'));cl=json.loads(raw(V/'closure-v2.json'))
assert res['complete'] and res['error'] is None and ext['exit_code']==0 and ext['wait_reaped']
assert res['pid']==ext['pid']==3940543 and not (Path('/proc')/str(res['pid'])).exists()
assert not (Path('/proc')/'3922644').exists()
assert res['completed_episodes']==2 and res['combined_encoded_bytes']==36274537
reads=[x for x in res['reads'] if x['kind']=='payload']
assert len(reads)==4 and sum(x['bytes'] for x in reads)==24183110 and all(x['load_invocations']==1 and x['decode_succeeded'] for x in reads)
assert len(res['payload_open_counts'])==4 and all(v==1 for v in res['payload_open_counts'].values())
assert res['affinity']==[0,1] and res['threads']==2 and res['rlimit_cpu']==[118,118] and res['rlimit_as']==17179869184
assert not res['cuda_initialized'] and len(res['denied_probes'])==6 and not res['guard_clean']
assert cl['resource']['cpu_external_cumulative_seconds']<120 and cl['resource']['wall_external_cumulative_seconds']<180
assert data['complete'] and [e['task_id'] for e in data['episodes']]==[0,1]
for e,idx in zip(data['episodes'],[9,6]):
 assert e['archive_rows']==e['analyzed_plans']==len(e['rows'])==16 and e['selected_row']==idx
 assert all(x['association_status']=='UNIQUE_CANONICAL_OCCURRENCE' for x in e['rows'])
 assert e['bindings']['selected_actual8_commands_equal'] and e['bindings']['pre_action_raw_eef_bytes_equal']
 assert e['rows'][idx]['prism_all8_min_m']==0 and e['rows'][idx]['native_cost_rank']==1
 assert e['comparisons']['all8']['unselected_strictly_better_prism']==[]
assert data['episodes'][0]['rows'][9]['prism_close_min_m']==0
assert all(x['close_commands']==0 and x['prism_close_min_m'] is None for x in data['episodes'][1]['rows'])
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
review={'decision':'ACCEPT_FIXED_POOL_DIAGNOSIS_DECLINE_MINIMUM_ALIGNMENT_RERANK','at':now,'output_manifest':ref(out),'result':ref(V/'result-v1.json'),'summary':ref(V/'summary-v2.md'),'verified_output_refs':len(m['files']),'verified_associated_rows':32,'original_process_and_recovery_exited':True,'cumulative_encoded_bytes':36274537,'cumulative_external_cpu_seconds':cl['resource']['cpu_external_cumulative_seconds'],'cumulative_external_wall_seconds':cl['resource']['wall_external_cumulative_seconds'],'guard_clean':False,'denied_probes_each_invocation':6,'cuda_initialized':False,'root_native_payload_reads_or_scientific_numeric_replay':0,'findings':['Both selected final-archive plans already attain minimum point-to-prism distance0; no strictly better unselected minimum-alignment candidate. Do not promote a pure reranking hypothesis.','Task1 all16 final archive plans have no positive close command in first8; does not establish absence earlier in search.','Task0 selected per-position proxy is inside only at outcome offset1, then leaves through offset8 while commands remain close; this is directly read from frozen per-step table, not a new metric.','H actual task0 prefix withdraws while aperture still closing. A possible temporal-completion proposal is a separate falsifiable mechanism; no efficacy established.'],'limits':['two exposed Dev states','fixed observed rotation/qpos with recorded controller-origin projection','arbitrary recognized point, not object volume/contact','no causal success claim or GPU release'],'goal_achieved':False}
with (V/'root-terminal-review-v2.json').open('x') as f:json.dump(review,f,indent=2);f.write('\n')
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r
sp=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py');a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
run='rdt-qd-ed-final-20260921T093925Z';session=W/'.arbor/sessions'/run;coord=session/'.coordinator'
with r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml');cp=r.read_json(coord/'checkpoint.json');tree=a.load_tree(W,run)
 assert state['current_cpu_task']['phase']=='N30_FIXED_HANDOFF_JAW_POOL_SCREEN_RECOVERY_V2'
 assert state['current_owned_workers']==[] and state['active_controller'] is None
 budget=copy.deepcopy(state['budget']);lex=state['worktree']
 task=copy.deepcopy(state['current_cpu_task']);task.update(status='COMPLETE_ACCEPTED_DESCRIPTIVE',closed_at=now,review=ref(V/'root-terminal-review-v2.json'),calculation_allowance_exhausted=True)
 state.setdefault('closed_cpu_tasks',{})[task['phase']]=task
 state.update(current_cpu_task=None,next_action='IDEATE one temporally coordinated capture/dwell proposal from closed pool, actual handoff and visual evidence; no more pool metric search, no GPU dispatch until a concrete candidate/protocol/budget is ready.',updated_at=now)
 state['study']['status']='N30_POOL_CLOSED_NEXT_MECHANISM_IDEATION_TARGET_NOT_MET'
 cp.update(status=state['study']['status'],phase='IDEATE',in_flight_executor=None,in_flight_executors=[],inflight_executor=None,inflight_executors=[],executor_task=None,next_action=state['next_action'],automatic_gpu_dispatch_authorized=False,automatic_gpu_dispatch_scope=None,updated_at=now,goal_achieved=False,target_achieved=False,target_met=False)
 tree['meta'].update(study_status=state['study']['status'],target_achieved=False,automatic_dispatch_authorized=False)
 node=a.node(tree,'14.1');node['cpu_task']=task;node['post_rejection_pool_review']=ref(V/'root-terminal-review-v2.json')
 node['insight']+=' Completed fixed decision16 pool screen:32/32 unique content associations; selected both minimum-prism0, no overlooked strictly better minimum-alignment row. Task1 all16 final plans open. Minimum-alignment reranking declined; temporal completion remains an untested separate hypothesis.'
 a.node(tree,tree['root_id'])['insight']='Goal NOT_MET. N29 all four arms0/6; N30 C0/Q0/N30 each0/2, rejected by frozen3/4 first-four gate, unrun cells Unknown. Fixed decision16 pool screen fully associated32 archive rows: both actual selected plans already minimum point-prism0, so minimum-alignment reranking lacks support. Task0 selected projected alignment is transient while actual hand withdraws during closure; task1 final archive contains no close command in first8. Capture/physical efficacy remain Unknown. Consider a temporally coordinated proposal operator, distinct from prior scalar lift bonuses, existing-close rescue, and cross-chunk continuation. Budget403/578,53.80872756284531/100GPUh; week revision pending; no GPU or protected-phase release.'
 assert state['budget']==budget and state['worktree']==lex
 tmp=W/'research-state.yaml.n30-pool-closed-v2'
 with tmp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(tmp,W/'research-state.yaml');r.durable_json(coord/'checkpoint.json',cp);a.save_tree(W,run,tree)
 note=f"\n### {now} — Fixed archive pool diagnosis accepted; minimum-alignment rerank declined\n\nAll32 rows unique canonical content associations, selected decode bound to prior actual8. Both selected prism minima0, no strictly better unselected row. Task0 selected per-position alignment is transient; task1 archive has no close command in first8. CPU combined4.109976s, encoded36274537bytes, two invocations each six denied probes, no CUDA; original failed pass preserved. No new metric sweep or success claim. Next is one separate temporal-completion hypothesis assessment, not a reranking variant. Review {V/'root-terminal-review-v2.json'}. Goal NOT_MET; no budget/GPU changes.\n"
 for p in [session/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md']:
  with p.open('a') as f:f.write(note)
print(json.dumps({'review':ref(V/'root-terminal-review-v2.json'),'verified_refs':len(m['files']),'status':state['study']['status']}))

