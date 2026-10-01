"""Closed Phase A byte bridge plus existing N23 quality proof; no tensor reads."""
import ast
import hashlib
from pathlib import Path
import subprocess
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n26_contract as c
from scripts.qd_ed_n24_bridge import settled_backend
from scripts import qd_ed_n25_backend as old_backend
from scripts import qd_ed_n25_contract as old_contract

ROUTES={'scripts/qd_ed_n23_worker.py':{'validate_context','run_worker','verify_receipt'},
        'scripts/qd_ed_final_runner.py':{'expand_candidate','is_n7_plan','is_n25_plan','is_n23_v2_plan','is_n23_plan','metered_plan',
          'typed_metered_plan','metered_support','validate_plan','check_budget','check_retry','run_plan','reconcile_ledger'}}
NEW_FUNCTIONS={'scripts/qd_ed_final_runner.py':{'is_n26_plan'},'scripts/qd_ed_n23_worker.py':set()}

def functions(text):
    return {n.name:ast.get_source_segment(text,n) for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}


def build(source,runtime,root):
    from scripts import qd_ed_n26_logical as logical
    root=Path(root);composition=logical.verify_composition(root,source);phase=w.read_ref(c.ref(root/c.PHASE_A_MANIFEST))
    w.require(phase['commit']==c.PHASE_A,'N26 Phase A source differs')
    changed=set(subprocess.check_output(['git','diff','--name-only',c.PHASE_A,'HEAD'],cwd=root,text=True).splitlines())
    w.require(changed<=logical.source_paths(root),'N26 changed scientific source')
    unchanged=[];deltas={}
    for row in phase['files']:
        path=row['path'];current=(root/path).read_bytes()
        if path not in ROUTES:
            w.require(hashlib.sha256(current).hexdigest()==row['sha256'],'N26 frozen Phase A byte drift: '+path)
            unchanged.append(row);continue
        oldbytes=subprocess.check_output(['git','show',c.PHASE_A+':'+path],cwd=root)
        w.require(hashlib.sha256(oldbytes).hexdigest()==row['sha256'],'N26 Phase A history differs')
        old=functions(oldbytes.decode());new=functions(current.decode())
        w.require(set(new)==set(old)|NEW_FUNCTIONS[path]
            and all(new[k]==old[k] for k in old.keys()-ROUTES[path]),'N26 shared functions outside routes changed')
        deltas[path]={k:{'old':hashlib.sha256(old[k].encode()).hexdigest() if k in old else None,
                        'new':hashlib.sha256(new[k].encode()).hexdigest()} for k in sorted(ROUTES[path]|NEW_FUNCTIONS[path])}
    plan=c.original_plan();w.require(plan['source_commit']=='51104470983cdbafd08feb87f2f39b7553779405','N26 old quality proof source differs')
    return {'schema':'n26-source-equivalence-bridge-logical-v1','composition':composition,
        'logical_predecessor':c.predecessor(),'composition_protocol':c.ref(c.LOGICAL_PROTOCOL),'phase_a_source':c.PHASE_A,'new_source':source,'runtime':runtime,
        'unchanged_files':unchanged,'shared_route_functions':deltas,'reverse_insertions':verify_reverse(root),'prior_backend_proof':plan['n23_cohort']['backend_proof'],
        'phase_a_review':phase_a_review(), 'prior_n25_backend_proof':historical_control_proof(runtime,root),
        'new_rbf_arithmetic_proof_required':True,'old_proof_scope':'N23 quality and unchanged N25 control math only; not N26 clean-input wiring'}


def verify(reference,source,runtime,root):
    value=w.read_ref(reference)
    w.require(reference==c.ref(c.BRIDGE) and value==build(source,runtime,root),'N26 byte bridge differs')
    return value


def verify_reverse(root):
    record=w.read_ref(c.ref(Path(root)/'experiments/qd_ed_n26/shared-route-insertions-v1.json'))
    w.require(record['schema']=='n26-reversible-shared-routes-v1' and record['base_commit']==c.PHASE_A
        and {r['path'] for r in record['files']}==set(ROUTES),'N26 reverse route schema differs')
    result=[]
    for row in record['files']:
        from scripts import qd_ed_n26_logical as logical
        current=logical.restore_shared(root,row['path']).decode();lines=current.splitlines(keepends=True)
        w.require(hashlib.sha256(current.encode()).hexdigest()==row['new_sha256'],'N26 new route bytes differ')
        last=len(lines)
        for edit in reversed(row['edits']):
            start,end=edit['new_start'],edit['new_end']
            w.require(0<=start<=end<=last and ''.join(lines[start:end])==edit['new'],'N26 reverse insertion mismatch')
            lines[start:end]=edit['old'].splitlines(keepends=True);last=start
        restored=''.join(lines).encode()
        frozen=subprocess.check_output(['git','show',c.PHASE_A+':'+row['path']],cwd=root)
        w.require(restored==frozen and hashlib.sha256(restored).hexdigest()==row['old_sha256'],'N26 exact prior byte reconstruction failed')
        result.append({'path':row['path'],'restored_sha256':row['old_sha256'],'new_sha256':row['new_sha256'],'edit_blocks':len(row['edits'])})
    return result


def phase_a_review():
    path=c.RUN_DIR/'root-cpu-review-v1.json'
    w.require(w.sha(path)=='ad2c38db5be770aca23e834e08814f2d1b3e13e87666ad5a8b35a8a19c8791b1',
              'N26 accepted Phase A review drift')
    return c.ref(path)


def historical_control_proof(runtime,root):
    reference=c.ref(old_contract.BACKEND_PROOF);proof=w.read_ref(reference)
    source=w.read_ref(c.ref(Path(root)/'experiments/qd_ed_n26/n25-control-source-manifest-v1.json'))
    w.require(source['commit']==c.BASE and len(source['files'])==257 and source['sha256']==w.canonical_sha(source['files']),
              'N26 historical N25 source closure differs')
    for item in source['files']:
        historical=subprocess.check_output(['git','show',c.BASE+':'+item['path']],cwd=root)
        w.require(hashlib.sha256(historical).hexdigest()==item['sha256'],'N26 historical source hash differs')
    w.require(proof.get('schema')=='n25-metered-tensor-proof-v1' and proof.get('accepted') is True
        and proof.get('source')==source and proof.get('runtime')==runtime,'N26 historical N25 proof differs')
    plan=w.read_ref(proof['plan']);report=w.read_ref(proof['report']);process=w.read_ref(proof['process'])
    w.require(plan.get('source')==source and plan.get('runtime')==runtime and proof['plan']==c.ref(old_backend.PLAN),
              'N26 historical N25 plan binding differs')
    old_backend.validate_report(report,plan,process)
    return reference


def settled_control_proofs(record,events,resources,r):
    from scripts import qd_ed_n26_logical as logical
    logical.current_matching(events,resources)
    settled_backend(record,events,r)
    old_backend.settled_proof(w.read_ref(record['prior_n25_backend_proof']),resources,r)
