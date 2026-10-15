"""CPU-only negative admission check for the actual frozen -m worker entrypoint."""
import hashlib,json,os,subprocess,time
from pathlib import Path
root=Path.cwd().resolve(); out=root.parent/'prospective-recovery-release-v2'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
entry=json.loads((out/'worker-entrypoints.CANDIDATE-v1.json').read_text())['commands'][0]
context=json.loads(Path(entry['context']['path']).read_text()); before=time.monotonic()
env={**os.environ,'CUDA_VISIBLE_DEVICES':'','PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'}
result=subprocess.run(entry['argv'],cwd=root,env=env,input='G',text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=45)
log=out/'entrypoint-negative-v1.log';log.write_text(result.stdout)
assert result.returncode!=0 and 'released plan contract' in result.stdout
plan=json.loads(Path(context['plan']['path']).read_text())
assert not Path(plan['artifact_root']).exists()
assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
evidence={'schema':'n32r2-actual-worker-entrypoint-negative-v1','argv':entry['argv'],'cwd':str(root),
 'context':entry['context'],'stdin':'G','environment_overrides':{k:env[k] for k in ('CUDA_VISIBLE_DEVICES','PYTHONDONTWRITEBYTECODE','OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE')},
 'returncode':result.returncode,'elapsed_seconds':time.monotonic()-before,'log':ref(log),
 'expected_rejection':'released plan contract','status':'PASS_EXPECTED_REJECTION',
 'worker_process_started':True,'gpu_dispatch':False,'main_started':False,'source_clean':True,'artifact_root_absent':True,
 'limitation':'Negative release-boundary check only; no accepted release, simulator, model, provider, native outcome audit, or efficacy evaluation.'}
(out/'entrypoint-negative-v1.json').write_text(json.dumps(evidence,indent=2)+'\n')
print(json.dumps(evidence,indent=2))
