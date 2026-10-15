import pathlib,json,hashlib,subprocess,datetime,os,time
O=pathlib.Path(__file__).parent; T=O.parent.parent
started=datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def save(name,d):
 with (O/name).open('x') as f: json.dump(d,f,indent=2)
def read(p): return json.loads(pathlib.Path(p).read_text())
a=read(O/'authority-v1.json'); rv=read(a['source_review']['path']); i=read(T/'001617/recovery-implementation/binding-impact-v1.json'); root=pathlib.Path(i['deployment_source_cwd']); base=rv['base_commit']; target=rv['source_commit']; cmds=[]
def git(*args):
 c=['git','--no-optional-locks','-C',str(root),*args];r=subprocess.run(c,capture_output=True,text=True);cmds.append({'argv':c,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr});return r
for ref in [a['source_review'],a['amendment'],a['standing_authority']]: assert sha(ref['path'])==ref['sha256']
assert sha(T/'001617/recovery-implementation/binding-impact-v1.json')=='451914f21dba6d39d47ac86a2653d139f84ea97d8a2ebe7cdb80ef1eedf84a2a'
for p in rv['stop_paths']: assert not os.path.lexists(p['path'])
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(a['deadline'].replace('Z','+00:00'))
ledgers={k:{'path':v['path'],'sha256':sha(v['path']),'bytes':pathlib.Path(v['path']).stat().st_size} for k,v in a['ledger_prefixes'].items()}; assert ledgers==a['ledger_prefixes']
before=git('rev-parse','HEAD').stdout.strip();assert before==base
status=git('status','--porcelain=v1','--untracked-files=no');assert status.returncode==0 and not status.stdout
assert git('merge-base','--is-ancestor',base,target).returncode==0
hashes=[]
for row in rv['source_file_hashes']:
 p=row['path'];data=subprocess.check_output(['git','-C',str(root),'show',target+':'+p]);h=hashlib.sha256(data).hexdigest();assert h==row['sha256'];assert sha(pathlib.Path(a['worktree'])/p)==h;hashes.append(row)
diff=subprocess.check_output(['git','-C',str(root),'diff',base,target,'--']);assert hashlib.sha256(diff).hexdigest()==rv['source_diff_sha256']
assert (O/'source-placement.diff').read_bytes()==diff
# Inspect only process argv and cwd; never environment/credentials. Exclude our own ancestors.
anc={os.getpid()};pid=os.getppid()
while pid>1:
 anc.add(pid)
 try: pid=int(pathlib.Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[1])
 except (OSError,ValueError):break
workers=[];inaccessible=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name) in anc: continue
 try:
  argv=(p/'cmdline').read_bytes().split(b'\0'); args=[s.decode(errors='replace') for s in argv if s]
 except FileNotFoundError:continue
 except PermissionError:inaccessible.append(int(p.name));continue
 if not args:continue
 # Actual launch/module arguments only: don't match wrapper prompts or shell command text.
 actual=[x for x in args[1:] if len(x)<500 and '\n' not in x and ' ' not in x]
 worker=any(x in ('main.py','scripts.qd_ed_n36_worker','scripts.qd_ed_n36_runner','scripts.qd_ed_n36_healthcheck','scripts.qd_ed_n36_supervise','scripts.qd_ed_n36_engineering','scripts.qd_ed_n36_engineering_r1') or x.endswith(('/qd_ed_n36_worker.py','/qd_ed_n36_healthcheck.py','/qd_ed_n36_runner.py','/main.py')) for x in actual)
 if worker:
  try: cwd=os.readlink(p/'cwd')
  except FileNotFoundError:continue
  except PermissionError:inaccessible.append(int(p.name));continue
  if cwd==str(root) or any('rdt-qd-ed-final-20260921T093925Z' in x for x in actual): workers.append({'pid':int(p.name),'cwd':cwd,'argv':args})
pre={'started_at':started,'before':before,'target':target,'tracked_clean':True,'exact_reviewed_files':hashes,'source_diff_sha256':hashlib.sha256(diff).hexdigest(),'live_workers':workers,'inaccessible_processes':inaccessible,'ledger_before':ledgers,'commands':cmds,'release_enabled':False}
save('source-placement-preflight-v2.json',pre)
assert not workers and not inaccessible,'Cannot establish no live workers'
for p in rv['stop_paths']: assert not os.path.lexists(p['path'])
r=git('merge','--ff-only','--no-edit',target);assert r.returncode==0
after=git('rev-parse','HEAD').stdout.strip();assert after==target
assert not git('status','--porcelain=v1','--untracked-files=no').stdout
for row in hashes: assert sha(root/row['path'])==row['sha256']
assert sha(root/'scripts/qd_ed_n36_engineering.py')==rv['parent_adapter_sha256']
save('source-placement-v1.json',{**pre,'after':after,'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commands':cmds,'tracked_clean_after':True,'preparatory_source_placement_only':True,'root_adoption':False,'gpu_authorized':False})
print('Source fast-forward verified',before,'->',after)
