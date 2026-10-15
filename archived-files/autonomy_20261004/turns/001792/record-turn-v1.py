from pathlib import Path
import json,hashlib,datetime,os,fcntl,subprocess,yaml
W=Path.cwd(); A=W.parent/'autonomy_20261004'; T=A/'turns/001792'; C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def read(p): return json.loads(p.read_text())
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def atomic(p,d,y=False):
 tmp=p.with_name(p.name+'.turn1792.tmp');tmp.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True) if y else json.dumps(d,indent=2)+'\n');os.replace(tmp,p)
prev=read(A/'turns/001791/operational-summary-v1.json'); driver=read(A/'driver-status.json'); boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def ident(r):
 v=dict(r,alive=False,identity_verified=False);p=Path('/proc')/str(r['pid'])/'stat'
 if p.exists():
  x=p.read_text().rsplit(') ',1)[1].split();v.update(state=x[0],alive=x[0]!='Z',identity_verified=boot==r['boot_id'] and int(x[19])==r['start_ticks'])
 return v
handles={k:ident(prev['live_handles'][k]) for k in ['wrapper','controller']};handles.update(driver=ident(driver['driver']),coordinator=ident(driver['process']))
ledgers={}
for name,r in prev['ledger_prefixes'].items():
 b=Path(r['path']).read_bytes();assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'];ledgers[name]={**ref(Path(r['path'])),'prior_prefix_preserved':True}
source=prev['current_source'].copy();assert subprocess.check_output(['git','-C',source['worktree'],'rev-parse','HEAD'],text=True).strip()==source['commit'];source['tracked_clean']=subprocess.run(['git','-C',source['worktree'],'diff','--quiet','HEAD']).returncode==0
now=datetime.datetime.now(datetime.timezone.utc);release=read(Path(prev['measurement']['release']['path']));stop=any(os.path.lexists(p) for p in release['stop_authority']['paths']);deadline=now>=datetime.datetime.fromisoformat(prev['deadline_utc'].replace('Z','+00:00'))
validation=read(T/'readiness-validation-v2.json');validation_ref=ref(T/'readiness-validation-v2.json')
status='READINESS_VALIDATION_REJECTED_REQUIRES_BOUNDED_DIAGNOSIS';next_step='Delegate bounded executor design/repair in isolated engineering worktree: explicitly scoped preparation binding validation with exact external release/source/runtime/process linkage and adversarial rejection tests; independent review before any adoption. Decide retained-proof eligibility explicitly; do not rewrite receipt or silently bypass consumer.'
acceptance_ref=None
if validation['status']=='PASS':
 assert not stop and not deadline
 preview=Path(validation['preview']['path']);assert ref(preview)['sha256']==validation['preview']['sha256']==validation['prospective_runtime']['sha256']
 acceptance=dict(schema='n36-preparation-root-acceptance-v1',approved=True,specification=validation['specification'],proof=validation['proof'],runtime=validation['prospective_runtime'],release_enabled=False,health_authorized=False,episode_authorized=False)
 ap=Path(validation['acceptance_path']);assert not ap.exists()
 with ap.open('x') as f:json.dump(acceptance,f,indent=2);f.write('\n')
 acceptance_ref=ref(ap);status='READINESS_PROOF_ACCEPTED_EXACT_RUNTIME_PRODUCTION_PENDING'
 next_step='Produce the exact accepted measured runtime using committed qd_ed_n36_bootstrap.py with -I -S -B -X pycache_prefix=/dev/null, selected current specification and qd_ed_n36_readiness_prepare --proof/--proof-sha256. Do not replay measurement. Then bind prospective one-use engineering health/episode releases using refreshed full ledger accounting and unchanged scientific gates.'
summary=dict(schema='autonomy-operational-summary-v1',turn=1792,at=now.isoformat(),current_source=source,owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles=handles,controller_status=status,ledger_prefixes=ledgers,completed_work=['Verified bound handoff, exact authority, driver deadline, private ledger prefixes, terminal controller and driver/coordinator identities; prior turn exited normally.','Recomputed exact ledger accounting; total already charged, refreshed recovery/health subtotals by 0.06520103282398648 GPUh with no new ledger charge or cap/reserve changes. Initial accounting assertion failed before mutation and is preserved.','Preserved initial CPU validation rejection; diagnosed validator missing frozen pycache prefix using matching content/rule hashes and launch provenance. Repeated CPU check with matching prefix; no source, receipt, audit or scientific rule changes.'],next_bounded_step=next_step,unresolved_evidence=['Production runtime binding and separate health/episode release pending.','Original validation/formal/required ablation goal remains incomplete.'],measurement=prev['measurement'],readiness_validation=validation_ref,readiness_root_acceptance=acceptance_ref,accounting=ref(T/'full-ledger-accounting-v1.json'),diagnosis=ref(T/'generated-receipt-diagnosis-v1.json'),binding_diagnosis=ref(T/'binding-diagnosis-v1.json'),deadline_utc=prev['deadline_utc'],stop_present=stop,deadline_passed=deadline,target_met=False)
summary['completed_work'].append('CPU readiness validation '+validation['status']+'; '+status)
sp=T/'operational-summary-v1.json';assert not sp.exists();atomic(sp,summary);sr=ref(sp);(T/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n')
with (C/'state.lock').open('a') as cl,(W/'data/qd-ed-state.lock').open('a') as rl:
 fcntl.flock(cl,fcntl.LOCK_EX);fcntl.flock(rl,fcntl.LOCK_EX)
 s=yaml.safe_load((W/'research-state.yaml').read_text());c=read(C/'checkpoint.json');tree=read(C/'idea_tree.json')
 for d in [s,c]:d.update(n36_measured_readiness_validation=validation_ref,n36_measured_readiness_root_acceptance=acceptance_ref,current_owned_workers=[],latest_operational_summary=sr,next_action=next_step,updated_at=summary['at'])
 tree['nodes']['15.6'].update(result=status,insight=next_step,readiness_validation=validation_ref)
 atomic(W/'research-state.yaml',s,True);atomic(C/'checkpoint.json',c);atomic(C/'idea_tree.json',tree)
print(json.dumps(dict(summary=sr,status=status,acceptance=acceptance_ref)))
