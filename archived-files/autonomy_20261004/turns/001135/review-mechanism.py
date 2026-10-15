import pathlib,json,hashlib,collections,datetime,sys,os,subprocess,yaml
root=pathlib.Path.cwd(); out=(root/'../autonomy_20261004/turns/001135').resolve()
sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as runner

def ref(p):
 p=pathlib.Path(p);return dict(path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def write(p,d):
 t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n');os.replace(t,p)
ledger=root/'data/attempt-ledger.jsonl';raw=ledger.read_bytes(); rows=[json.loads(x) for x in raw.splitlines()];rows=[x for x in rows if x.get('identity',{}).get('iteration')=='N35_CLOSURE_INTENT_DEV_20261009' and x.get('event')=='valid'];assert len(rows)==28
cells=[];totals=collections.Counter();reasons_total=collections.Counter();exclusions=collections.Counter()
for r in rows:
 assert r['identity']['split']=='dev'
 receipt=r['n35_worker_receipt'];assert ref(receipt['path'])['sha256']==receipt['sha256'];d=json.loads(pathlib.Path(receipt['path']).read_text());a=d['audit_report'];assert ref(a['path'])['sha256']==a['sha256'];ad=json.loads(pathlib.Path(a['path']).read_text());assert d['accepted'] and ad['accepted'] and not ad['errors']
 n=d['native_counts'];life=n.get('lifecycle',{});p=pathlib.Path(a['path']).parent/'eds_metrics.jsonl';reasons=collections.Counter()
 for line in p.read_text().splitlines():reasons.update(json.loads(line).get('capture_dwell_proposal',{}).get('reasons',[]))
 c=dict(attempt_id=r['attempt_id'],identity=r['identity'],success=r['success'],receipt=receipt,audit=a,metrics=ref(p),native_counts={k:v for k,v in n.items() if k not in ['runtime_identity','lifecycle','compute_expected']},lifecycle={k:v for k,v in life.items() if k!='resets'},reset_reasons=dict(collections.Counter(life.get('resets',[]))),proposal_reasons=dict(reasons));cells.append(c)
 if r['identity']['profile']=='N35':
  totals.update({k:v for k,v in n.items() if type(v) is int});totals.update({k:v for k,v in life.items() if type(v) is int});reasons_total.update(reasons);exclusions.update(life.get('exclusions',{}))
next_action='Bounded Dev-only native diagnosis of N35 approach-to-close transition: inspect selected approach decisions and linked observed jaw/target geometry on tasks0 and6, contrast N34 within this same cohort, and identify whether geometry, action execution, or stage/reset timing blocks direct-close entry. No threshold tuning, new GPU dispatch, valid-cell replay, or protected evaluation. Use turn001135 hash-bound aggregate review; do not rerun native audits or rebuild old provenance.'
insight='N35 rejected at7 matched tasks: C0 1/7,Q0 0/7,N34 1/7,N35 1/7; upper bound4/10<5. Across185 N35 guided decisions,0 eligible boundaries,0 direct-close selections,0 created tokens,0 memory selections. Approach proposals changed767 times and content was selected in98 decisions, so generic proposal activity does not exercise closure memory. Task5 success had0 proposal-content selections; indirect effects unresolved. Diagnose approach-to-close entry on Dev only before another method.'
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
rec={'schema':'n35-dev-mechanism-review-v1','at':now,'source':'52a87af0bf11f95b21ce17aba456dc98944d9774','ledger':dict(**ref(ledger),bytes=len(raw)),'scope':'All28 terminal Dev cells, authenticated existing worker/native audit summaries and scalar metrics; no native audit rerun or protected reads','cells':cells,'n35_totals':dict(totals),'n35_proposal_reasons':dict(reasons_total),'n35_boundary_exclusions':dict(exclusions),'outcomes':{profile:dict(successes=sum(c['success'] for c in cells if c['identity']['profile']==profile),denominator=7) for profile in ['C0','Q0','N34','N35']},'unobserved_tasks':[7,8,9],'promotion':False,'target_met':False,'interpretation':insight,'limits':['Existing accepted audits authenticated; native tensors not re-audited.','Selected proposal content does not prove unique causal ancestry or physical grasp.','N34 and N35 trajectories differ on some tasks despite zero memory use; no claim of full trajectory equivalence.','Closure memory efficacy remains untested by this cohort because its antecedent did not occur.'],'next_action':next_action}
assert totals['guided_decisions']==185 and totals['changed_proposals_verified']==767 and totals['selected_proposal_content_decisions']==98
write(out/'mechanism-review-v1.json',rec)
with runner.locked(root/'data/qd-ed-state.lock'):
 assert ledger.read_bytes()==raw
 statep=root/'research-state.yaml';cpp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';s=yaml.safe_load(statep.read_text());c=json.loads(cpp.read_text());assert s['active_controller'] is None and not pathlib.Path('/proc/2632351').exists()
 for p in [statep,cpp]:(out/(p.name+'.before-mechanism')).write_bytes(p.read_bytes())
 for obj in [s,c]:obj['n35_dev_mechanism_review']=ref(out/'mechanism-review-v1.json');obj['next_action']=next_action;obj['updated_at']=now
 tmp=statep.with_name(statep.name+'.tmp');tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));os.replace(tmp,statep);write(cpp,c)
 subprocess.run([sys.executable,'/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py','update','--cwd',str(root),'--run-name','rdt-qd-ed-final-20260921T093925Z','--node-id','15.5','--status','done','--score',str(1/7),'--insight',insight,'--result',str(out/'mechanism-review-v1.json')],check=True,stdout=subprocess.DEVNULL)
(out/'operational-summary.md').write_text(f'''Turn001135: N35 Dev mechanism review recorded at {now}.

Source52a87af0bf11f95b21ce17aba456dc98944d9774 unchanged. Driver268073/start97715947 and coordinator4004251/start144323825 verified on boot2a1fa95f-ab0d-488c-a298-fc488ddd2af7. Closed controller2632351 absent; no active GPU controller, STOP absent at entry. Authorization ends2026-10-11T11:13:13Z. Prior turn001134 completed normally; ledger unchanged at7513934 bytes/SHA256 aff9bf3e50b5d82b06cbb54f067746e3eeb6c27e499235519b903f42957ac368.

Authenticated28 Dev worker receipts and native audits; aggregated mechanism counters without rerunning audits. {insight}

Idea Tree15.5 marked done with absolute observed Dev score1/7, no promotion. Owning state/checkpoint reference review SHA256 {ref(out/'mechanism-review-v1.json')['sha256']}. All502 charges/75.243793112159 GPUh and protected reserves retained. No new dispatch, source changes or process signals.

Next: {next_action}

Original validation/formal/required-ablation goal remains unfulfilled. This is a bounded continuation handoff, not a completion record.
''')
print(json.dumps({'review':ref(out/'mechanism-review-v1.json'),'n35_totals':dict(totals),'reasons':dict(reasons_total),'exclusions':dict(exclusions)},indent=2))
