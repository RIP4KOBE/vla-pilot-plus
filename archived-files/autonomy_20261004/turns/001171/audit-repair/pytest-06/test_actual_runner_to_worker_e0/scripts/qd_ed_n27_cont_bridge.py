"""Exact three-file administrative/config reversal, old numerical proof inherited."""
import ast
import hashlib
import json
from pathlib import Path
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n27_cont_history as h
DOC='docs/experiments/n27_hydra_continuation'
ROUTES={'scripts/qd_ed_final_runner.py':{'metered_support','check_budget','check_retry'},'scripts/qd_ed_n23_worker.py':{'validate_context'}}
CHANGED=set(ROUTES)|{'configs/config.yaml'}

def functions(text):return {n.name:ast.get_source_segment(text,n) for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
def source_paths(root):
    root=Path(root);old=json.loads((root/DOC/'original-source-v1.json').read_text())
    paths={x['path'] for x in old['files']}
    for pattern in ('scripts/qd_ed_n27_cont_*.py','tests/test_n27_cont*.py','tests/n27_cont_*.py',DOC+'/*'):
        paths.update(str(p.relative_to(root)) for p in root.glob(pattern) if p.is_file())
    return paths

def reverse_source(root,source):
    root=Path(root);old=json.loads((root/DOC/'original-source-v1.json').read_text());patch=json.loads((root/DOC/'reverse-source-v1.json').read_text())
    w.require(old['commit']==h.BASE and len(old['files'])==345 and patch['base_commit']==h.BASE and set(patch['files'])==CHANGED,'source bridge base/scope')
    index={x['path']:x['sha256'] for x in source['files']}
    w.require(len(index)==len(source['files']) and set(index)==source_paths(root),'source closure')
    for row in old['files']:
        path=row['path'];data=(root/path).read_bytes();w.require(hashlib.sha256(data).hexdigest()==index[path],'current source bytes')
        if path in CHANGED:
            p=patch['files'][path];w.require(p['new_sha256']==index[path] and p['old_sha256']==row['sha256'],'route hashes')
            lines=data.decode().splitlines(keepends=True)
            for edit in reversed(p['edits']):
                a,z=edit['new_start'],edit['new_end'];w.require(''.join(lines[a:z])==edit['new'],'reverse hunk');lines[a:z]=edit['old'].splitlines(keepends=True)
            restored=''.join(lines).encode()
            if path in ROUTES:
                a,z=functions(restored.decode()),functions(data.decode());w.require(set(a)==set(z) and {k for k in a if a[k]!=z[k]}==ROUTES[path],'function allowlist')
            else:w.require(data.replace(b'    diversity_update_mode: legacy_additive\n',b'',1)==restored and data.count(b'    diversity_update_mode: legacy_additive\n')==1,'sole disabled config default')
            data=restored
        w.require(hashlib.sha256(data).hexdigest()==row['sha256'],'old scientific byte drift: '+path)
    return old

def build(source,seal,root):
    w.verify_source(root,source);old=reverse_source(root,source);w.require(old==seal['original_source'],'sealed old source differs')
    return {'schema':'n27-hydra-source-bridge-v1','old_source':old,'new_source':source,'changed_existing':sorted(CHANGED),
        'unchanged_original_files':342,'reverse_exact':True,'historical_backend_proof':seal['historical_backend_proof'],
        'new_numerical_preflight':False,'runtime':seal['runtime'],
        'interpretation':'Old 36-case proof belongs to source095; unchanged numerical bytes and exact administrative/config bridge, not a new proof.'}
