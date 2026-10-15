import pathlib,json,hashlib,datetime,os,sys,yaml,collections,math
root=pathlib.Path.cwd();out=root.parent/'autonomy_20261004/turns/000515';sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as runner
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,v):
 t=p.with_name(p.name+'.tmp515');t.write_text(json.dumps(v,indent=2)+'\n');os.replace(t,p)
r=json.loads((out/'feasibility-v1.json').read_text());old=json.loads((out.parent/'000513/reachability-v1.json').read_text());assert len(r['rows'])==1571
assert json.loads((out/'input-manifest.json').read_text())==json.loads((out.parent/'000513/input-manifest.json').read_text())
for a,b in zip(r['rows'],old['rows']):
 assert all(a[k]==v for k,v in b.items())
n=[x for x in r['rows'] if x['profile']=='N32'];eligible=[x for x in n if x['guided'] and x['recognized_target'] and x['nonempty_jaw']];assert len(n)==540 and len(eligible)==102
assert all('nominal_reachable' in x and x['entry'] is False for x in eligible)
assert sum(x['reason']=='unrecognized_target' for x in n)==438
assert all(x['reason']=='Unknown_missing_observation_packet' for x in r['rows'] if x['profile']!='N32')
for x in eligible:
 assert all(math.isfinite(v) and abs(v)<=1 for v in x['translation_command'])
 if not x['clipped']:
  a=x['nominal_endpoint_hand_target'];lo,hi=x['jaw_interval'];assert max(abs(a[0]),abs(a[1]-(lo+hi)/2),abs(a[2]+.0036))<1e-12
reachable=sum(x['nominal_reachable'] for x in eligible);nonzero=sum(x['nonzero_command'] for x in eligible)
assert ref(root/'data/attempt-ledger.jsonl')==r['ledger'];assert not pathlib.Path('/proc/1070042').exists()
now=datetime.datetime.now(datetime.timezone.utc);assert not (out.parent.parent/'STOP').exists();assert now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
handles={};boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for pid,start in [(268073,97715947),(2373890,133331210)]:
 f=pathlib.Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1].split();assert int(f[19])==start;handles[str(pid)]={'pid':pid,'start_ticks':start,'boot_id':boot,'state':f[0]}
next_action=('N34 positive CPU geometry licenses isolated executor implementation and native audit preparation only. Freeze scope from turn514 ideation; preserve 8/.01, literal prism, one final-slot competitor, open approach then observed-entry closure, ordinary QD/ED selection and other candidates. Prove native action channel mapping, FP32/BF16 encode/decode, source/audit parity and zero-effect false-trigger controls before root integration. No GPU release until prospective fresh matched Dev protocol, native evidence and budget/reserve review.' if reachable else 'N34 rejected by prespecified zero-reachable CPU rule. Return to constraints-first distinct mechanism ideation without changing prism, 8/.01 or fitting thresholds.')
review={'schema':'n34-cpu-feasibility-root-review-v1','at':now.isoformat(),'node_id':'15.4','decision':'CPU_GEOMETRY_FEASIBLE_NATIVE_IMPLEMENTATION_PENDING' if reachable else 'REJECT_CPU_NOMINAL_UNREACHABLE','observation':ref(out/'feasibility-v1.json'),'registration':ref(out.parent/'000514/n34-registration-v1.json'),'source_commit':'04d1255016fa13a2d467995b9e37a6a829356a1c','scientific_source_commit':'1065f38122379a515b60a9a424f574330405b66f','live_handles':handles,'controller_status':'NUMERIC_FUTILITY; exit0; PID1070042 absent','prior_turn_exit':0,'ledger':r['ledger'],'denominators':{'cells':18,'all_decisions':1571,'n32_observation_contexts':540,'eligible_outside_prism':102,'nonzero_commands':nonzero,'nominal_reachable':reachable,'unrecognized_targets':438,'controls_without_packets_unknown':1031,'malformed_n32':0},'per_task':[{'task':c['task'],'eligible':c['nonzero_commands'],'nominal_reachable':c['nominal_reachable']} for c in r['cells'] if c['profile']=='N32'],'checks':['Input manifest identical to turn513 exposed packets; all input bundle hashes checked.','All shared extracted fields identical to bound turn513 rows.','Unclipped endpoints numerically coincide with unchanged jaw center within 1e-12.','Quaternion convention and prism checked against native reference.'],'limitations':['Nominal projection is not actual robot dynamics or task success.','Native dtype, decode, ordinary selection and physical efficacy unresolved.','Tracked target is not a verified grasp contact.','Control packets remain Unknown.'],'new_gpu_dispatches':0,'scientific_promotion':False,'goal_met':False,'next_action':next_action}
write(out/'feasibility-root-review-v1.json',review);rr=ref(out/'feasibility-root-review-v1.json');cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json'
with runner.locked(root/'data/qd-ed-state.lock'):
 s=yaml.safe_load((root/'research-state.yaml').read_text());c=json.loads(cp.read_text());assert s['active_controller'] is None and c['active_controller'] is None and not s['current_owned_workers'];assert ref(root/'data/attempt-ledger.jsonl')==r['ledger']
 assert s['n34_cpu_ideation']==review['registration']
 for d in [s,c]:d['n34_cpu_feasibility_review']=rr;d['next_action']=next_action;d['updated_at']=now.isoformat()
 tmp=root/'research-state.yaml.tmp515';tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));os.replace(tmp,root/'research-state.yaml');write(cp,c)
 tree=json.loads(tp.read_text());node=tree['nodes']['15.4'];assert node['status']=='pending';node.update(status='pending' if reachable else 'pruned',insight=f'Fixed nominal approach has {reachable}/102 reachable endpoints and {nonzero}/102 nonzero commands. CPU geometry only; native representation, selection and efficacy unresolved.',result=review['decision'],n34_cpu_feasibility_review=rr,execution_authorized=False);write(tp,tree)
(out/'operational-summary.md').write_text(f'''Turn515: N34 registered CPU geometry screen completed.

Source {review['source_commit']}; scientific source {review['scientific_source_commit']} unchanged. Driver268073/start97715947 and coordinator2373890/start133331210 verified on boot{boot}. N32R3 controller1070042 absent, NUMERIC_FUTILITY/exit0; no owning controller or GPU worker. Prior514 exit0; no recovery needed. STOP absent; authorization ends2026-10-11T11:13:13Z.

Completed bound extraction of18 exposed Dev cells/1571 decisions, identical input manifest and shared fields to turn513. All540 N32 packets present;102 eligible outside-prism contexts produce{nonzero} nonzero commands and{reachable} nominal reachable endpoints. Controls1031 missing packets remain Unknown,438 N32 contexts have unrecognized targets. Review {rr['sha256']}. No benchmark source edits, GPU/provider calls, historical audit replay, threshold changes or protected result reads.

Ledger unchanged1326 rows/6659252 bytes/{r['ledger']['sha256']};442 dispatches and62.81145837588456GPUh retained. State/checkpoint/tree record review.

Next bounded step: {next_action}

Unresolved: native dtype/channel feasibility, tracked-keypoint grasp relevance, ordinary selection, physical efficacy and original validation/formal/required-ablation evidence. Goal unmet; no completion record. Driver continues.
''')
print(json.dumps(review['denominators']));print(json.dumps(rr))
