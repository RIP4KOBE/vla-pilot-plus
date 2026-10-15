import json,hashlib,datetime,fcntl,shutil,subprocess,sys
from pathlib import Path
from decimal import Decimal as D
import yaml
w=Path.cwd();sys.path.insert(0,str(w))
from scripts import qd_ed_final_runner as r, qd_ed_n36_contract as c
base=w.parent/'autonomy_20261004';out=(base/'turns/001222').resolve()
def read(p):return json.loads(p.read_text())
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def verify(x):assert ref(Path(x['path']))['sha256']==x['sha256']
def write(p,v):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2)+'\n');t.replace(p)
now=datetime.datetime.now(datetime.timezone.utc);deadline=datetime.datetime.fromisoformat(c.DEADLINE.replace('Z','+00:00'))
ds=read(base/'driver-status.json');assert ds['turn']==1222
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for h in [ds['driver'],ds['process']]:
 a=Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(a[19])==h['start_ticks'] and a[0]!='Z'
assert not (base/'STOP').exists() and now<deadline
assert read(base/'turns/001221/receipt.json')['exit']==0
prior=read(base/'turns/001221/operational-summary.json')
for pid in (300761,292633,292634): assert not Path(f'/proc/{pid}').exists()
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert source==prior['source']
pr=base/'turns/001147/protocol-preparation'
plan=read(base/'turns/001219/runtime-input-repair/cpu-v1/runtime-candidate-v1/draft/plan.metadata-complete.draft.json')
protocol=plan['protocol'];accounting=plan['accounting'];verify(protocol);verify(accounting)
from scripts import qd_ed_n36_recovery as recovery
recovery.validate_protocol(plan)
approval=ref(base/'user-authorization-v1.json');assert approval['sha256']=='a8d4dfc38b1fd5e9895d5a78b8eab0d0334ef5cb2716ba6aeeb35a8140c5506c'
frozen=read(pr/'prospective-accounting-v1.json');ledgers={}
for name,x in frozen['ledger_prefixes'].items():
 p=w/'data'/name;b=p.read_bytes();assert len(b)>=x['bytes'] and hashlib.sha256(b[:x['bytes']]).hexdigest()==x['sha256'];ledgers[name]={**ref(p),'bytes':len(b),'prior_prefix_matches':True}
