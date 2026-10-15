"""Actual v2 copied-archive validation; refuses live/incomplete original evidence."""
from pathlib import Path
import datetime,hashlib,json,os,shutil,subprocess,sys
ROOT=Path('/home/hynx/lizhuo/VLA-Pilot++')
CHECKS=ROOT/'.worktrees/exp/steering-integration/checks'
ORIGINAL=ROOT/'.worktrees/exp/steering-integration/runs/eds-common-20261013'
CANDIDATE=CHECKS/'post-cohort-fixes/candidate'
BASE=CHECKS/'archive-v2-candidate-validation'
PYTHON=Path('/home/hynx/miniconda3/envs/vla-pilot/bin/python')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 return h.hexdigest()
def inventory(p):
 result={}
 for f in sorted(p.rglob('*')):
  if f.is_symlink(): raise RuntimeError('No archive symlinks permitted: '+str(f))
  if f.is_file():result[str(f.relative_to(p))]={'bytes':f.stat().st_size,'sha256':sha(f)}
 return result
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
status=json.loads((ORIGINAL/'status.json').read_text())
assert status['state']=='finished' and status['exit_code']==0 and status['source_unchanged'] is True
manifest=json.loads((ORIGINAL/'manifest.json').read_text())
assert manifest['schema']=='steering_cohort_v2' and manifest['commit']=='33954ead452927fc3168efb610487a688f89169e'
original_audit=json.loads((ORIGINAL/'audit.json').read_text())
assert original_audit['valid'] is True and original_audit['full_audit_performed'] is True and original_audit['scope']=='full_v2_contract_and_recorded_method_evidence'
assert original_audit['completed']==original_audit['planned']==10
other_states={m:json.loads((ORIGINAL.parent/f'{m}-common-20261013/status.json').read_text())['state'] for m in ('vls','eds_qd')}
assert any(s=='running' for s in other_states.values()),'Parent authorization is for EDS completed before the other cohorts'
assert all(sha(ROOT/p)==h and sha(ORIGINAL/'source'/p)==h for p,h in manifest['source_sha256'].items())
assert not BASE.exists()
size=sum(p.stat().st_size for p in ORIGINAL.rglob('*') if p.is_file())
free=shutil.disk_usage(CHECKS).free
assert free-size>2*1024**3, f'Insufficient reserved disk space: free={free} copy={size}'
BASE.mkdir();shutil.copyfile(__file__,BASE/'validation-helper.py')
before=inventory(ORIGINAL);save(BASE/'original-files.json',before)
print(json.dumps({'event':'v2_copy_started','files':len(before),'bytes':size,'free_bytes':free,'other_states':other_states}),flush=True)
COPY=BASE/'renamed-eds-preserved';shutil.copytree(ORIGINAL,COPY,copy_function=shutil.copyfile)
assert inventory(COPY)==before
AUDITOR=BASE/'candidate-auditor';shutil.copytree(CANDIDATE,AUDITOR,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
(AUDITOR/'core').mkdir()
for name in ('stage_fused_carry_hold.py','stage_failed_contact_recheck.py'):
 shutil.copyfile(ORIGINAL/'source/core'/name,AUDITOR/'core'/name)
SUPPORT=BASE/'support'
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',PYTHON_DOTENV_DISABLED='1',VLA_CODEX_ONLY='1')
cmd=[str(PYTHON),str(AUDITOR/'scripts/prepare_steering_archive.py'),str(ORIGINAL),'--support-dir',str(SUPPORT)]
p=subprocess.run(cmd,cwd=BASE,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(BASE/'prepare-support.log').write_text(p.stdout)
assert p.returncode==0,p.stdout
DRIVER=BASE/'offline-driver.py'
DRIVER.write_text('''from pathlib import Path
import hashlib,json,os,sys
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[4]
AUDITOR=BASE/'candidate-auditor';ARCHIVE=BASE/'renamed-eds-preserved';SUPPORT=BASE/'support'
REPORTS=BASE/'reports';REPORTS.mkdir()
sys.path[:]=[str(AUDITOR)]+[p for p in sys.path if p and not Path(p).resolve().is_relative_to(ROOT)]
blocked=[];opened=set()
def hook(event,args):
 if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
  p=Path(os.fsdecode(args[0])).resolve()
  if p.is_relative_to(ROOT) and not p.is_relative_to(BASE):
   blocked.append(str(p));raise PermissionError('Original workspace unavailable for portable audit')
  if p.is_relative_to(BASE):opened.add(str(p.relative_to(BASE)))
 if event in ('socket.connect','socket.getaddrinfo','subprocess.Popen','os.system'):
  raise PermissionError('Offline audit forbids network and subprocesses')
sys.addaudithook(hook)
from scripts.audit_steering import audit
import torch
assert not torch.cuda.is_initialized()
r=audit(ARCHIVE,archive_support=SUPPORT,output_path=REPORTS/'cohort-v2.json')
summary={k:r.get(k) for k in ('valid','scope','full_audit_performed','completed','planned','successes','success_task_ids','errors')}
summary.update(blocked_original_read_attempts=blocked,opened_evidence_files=sorted(opened),cuda_initialized=torch.cuda.is_initialized(),checker_source={str(p.relative_to(AUDITOR)):hashlib.sha256(p.read_bytes()).hexdigest() for p in AUDITOR.rglob('*.py')},source_runtime_commit=json.loads((ARCHIVE/'manifest.json').read_text())['commit'])
summary['validation_pass']=r.get('valid') is True and r.get('full_audit_performed') is True and r.get('completed')==r.get('planned')==10 and not blocked and not summary['cuda_initialized']
(BASE/'offline-result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ('opened_evidence_files','checker_source')}),flush=True)
raise SystemExit(0 if summary['validation_pass'] else 2)
''')
command=[str(PYTHON),'-u',str(DRIVER)]
with (BASE/'offline-validation.log').open('w') as log:
 proc=subprocess.Popen(command,cwd=BASE,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 for line in proc.stdout:print(line,end='',flush=True);log.write(line);log.flush()
 proc.wait()
unchanged_original=inventory(ORIGINAL)==before;unchanged_copy=inventory(COPY)==before
unchanged_frozen=all(sha(ROOT/p)==h for p,h in manifest['source_sha256'].items())
receipt={'schema':'actual_v2_archive_candidate_receipt_v1','generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scientific_runtime_commit':manifest['commit'],'original_run':str(ORIGINAL),'relocated_run':str(COPY),'original_status':status,'original_audit_sha256':sha(ORIGINAL/'audit.json'),'original_audit_valid':original_audit['valid'],'other_cohort_states_at_start':other_states,'copied_files':len(before),'copied_bytes':size,'copy_mode':'full regular byte copies; no symlinks or hardlinks','original_inventory_sha256':sha(BASE/'original-files.json'),'original_unchanged':unchanged_original,'copy_final_matches_original':unchanged_copy,'frozen_runtime_files_checked':len(manifest['source_sha256']),'frozen_runtime_unchanged':unchanged_frozen,'candidate_source_files':{str(p.relative_to(AUDITOR)):sha(p) for p in AUDITOR.rglob('*') if p.is_file()},'prepare_command':cmd,'offline_driver_command':command,'offline_exit_code':proc.returncode,'offline_result_sha256':sha(BASE/'offline-result.json') if (BASE/'offline-result.json').exists() else None,'candidate_audit_sha256':sha(BASE/'reports/cohort-v2.json') if (BASE/'reports/cohort-v2.json').exists() else None,'support_manifest_sha256':sha(SUPPORT/'manifest.json'),'helper_sha256':sha(BASE/'validation-helper.py'),'driver_sha256':sha(DRIVER),'space_remaining_bytes':shutil.disk_usage(BASE).free,'limits':['The experiment remains attributed to the original frozen scientific runtime, not this separately identified candidate auditor.','This copies one already complete accepted cohort and performs offline checks only; no new episode/model/API/GPU execution.','Original frozen final aggregation must still precede any root patch application.']}
save(BASE/'receipt.json',receipt)
assert unchanged_original and unchanged_copy and unchanged_frozen
print(json.dumps({'receipt':str(BASE/'receipt.json'),'sha256':sha(BASE/'receipt.json'),'exit_code':proc.returncode}),flush=True)
raise SystemExit(proc.returncode)
