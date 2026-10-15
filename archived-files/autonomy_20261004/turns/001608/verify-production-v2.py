import pathlib,json,hashlib,sys,datetime,time,traceback,yaml
W=pathlib.Path.cwd(); A=W.parent/'autonomy_20261004';T=A/'turns/001608'
def read(p):return json.loads(pathlib.Path(p).read_text())
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def save(n,d): (T/n).write_text(json.dumps(d,indent=2)+'\n')
old=read(A/'turns/001607/operational-summary-v1.json');boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def ident(h):
 p=pathlib.Path('/proc')/str(h['pid'])/'stat';v=p.read_text().rsplit(')',1)[1].split() if p.exists() else None;match=bool(v and int(v[19])==h['start_ticks'] and h['boot_id']==boot);return {**h,'observed_start_ticks':int(v[19]) if v else None,'identity_matches':match,'live':bool(match and v[0]!='Z'),'state':v[0] if v else None}
ds=read(A/'driver-status.json');assert ds['turn']==1608
assert ident(ds['driver'])['live'] and ident(ds['process'])['live']
assert not any(ident(h)['live'] for h in [*old['live_handles'].values(),*old['prior_cohort_handles'].values()])
assert not (A/'STOP').exists() and datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(old['deadline'].replace('Z','+00:00'))
for r in old['ledger_prefixes'].values():assert ref(pathlib.Path(r['path']))['sha256']==r['sha256']
att=read(A/'turns/001607/root-final-binding-reattestation-v1.json');pr=att['reviewed_plan'];assert ref(pathlib.Path(pr['path']))['sha256']==pr['sha256']
p=read(pr['path']);p.update(frozen=True,release_enabled=True,authority=att['authority'],b5_review={k:old['b5_operational_review'][k] for k in ('path','sha256')});p['phase_authorization']['engineering']=True
save('engineering-plan.frozen-v2.json',p)
save('plan-provenance-v2.json',{'parent_disabled_plan':pr,'plan':ref(T/'engineering-plan.frozen-v2.json'),'root_reattestation':old['root_final_binding_reattestation'],'changed_fields':['frozen','release_enabled','authority','b5_review','phase_authorization.engineering'],'gpu_dispatch':False})
sys.path.insert(0,p['worktree'])
from scripts import qd_ed_n36_engineering as e
checks={}; start=time.monotonic()
try:
 e.validate_plan(p);checks['plan']='PASS'
 authority=e.read(p['authority']);e.validate_authority(p,authority);checks['authority']='PASS'
 e.validate_state(p,authority,yaml.safe_load((W/'research-state.yaml').read_text()));checks['owning_state']='PASS'
 e.launch_guard(p,authority,need=2100);checks['stop_deadline']='PASS'
 save('production-validation-v2.json',{'checks':checks,'gpu_dispatch':False})
 evidence=e.full.verify_audit_closure(e.read(p['audit_plan']));checks['audit_closure']='PASS'
 e.b.verify_engineering_manifest(p['engineering_manifest'],p,evidence.runtime,e.row(),audit=e.read(p['audit_plan']));checks['engineering_manifest']='PASS'
 result={'decision':'PASS','checks':checks,'audit_manifests':len(evidence.manifests)}
except Exception as exc:
 result={'decision':'BLOCKED','checks':checks,'error':str(exc),'traceback':traceback.format_exc()}
result.update(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-start,gpu_dispatch=False,plan=ref(T/'engineering-plan.frozen-v2.json'))
save('pre-release-closure-v2.json',result);print(json.dumps(result))
