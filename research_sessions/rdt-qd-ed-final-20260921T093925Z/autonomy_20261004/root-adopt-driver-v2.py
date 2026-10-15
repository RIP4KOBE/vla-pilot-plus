from pathlib import Path
import ast,datetime,fcntl,hashlib,importlib.util,json,os,subprocess,yaml
A=Path(__file__).resolve().parent;W=A.parent/'study_worktree';unit='arbor-rdt-qd-ed-20261004.service'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def read(p):return json.loads(Path(p).read_text())
def mod(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
d=mod('driver_v2',A/'driver_v2.py');a=mod('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py')
manifest=read(A/'driver-v2-delivery-manifest.json');assert sha(A/'driver-v2-delivery-manifest.json')=='17bbe3836362853dcec3324262d6f2847faeee3008ac6ef9944aeeaecdbc91a4'
for f in manifest['files']:
 p=Path(f['path']);assert p.parent==A and p.stat().st_size==f['bytes'] and sha(p)==f['sha256']
old=(A/'driver_v1.py').read_text();new=(A/'driver_v2.py').read_text()
assert new==old.replace("    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):env[key]='2'\n",'').replace('    os.sched_setaffinity(0,{0,1})\n','')
assert read(A/'cpu-driver-v2-threads-resource.json')['guard_clean'] is True
props=subprocess.check_output(['systemctl','--user','show',unit,'-p','ActiveState','-p','MainPID','-p','CPUAffinity','-p','AllowedCPUs','-p','CPUQuotaPerSecUSec'],text=True)
assert 'ActiveState=inactive' in props and 'MainPID=0' in props and 'CPUAffinity=\n' in props and 'CPUQuotaPerSecUSec=infinity' in props
assert read(A/'active-turn.json')['closed'] is True
lease=d.Lease(A/'coordinator.lease');assert lease.acquire()
try:
 now=datetime.datetime.now(datetime.timezone.utc).isoformat()
 review={'schema':'autonomy-root-driver-v2-adoption-v1','recorded_at':now,'decision':'ACCEPT','delivery':ref(A/'driver-v2-delivery-manifest.json'),'prior_review':ref(A/'root-review-v1.json'),'prior_release':ref(A/'release-v1.json'),'driver':ref(A/'driver_v2.py'),'network_amendment':ref(A/'root-service-network-amendment-v1.json'),'CPU_amendment':ref(A/'root-cpu-environment-amendment-v1.json'),'source_delta_exactly_two_production_restriction_removals':True,'three_focused_tests_passed':True,'prior_successful_official_turns':[ref(A/'turns/000002/receipt.json'),ref(A/'turns/000003/receipt.json')],'service_limits_unset':True,'live_N31_scientific_controller_unchanged':True}
 d.atomic(A/'root-driver-v2-adoption-v1.json',review)
 hand=read(A/'handoff-v1.json');hand.update(recorded_at=now,supersedes=ref(A/'handoff-v1.json'),operational_amendments=[ref(A/'root-driver-v2-adoption-v1.json')],current_release_scope='N31 scientific release unchanged; local coordinator now uses operational driver_v2 and release-v2. Two successful official coordinator turns already verified continuation. First transport error retained and proxy corrected. Root transfers coordinator lease again after this maintenance.')
 d.atomic(A/'handoff-v2.json',hand)
 release=read(A/'release-v1.json');release.update(driver=ref(A/'driver_v2.py'),handoff=ref(A/'handoff-v2.json'),root_review=ref(A/'root-driver-v2-adoption-v1.json'),recorded_at=now,supersedes=ref(A/'release-v1.json'))
 d.atomic(A/'release-v2.json',release);d.validate_release(A/'release-v2.json')
 drop=A/'service-driver-v2.conf';drop.write_text('[Service]\nExecStart=\nExecStart=/home/hynx/miniconda3/envs/vla-pilot/bin/python -I -B '+str(A/'driver_v2.py')+' --release '+str(A/'release-v2.json')+'\n')
 link=Path('/home/hynx/.config/systemd/user')/(unit+'.d')/'20-driver.conf';assert not link.exists();link.symlink_to(drop)
 subprocess.run(['systemctl','--user','daemon-reload'],check=True,timeout=30)
 subprocess.run(['systemctl','--user','start',unit],check=True,timeout=30)
 props=subprocess.check_output(['systemctl','--user','show',unit,'-p','ActiveState','-p','SubState','-p','MainPID','-p','UnitFileState'],text=True)
 assert 'ActiveState=active' in props and 'SubState=running' in props
 record={'schema':'autonomy-root-service-activation-v2','recorded_at':now,'release':ref(A/'release-v2.json'),'handoff':ref(A/'handoff-v2.json'),'service':ref(A/unit),'dropins':[ref(A/'service-network-v1.conf'),ref(drop)],'service_properties':props,'driver_start_waits_for_root_lease':True,'target_met':False}
 d.atomic(A/'root-service-activation-v2.json',record)
 run='rdt-qd-ed-final-20260921T093925Z';cpfile=W/'.arbor/sessions'/run/'.coordinator/checkpoint.json'
 with (W/'data/qd-ed-state.lock').open('a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  with a.state_lock(W,run):
   s=yaml.safe_load((W/'research-state.yaml').read_text());cp=read(cpfile);tree=a.load_tree(W,run)
   item=s['local_autonomous_coordinator'];item.update(status='SERVICE_ACTIVE_V2_HANDOFF_ON_ROOT_LEASE_RELEASE',release=ref(A/'release-v2.json'),handoff=ref(A/'handoff-v2.json'),activation=ref(A/'root-service-activation-v2.json'))
   cp['local_autonomous_coordinator']=item;tree['meta']['local_autonomous_coordinator']=item
   s['updated_at']=cp['updated_at']=now
   temp=W/'research-state.yaml.driver-v2-tmp'
   with temp.open('x') as f:yaml.safe_dump(s,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
   os.replace(temp,W/'research-state.yaml');d.atomic(cpfile,cp);a.save_tree(W,run,tree)
 print(json.dumps({'activated':True,'release':ref(A/'release-v2.json'),'service_properties':props}))
finally:lease.close()
