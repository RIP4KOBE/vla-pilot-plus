import pathlib,json,hashlib,datetime,fcntl,os,yaml
root=pathlib.Path.cwd();base=root.parent/'autonomy_20261004';out=base/'turns/001882';prev=json.loads((base/'turns/001881/operational-summary-v1.json').read_text());now=datetime.datetime.now(datetime.timezone.utc).isoformat()
def ref(p):return {'path':str(p.absolute()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
graphdir=base/'turns/001881/reviewed-graph-v2';result=graphdir/'strict-production-admission-result-v1.json';done=result.exists();r=json.loads(result.read_text()) if done else None
process=json.loads((out/'cpu-admission-process-v1.json').read_text());live=False
try:
 s=pathlib.Path('/proc/%s/stat'%process['pid']).read_text().rsplit(')',1)[1].split();live=int(s[19])==process['start_ticks'] and s[0]!='Z'
except FileNotFoundError:pass
status=r['status'] if done else ('RUNNING' if live else 'INTERRUPTED_RECONCILE_BEFORE_RETRY')
nextstep=('Inspect terminal exact production admission result and resolve only its named blocker. Preserve frozen source and all historical pinned paths; never blanket canonicalize specification references.' if status=='BLOCKED' else 'Continue with fresh readiness/accounting/release and independent review under remaining deadline; admission alone grants no GPU authority.' if status=='PASS' else 'Monitor recorded CPU admission PID/boot/start; do not duplicate it. After terminal result, inspect named blockers or proceed to fresh readiness/accounting/release and independent review.')
record=dict(status=status,at=now,graph=ref(graphdir/'graph.complete-disabled-v1.json'),preflight=ref(graphdir/'production-preflight-result-v1.json'),result=ref(result) if done else None,process=process,source=prev['current_source'],gpu_authorized=False)
liveinfo=json.loads((out/'live-reconciliation-final-v1.json').read_text())
summary=dict(schema='autonomy-operational-summary-v1',at=now,turn=1882,current_source=prev['current_source'],owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles=liveinfo['driver'],cpu_operation_handles=[process] if live else [],controller_status='NO_LIVE_EXPERIMENT_CONTROLLER_CPU_ADMISSION_'+status,ledger_prefixes=prev['ledger_prefixes'],ledgers_unchanged=True,completed_work=['Verified bound authority, driver identity, ACTIVE/PASS isolation and four unchanged private ledgers.','Reconciled prior CPU admission process as absent without a terminal result; preserved original record and Unknown exit cause.','Reran exact guarded CPU admission with unchanged source and graph; no GPU worker launched.'],admission=record,next_bounded_step=nextstep,unresolved_evidence=['Full graph admission' if status!='PASS' else 'Fresh measured readiness','Fresh accounting/release and independent review','Valid native engineering execution','Original validation/formal/required ablation evidence'],target_met=False,stop_present=(base/'STOP').exists(),deadline='2026-10-11T11:13:13Z')
with (root/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for x in prev['ledger_prefixes'].values():assert ref(pathlib.Path(x['path']))['sha256']==x['sha256']
 (out/'operational-summary-v1.json').write_text(json.dumps(summary,indent=2)+'\n');sr=ref(out/'operational-summary-v1.json');(out/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n')
 for p,isyaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if isyaml else json.loads(p.read_text());d['n36_reviewed_successor_graph_admission']=record;d['latest_operational_summary']=sr;d['next_action']=nextstep;d['updated_at']=now;t=p.with_name(p.name+'.001882.tmp');t.write_text(yaml.safe_dump(d,sort_keys=False) if isyaml else json.dumps(d,indent=2)+'\n');os.replace(t,p)
print(json.dumps({'status':status,'live':live,'summary':sr}))
