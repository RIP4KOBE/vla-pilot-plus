"""Byte/function equivalence to the settled N23 arithmetic proof; no GPU work."""
import ast
import hashlib
from pathlib import Path
import subprocess

from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n24_contract as c

UNCHANGED_BASE=('main.py','core/qd_actuator_clipped_quality.py','core/qd_executed_quality.py','core/qd_ed.py',
 'core/qd_grasp_timing.py','core/rdt_libero_action_converter.py','core/env_adapters/libero_adapter.py',
 'scripts/qd_ed_audit_backend.py','scripts/qd_ed_n23_backend_preflight.py','scripts/qd_ed_n23_v2_backend.py',
 'configs/qd_ed_final/candidate_n23.json','configs/qd_ed_final/candidate_n7.json','configs/qd_ed_final/baseline_profiles.json')
UNCHANGED_PHASE_A=('core/rdt_policy_steer.py','core/decision_evidence.py','core/eds_eval_metrics.py',
 'core/qd_gripper_parent_rescue.py','scripts/audit_decision_evidence.py','scripts/audit_gripper_parent_rescue.py',
 'configs/config.yaml','configs/qd_ed_final/candidate_n24.json')
WORKER_CHANGED={'validate_context','run_worker','verify_receipt'}


def old_bytes(root,commit,path):
    return subprocess.check_output(['git','show',commit+':'+path],cwd=root)


def functions(text):
    return {n.name:ast.get_source_segment(text,n) for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}


def build(source,runtime,root):
    root=Path(root)
    changed=set(subprocess.check_output(['git','diff','--name-only',c.PHASE_A,'HEAD'],cwd=root,text=True).splitlines())
    w.require(changed<=c.CONTROLLER_DELTA,'N24 controller changed frozen Phase A science')
    records=[]
    for commit,paths in ((c.BASE,UNCHANGED_BASE),(c.PHASE_A,UNCHANGED_PHASE_A)):
        for path in paths:
            current=(root/path).read_bytes()
            w.require(current==old_bytes(root,commit,path),'N24 source-equivalence drift: '+path)
            records.append({'path':path,'sha256':hashlib.sha256(current).hexdigest(),'base_commit':commit})
    old=functions(old_bytes(root,c.BASE,'scripts/qd_ed_n23_worker.py').decode())
    new=functions((root/'scripts/qd_ed_n23_worker.py').read_text())
    w.require(set(old)==set(new) and all(old[k]==new[k] for k in old.keys()-WORKER_CHANGED),
        'N24 worker changed functions outside explicit cohort/arithmetic routing')
    # The allowed three bodies are separately SHA-bound for explicit root review.
    worker_delta={k:{'old_sha256':hashlib.sha256(old[k].encode()).hexdigest(),
        'new_sha256':hashlib.sha256(new[k].encode()).hexdigest()} for k in sorted(WORKER_CHANGED)}
    parent=c.original_plan()
    w.require(parent['source_commit']==c.BASE,'N24 arithmetic parent source differs')
    return {'schema':'n24-source-equivalence-bridge-v1','from_source':c.BASE,'phase_a_source':c.PHASE_A,
        'new_source':source,'runtime':runtime,'unchanged_files':records,'worker_route_changes':worker_delta,
        'prior_backend_proof':parent['n23_cohort']['backend_proof'],
        'phase_a_cpu_report':c.ref(c.RUN_DIR/'cpu-implementation-report-v1.md'),
        'phase_a_cpu_tests':c.ref(c.RUN_DIR/'cpu-test-results-v1.json'),
        'new_gpu_preflight':False,'scope':'same numerical functions; new parent routing proven on CPU, no task efficacy claim'}


def verify(reference,source,runtime,root):
    record=w.read_ref(reference)
    w.require(reference==c.ref(c.BRIDGE) and record==build(source,runtime,root),'N24 source bridge differs')
    return record


def settled_backend(record,events,r):
    """Consume only hash-bound old proof JSON and settled cost, never tensor corpus."""
    proof=record['prior_backend_proof'];plan=w.read_ref(proof['plan']);report=w.read_ref(proof['report'])
    groups=r['event_groups'](events);group=groups.get(proof['attempt_id'],[])
    w.require([e['event'] for e in group]==['reserved','dispatched','valid'],'N24 historical backend not settled')
    final=group[-1]
    w.require(final.get('outcome_valid') is True and final.get('budget_bucket')=='recovery'
        and final.get('backend_preflight_report')==proof['report'] and final.get('process')==report.get('process')
        and report.get('schema')=='n23-backend-preflight-proof-v2' and report.get('accepted') is True
        and report.get('task_outcome') is False and report.get('attempt_id')==proof['attempt_id']
        and report.get('plan')==proof['plan'] and report.get('source')==plan['source']
        and plan['source']['commit']==c.BASE and plan['runtime']==report.get('runtime')==record['runtime']
        and 0<=report['worker_wall_seconds']<=final['gpu_process_wall_seconds']<=160,'N24 old arithmetic proof identity/cost differs')
    batches=report.get('batches',[]);synthetic=report.get('synthetic',[])
    w.require(len(batches)==176 and sum(x.get('candidates',0) for x in batches)==2816 and len(synthetic)==2
        and all(x.get('candidates')==16 and x.get('dtype')=='torch.bfloat16' for x in batches)
        and [x.get('dtype') for x in synthetic]==['torch.float32','torch.bfloat16']
        and all(x.get('candidates')==4 for x in synthetic)
        and all(x.get('accepted') is True and x.get('mismatches')==[] and x.get('production_helper_passed') is True
                and x.get('independent_passed') is True and x.get('wrong_score_rejected') is True for x in batches+synthetic)
        and report.get('wrong_bounds_rejected') is True and report.get('errors')==[], 'N24 strict arithmetic proof coverage differs')
    backend=report.get('backend',{})
    w.require(backend.get('kind')=='cuda' and backend.get('logical_device')=='cuda:0'
        and backend.get('physical_uuid')==c.GPU7_UUID
        and {'torch.float32','torch.bfloat16'}<=set(backend.get('dtype_coverage',[])), 'N24 old assigned backend proof differs')
    return proof
