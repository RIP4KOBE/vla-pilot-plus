import json,pathlib,hashlib,datetime,fcntl,yaml,subprocess
root=pathlib.Path.cwd();base=root.parent/'autonomy_20261004';out=(base/'turns/001199').resolve();cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
validation=json.loads((out/'public-release-validation-v2.json').read_text());assert validation['status']=='PASS',validation
now=datetime.datetime.now(datetime.timezone.utc).isoformat();ds=json.loads((base/'driver-status.json').read_text());assert ds['turn']==1199
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for h in [ds['driver'],ds['process']]:
 a=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(a[19])==h['start_ticks'] and a[0]!='Z'
ready=json.loads((base/'turns/001198/runtime-readiness-review-v1.json').read_text())
for x in ready['ledger_prefixes'].values():assert ref(pathlib.Path(x['path']))['sha256']==x['sha256']
next_action='Adopt turn1199 PASS public-release-validation-v2 and exact plan.frozen-v2/execution-release-v2 under runner/state locks, verify contiguous admission and no live handles, launch one N36 controller through frozen qd_ed_n36_bootstrap.py (runner requires source_execution.active; do not call runner.launch from an unbootstrapped wrapper). Preserve controller PID/boot/start and status/result before release of parent start gate. Monitor RT-03/04 live audits; zero automatic recovery.'
with open(root/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 s=yaml.safe_load((root/'research-state.yaml').read_text());ck=json.loads(cp.read_text());tree=json.loads((cp.parent/'idea_tree.json').read_text())
 assert s['active_controller'] is None and ck['active_controller'] is None and not s['current_owned_workers']
 for d in [s,ck]:d.update(n36_runtime_rebinding=ref(out/'runtime-rebinding-review-v1.json'),n36_public_release_validation=ref(out/'public-release-validation-v2.json'),phase='N36_PUBLIC_RELEASE_VALIDATED_ADOPTION_PENDING',next_action=next_action,updated_at=now)
 tree['nodes']['15.6'].update(result='PUBLIC_RELEASE_VALIDATION_PASS_ADOPTION_PENDING',public_release_validation=ref(out/'public-release-validation-v2.json'),score=None)
 p=root/'research-state.yaml';tmp=p.with_name(p.name+'.tmp');tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(p);write(cp,ck);write(cp.parent/'idea_tree.json',tree)
summary={'schema':'autonomy-bounded-operation-summary-v1','at':now,'source':s['source_commit'],'driver':ds['driver'],'coordinator':ds['process'],'live_handles':{},'active_controller':None,'ledger_prefixes':ready['ledger_prefixes'],'completed':'Rebound readiness runtime into reviewed closure/controller evidence and all40 manifests. Retained failed v1 release validation (missing generic root metadata); separately corrected only inventory/seed/input-label metadata, v2 full public release validation PASS. No GPU dispatch or new charge.','release_validation':ref(out/'public-release-validation-v2.json'),'next_action':next_action,'unresolved':['Locked release adoption and single bootstrapped controller launch','RT-03/04 live native/controller/episode audit obligations','Original validation/formal/required ablation evidence'],'target_met':False,'stop_present':(base/'STOP').exists(),'deadline':'2026-10-11T11:13:13Z'}
write(out/'operational-summary.json',summary)
(out/'operational-summary.md').write_text(f"Source {s['source_commit']}. Driver {ds['driver']['pid']} / coordinator {ds['process']['pid']} boot/start verified. No live experiment controller or GPU worker. Prior turn normal; ledger retained at 502 attempts.\n\n{summary['completed']}\n\nNext: {next_action}\n\nOriginal validation/formal/ablation goal remains unproved. No completion record.\n")
print(json.dumps({'phase':s['phase'],'summary':ref(out/'operational-summary.json')}))
