#!/usr/bin/env python3
"""Atomically relocate historical worktrees with submodule Git metadata."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import time

EXP=Path('/home/hynx/VLA-Pilot++/.worktrees/exp')
ROOT=Path(__file__).resolve().parent
MAPPING={
    'eds-init-pg-diverse-sampling':'eds_init_pg_diverse_sampling',
    'eds-qd-stage-guidance-transition':'eds_qd_stage_guidance_transition',
    'eds-quality-diversity':'eds_quality_diversity',
}

def git(*args,cwd=EXP):
    return subprocess.check_output(('git',*args),cwd=cwd,text=True,stderr=subprocess.PIPE).strip()

def submodule_gitfiles(old):
    modules=old/'.gitmodules'
    if not modules.is_file():return []
    lines=git('-C',str(old),'config','--file','.gitmodules','--get-regexp',r'\.path$').splitlines()
    found=[]
    for line in lines:
        parts=line.split(maxsplit=1)
        if len(parts)!=2:continue
        path=parts[1];file=old/path/'.git'
        if not file.is_file():continue
        original=file.read_text()
        assert original.startswith('gitdir: ') and '\n' not in original.strip()
        admin=(file.parent/original.strip().removeprefix('gitdir: ')).resolve()
        assert admin.is_dir(),f'broken submodule admin {file}'
        found.append((path,original,str(admin)))
    return found

def relocate(oldname,newname):
    old=EXP/oldname;new=ROOT/newname
    if old.is_symlink():
        assert old.resolve()==new.resolve() and new.is_dir()
        return {'name':oldname,'old_path':str(old),'archive_path':str(new),
                'head':git('-C',str(new),'rev-parse','HEAD'),'already_moved':True}
    assert old.is_dir() and not new.exists()
    assert old.stat().st_dev==ROOT.stat().st_dev,'cross-filesystem move prohibited'
    head=git('-C',str(old),'rev-parse','HEAD')
    status=git('-C',str(old),'status','--porcelain','--untracked-files=no')
    modules=submodule_gitfiles(old)
    os.rename(old,new)
    old.symlink_to(new,target_is_directory=True)
    try:
        for path,original,admin in modules:
            (new/path/'.git').write_text(f'gitdir: {admin}\n')
        git('worktree','repair',str(new))
        assert git('-C',str(new),'rev-parse','HEAD')==head
        assert git('-C',str(new),'status','--porcelain','--untracked-files=no')==status
        for path,original,admin in modules:
            git('-C',str(new/path),'rev-parse','HEAD')
            git('-C',str(old/path),'rev-parse','HEAD')
        return {'name':oldname,'old_path':str(old),'archive_path':str(new),
                'head':head,'tracked_status_before_after':status,
                'submodule_gitfiles_rebased':len(modules),'already_moved':False}
    except BaseException:
        for path,original,admin in modules:
            (new/path/'.git').write_text(original)
        old.unlink()
        os.rename(new,old)
        git('worktree','repair',str(old))
        raise

def main():
    assert ROOT==(EXP/'eds-qd-autoresearch-libero-swap-ood/historical_variants').resolve()
    entries=[{'name':'eds-init-fps','old_path':str(EXP/'eds-init-fps'),
              'archive_path':str(ROOT/'eds_init_fps'),
              'head':git('-C',str(ROOT/'eds_init_fps'),'rev-parse','HEAD'),
              'already_moved':True}]
    for oldname,newname in MAPPING.items():
        row=relocate(oldname,newname)
        entries.append(row)
        print(json.dumps({'archived':oldname,'at':row['archive_path'],
                          'submodule_gitfiles_rebased':row.get('submodule_gitfiles_rebased',0)}),flush=True)
    record={'schema':'historical-exp-worktree-archive-v1','created_unix':time.time(),
            'entries':entries,'protected_existing_autoresearch_worktree_touched':False,
            'peer_gpu6_deferred_until_other_session_stops':True}
    out=ROOT/'historical-layout-v1.json';tmp=out.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n');os.replace(tmp,out)
    print(json.dumps({'manifest':str(out),'entries':len(entries)}),flush=True)

if __name__=='__main__':main()
