import json,hashlib,datetime,os
from pathlib import Path
BASE=Path(__file__).resolve().parent;TURNS=BASE.parent.parent;CPU=BASE/'cpu-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def ref(p):return {'path':str(p),'sha256':sha(p),'bytes':Path(p).stat().st_size}
def write(p,v):
 with (BASE/p).open('x') as f:json.dump(v,f,indent=2);f.write('\n')
a=read(BASE/'authority-v1.json');root=Path(a['implementation_worktree'])
assert not os.path.lexists(root.parent.parent.parent/'autonomy_20261004/STOP')
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-10T01:12:51+00:00')
m=read(BASE/'materialization-v1.json');inspection=read(BASE/'target-inspection-v1.json');checks=read(CPU/'checks-v1.json');all40=read(CPU/'all40-composition-v1.json');rv=read(CPU/'runtime-files-validation-v1.json')
assert not inspection['conflicts'] and all(c['status']=='PASS' for c in checks.values())
assert all40['all_pass'] and all40['actual']==40 and rv['status']=='PASS' and not read(CPU/'runtime-files-pending-v1.json')
candidate=ref(CPU/'runtime-candidate-v1/draft/plan.metadata-complete.draft.json');plan=read(candidate['path'])
assert plan['release_enabled'] is False and plan['frozen'] is False and plan['runtime_ready'] is False
old=read(TURNS/'001216/materialization-repair/report-v1.json');oldplan=read(old['candidate']['path'])
for k in ['protocol','accounting','limits','worker_contract','deadline','cohort','episodes','phase_authorization']:
 assert plan[k]==oldplan[k],k
