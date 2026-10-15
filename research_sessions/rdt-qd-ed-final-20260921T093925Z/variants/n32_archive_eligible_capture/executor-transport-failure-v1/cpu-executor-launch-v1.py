import subprocess,os,json,time,pathlib,hashlib,resource
v=pathlib.Path(__file__).parent
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def handle(pid):
 s=pathlib.Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1].split()
 return {'pid':pid,'boot_id':boot,'start_ticks':int(s[19]),'state':s[0]}
def write(name,x):
 p=v/name;t=p.with_suffix('.tmp');t.write_text(json.dumps(x,indent=2)+'\n');t.replace(p)
env=os.environ.copy();env.update(OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',CUDA_VISIBLE_DEVICES='')
cli='/home/hynx/.codex/packages/standalone/releases/0.155.1-x86_64-unknown-linux-musl/bin/codex'
argv=[cli,'exec','--ignore-user-config','--ephemeral','--json','--color','never','-C',str(v/'implementation_worktree'),'-s','danger-full-access','-m','gpt-6-astra','-c','model_provider="openai"','-c','approval_policy="never"','--output-last-message',str(v/'executor-last-message.txt'),'-']
start=time.time()
with open(v/'executor-prompt-v1.txt','rb') as inp,open(v/'executor-events.jsonl','wb') as out,open(v/'executor-stderr.log','wb') as err:
 p=subprocess.Popen(argv,stdin=inp,stdout=out,stderr=err,env=env)
 write('executor-process-v1.json',{'schema':'n32-cpu-executor-process-v1','started_unix':start,'wrapper':handle(os.getpid()),'executor':handle(p.pid),'argv':argv,'prompt_sha256':hashlib.sha256((v/'executor-prompt-v1.txt').read_bytes()).hexdigest(),'gpu_authorized':False,'wall_cap_seconds':1800})
 code=p.wait()
 write('executor-exit-v1.json',{'exit':code,'finished_unix':time.time(),'elapsed_seconds':time.time()-start})
