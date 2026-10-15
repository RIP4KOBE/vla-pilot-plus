from pathlib import Path
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
(BASE/'offline-result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ('opened_evidence_files','checker_source')}),flush=True)
raise SystemExit(0 if summary['validation_pass'] else 2)
