from pathlib import Path
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
 (REPORTS/f'task{task}-contract.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
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
(BASE/'offline-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'event':'offline_complete','valid':result['valid'],'negative_cases':negative,'cuda_initialized':result['cuda_initialized'],'blocked_original_read_attempts':blocked}),flush=True)
raise SystemExit(0 if result['valid'] else 2)
