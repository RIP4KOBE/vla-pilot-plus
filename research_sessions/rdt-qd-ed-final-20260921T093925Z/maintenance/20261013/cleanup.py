"""Remove only regenerable historic sweep plots and disposable Python caches."""
import argparse
import collections
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat

U = Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood')
R = U / 'research_sessions/rdt-qd-ed-final-20260921T093925Z'
D = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')
C = R / 'maintenance/20261013'
H = U / 'historical_variants/eds_init_pg_diverse_sampling'
PATTERN = re.compile(r'iter_00([1-8])_(population|best_trajectory)_3d\.png$')

def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def disk():
    return {str(p): dict(zip(('total','used','free'), shutil.disk_usage(p))) for p in (U,D)}

def protected():
    ps = [R/'study_worktree/research-state.yaml'] + sorted((R/'study_worktree/data').glob('*ledger.jsonl'))
    return {str(p):sha(p) for p in ps}

def candidates():
    # Never follow compatibility links or touch real experiment outputs on D.
    for category,prefix in [('ood_eval','level4_libero_object_swap_rbf_'),('rdt_eds_eval','level3_libero_object_rbf_')]:
        root = H/'outputs'/category
        for run in sorted(root.iterdir()):
            if run.is_symlink() or not run.is_dir() or not run.name.startswith(prefix): continue
            for base,dirs,files in os.walk(run,followlinks=False):
                dirs[:]=[d for d in dirs if not (Path(base)/d).is_symlink()]
                b=Path(base)
                if b.name != 'full_eds_process': continue
                trace=b.parent/'tensors/mechanism_trace.pt'
                if not trace.is_file() or trace.stat().st_size == 0: continue
                if not all((b/f'iter_{i:03d}_{kind}_3d.png').is_file() for i in (0,9) for kind in ('population','best_trajectory')): continue
                for name in files:
                    if PATTERN.fullmatch(name): yield b/name, 'regenerable_historical_intermediate_3d_plot', str(trace)
    for root in (U,D):
        for base,dirs,files in os.walk(root,followlinks=False):
            dirs[:]=[d for d in dirs if d not in ('.git','.codex') and not (Path(base)/d).is_symlink()]
            b=Path(base)
            if not any(x in b.parts for x in ('__pycache__','.pytest_cache','.mypy_cache','.ruff_cache')): continue
            for name in files:
                p=b/name
                if '__pycache__' in b.parts and not name.endswith('.pyc'): continue
                if not p.is_symlink(): yield p,'regenerable_python_or_test_cache',None

def plan():
    assert all(r['pixel_equal'] for r in json.loads((C/'regeneration-check.json').read_text())['results'])
    counters=collections.Counter(); sizes=collections.Counter(); n=0
    manifest=C/'deletion-plan.jsonl.gz'
    assert not manifest.exists(), 'A cleanup plan already exists'
    before={'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'disk':disk(),'protected':protected()}
    (C/'before.json').write_text(json.dumps(before,indent=2)+'\n')
    with gzip.open(manifest,'wt') as f:
        for p,reason,trace in candidates():
            s=p.lstat()
            if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1: continue
            row={'path':str(p),'reason':reason,'bytes':s.st_size,'allocated_bytes':s.st_blocks*512,'device':s.st_dev,'inode':s.st_ino,'mtime_ns':s.st_mtime_ns,'sha256':sha(p),'regeneration_trace':trace}
            f.write(json.dumps(row)+'\n');counters[reason]+=1;sizes[reason]+=s.st_blocks*512;n+=1
            if n%20000==0:print(json.dumps({'planned':n,'allocated_bytes':sum(sizes.values())}),flush=True)
    summary={'files':dict(counters),'allocated_bytes':dict(sizes),'plan_sha256':sha(manifest)}
    (C/'plan-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)

def apply():
    before=json.loads((C/'before.json').read_text())
    assert protected()==before['protected'],'Research state or ledgers changed'
    plan_summary=json.loads((C/'plan-summary.json').read_text());manifest=C/'deletion-plan.jsonl.gz'
    assert sha(manifest)==plan_summary['plan_sha256']
    result=C/'deleted-files.jsonl.gz';assert not result.exists(),'Cleanup already attempted'
    counts=collections.Counter();sizes=collections.Counter();skipped=[]
    with gzip.open(manifest,'rt') as src,gzip.open(result,'wt') as dst:
        for line in src:
            row=json.loads(line);p=Path(row['path']);s=p.lstat()
            assert stat.S_ISREG(s.st_mode) and s.st_nlink==1
            assert (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)==(row['device'],row['inode'],row['bytes'],row['mtime_ns']),str(p)
            assert sha(p)==row['sha256'],str(p)
            if row['regeneration_trace']:
                t=Path(row['regeneration_trace']);assert t.is_file() and t.stat().st_size>0
            p.unlink();dst.write(line);counts[row['reason']]+=1;sizes[row['reason']]+=row['allocated_bytes']
            if sum(counts.values())%20000==0:print(json.dumps({'deleted':sum(counts.values()),'allocated_bytes':sum(sizes.values())}),flush=True)
    assert protected()==before['protected'],'Protected files changed during cleanup'
    final={'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'deleted_files':dict(counts),'reclaimed_allocated_bytes':dict(sizes),'disk_after':disk(),'protected_unchanged':True,'deleted_manifest_sha256':sha(result)}
    (C/'cleanup-result.json').write_text(json.dumps(final,indent=2)+'\n');print(json.dumps(final),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('plan','apply'));args=parser.parse_args()
    (plan if args.mode=='plan' else apply)()
