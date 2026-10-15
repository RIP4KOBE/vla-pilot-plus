import pathlib,json,hashlib,datetime,os,sys,yaml
root=pathlib.Path.cwd();out=root.parent/'autonomy_20261004/turns/000513';sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as runner
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,v):
 t=p.with_name(p.name+'.tmp513');t.write_text(json.dumps(v,indent=2)+'\n');os.replace(t,p)
now=datetime.datetime.now(datetime.timezone.utc);r=json.loads((out/'reachability-v1.json').read_text());assert len(r['rows'])==1571
n=[x for x in r['rows'] if x['profile']=='N32'];assert len(n)==540 and sum(x['guided'] for x in n)==102
assert sum(x['entry'] is True for x in n)==0
assert sum(x['reason']=='no_current_entry' for x in n)==102 and sum(x['reason']=='unrecognized_target' for x in n)==438
assert all(x['changed_opportunities']==0 for x in n if x['guided'])
assert ref(root/'data/attempt-ledger.jsonl')==r['ledger'];assert not pathlib.Path('/proc/1070042').exists();assert not list((root.parent/'autonomy_20261004').glob('*STOP*'));assert now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
handles={};boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for pid,start in [(268073,97715947),(2352376,133265613)]:
 f=pathlib.Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1].split();assert int(f[19])==start;handles[str(pid)]={'pid':pid,'start_ticks':start,'boot_id':boot,'state':f[0]}
next_action='Constraints-first Arbor successor ideation using N33 exact current-observation trigger rejection and N32 projection-error evidence. N33 has zero entry hits across all102 eligible guided N32 dev decisions; do not expand its prism or tune thresholds. Select a distinct falsifiable mechanism addressing observed execution/geometry or capture timing, screen feasibility before isolated executor implementation, and freeze prospective dev source/protocol/native audits before any new GPU release. Preserve all442 charges and protected gates; no historical replay or protected-result access.'
review={'schema':'n33-cpu-reachability-root-review-v1','at':now.isoformat(),'node_id':'15.3','decision':'REJECT_CPU_TRIGGER_UNREACHABLE_ON_EXPOSED_DEV','observation':ref(out/'reachability-v1.json'),'registration':ref(out.parent/'000512/n33-registration-v1.json'),'source_commit':'04d1255016fa13a2d467995b9e37a6a829356a1c','scientific_source_commit':'1065f38122379a515b60a9a424f574330405b66f','source_references':[ref(root/'scripts/qd_ed_n31_reference.py'),ref(root/'scripts/qd_ed_n32_native.py'),ref(root/'scripts/qd_ed_n30_native.py')],'live_handles':handles,'controller_status':'NUMERIC_FUTILITY; exit0; PID1070042 absent','prior_turn_exit':0,'ledger':r['ledger'],'denominators':{'logical_cohort_cells':18,'all_decisions':1571,'n32_observation_contexts':540,'eligible_guided_recognized_target_nonempty_jaw':102,'entry_hits':0,'admissible_changed_opportunities':0,'unrecognized_target_n32_contexts':438,'controls_without_packets_unknown':1031,'missing_or_malformed_n32_packets':0},'interpretation':['Literal unchanged N31 hand prism applied at current observed EEF with contemporaneous quaternion/jaw and recognized tracked target, never projected positions.','Zero trigger hits makes native proposal-byte evaluation unnecessary: false-trigger path has no proposed changes.','This closes the registered candidate under its prospective CPU feasibility rule; it does not establish universal unreachability or task efficacy.','Control observation packets are absent and remain Unknown; no predicted or future observations substituted.','Tasks6–9 remain unobserved; no results inferred.'],'new_gpu_dispatches':0,'audit_replay':False,'scientific_promotion':False,'goal_met':False,'next_action':next_action}
write(out/'reachability-root-review-v1.json',review);rr=ref(out/'reachability-root-review-v1.json');cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json'
with runner.locked(root/'data/qd-ed-state.lock'):
 s=yaml.safe_load((root/'research-state.yaml').read_text());c=json.loads(cp.read_text());assert s['active_controller'] is None and c['active_controller'] is None and not s['current_owned_workers'];assert ref(root/'data/attempt-ledger.jsonl')==r['ledger']
 for d in [s,c]:d['n33_cpu_reachability_review']=rr;d['next_action']=next_action;d['updated_at']=now.isoformat()
 tmp=root/'research-state.yaml.tmp513';tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));os.replace(tmp,root/'research-state.yaml');write(cp,c)
 tree=json.loads(tp.read_text());node=tree['nodes']['15.3'];assert node['status']=='pending';node.update(status='pruned',insight='Exact current-observation capture trigger has0/102 eligible guided entry hits across six N32 dev tasks;438 other contexts have unrecognized targets. Reject this implementation by prospective CPU rule, without prism expansion. Control1031 missing packets remain Unknown; no efficacy claim.',result=review['decision'],n33_cpu_reachability_review=rr,execution_authorized=False);write(tp,tree)
(out/'operational-summary.md').write_text(f'''Turn513: N33 CPU reachability closed; no GPU dispatch.

Current source {review['source_commit']}; scientific source {review['scientific_source_commit']} unchanged. Driver268073/start97715947 and coordinator2352376/start133265613 verified on boot{boot}. N32R3 controller1070042 absent, NUMERIC_FUTILITY/exit0; state/checkpoint have no active controller or worker. Turn512 exit0 and registration hash verified, no abnormal side effects to recover. STOP absent; authorization ends2026-10-11T11:13:13Z.

Completed availability-first hash-bound extraction across18 accepted development cells,1571 decisions. All540 N32 observation packets present:102 eligible guided recognized-target decisions with nonempty jaw intervals, zero literal current-prism entry hits, zero possible changed proposal opportunities;438 decisions have no recognized target. Controls1031 missing packets remain Unknown. No malformed N32 packets. Node15.3 pruned by its prospective CPU rule; no threshold adjustment, new provider call, benchmark-source edit, protected-result read or full native audit replay. Review SHA256 {rr['sha256']}.

Owning ledger unchanged1326 rows/6659252 bytes/SHA256 {r['ledger']['sha256']};442 dispatches and62.81145837588456GPUh retained, protected reserves unchanged. State/checkpoint/tree link the closure.

Next bounded step: {next_action}

Unresolved: a reachable and effective capture mechanism, tracked-keypoint grasp relevance, original validation/formal/required-ablation evidence. Goal unmet; no completion record. Local driver continues.
''')
print(json.dumps(rr))
