from pathlib import Path
import json,hashlib,datetime,subprocess,os,time,yaml
W=Path.cwd();A=W.parent/'autonomy_20261004';T=A/'turns/001788'
def read(p):return json.loads(p.read_text())
def ident(pid):
 v=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split();return dict(pid=pid,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(v[19]),state=v[0])
ds=read(A/'driver-status.json');assert ds['turn']==1788
for k in ['driver','process']:
 h=ident(ds[k]['pid']);assert all(h[x]==ds[k][x] for x in ['pid','boot_id','start_ticks']) and h['state']!='Z'
s=yaml.safe_load((W/'research-state.yaml').read_text());assert not s['current_owned_workers'] and not s['active_executor']
r=read(T/'release-preparation-result-v1.json')['release'];release=read(Path(r['path']));assert hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()==r['sha256']
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(release['expires_at'])
for p in release['stop_authority']['paths']:assert not Path(p).exists()
prior=read(A/'turns/001787/operational-summary-v1.json')
for v in prior['ledger_prefixes'].values():assert hashlib.sha256(Path(v['path']).read_bytes()).hexdigest()==v['sha256']
E=release['source_cwd'];assert subprocess.check_output(['git','-C',E,'rev-parse','HEAD'],text=True).strip()=='a5b32cdefc0879e98011f86b1559e4250926ba62'
assert not subprocess.check_output(['git','-C',E,'status','--porcelain','--untracked-files=no'],text=True).strip()
cmd=[release['interpreter']['path'],'-I','-S','-B','-X','pycache_prefix=/dev/null',str(Path(E)/'scripts/qd_ed_n36_bootstrap.py'),'scripts.qd_ed_n36_readiness_prepare','--release',r['path'],'--release-sha256',r['sha256']]
wrapper='''import subprocess,json,pathlib,datetime,os
T=pathlib.Path(TURN)
def identity(pid):
 s=pathlib.Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split();return dict(pid=pid,boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(s[19]),state=s[0])
os.environ['QD_ED_N36_R1_SPECIFICATION']=json.dumps(SPEC)
with (T/'measurement.log').open('xb') as log:
 p=subprocess.Popen(COMMAND,cwd=CWD,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 (T/'measurement-process-v1.json').write_text(json.dumps(dict(wrapper=identity(os.getpid()),controller=identity(p.pid),command=COMMAND,specification=SPEC),indent=2)+'\\n')
 rc=p.wait()
 (T/'measurement-exit-v1.json').write_text(json.dumps(dict(returncode=rc,at=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2)+'\\n')
'''
wrapper=wrapper.replace('TURN',repr(str(T))).replace('SPEC',repr(release['specification'])).replace('COMMAND',repr(cmd)).replace('CWD',repr(E))
# Replace tokens without altering the specification environment variable name.
wrapper=wrapper.replace('QD_ED_N36_R1_'+repr(release['specification'])+'IFICATION','QD_ED_N36_R1_SPECIFICATION')
compile(wrapper,'measurement-wrapper-v1.py','exec')
(T/'measurement-wrapper-v1.py').write_text(wrapper)
with (T/'measurement-launch-intent-v1.json').open('x') as f:json.dump(dict(release=r,source='a5b32cdefc0879e98011f86b1559e4250926ba62',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),purpose='readiness_preparation_only',specification=release['specification'],reservation_seconds=600,provider_calls=1,episode_authorized=False,health_authorized=False),f,indent=2)
with (T/'measurement-wrapper.log').open('xb') as log:p=subprocess.Popen(['/usr/bin/python3',str(T/'measurement-wrapper-v1.py')],cwd=E,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
for _ in range(30):
 if (T/'measurement-process-v1.json').exists():break
 time.sleep(.1)
print((T/'measurement-process-v1.json').read_text())
