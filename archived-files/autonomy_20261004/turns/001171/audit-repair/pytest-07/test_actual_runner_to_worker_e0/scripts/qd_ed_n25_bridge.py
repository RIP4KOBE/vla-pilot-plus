"""Closed Phase A byte bridge plus existing N23 quality proof; no tensor reads."""
import ast
import hashlib
from pathlib import Path
import subprocess
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n25_contract as c
from scripts.qd_ed_n24_bridge import settled_backend

ROUTES={'scripts/qd_ed_n23_worker.py':{'validate_context','run_worker','verify_receipt'},
        'scripts/qd_ed_final_runner.py':{'expand_candidate','is_n7_plan','is_n23_v2_plan','is_n23_plan','metered_plan',
          'typed_metered_plan','metered_support','validate_plan','check_budget','check_retry','run_plan','reconcile_ledger'}}
NEW_FUNCTIONS={'scripts/qd_ed_final_runner.py':{'is_n25_plan'},'scripts/qd_ed_n23_worker.py':set()}

def functions(text):
    return {n.name:ast.get_source_segment(text,n) for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}


def build(source,runtime,root):
    root=Path(root);phase=w.read_ref(c.ref(root/c.PHASE_A_MANIFEST))
    w.require(phase['commit']==c.PHASE_A,'N25 Phase A source differs')
    changed=set(subprocess.check_output(['git','diff','--name-only',c.PHASE_A,'HEAD'],cwd=root,text=True).splitlines())
    w.require(changed<=c.CONTROLLER_DELTA,'N25 changed scientific source')
    unchanged=[];deltas={}
    for row in phase['files']:
        path=row['path'];current=(root/path).read_bytes()
        if path not in ROUTES:
            w.require(hashlib.sha256(current).hexdigest()==row['sha256'],'N25 frozen Phase A byte drift: '+path)
            unchanged.append(row);continue
        oldbytes=subprocess.check_output(['git','show',c.PHASE_A+':'+path],cwd=root)
        w.require(hashlib.sha256(oldbytes).hexdigest()==row['sha256'],'N25 Phase A history differs')
        old=functions(oldbytes.decode());new=functions(current.decode())
        w.require(set(new)==set(old)|NEW_FUNCTIONS[path]
            and all(new[k]==old[k] for k in old.keys()-ROUTES[path]),'N25 shared functions outside routes changed')
        deltas[path]={k:{'old':hashlib.sha256(old[k].encode()).hexdigest() if k in old else None,
                        'new':hashlib.sha256(new[k].encode()).hexdigest()} for k in sorted(ROUTES[path]|NEW_FUNCTIONS[path])}
    plan=c.original_plan();w.require(plan['source_commit']==c.BASE,'N25 old quality proof source differs')
    return {'schema':'n25-source-equivalence-bridge-v1','phase_a_source':c.PHASE_A,'new_source':source,'runtime':runtime,
        'unchanged_files':unchanged,'shared_route_functions':deltas,'reverse_insertions':verify_reverse(root),'prior_backend_proof':plan['n23_cohort']['backend_proof'],
        'phase_a_review':c.ref(c.RUN_DIR/'root-conditional-cpu-review-v1.json'),
        'new_rbf_arithmetic_proof_required':True,'old_proof_scope':'N23 quality only; not N25 RBF'}


def verify(reference,source,runtime,root):
    value=w.read_ref(reference)
    w.require(reference==c.ref(c.BRIDGE) and value==build(source,runtime,root),'N25 byte bridge differs')
    return value


def verify_reverse(root):
    record=w.read_ref(c.ref(Path(root)/'docs/03_evidence/qd_ed_final/n25/shared-route-insertions-v1.json'))
    w.require(record['schema']=='n25-reversible-shared-routes-v1' and record['base_commit']==c.PHASE_A
        and {r['path'] for r in record['files']}==set(ROUTES),'N25 reverse route schema differs')
    result=[]
    for row in record['files']:
        current=(Path(root)/row['path']).read_text();lines=current.splitlines(keepends=True)
        w.require(hashlib.sha256(current.encode()).hexdigest()==row['new_sha256'],'N25 new route bytes differ')
        last=len(lines)
        for edit in reversed(row['edits']):
            start,end=edit['new_start'],edit['new_end']
            w.require(0<=start<=end<=last and ''.join(lines[start:end])==edit['new'],'N25 reverse insertion mismatch')
            lines[start:end]=edit['old'].splitlines(keepends=True);last=start
        restored=''.join(lines).encode()
        frozen=subprocess.check_output(['git','show',c.PHASE_A+':'+row['path']],cwd=root)
        w.require(restored==frozen and hashlib.sha256(restored).hexdigest()==row['old_sha256'],'N25 exact prior byte reconstruction failed')
        result.append({'path':row['path'],'restored_sha256':row['old_sha256'],'new_sha256':row['new_sha256'],'edit_blocks':len(row['edits'])})
    return result
