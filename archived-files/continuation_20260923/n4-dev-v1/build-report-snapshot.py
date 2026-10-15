import argparse,collections,datetime,hashlib,json,os,pathlib,sys
W=pathlib.Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z');B=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(W/'scripts'));import qd_ed_final_runner as r;import qd_ed_n4_plan as n
p=argparse.ArgumentParser();p.add_argument('--output-dir',type=pathlib.Path,required=True);p.add_argument('--plan-revision',type=pathlib.Path,action='append',default=[]);args=p.parse_args();D=args.output_dir.resolve();assert D.is_relative_to(B);D.mkdir(exist_ok=False,parents=True)
ref=lambda q:{'path':str(pathlib.Path(q).resolve()),'sha256':r.digest(q)}
def write(name,value):
 with (D/name).open('x') as f:json.dump(value,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
base_path=B/'plan.frozen.json';base=r.read_json(base_path);source={x['path']:x['sha256'] for x in base['code_files']}
for f in ['scripts/qd_ed_n4_report.py','scripts/qd_ed_n4_plan.py']:assert r.digest(W/f)==source[f]
with r.locked(W/'data/qd-ed-state.lock'):
 raw=(W/'data/attempt-ledger.jsonl').read_bytes();health_raw=(W/'data/gpu-healthcheck-ledger.jsonl').read_bytes()
assert raw.endswith(b'\n') and health_raw.endswith(b'\n')
events=[]
for line in raw.splitlines():
 e=json.loads(line)
 if e.get('identity',{}).get('iteration')==n.COHORT:events.append(e)
groups=collections.OrderedDict()
for e in events:groups.setdefault(e['attempt_id'],[]).append(e)
assert groups and all(g[-1]['event'] in r.TERMINAL for g in groups.values()),'report snapshot requires all owned cohort records terminal'
excerpt={'schema':'qd-ed-n4-journal-excerpt-v1','cohort_id':n.COHORT,'extraction':'all_events_all_n4_attempts_through_snapshot','snapshot_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_journal':{'path':str(W/'data/attempt-ledger.jsonl'),'sha256':hashlib.sha256(raw).hexdigest()},'source_journal_bytes':len(raw),'events':events,'terminal_attempt_ids':list(groups),'inflight_attempt_ids':[]}
write('journal-excerpt.json',excerpt)
plans=[ref(base_path)]+[ref(x) for x in args.plan_revision];assert len({p['sha256'] for p in plans})==len(plans)
attempts=[]
for g in groups.values():
 terminal=g[-1];out=r.owned(terminal['output_dir'],base['artifact_root']);path=out/'attempt-result.json';assert r.read_json(path)==terminal
 assert terminal['plan_sha256'] in {x['sha256'] for x in plans}
 spec={'terminal':ref(path)}
 if terminal['event']=='valid' and terminal.get('outcome_valid') is True:
  audit=out/'eds_eval/decision-evidence-audit.json'
  if audit.exists():
   data=r.read_json(audit);spec['audit']=ref(audit)
   if data.get('accepted') is True and data.get('evidence_complete') is True:
    spec['compute']=ref(out/'eds_eval/episode_compute.jsonl');spec['metrics']=ref(out/'eds_eval/eds_metrics.jsonl')
 attempts.append(spec)
health=[]
for declared in base['n4_cohort']['health_resources']:
 records=[json.loads(line) for line in health_raw.splitlines() if json.loads(line).get('resource_id')==declared['resource_id']]
 assert records and records[-1]['event'] in ['completed','aborted'];last=records[-1];hp=r.owned(pathlib.Path(last['output_dir'])/'healthcheck-result.json',base['artifact_root']);actual=r.read_json(hp)
 assert actual==last,'health terminal differs from resource journal'
 health.append({**declared,'terminal':ref(hp)})
script=W/'scripts/qd_ed_n4_report.py';auth={'schema':'qd-ed-n4-report-authorization-v1','status':'authorized','script':ref(script),'protocol_sha256':base['n4_cohort']['protocol']['sha256'],'base_plan_sha256':r.digest(base_path),'journal_excerpt_sha256':r.digest(D/'journal-excerpt.json'),'scope':'Complete N4-only terminal metadata snapshot and named accepted audit/compute/metrics. No raw native reread, provider/model/GPU call or promotion.','snapshot_builder':ref(__file__)}
write('authorization.json',auth)
manifest={'schema':'qd-ed-n4-report-input-v1','script_sha256':r.digest(script),'protocol_sha256':base['n4_cohort']['protocol']['sha256'],'authorization':ref(D/'authorization.json'),'base_plan':ref(base_path),'plan_revisions':plans[1:],'journal_excerpt':ref(D/'journal-excerpt.json'),'attempts':attempts,'health_resources':health,'input_scope_complete':True}
write('manifest.json',manifest)
print(json.dumps({'manifest':ref(D/'manifest.json'),'terminal_count':len(attempts),'original_expected_cells':12,'GPU_dispatches':0,'report_execution_authorized':True}))
