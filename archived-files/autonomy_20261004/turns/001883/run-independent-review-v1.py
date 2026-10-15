import pathlib,subprocess,os,json,datetime
P=pathlib.Path;O=P(__file__).resolve().parent
cwd=P('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree')
cli='/home/hynx/.codex/packages/standalone/releases/0.155.1-x86_64-unknown-linux-musl/bin/codex'
env=dict(os.environ)
for k in list(env):
 if k in {'OPENAI_API_KEY','OPENAI_BASE_URL','OPENAI_ORG_ID','OPENAI_ORGANIZATION','OPENAI_PROJECT_ID','OPENAI_API_TYPE','OPENAI_API_VERSION','CODEX_API_KEY','CODEX_ACCESS_TOKEN','CODEX_MODEL_PROVIDER','CHATGPT_BASE_URL','GOOGLE_API_KEY','GEMINI_API_KEY','POE_API_KEY','POE_TOKEN'} or k.startswith('AZURE_OPENAI_'):env.pop(k,None)
argv=[cli,'exec','--ignore-user-config','--ephemeral','--json','--color','never','-C',str(cwd),'-s','read-only','-m','gpt-6-astra','-c','model_provider="openai"','-c','approval_policy="never"','--output-last-message',str(O/'independent-review-final.txt'),'-']
def handle(pid):
 f=(P('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split();return dict(pid=pid,boot_id=P('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(f[19]))
with (O/'independent-review-events-v2.jsonl').open('x') as log,(O/'independent-review-stderr-v2.log').open('x') as err:
 p=subprocess.Popen(argv,cwd=cwd,env=env,stdin=subprocess.PIPE,stdout=log,stderr=err,start_new_session=True)
 (O/'independent-review-process.json').write_text(json.dumps(dict(wrapper=handle(os.getpid()),process=handle(p.pid),argv=argv),indent=2)+'\n')
 p.communicate((O/'independent-review-prompt.txt').read_bytes())
 (O/'independent-review-exit.json').write_text(json.dumps(dict(returncode=p.returncode,at=datetime.datetime.now(datetime.timezone.utc).isoformat()))+'\n')
