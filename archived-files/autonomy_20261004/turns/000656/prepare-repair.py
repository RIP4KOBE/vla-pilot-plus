import pathlib,json,hashlib,datetime,subprocess,yaml,shutil
root=pathlib.Path.cwd();base=root.parent;out=(base/'autonomy_20261004/turns/000656').resolve();v=(base/'variants/n34_observed_jaw_approach/recovery5-identity-repair-v1').resolve();old=v.parent/'recovery4-identity-repair-v1';wt=v.parent/'production_worktree'
def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def put(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def handle(pid):
 p=pathlib.Path(f'/proc/{pid}/stat');s=p.read_text().split(') ',1)[1].split() if p.exists() else None
 return {'pid':pid,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':int(s[19]) if s else None,'state':s[0] if s else 'ABSENT'}
now=datetime.datetime.now(datetime.timezone.utc);driver=json.loads((base/'autonomy_20261004/driver-status.json').read_text());authority=json.loads((base/'autonomy_20261004/user-authorization-v1.json').read_text());assert now<datetime.datetime.fromisoformat(authority['continuous_window']['end_utc'].replace('Z','+00:00'));assert not (base/'autonomy_20261004/STOP').exists();assert driver['turn']==656
for h in [driver['driver'],driver['process']]:
 actual=handle(h['pid']);assert all(actual[k]==h[k] for k in ['pid','boot_id','start_ticks'])
s=yaml.safe_load((root/'research-state.yaml').read_text());assert s['active_controller'] is None;assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
prior=json.loads((out.parent/'000655/runtime-inventory-review-v1.json').read_text());prefixes={}
for n,prefix in prior['ledger_prefixes'].items():
 b=(root/'data'/n).read_bytes();assert len(b)==prefix['bytes'] and hashlib.sha256(b).hexdigest()==prefix['sha256'];prefixes[n]=prefix
assert json.loads((out.parent/'000655/receipt.json').read_text())['status']=='completed_turn'
for pid in [743485,746235,718852,718853]:assert handle(pid)['state']=='ABSENT'
assert subprocess.check_output(['git','-C',str(wt),'status','--porcelain'],text=True)==''
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();executor_source=subprocess.check_output(['git','-C',str(wt),'rev-parse','HEAD'],text=True).strip();assert source==s['source_commit']=='e52618ee42c656d83f50178a3f47b7e25225f68d'
put(out/'entry-reconciliation-v1.json',{'at':now.isoformat(),'source':source,'executor_source':executor_source,'prior_turn_completed':True,'active_controller':None,'ledger_prefixes':prefixes,'driver_stop_present':False,'deadline':authority['continuous_window']['end_utc'],'handles':{str(pid):handle(pid) for pid in [268073,782895,743485,746235,718852,718853]}})
assert not v.exists();v.mkdir()
a=json.loads((old/'authority-v1.json').read_text());a.update(schema='n34r5-recovery-identity-repair-authority-v1',at=now.isoformat(),owning_source=source,executor_source=executor_source,cohort='N34R5_OBSERVED_JAW_APPROACH_DEV_20261008',terminal_closure=ref(out.parent/'000654/terminal-closure-v1.json'),runtime_preparation=ref(out.parent/'000655/runtime-inventory-review-v1.json'),fresh_identity_format='n34r5_dev_t{task_id:02d}_{profile.lower()}_20261008',ledger_prefixes=prefixes)
a['replacement']={'old_episode_key':'n34r4_dev_t00_c0_20261008','new_episode_key':'n34r5_dev_t00_c0_20261008','budget_bucket':'recovery'}
b=s['budget_snapshot'];a['history_snapshot']={k:b[k] for k in ['dispatched','gpu_hours_consumed','by_bucket']};pr={'validation':32-b['gpu_hours_by_bucket']['validation'],'formal':12-b['gpu_hours_by_bucket']['formal']};unprotected=224-b['gpu_hours_consumed']-sum(pr.values());caps=a['caps_unchanged']['buckets'];mapping=a['bucket_mapping']
a['arithmetic']={'remaining_attempts':1800-b['dispatched'],'after_max_total_attempts':b['dispatched']+30,'after_max_gpu_hours':b['gpu_hours_consumed']+5,'remaining_by_bucket':{k:caps[k]-b['by_bucket'][k] for k in caps},'after_max_by_bucket':{k:b['by_bucket'][k]+mapping.get(k,0) for k in caps},'protected_gpu_hours_remaining':pr,'unprotected_gpu_hours_remaining':unprotected,'unprotected_gpu_hours_after_max':unprotected-5}
assert a['arithmetic']['after_max_total_attempts']==477 and unprotected>5
put(v/'authority-v1.json',a)
prompt=(old/'executor-prompt-v1.txt').read_text()
import re
mapping={'recovery4-identity-repair-v1':'recovery5-identity-repair-v1','N34R4':'N34R5','N34R3':'N34R4','n34r4_dev_':'n34r5_dev_','n34r3_dev_':'n34r4_dev_','turn644':'turn654','turn645':'turn655','missing torch.utils.serialization runtime coverage':'missing lazy OpenGL conversion-handler runtime coverage'}
prompt=re.sub('|'.join(map(re.escape,sorted(mapping,key=len,reverse=True))),lambda x:mapping[x[0]],prompt)
prompt=prompt.replace('All invalid N34, N34R1, N34R2 and N34R4','All invalid N34, N34R1, N34R2, N34R3 and N34R4')
(v/'executor-prompt-v1.txt').write_text(prompt)
shutil.copyfile(old/'executor-launch-v1.py',v/'executor-launch-v1.py')
print(json.dumps({'authority':ref(v/'authority-v1.json'),'arithmetic':a['arithmetic'],'output':str(v)}))
