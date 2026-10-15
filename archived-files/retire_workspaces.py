"""Retire only pre-inventoried worktrees after complete copy/checksum validation."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import time

ROOT=Path('/home/hynx/lizhuo/VLA-Pilot++')
BASE=ROOT/'.worktrees/exp/repository-maintenance-20261015'
PLAN=json.loads((BASE/'cleanup-plan.json').read_text())
COPY=json.loads((BASE/'archive-copy-receipt.json').read_text())
ARCHIVE=Path(PLAN['archive_root'])

def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True,stderr=subprocess.STDOUT)

def save(value):
    p=BASE/'retirement-receipt.json';t=p.with_suffix('.tmp');t.write_text(json.dumps(value,indent=2)+'\n');t.replace(p)

assert COPY['state']=='verified' and len(COPY['groups'])==len(PLAN['groups'])
assert all(g['checksum_and_metadata_match'] for g in COPY['groups'])
assert git('branch','--show-current').strip()=='main'
assert all(x['valid'] for x in json.loads((BASE/'cohort-review-index.json').read_text()))
assert not any(x.get('free') is not True for x in json.loads((BASE/'lock-check.json').read_text()))
with (ARCHIVE/'all-refs.bundle').open('rb') as f:
    assert hashlib.file_digest(f,'sha256').hexdigest()==COPY['git']['bundle_sha256']
git('bundle','verify',str(ARCHIVE/'all-refs.bundle'))

# Inspect processes on the actual host; this tool is launched with host access.
roots=[Path(g['source']) for g in PLAN['groups']]
busy=[]
for proc in Path('/proc').glob('[0-9]*'):
    try:
        cwd=Path(os.readlink(proc/'cwd')).resolve()
        if any(cwd.is_relative_to(p) for p in roots):
            busy.append({'pid':int(proc.name),'cwd':str(cwd)})
    except OSError:
        pass
assert not busy, busy
for w in PLAN['worktrees']:
    original=Path(w['realpath']);snapshot=Path(w['archive_path'])
    assert original!=ROOT and not original.is_symlink()
    assert snapshot.is_dir() and snapshot.is_relative_to(ARCHIVE)
    assert git('-C',w['worktree'],'rev-parse','HEAD').strip()==w['HEAD']
for b in PLAN['branches']:
    if b['name']!='main':
        assert git('rev-parse','refs/heads/'+b['name']).strip()==b['head']

receipt={'state':'retiring','started_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'worktrees':[],'branches':[],'cache_dirs':[],'archive_bundle_sha256':COPY['git']['bundle_sha256']}
save(receipt)
# Descendants first: all bytes were archived together before removing any root.
for w in sorted(PLAN['worktrees'],key=lambda x:len(Path(x['realpath']).parts),reverse=True):
    original=Path(w['realpath']); snapshot=Path(w['archive_path'])
    output=git('worktree','remove','--force',w['worktree'])
    assert not original.exists() and not original.is_symlink(),str(original)
    original.parent.mkdir(parents=True,exist_ok=True)
    original.symlink_to(snapshot,target_is_directory=True)
    receipt['worktrees'].append({'original':w['worktree'],'head':w['HEAD'],'archive':str(snapshot),'retired':True,'legacy_alias':str(original)})
    save(receipt)
    print('retired worktrees',len(receipt['worktrees']),flush=True)
for b in PLAN['branches']:
    if b['name']=='main':continue
    output=git('branch','-D','--',b['name'])
    receipt['branches'].append({'name':b['name'],'head':b['head'],'deleted_local_only':True})
    save(receipt)
for name in ['.pytest_cache','__pycache__']:
    p=ROOT/name
    if p.is_dir() and not p.is_symlink():
        shutil.rmtree(p);receipt['cache_dirs'].append(name)
assert len(git('worktree','list','--porcelain').strip().split('\n\n'))==1
assert git('for-each-ref','--format=%(refname:short)','refs/heads').strip()=='main'
receipt.update(state='complete',completed_at_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),remaining_worktrees=1,remaining_local_branches=['main'])
save(receipt)
shutil.copy2(BASE/'retirement-receipt.json',ARCHIVE/'retirement-receipt.json')
print('RETIRED',len(receipt['worktrees']),'WORKTREES AND',len(receipt['branches']),'LOCAL BRANCHES',flush=True)
