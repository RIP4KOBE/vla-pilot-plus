from pathlib import Path
import os,subprocess,json,time
O=Path(__file__).parent
W=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
def put(n,v):
 p=O/n;t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2)+'\n');t.replace(p)
def ident(pid):
 s=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split();return dict(pid=pid,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(s[19]),state=s[0])
def child_environment():
    env=dict(os.environ)
    for key in list(env):
        if key in {'OPENAI_API_KEY','OPENAI_BASE_URL','OPENAI_ORG_ID','OPENAI_ORGANIZATION','OPENAI_PROJECT_ID',
                   'OPENAI_API_TYPE','OPENAI_API_VERSION','CODEX_API_KEY','CODEX_ACCESS_TOKEN','CODEX_MODEL_PROVIDER',
                   'CHATGPT_BASE_URL','GOOGLE_API_KEY','GEMINI_API_KEY','POE_API_KEY','POE_TOKEN'} or key.startswith('AZURE_OPENAI_'):
            env.pop(key,None)
    # Managed saved auth stays in inherited HOME/CODEX_HOME, unopened and unmodified.
    return env
env=child_environment();env['CUDA_VISIBLE_DEVICES']='';env['OMP_NUM_THREADS']='2';env['OPENBLAS_NUM_THREADS']='2'
cmd=['/home/hynx/.codex/packages/standalone/releases/0.155.1-x86_64-unknown-linux-musl/bin/codex','exec','--ignore-user-config','--ephemeral','--json','--color','never','-C',str(W),'-s','danger-full-access','-m','gpt-6-astra','-c','model_provider="openai"','-c','approval_policy="never"','--output-last-message',str(O/'last-message.txt'),'-']
start=time.time()
with (O/'prompt.txt').open('rb') as inp,(O/'events.jsonl').open('wb') as log,(O/'stderr.log').open('wb') as err:
 p=subprocess.Popen(cmd,cwd=W,env=env,stdin=inp,stdout=log,stderr=err)
 put('process-v1.json',dict(wrapper=ident(os.getpid()),executor=ident(p.pid),command=cmd,started_unix=start,gpu_authorized=False))
 try: code=p.wait(timeout=1200);timed=False
 except subprocess.TimeoutExpired:
  p.terminate()
  try:p.wait(timeout=20)
  except subprocess.TimeoutExpired:p.kill();p.wait()
  code=p.returncode;timed=True
 put('exit-v1.json',dict(exit=code,timeout=timed,elapsed_seconds=time.time()-start,finished_unix=time.time()))
