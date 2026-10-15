import pathlib,json,datetime,subprocess,hashlib,time,os
root=pathlib.Path.cwd();out=root.parent/'autonomy_20261004/turns/000469/image-transport-probe-sanitized';out.mkdir(exist_ok=False)
old=root.parent/'autonomy_20261004/turns/000445/image-transport-probe'; a=json.loads((old/'authority.json').read_text());a['argv']=[x.replace(str(old),str(out)) for x in a['argv']];a['at']=datetime.datetime.now(datetime.timezone.utc).isoformat();a['source']='04d1255016fa13a2d467995b9e37a6a829356a1c'
assert not (root.parent/'autonomy_20261004/STOP').exists()
assert hashlib.sha256(pathlib.Path(a['image']['path']).read_bytes()).hexdigest()==a['image']['sha256']
(out/'authority.json').write_text(json.dumps(a,indent=2)+'\n')
env=os.environ.copy()
import sys
sys.path.insert(0,str(root))
from scripts.qd_ed_final_runner import codex_removed_environment
for k in codex_removed_environment():env.pop(k,None)
assert not any(env.get(k) for k in codex_removed_environment())
(out/'environment-policy.json').write_text(json.dumps({'removed_names':sorted(codex_removed_environment()),'saved_auth_opened':False,'production_filter_used':True}))
start=time.monotonic()
with (out/'events.jsonl').open('w') as f,(out/'stderr.log').open('w') as e:
 p=subprocess.Popen(a['argv'],stdin=subprocess.PIPE,stdout=f,stderr=e,env=env,text=True)
 stat=pathlib.Path(f'/proc/{p.pid}/stat').read_text().rsplit(')',1)[1].split();(out/'process.json').write_text(json.dumps({'pid':p.pid,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':int(stat[19])}))
 try:p.communicate(a['prompt'],timeout=180);status='completed'
 except subprocess.TimeoutExpired:p.kill();p.communicate();status='timeout'
rows=[json.loads(l) for l in (out/'events.jsonl').read_text().splitlines() if l.strip()]; completed=[v for v in rows if v.get('type')=='turn.completed'];errors=[v for v in rows if v.get('type') in ['error','turn.failed']];messages=[v.get('item',{}).get('text') for v in rows if v.get('type')=='item.completed' and v.get('item',{}).get('type')=='agent_message']
result={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit':p.returncode,'status':status,'elapsed_seconds':time.monotonic()-start,'completed_turns':len(completed),'errors':errors,'messages':messages,'usage':[v.get('usage') for v in completed],'scientific_evidence':False,'gpu_dispatched':False}
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='errors'}))
