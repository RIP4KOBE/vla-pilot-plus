import pathlib,json,hashlib,datetime,subprocess,sys,shutil,yaml,numpy as np
root=pathlib.Path.cwd();out=(root.parent/'autonomy_20261004/turns/000877').resolve();sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as runner
def read(p):return json.loads(pathlib.Path(p).read_text())
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 q=p.with_suffix(p.suffix+'.tmp');q.write_text(json.dumps(d,indent=2)+'\n');q.replace(p)
prev=read(out.parent/'000876/mechanism-comparison-v1.json');d=read(out/'native-mechanism-extraction-v1.json');driver=read(root.parent/'autonomy_20261004/driver-status.json');assert driver['turn']==877
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip();handles=[]
for k in ['driver','process']:
 h=driver[k];f=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(f[19])==h['start_ticks'];handles.append(dict(h,observed_state=f[0]))
assert not pathlib.Path('/proc/2303352').exists();assert read(out.parent/'000876/receipt.json')['exit']==0
plan=read(out.parent/'000861/plan.frozen-v1.json');assert not pathlib.Path(plan['stop_path']).exists();now=datetime.datetime.now(datetime.timezone.utc);assert now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert source==prev['source']
matched=0
for t in d['tasks']:
 for dec in t['decisions']:
  if 'decoded_first8_actions' not in dec:continue
  a=np.array(dec['decoded_first8_actions'])
  for x in t['executed_actions']:
   if x['decision_id']==dec['decision_id']:assert np.allclose(a[x['step']-dec['step']],x['action'],rtol=0,atol=1e-7);matched+=1
assert matched==50
next_step='Read current Idea Tree constraints then Arbor ideation gate. Evaluate a bounded observation-conditioned closure-persistence hypothesis against existing N31/N34 history: task6 closed at536 then reopened at544, but no measured grasp proof. Freeze a falsifiable Dev protocol and independent executor review before any new source/release; no replay of N34 or protected evaluation. Avoid further broad retrospective audit unless needed to resolve this specific hypothesis.'
findings=['Task5 steps0/8/16: no direct selected proposal content. Step16 has possible indirect content ancestry through parent allocation; original archive occurrence ancestry and causal effect remain unproved.','Task6 step536 executed eight +1 gripper commands; next chunk544 executed eight -1 commands. Observed jaw qpos separation at536/544/552 was approximately0.078475/0.021829/0.059152m. This supports close/reopen behavior, not successful capture.','Task6 tracked target z at528/536/544 was0.048835/0.079480/0.050438m. Tracker changes are not privileged object motion or grasp evidence. All50 sampled pre-reset outcomes lack contemporaneous_target_pose.','All50 sampled executed actions match their decoded chunk positions at absolute tolerance1e-7. Selected content/possible ancestry are diagnostic only; no promotion or completion.']
r={'schema':'n34-native-mechanism-root-review-v1','at':now.isoformat(),'source':source,'handles':handles,'controller_absent':2303352,'controller_status':ref(out.parent/'000861/controller-status-v1.json'),'prior_turn_completed':True,'STOP_absent':True,'authorization_end':'2026-10-11T11:13:13Z','extraction':ref(out/'native-mechanism-extraction-v1.json'),'extractor':ref(out/'extract.py'),'action_linkage_matches':matched,'findings':findings,'next_step':next_step,'target_met':False,'new_dispatch':False,'validation_authorized':False,'formal_authorized':False,'ledger_prefixes':prev['ledger_prefixes']}
with runner.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
 with runner.locked(root/'data/qd-ed-state.lock'):
  for n,v in prev['ledger_prefixes'].items():
   b=(root/'data'/n).read_bytes();assert len(b)==v['bytes'] and hashlib.sha256(b).hexdigest()==v['sha256']
  write(out/'native-mechanism-review-v1.json',r);rr=ref(out/'native-mechanism-review-v1.json')
  sp=root/'research-state.yaml';cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json'
  for p in [sp,cp,tp]:shutil.copyfile(p,out/(p.name+'.before'))
  s=runner.read_state(sp);c=read(cp);t=read(tp)
  for obj in [s,c]:obj.update(n34_dev_native_mechanism=rr,next_action=next_step,updated_at=now.isoformat())
  t['nodes']['15.4']['native_mechanism_review']=rr;t['nodes']['15.4']['insight']+=' Native bounded extraction: task5 step16 possible indirect proposal-content ancestry; task6 closes536 then reopens544 with measured jaw response. No grasp proof or promotion. All50 sampled actions linked to decoded chunks.'
  q=sp.with_suffix('.tmp');q.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));q.replace(sp);write(cp,c);write(tp,t)
  write(out/'diagnosis-adoption-v1.json',{'review':rr,'state':ref(sp),'checkpoint':ref(cp),'tree':ref(tp),'no_new_dispatch':True})
(out/'operational-summary.md').write_text(f'''Turn877 — {now.isoformat()}\n\nSource {source} unchanged. Live driver268073/start97715947 and coordinator2410857/start140259530 verified on boot {boot}; controller2303352 absent, terminal NUMERIC_FUTILITY_NO_PROMOTION reconciled in turn875. Turn876 exited normally. STOP absent; authorization ends2026-10-11T11:13:13Z. No GPU dispatch, source edits or protected results read.\n\nCompleted hash-verified bounded Dev task5 steps0–24 and task6 steps528–552 extraction. All50 sampled executed actions match decoded chunks. Task5 step16 has possible indirect proposal-content ancestry, not original-occurrence or causal proof. Task6 closes536–543 then reopens544–551; measured jaw separation follows. Tracked target changes do not prove capture; contemporaneous target poses absent. Review: native-mechanism-review-v1.json.\n\nAll ledger prefixes unchanged:474 attempts,69.99568238388729 GPUh; history and protected reserves retained.\n\nNext bounded step: {next_step}\n\nOriginal validation/formal/required ablation goal remains unmet; no completion record.\n''')
print(json.dumps({'review':rr,'matched_actions':matched,'next_step':next_step}))
