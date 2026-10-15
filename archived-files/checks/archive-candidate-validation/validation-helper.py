from pathlib import Path
import datetime,hashlib,json,os,shutil,subprocess,sys
ROOT=Path('/home/hynx/lizhuo/VLA-Pilot++')
CHECKS=ROOT/'.worktrees/exp/steering-integration/checks'
ORIGINAL=ROOT/'.worktrees/exp/steering-integration/runs/eds-migration-20261013'
CANDIDATE=CHECKS/'post-cohort-fixes/candidate'
BASE=CHECKS/'archive-candidate-validation'
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
assert not BASE.exists()
assert shutil.disk_usage(CHECKS).free>4*1024**3
BASE.mkdir()
shutil.copyfile(__file__,BASE/'validation-helper.py')
freeze=json.loads((CHECKS/'common-framework-freeze.json').read_text())
manifest=json.loads((ORIGINAL/'manifest.json').read_text())
assert json.loads((ORIGINAL/'status.json').read_text())['state']=='finished'
before=inventory(ORIGINAL);save(BASE/'original-files.json',before)
print(json.dumps({'event':'copy_started','files':len(before),'bytes':sum(x['bytes'] for x in before.values()),'free_bytes':shutil.disk_usage(CHECKS).free}),flush=True)
COPY=BASE/'renamed-migration-preserved'
shutil.copytree(ORIGINAL,COPY,copy_function=shutil.copyfile)
assert inventory(COPY)==before
AUDITOR=BASE/'candidate-auditor'
shutil.copytree(CANDIDATE,AUDITOR,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
(AUDITOR/'core').mkdir()
core_receipt={}
for name in ('stage_fused_carry_hold.py','stage_failed_contact_recheck.py'):
 src=ROOT/'core'/name
 shutil.copyfile(src,AUDITOR/'core'/name)
 core_receipt['core/'+name]=sha(src)
SUPPORT=BASE/'support'
env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',PYTHON_DOTENV_DISABLED='1',VLA_CODEX_ONLY='1')
cmd=[str(PYTHON),str(AUDITOR/'scripts/prepare_steering_archive.py'),str(ORIGINAL),'--support-dir',str(SUPPORT)]
p=subprocess.run(cmd,cwd=BASE,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(BASE/'prepare-support.log').write_text(p.stdout)
assert p.returncode==0,p.stdout
# The v1 wrapper deliberately reads its own fixture; supply exactly the separately
# verified support bytes to the external auditor, without modifying any run receipt.
fixture=AUDITOR/'tests/fixtures/steering_rng/fixture-manifest.json';fixture.parent.mkdir(parents=True)
shutil.copyfile(SUPPORT/'fixture-manifest.json',fixture)
assert sha(fixture)==json.loads((SUPPORT/'manifest.json').read_text())['files']['fixture-manifest.json']
config_before={p:sha(ROOT/p) for p in json.loads((CHECKS.parent/'runs/eds-common-20261013/manifest.json').read_text())['source_sha256']}
assert all(sha(ROOT/p)==h for p,h in json.loads((CHECKS.parent/'runs/eds-common-20261013/manifest.json').read_text())['source_sha256'].items())
DRIVER=BASE/'offline-driver.py'
DRIVER.write_text('''from pathlib import Path
import hashlib,json,os,socket,sys
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[4]
AUDITOR=BASE/'candidate-auditor'
ARCHIVE=BASE/'renamed-migration-preserved'
SUPPORT=BASE/'support'
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
from scripts.audit_steering_contract import audit_run
import torch
assert not torch.cuda.is_initialized()
wrapper=audit(ARCHIVE,archive_support=SUPPORT,output_path=REPORTS/'legacy-wrapper.json')
print(json.dumps({'legacy_valid':wrapper.get('valid'),'scope':wrapper.get('scope'),'full_audit_performed':wrapper.get('full_audit_performed'),'successes':wrapper.get('successes'),'errors':wrapper.get('errors')}),flush=True)
contracts=[]
for task in range(10):
 r=audit_run(ARCHIVE,task=task,archive_support=SUPPORT)
 (REPORTS/f'task{task}-contract.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\\n')
 row={'task_id':task,'summary':r['summary'],'task_contract_valid':r.get('task_contract_valid'),'task_evidence_complete':r.get('task_evidence_complete')}
 contracts.append(row);print(json.dumps(row),flush=True)
# Exercise the real archived task evidence: keep the original raw frame available,
# remove/corrupt only its independent copy, then restore its exact bytes.
frame=sorted((ARCHIVE/'output/eds_eval/stage_unmarked_frames/episode_000').glob('*.png'))[0]
raw=frame.read_bytes();negative=[]
for mode in ('missing_raw_frame','same_size_corrupt_raw_frame'):
 try:
  if mode=='missing_raw_frame':frame.unlink()
  else:frame.write_bytes(bytes([raw[0]^1])+raw[1:])
  r=audit_run(ARCHIVE,task=0,archive_support=SUPPORT)
  negative.append({'case':mode,'rejected':r['summary'].get('fail',0)>0,'failed':[k for k,v in r['checks'].items() if v['status']=='fail']})
 finally:frame.write_bytes(raw)
bundle=SUPPORT/'fixture-manifest.json';raw=bundle.read_bytes()
try:
 bundle.write_bytes(bytes([raw[0]^1])+raw[1:])
 try:
  r=audit_run(ARCHIVE,task=0,archive_support=SUPPORT)
  negative.append({'case':'same_size_corrupt_support','rejected':r['summary'].get('fail',0)>0})
 except Exception as exc:negative.append({'case':'same_size_corrupt_support','rejected':True,'error_type':type(exc).__name__})
finally:bundle.write_bytes(raw)
result={'schema':'actual_legacy_archive_candidate_validation_v1','legacy_wrapper_valid':wrapper.get('valid'),'legacy_wrapper_scope':wrapper.get('scope'),'full_v2_audit_performed':False,'tasks':contracts,'negative_cases':negative,'blocked_original_read_attempts':blocked,'opened_evidence_files':sorted(opened),'cuda_initialized':torch.cuda.is_initialized(),'limits':['The migration manifest remains steering_cohort_v1 and is not promoted to v2.','The legacy wrapper reads its own fixture path: this external auditor received the exact hash-verified support fixture at that path; integrated standalone v1 wrapper relocation still requires this fixture.','All ten task contract audits use explicit hash-bound archive support and real copied raw evidence.','No simulator, model API, model loading or scientific rerun was performed.']}
result['valid']=wrapper.get('valid') is True and all(r['task_contract_valid'] is True and r['task_evidence_complete'] is True and r['summary'].get('fail',0)==0 for r in contracts) and all(r['rejected'] for r in negative) and not blocked and not result['cuda_initialized']
(BASE/'offline-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\\n')
print(json.dumps({'event':'offline_complete','valid':result['valid'],'negative_cases':negative,'cuda_initialized':result['cuda_initialized'],'blocked_original_read_attempts':blocked}),flush=True)
raise SystemExit(0 if result['valid'] else 2)
''')
command=[str(PYTHON),'-u',str(DRIVER)]
with (BASE/'offline-validation.log').open('w') as log:
 p=subprocess.Popen(command,cwd=BASE,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 for line in p.stdout: print(line,end='',flush=True);log.write(line);log.flush()
 p.wait()
unchanged_original=inventory(ORIGINAL)==before
unchanged_copy=inventory(COPY)==before
unchanged_frozen=all(sha(ROOT/p)==h for p,h in config_before.items())
receipt={'schema':'actual_legacy_archive_candidate_receipt_v1','generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'original_run':str(ORIGINAL),'relocated_run':str(COPY),'copied_files':len(before),'copied_bytes':sum(x['bytes'] for x in before.values()),'copy_mode':'full regular byte copies; no symlinks or hardlinks','original_inventory_sha256':sha(BASE/'original-files.json'),'original_unchanged':unchanged_original,'copy_final_matches_original':unchanged_copy,'frozen_runtime_files_checked':len(config_before),'frozen_runtime_unchanged':unchanged_frozen,'candidate_source_files':{str(p.relative_to(AUDITOR)):sha(p) for p in AUDITOR.rglob('*') if p.is_file()},'core_audit_source_sha256':core_receipt,'prepare_command':cmd,'offline_driver_command':command,'offline_exit_code':p.returncode,'offline_result_sha256':sha(BASE/'offline-result.json') if (BASE/'offline-result.json').exists() else None,'support_manifest_sha256':sha(SUPPORT/'manifest.json'),'helper_sha256':sha(BASE/'validation-helper.py'),'driver_sha256':sha(DRIVER),'space_remaining_bytes':shutil.disk_usage(BASE).free}
save(BASE/'receipt.json',receipt)
assert unchanged_original and unchanged_copy and unchanged_frozen
print(json.dumps({'receipt':str(BASE/'receipt.json'),'sha256':sha(BASE/'receipt.json'),'exit_code':p.returncode}),flush=True)
raise SystemExit(p.returncode)
