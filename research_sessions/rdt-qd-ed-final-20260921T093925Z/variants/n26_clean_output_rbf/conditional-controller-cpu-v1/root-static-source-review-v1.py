#!/usr/bin/env python3
"""Independent root static composition verification; no experiment history access."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve()
I=HERE.parent.parent/'conditional_implementation'
W=I.parent.parent.parent/'study_worktree'
sys.path[:0]=[str(I/'scripts'),str(I)]
from scripts import qd_ed_n26_logical as logical,qd_ed_n26_contract as c,qd_ed_n23_worker as w
from scripts import qd_ed_final_runner as r
def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=I,text=True).strip()
    assert head=='6026794cd5d52f3a5054bf2704ebb3c516f9f47e'
    assert subprocess.check_output(['git','status','--porcelain=v1'],cwd=I,text=True)==''
    source=w.source_record(I,c.source_paths(vars(r)))
    assert len(source['files'])==315
    composed=logical.verify_composition(I,source)
    assert len(composed['accepted_unchanged'])==280
    assert len(composed['common_administrative_unchanged'])==19
    shared={p:logical.restore_shared(I,p) for p in logical.SHARED}
    from scripts.qd_ed_n26_bridge import functions
    for p,b in shared.items():
        a,z=functions(b.decode()),functions((I/p).read_text())
        required={'metered_support','check_budget','check_retry'} if p.endswith('final_runner.py') else {'validate_context'}
        assert set(a)==set(z) and {k for k in a if a[k]!=z[k]}==required
    worker='scripts/qd_ed_n23_worker.py'
    a,z=functions(shared[worker].decode()),functions((I/worker).read_text())
    assert all(a[k]==z[k] for k in ('run_worker','verify_receipt','require','sha','canonical_sha','read_ref'))
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip()=='6f796358aa84d53e9c8a04859f7d19352c9db7fe'
    import torch
    assert not torch.cuda.is_initialized()
    record={'schema':'n26-root-static-composition-review-v1','accepted':True,
      'source':source,'composition':composed,'shared_function_scope_verified':True,
      'accepted_worker_run_and_receipt_unchanged':True,
      'real_experiment_metadata_reads':0,'tensor_reads':0,'gpu_or_api_operations':0,
      'active_worktree_commit_unchanged':'6f796358aa84d53e9c8a04859f7d19352c9db7fe',
      'cuda_initialized':False,'reviewer':w.sha(HERE),'gpu_authorized':False}
    out=HERE.parent/'root-static-source-review-v1.json'
    with out.open('x') as f:json.dump(record,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'review':w.sha(out),'source_commit':head,'source_files':315,
      'accepted_unchanged':280,'common_administrative_unchanged':19,'gpu_authorized':False}))
if __name__=='__main__':main()