events=[json.loads(x) for x in (w/'data/attempt-ledger.jsonl').read_text().splitlines()];resources=[json.loads(x) for x in (w/'data/gpu-healthcheck-ledger.jsonl').read_text().splitlines()]
snap=r.budget_snapshot(events,resources);recovery.preserve_charge(events);assert snap['dispatched']==503;assert snap['running']==snap['gpu_healthcheck_inflight']==0
assert all(v[-1]['event'] in r.TERMINAL for v in r.event_groups(events).values())
margin=D('0.23357169027962');charge=D(str(snap['gpu_hours_consumed']))+margin;cap=D('53.08404692669838')+D(168);protected=sum(max(D(0),D(str(v))-D(str(snap['gpu_hours_by_bucket'][k]))) for k,v in c.CAPS['protected_gpu_hours'].items())
assert cap-charge-protected-D(21)>0 and (deadline-now).total_seconds()>=75600
recon={'schema':'n36-root-accounting-reconciliation-v1','at':now.isoformat(),'source':source,'approval':approval,'frozen_accounting':accounting,'protocol':protocol,'ledger_prefixes':ledgers,'snapshot':snap,'retained_margin_gpu_hours':str(margin),'conservative_charge_gpu_hours':str(charge),'effective_cap_gpu_hours':str(cap),'protected_remaining_gpu_hours':str(protected),'unprotected_after_full_21h':str(cap-charge-protected-D(21)),'attempts_after_all40':543,'bucket_after_max':{k:snap['by_bucket'][k]+c.LIMITS.get(k,0) for k in c.CAPS['buckets']},'cohort_arithmetic':'40*(1800+40)+1800+200=75600 seconds=21 hours; baseline10 development30 zero recovery attempts','remaining_wall_hours':(deadline-now).total_seconds()/3600,'full_cohort_wall_cap_fits_now':True,'reservation_created':False,'gpu_dispatch':False,'caps_increased':False,'historical_charges_unchanged':True,'n31_deadline_unchanged':'2026-10-10T17:42:00Z','note':'Allocation only. Current device/provider readiness and detached release required before any GPU operation; CPU runtime review is not execution proof.'}
write(out/'accounting-reconciliation-v1.json',recon)
next_action='Obtain detached N36R1 production review using turn1222 budget authority and turn1219 CPU verified candidate. Establish current official provider readiness and verify accounted reusable CUDA/EGL proof. Then freeze ready runtime, rebind runtime closure/controller/all40 manifests, create detached N36 release and run complete public validation before single-worker dispatch. N36R1 accounting adopted in turn1222; do not repeat CPU preparation or accounting absent a changed ledger/defect. Preserve RT-03/04 live obligations.'
with open(w/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 sp=w/'research-state.yaml';cp=w/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json'
 s=yaml.safe_load(sp.read_text());checkpoint=read(cp);tree=read(tp)
 assert s.get('active_controller') is None and checkpoint.get('active_controller') is None
 assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
 assert s['budget_snapshot']==snap and r.authorized_gpu(s)==7
 verify(s['n36r1_runtime_input_repair']['report'])
 for x in ledgers.values():verify(x)
 for f in [sp,cp,tp]:shutil.copyfile(f,out/(f.name+'.before'))
 amendment={'approval':approval,'prospective_accounting':accounting,'pre_release_accounting':ref(out/'accounting-reconciliation-v1.json'),'history_boundary':{'dispatched':503,'conservative_gpu_hours':float(charge)},'scope':'N36R1 fresh all40 Dev only, 21 GPU hours including bounded healthchecks; zero automatic recovery; cumulative caps and protected reserves unchanged.'}
 authority={'schema':'n36-budget-authority-v1','approved':True,'cohort':c.RECOVERY_COHORT,'limits':c.LIMITS,'caps':c.CAPS,'validation_authorized':False,'formal_authorized':False,'coordinator_ends_at':c.DEADLINE,'automatic_recoveries':0,'protocol':protocol,'accounting':accounting,'starts_at':now.isoformat(),'weekly_window':{'ends_at':c.DEADLINE,'origin_gpu_hours':53.08404692669838,'increment_gpu_hours':168.0},'approval_basis':approval,'ledger_prefixes':ledgers,'previous_amendment':s['budget']['amendment'],'amendment':accounting}
 recovery.validate_authority(plan,authority)
 write(out/'budget-authority-v1.json',authority);ar=ref(out/'budget-authority-v1.json')
 adoption={'schema':'n36-accounting-adoption-v1','at':now.isoformat(),'authority':ar,'reconciliation':ref(out/'accounting-reconciliation-v1.json'),'previous_budget_authority':s.get('n36_budget_authority'),'source':source,'dispatch_authorized':False,'reservation_created':False,'target_met':False}
 write(out/'accounting-adoption-v1.json',adoption)
 s['budget']['amendment']=amendment
 for obj in [s,checkpoint]:obj.update(n36r1_budget_authority=ar,n36r1_accounting_adoption=ref(out/'accounting-adoption-v1.json'),status='N36R1_ACCOUNTING_ADOPTED_PRODUCTION_RELEASE_PENDING',phase='N36R1_ACCOUNTING_ADOPTED_PRODUCTION_RELEASE_PENDING',next_action=next_action,updated_at=now.isoformat())
 tree['nodes']['15.6'].update(accounting_adoption=ref(out/'accounting-adoption-v1.json'),result='CPU_RUNTIME_REVIEW_PASS_ACCOUNTING_ADOPTED_NO_GPU_RELEASE',score=None)
 tmp=sp.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(sp);write(cp,checkpoint);write(tp,tree)
summary={'schema':'autonomy-bounded-operation-summary-v1','at':now.isoformat(),'source':source,'driver':ds['driver'],'coordinator':ds['process'],'live_handles':{},'active_controller':None,'ledger_prefixes':ledgers,'retained_attempts':503,'retained_gpu_hours':snap['gpu_hours_consumed'],'new_gpu_dispatches':0,'completed':'Verified current identity/normal prior exit, ledger accounting and exact protocol; adopted finite N36R1 allocation with arithmetic and preserved prior amendment. No runtime readiness flag, GPU reservation or release created.','accounting_adoption':ref(out/'accounting-adoption-v1.json'),'next_action':next_action,'unresolved':['Current provider and reusable CUDA/EGL readiness','Frozen rebound runtime and detached release','RT-03/04 actual live receipts and whole-episode audits','Original validation/formal/required ablation evidence'],'stop_present':False,'deadline':c.DEADLINE,'target_met':False}
write(out/'operational-summary.json',summary)
(out/'operational-summary.md').write_text(f'Source {source}. Driver {ds["driver"]["pid"]} / coordinator {ds["process"]["pid"]} boot/start identities verified; no active experiment controller or GPU worker.\n\nAdopted finite N36 accounting: 40 fresh Dev cells, 21 GPU-hour cap, zero automatic recovery. Retained 503 attempts / 75.26779409697457 GPU hours plus admission margin; ledgers unchanged and protected reserves intact. No GPU dispatch or runtime release.\n\nNext: {next_action}\n\nActual live audit evidence and original validation/formal/ablation completion remain unresolved. Goal not complete.\n')
print(json.dumps({'adoption':ref(out/'accounting-adoption-v1.json'),'arithmetic':recon,'next_action':next_action},indent=2))

(out/'operational-summary.sha256').write_text(hashlib.sha256((out/'operational-summary.json').read_bytes()).hexdigest()+'  operational-summary.json\n')
