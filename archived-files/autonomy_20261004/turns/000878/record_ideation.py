import pathlib,json,hashlib,datetime,subprocess,sys,shutil,yaml
w=pathlib.Path.cwd();out=(w.parent/'autonomy_20261004/turns/000878').resolve();sys.path.insert(0,str(w));from scripts import qd_ed_final_runner as runner
def read(p):return json.loads(pathlib.Path(p).read_text())
def ref(p):return dict(path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def write(p,d):
 q=p.with_suffix('.tmp');q.write_text(json.dumps(d,indent=2)+'\n');q.replace(p)
now=datetime.datetime.now(datetime.timezone.utc);driver=read(w.parent/'autonomy_20261004/driver-status.json');assert driver['turn']==878
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip();handles=[]
for k in ['driver','process']:
 h=driver[k];f=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(f[19])==h['start_ticks'];handles.append(dict(h,observed_state=f[0]))
assert not pathlib.Path('/proc/2303352').exists();assert read(out.parent/'000877/receipt.json')['exit']==0
assert now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
plan=read(out.parent/'000861/plan.frozen-v1.json');assert not pathlib.Path(plan['stop_path']).exists();assert not (w.parent/'autonomy_20261004/STOP').exists()
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert source=='969d5fb57c90f61dfc93331346f0ea8158f4eaf1'
prior=read(out.parent/'000877/native-mechanism-review-v1.json')
constraints=subprocess.check_output(['python','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py','view','--cwd',str(w),'--run-name','rdt-qd-ed-final-20260921T093925Z','--format','constraints'],text=True);(out/'tree-constraints.txt').write_text(constraints)
design='''# N35 closure-intent proposal memory — CPU feasibility registration

This is a new hypothesis, not a released GPU protocol. Existing N34 source, results and gates remain unchanged. Only exposed Dev evidence may be used. No validation/formal access.

PROBE BLOCK
Q1 First principles: loss of action intent across replanning boundaries. Turn877 task6 executes +1 at536–543 then -1 at544–551 with measured jaw closure/reopening; turn876 task6 had30/44 direct proposal-content selections yet failed. These support a control-state failure hypothesis, not grasp causation.
Q2 Hidden assumption: the current observation and archive alone retain useful closure intent. Dropping it permits an explicitly expiring memory of a physically executed close event.
Q3 Elephant: tracked target proximity and jaw closure are not contact or grasp labels; persisting a false closure can worsen performance.
Q4 Hamming: yes, temporarily preserving an otherwise discarded physical action intent is a meaningful class-level planning question; only task success can support efficacy.

Four moves considered:
- Assumption inversion: one-boundary closure-intent memory as an ordinary QD competitor (selected).
- Backward from success: contact-confirmed lift option; defer because present evidence lacks a reliable nonprivileged contact signal and it combines another intervention.
- Analogical transfer: hysteretic forced gripper latch; reject because forced execution bypasses ordinary QD/ED selection and obscures the original goal.
- Failure reverse engineering: rescue all closed archive candidates; reject as N24-style within-search retention without a new counter.

Survivor declaration:
1. Assumption challenged: useful intent must be reconstructed independently every chunk.
2. Mechanism class: planning/control state in QD proposal generation.
3. Mechanism and hypothesis: one expiring close-intent competitor may reduce immediate reopening because actual execution and jaw response establish a prior action event; test fresh matched Dev success and native selection/execution, not jaw motion alone.
4. Orthogonality: N31/N32 forecast entry within a chunk; N33/N34 use present geometry. N30 shifts a previous winner after approach progress. N35 retains only closure intent after actual full-prefix execution, does not replay or shift a prior trajectory, and leaves ordinary quality/ED unchanged.
5. Conflicts: N24 and N30 failed; this does not infer that memory generally works. It specifically tests the previously unrepresented executed close event. N34's task5 success has no direct selected proposal and is not evidence for this change.
Self-check: not a scalar tuning change, prompt tweak or increased compute; falsifiable discrete state with explicit expiry and negative outcomes. No claim of novelty beyond local mechanism distinction.

CPU contract (frozen before reading additional native fields):
Use only N34 Dev task6 contexts/decisions/actions already bound by turn877 extraction, steps528–552. At boundary544, eligibility requires (a) prior guided536 chunk with direct selected content equal to its observed_close_dwell proposal, (b) all eight executed gripper commands positive and identity-linked, (c) same recognized target and same Stage between536 and544 with guidance enabled at544, and (d) finite measured jaw separation strictly decreased across the boundary. Any missing required field is Unknown, not eligible. Do not substitute ancestry, tracker motion or commanded closure for these requirements.
If eligible, define a single-use memory for boundary544 only. In the ordinary offspring replacement slot, copy the current ordinary archive best and replace only its first-eight gripper commands with native +1; leave translations/rotations/later actions untouched. It competes with the other15 unchanged candidates under unchanged scoring/archive/ED selection. It does not force action execution, add model calls or persist through unguided steps. Expire after that boundary regardless of selection; no rearming from a memory-generated closure. Reset on episode/target/Stage change or incomplete execution. Existing N34 current-observation proposal is the fallback when memory is ineligible; the memory proposal replaces that same slot when eligible, never adds a slot.
CPU feasibility must establish all trigger fields, identity linkage, one nonidentical native proposal, and an executable production hook without protected inputs. Any absent trigger, missing provenance, identical proposal, or unresolvable source ambiguity rejects this exact design; no threshold/gate relaxation using task6. CPU result never demonstrates task gain.

Before implementation: independent CPU executor review must assess these gates and exact source hook, including whether repeated parent rounds can consume one boundary memory consistently without changing total proposal count. Coordinator does not edit benchmark code.
Before GPU: separate immutable prospective Dev protocol with fresh matched C0/Q0/N34/N35 controls, task/seed identities, success/futility gates at least as strict as retained necessary5/10 and >=controls, full cost/native audits, finite budget arithmetic and protected reserves. Exact counts/order/cap/deadline must be frozen and reviewed before dispatch. No reuse of old controls as fresh evidence. Current registration authorizes no GPU execution or scientific promotion.
'''
(out/'n35-cpu-hypothesis-v1.md').write_text(design)
hyp='Mechanism: N35 one-boundary executed-closure intent memory supplies one ordinary QD offspring competitor with a positive gripper prefix.\nHypothesis: Retaining closure intent only after identity-valid execution and measured jaw response may prevent immediate reopening without forcing selection or replaying a prior trajectory.\nObservable: First pass a frozen Dev-only CPU eligibility/native-change gate; then separately preregister fresh matched Dev task gains and complete native audits, never infer grasp from closure.\nConflicts: N24 closed-parent rescue and N30 shifted-winner continuity failed; this stores an expiring executed closure event and modifies only current-plan gripper commands, with strict rejection if the proposed trigger is unsupported.'
next_step='Independent CPU feasibility review of N35 node15.5 using turn878 frozen CPU contract and only turn877-bound Dev task6 steps528–552; verify all trigger fields, current source hook and native-byte difference. Reject if Unknown/ineligible; no GPU or benchmark implementation before review. If feasible, freeze complete matched Dev protocol and executor implementation/audit scope before source changes.'
with runner.locked(w/'data/qd-ed-runner.lock',nonblocking=True):
 with runner.locked(w/'data/qd-ed-state.lock'):
  for n,v in prior['ledger_prefixes'].items():
   b=(w/'data'/n).read_bytes();assert len(b)==v['bytes'] and hashlib.sha256(b).hexdigest()==v['sha256']
  sp=w/'research-state.yaml';cp=w/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json'
  for p in [sp,cp,tp]:shutil.copyfile(p,out/(p.name+'.before'))
  t=read(tp);assert '15.5' not in t['nodes']
  result=subprocess.check_output(['python','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py','add','--cwd',str(w),'--run-name','rdt-qd-ed-final-20260921T093925Z','--parent-id','15','--hypothesis',hyp],text=True);(out/'tree-add.txt').write_text(result)
  t=read(tp);assert t['nodes']['15.5']['hypothesis']==hyp
  record=dict(schema='n35-cpu-ideation-registration-v1',at=now.isoformat(),source=source,handles=handles,controller_absent=2303352,prior_turn_completed=True,STOP_absent=True,authorization_end='2026-10-11T11:13:13Z',constraints=ref(out/'tree-constraints.txt'),design=ref(out/'n35-cpu-hypothesis-v1.md'),evidence=ref(out.parent/'000877/native-mechanism-review-v1.json'),ledger_prefixes=prior['ledger_prefixes'],node_id='15.5',next_step=next_step,new_dispatch=False,target_met=False,gpu_authorized=False)
  write(out/'n35-registration-v1.json',record);rr=ref(out/'n35-registration-v1.json')
  s=runner.read_state(sp);c=read(cp)
  for obj in [s,c]:obj.update(n35_cpu_ideation=rr,next_action=next_step,updated_at=now.isoformat())
  t['nodes']['15.5'].update(registration=rr,execution_authorized=False,result='CPU_FEASIBILITY_PENDING_NO_GPU_RELEASE')
  q=sp.with_suffix('.tmp');q.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));q.replace(sp);write(cp,c);write(tp,t)
  write(out/'ideation-adoption-v1.json',dict(registration=rr,state=ref(sp),checkpoint=ref(cp),tree=ref(tp)))
(out/'operational-summary.md').write_text(f'Turn878 — {now.isoformat()}\n\nSource {source}; scientific source1065f38122379a515b60a9a424f574330405b66f unchanged. Live driver268073/start97715947 and coordinator2419793/start140290578 verified on boot {boot}. Old controller2303352 absent, terminal closure already reconciled; no owned worker/executor. Prior turn877 completed normally. STOP absent; authority ends2026-10-11T11:13:13Z.\n\nCompleted Arbor constraints/ideation gate and registered pending N35 node15.5 with frozen CPU eligibility/rejection contract and no GPU release. Closure intent is a hypothesis, not grasp evidence.\n\nLedger prefixes unchanged:474 attempts,69.99568238388729 GPUh. No code edits, new charges, protected result access or completion claim.\n\nNext: {next_step}\n\nUnresolved: trigger eligibility, source/native feasibility, causal efficacy, original validation/formal/required ablation evidence.\n')
print(json.dumps(rr))
