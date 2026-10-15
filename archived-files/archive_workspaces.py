"""One-off maintenance: copy and verify, never delete source workspaces."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path('/home/hynx/lizhuo/VLA-Pilot++')
BASE = ROOT / '.worktrees/exp/repository-maintenance-20261015'
PLAN = json.loads((BASE / 'cleanup-plan.json').read_text())
ARCHIVE = Path(PLAN['archive_root'])

def save(name, data):
    p = BASE / name
    temp = p.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    temp.replace(p)

def run(args, log):
    with (BASE / log).open('w') as f:
        p = subprocess.run(args, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    if p.returncode:
        raise RuntimeError(f'{args[0]} failed {p.returncode}: {log}')

def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def main():
    ARCHIVE.mkdir(mode=0o700, exist_ok=False)
    (ARCHIVE/'workspaces').mkdir()
    run(['rsync','-aH',str(ROOT/'.git')+'/',str(ARCHIVE/'git-admin')+'/'], 'archive-git-copy.log')
    run(['git','bundle','create',str(ARCHIVE/'all-refs.bundle'),'--all'], 'archive-bundle-create.log')
    run(['git','bundle','verify',str(ARCHIVE/'all-refs.bundle')], 'archive-bundle-verify.log')
    heads = subprocess.check_output(['git','bundle','list-heads',str(ARCHIVE/'all-refs.bundle')],cwd=ROOT,text=True)
    (ARCHIVE/'bundle-heads.txt').write_text(heads)
    bundled = {line.split()[1]:line.split()[0] for line in heads.splitlines()}
    for b in PLAN['branches']:
        assert bundled['refs/heads/'+b['name']] == b['head'], b
    for w in PLAN['worktrees']:
        assert w['HEAD'] in bundled.values(), ('Detached head not independently preserved',w['HEAD'])
    git_receipt = {'bundle_sha256':sha(ARCHIVE/'all-refs.bundle'), 'bundle_bytes':(ARCHIVE/'all-refs.bundle').stat().st_size,'all_branch_heads_verified':True,'all_worktree_heads_verified':True}
    save('git-archive-receipt.json',git_receipt)
    shutil.copy2(BASE/'inventory-before.json',ARCHIVE/'inventory-before.json')
    shutil.copy2(BASE/'cleanup-plan.json',ARCHIVE/'cleanup-plan.json')
    done=[]
    for i,g in enumerate(PLAN['groups']):
        start=time.time()
        save('archive-progress.json',{'state':'copying','group':g['id'],'index':i+1,'total':len(PLAN['groups']),'completed':done})
        print('copying',g['id'],g['source'],flush=True)
        run(['rsync','-aH','--',g['source']+'/',g['destination']+'/'],g['id']+'-copy.log')
        save('archive-progress.json',{'state':'checksumming','group':g['id'],'index':i+1,'total':len(PLAN['groups']),'completed':done})
        run(['rsync','-aHnci','--delete','--',g['source']+'/',g['destination']+'/'],g['id']+'-verify.log')
        check=(BASE/(g['id']+'-verify.log')).read_text()
        if check.strip():
            raise RuntimeError('Source/archive checksum or metadata differences: '+g['id'])
        done.append(dict(g,checksum_and_metadata_match=True,seconds=time.time()-start))
        save('archive-copy-receipt.json',{'state':'in_progress','groups':done,'git':git_receipt})
        print('verified',g['id'],round(time.time()-start,1),flush=True)
    receipt={'state':'verified','groups':done,'git':git_receipt,'source_deleted':False,'symlinks':'preserved, not dereferenced; external targets retained at existing locations'}
    save('archive-copy-receipt.json',receipt)
    save('archive-progress.json',{'state':'verified','completed':done})
    shutil.copy2(BASE/'archive-copy-receipt.json',ARCHIVE/'copy-receipt.json')
    print('ALL ARCHIVE COPIES VERIFIED; NO SOURCE DELETION PERFORMED',flush=True)

if __name__=='__main__':
    try:
        main()
    except Exception as e:
        save('archive-progress.json',{'state':'failed','error':str(e)})
        raise
