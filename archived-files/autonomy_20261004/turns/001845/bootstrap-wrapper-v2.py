import pathlib,json,os,subprocess,datetime
P=pathlib.Path;T=P(__file__).resolve().parent;v=json.loads((T/'release-validation-v1.json').read_text());ref=v['release'];r=json.loads(P(ref['path']).read_text());os.environ['QD_ED_N36_R1_SPECIFICATION']=json.dumps(r['specification'])
def identity(pid):
 s=P(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split();return dict(pid=pid,start_ticks=int(s[19]),boot_id=P('/proc/sys/kernel/random/boot_id').read_text().strip(),state=s[0])
cmd=[r['interpreter']['path'],'-I','-S','-B','-X','pycache_prefix=/dev/null',str(P(r['source_cwd'])/'scripts/qd_ed_n36_bootstrap.py'),'scripts.qd_ed_n36_readiness_prepare','--release',ref['path'],'--release-sha256',ref['sha256']]
with (T/'measurement-v2.log').open('x') as log:
 p=subprocess.Popen(cmd,cwd=r['source_cwd'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,stdin=subprocess.DEVNULL)
 (T/'measurement-process-v2.json').write_text(json.dumps(dict(wrapper=identity(os.getpid()),controller=identity(p.pid),command=cmd,release=ref),indent=2)+'\n')
 rc=p.wait()
 (T/'measurement-exit-v2.json').write_text(json.dumps(dict(returncode=rc,at=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2)+'\n')