preservation=read(BASE/'prior-preservation-and-bound-refs-v1.json')
for r in preservation['prior_artifacts']:assert sha(r['path'])==r['sha256']
for r in a['ledger_prefixes'].values():assert sha(r['path'])==r['sha256'] and Path(r['path']).stat().st_size==r['bytes']
assert read(CPU/'final-preservation-v1.json')['git_status']==''
changed=[r for r in m['files'] if not r['existed_before']]
write('changed-dependency-paths-v1.json',changed)
next_steps=read(TURNS/'001216/materialization-repair/root-next-commands-v1.json')
next_steps.update(schema='n36r1-runtime-input-repair-root-next-v1',candidate=candidate,dependency_source_materialization='COMPLETE: prior 537 retained; additional 148 regular files and 12 exact contained pinned symlinks restored',full_runtime_input_validation='PASS: all 3291 runtime file paths exist and SHA256/size match; this is CPU input validation only',remaining_prerequisites=next_steps['remaining_prerequisites'][1:])
next_steps['environment']={k:v.replace(str(TURNS/'001216/materialization-repair'),str(BASE)) for k,v in next_steps['environment'].items()}
next_steps['review_commands']=[['sha256sum',str(BASE/'report-v1.json'),candidate['path']],['git','--no-replace-objects','-C',str(root),'rev-parse','HEAD'],['git','--no-replace-objects','-C',str(root),'status','--porcelain'],['/home/hynx/miniconda3/envs/vla-pilot/bin/python3.12','-B',str(BASE/'verify-candidate-v1.py')]]
next_steps['environment'].update(GIT_OPTIONAL_LOCKS='0',GIT_NO_LAZY_FETCH='1')
write('root-next-commands-v1.json',next_steps)
limitations=['CPU file and configuration validation only; runtime_ready=false and native_readiness=false. No device/provider/controller execution or same-worker attestations.',*next_steps['remaining_prerequisites']]
report={'schema':'n36r1-runtime-input-repair-report-v1','node_id':'15.6','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'CPU_RUNTIME_INPUTS_VERIFIED_ALL40_COMPOSED_DISABLED','source':a['source'],'authority':ref(BASE/'authority-v1.json'),'worktree':str(root),'candidate':candidate,'release_enabled':False,'runtime_ready':False,'native_readiness':False,'frozen':False,'root_approval_granted':False,'budget_adopted':False,'scientific_success':False,'target_met':False,'materialization':{'count':len(changed),'regular_files':sum(r['mode']!='120000' for r in changed),'symlinks':sum(r['mode']=='120000' for r in changed),'payload_bytes':sum(r['bytes'] for r in changed),'pins':m['pins'],'conflicts':inspection['conflicts'],'all_targets_preflighted_before_copy':True,'changed_dependency_paths':changed,'evidence':ref(BASE/'materialization-v1.json'),'inspection':ref(BASE/'target-inspection-v1.json'),'strict_source_record':'PASS','source_count':m['source_count']},'runtime_input_validation':{'status':'PASS','count':rv['count'],'missing':[],'mismatches':[],'evidence':ref(CPU/'runtime-files-validation-v1.json'),'inventory_and_seed_bytes_unchanged':True},'all40':all40,'checks':checks,'source_record':ref(BASE/'source-record-v1.json'),'protocol':plan['protocol'],'accounting':plan['accounting'],'native_build':plan['native_build'],'runtime':plan['runtime'],'runtime_closure':plan['runtime_closure'],'controller_semantics':plan['controller_semantics'],'required_plan_metadata':{k:plan[k] for k in next_steps['required_metadata_after_success']},'preservation':read(CPU/'final-preservation-v1.json'),'prior_artifact_preservation':ref(BASE/'prior-preservation-and-bound-refs-v1.json'),'prior_LFS_scope_exception':old['prior_LFS_scope_exception'],'retained_original_charge_seconds':86.40354533703066,'readiness_limitations':limitations,'root_next_commands':ref(BASE/'root-next-commands-v1.json'),'current_scope':old['current_scope'],'elapsed_bound':{'started_at':'2026-10-10T00:42:51Z','finished_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cap_seconds':1800,'deadline':'2026-10-11T11:13:13Z'},'artifacts':[]}
for p in sorted(BASE.rglob('*')):
 if p.is_file() and p.suffix in ('.json','.py') and not p.name.startswith(('executor-','wrapper-')):report['artifacts'].append(ref(p))
write('report-v1.json',report)
md=f'''# Node 15.6 bounded CPU runtime-input repair

Status: **CPU_RUNTIME_INPUTS_VERIFIED_ALL40_COMPOSED_DISABLED**.

Authority and bound refs verified. Source remains `{a['source']}`; worktree clean. Complete preflight found no conflicts. Restored **{len(changed)}** dependency paths: **148 regular files and 12 exact Git symlinks**, all targets contained within LeRobot. Link texts, tree modes, blob IDs, resolved target blobs and unchanged inventory payload hashes are recorded in `target-inspection-v1.json`. No differing paths overwritten.

All **{rv['count']} runtime files** exist and match SHA256 and size. Strict unchanged source verification covers **{m['source_count']} files**. Existing unchanged preparation/composition implementation produced and reverified **40/40 actual manifests**, with required run/inventory/seed/identity metadata. Fresh disabled runtime, closure, controller and native bindings are included. Native binding inherits exact metadata/library bytes; it is not a device attestation.

Candidate: `{candidate['path']}`

Candidate SHA256: `{candidate['sha256']}`

Runtime SHA256: `{plan['runtime']['sha256']}`

Closure SHA256: `{plan['runtime_closure']['sha256']}`

Native SHA256: `{plan['native_build']['sha256']}`

Controller SHA256: `{plan['controller_semantics']['sha256']}`

Report SHA256: `{sha(BASE/'report-v1.json')}`

Every CPU check passed. Frozen protocol/accounting/thresholds and episode definitions are unchanged. Original invalid **86.40354533703066 GPU seconds** remain charged. Prior 77 recorded artifacts and both authority ledger hashes/lengths still match. The prior archive/LFS incident is retained verbatim in the JSON report; no archive, LFS, network or shared Git metadata writes were used in this repair.

**release_enabled=false; runtime_ready=false; native_readiness=false.** No scientific success is claimed. No source edits/commits, owning state writes, GPU, provider probes, controller runs or delegation occurred.

Root next steps: independently review the new bindings, reconcile full accounting and finite budget authority, obtain detached production review/release, and establish separately authorized same-worker device/provider/native/controller readiness. Recompose dependent bindings if readiness changes. Validation/formal/ablation remain unauthorized. Exact prospective review commands and prerequisites are in `root-next-commands-v1.json`.

Per-path hashes and all40 manifest/config hashes are in `report-v1.json`; full CPU runtime evidence is in `cpu-v1/runtime-files-validation-v1.json`.
'''
with (BASE/'report-v1.md').open('x') as f:f.write(md)
write('report-digests-v1.json',{'reports':[ref(BASE/'report-v1.json'),ref(BASE/'report-v1.md')]})
print(json.dumps({'status':report['status'],'candidate':candidate,'changed':len(changed),'runtime_files':rv['count'],'manifests':all40['actual'],'release_enabled':False}))
