import json,hashlib,datetime,os,fcntl
from pathlib import Path
import yaml
W=Path.cwd();O=W.parent/'autonomy_20261004/turns/001784'
def ref(p):return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def read(p):return json.loads(p.read_text())
prior=read(O.parent/'001783/operational-summary-v1.json');result=read(O/'graph-admission-result-v1.json')
for r in prior['ledger_prefixes'].values():assert ref(Path(r['path']))['sha256']==r['sha256']
d=read(O.parent.parent/'driver-status.json');boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();handles={}
for k in ['driver','process']:
 r=d[k];a=(Path('/proc')/str(r['pid'])/'stat').read_text().rsplit(')',1)[1].split();assert int(a[19])==r['start_ticks'] and boot==r['boot_id'] and a[0]!='Z';handles[k]={**r,'state':a[0],'alive':True,'identity_verified':True}
passed=result['graph_verified'];next_step=('Independently review turn001784 graph.complete-disabled-v1.json and graph-admission-result-v1.json for B5; preserve source/runtime/policy exact bindings and prior historical artifacts. After B5 acceptance, root may adopt the graph/accounting and issue a separate finite preparation-only release under standing authority. No health/episode dispatch before measured readiness and their separate scientific/engineering gates.' if passed else 'Diagnose the exact turn001784 graph-admission-result-v1.json blocker using the preserved refreshed disabled graph. No dispatch or weakening admission; preserve exact failure and all old artifacts.')
record={'status':result['status'],'graph':ref(O/'graph.complete-disabled-v1.json'),'admission':ref(O/'graph-admission-result-v1.json'),'composition':ref(O/'composition-record-v1.json'),'independent_b5_pending':True,'release_enabled':False}
with open(W/'data/qd-ed-state.lock','a') as f:
 fcntl.flock(f,fcntl.LOCK_EX)
 for p,is_yaml in [(W/'research-state.yaml',True),(W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  v=yaml.safe_load(p.read_text()) if is_yaml else read(p);v['n36_reviewed_controller_graph_refresh']=record;v['next_action']=next_step
  temp=p.with_name(p.name+'.turn001784.tmp');temp.write_text(yaml.safe_dump(v,sort_keys=False,allow_unicode=True) if is_yaml else json.dumps(v,indent=2)+'\n');os.replace(temp,p)
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
s=dict(prior,turn=1784,at=now,live_handles=handles,controller_status='No active cohort; refreshed disabled graph '+result['status']+'; independent B5 pending',completed_work=['Verified bound handoff/authority, driver/coordinator identities, STOP/deadline, terminal previous executor and unchanged four private ledgers.','Refreshed controller references and transitive hashes in disabled plan/audit and affected manifests; retained historical originals, frozen scientific source, runtime and policy.','Ran unmodified production verify_graph against the exact deployed source: '+result['status']+'. No GPU/provider work or budget charges.'],next_bounded_step=next_step,unresolved_evidence=['Independent B5, graph/accounting adoption and separate finite readiness release remain pending.','Native readiness, scientific promotion, validation/formal and required ablations remain unproven.'],graph_refresh=record,deadline_passed=now>prior['deadline_utc'],stop_present=any((O.parent.parent/x).exists() for x in ['STOP']),gpu_dispatches=0,target_met=False)
if not passed:s['unresolved_evidence'].insert(0,result.get('error','Unknown graph failure'))
p=O/'operational-summary-v1.json';assert not p.exists();p.write_text(json.dumps(s,indent=2)+'\n');(O/'operational-summary-v1.sha256').write_text(ref(p)['sha256']+'  operational-summary-v1.json\n');print(json.dumps({'summary':ref(p),'status':result['status'],'next_step':next_step}))
