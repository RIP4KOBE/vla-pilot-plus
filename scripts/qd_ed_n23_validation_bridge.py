"""Exact historical science bridge; evaluation source is a new commit."""
import subprocess
from pathlib import Path
from scripts import qd_ed_n23_worker as w

DEV_COMMIT='51104470983cdbafd08feb87f2f39b7553779405'
WORKER_INSERT="""    validation_plan = read_ref(context['plan'])
    if validation_plan.get('n23_validation') is not None:
        from scripts import qd_ed_n23_validation_contract as validation
        return validation.validate_worker_context(context, main_argv, ROOT)
"""
RUNNER_EDITS=[
("def is_n23_v2_plan(plan):\n", "def is_n23_validation_plan(plan):\n    return plan.get('n23_validation') is not None\n\n\ndef is_n23_v2_plan(plan):\n"),
("def n23_support(plan=None):\n", "def n23_support(plan=None):\n    if plan is not None and is_n23_validation_plan(plan):\n        from scripts import qd_ed_n23_validation_contract\n        return qd_ed_n23_validation_contract\n"),
("        require(row.get('iteration') in {n23v2.COHORT,n23v2.PREFLIGHT}, 'N23 v2 finite budget scope differs')",
 "        if row.get('iteration') == 'N23_VALIDATION_20260930':\n            from scripts import qd_ed_n23_validation_contract as n23validation\n            n23validation.require_budget_state(state, globals())\n        else:\n            require(row.get('iteration') in {n23v2.COHORT,n23v2.PREFLIGHT}, 'N23 v2 finite budget scope differs')"),
("def check_retry(events, row):\n", "def check_retry(events, row):\n    if row.get('n23_validation_recovery_eligibility') is not None:\n        from scripts import qd_ed_n23_validation_recovery as recovery\n        return recovery.check_retry(events, row, globals())\n"),
("    sync_state_from_journal(root,[*events,event])\n",
 "    sync_state_from_journal(root,[*events,event])\n    if event.get('identity', {}).get('iteration') == 'N23_VALIDATION_20260930':\n        from scripts import qd_ed_n23_validation_identity as validation_identity\n        validation_identity.register_dispatch(root, event)\n"),
("            if is_n23_v2_plan(plan):\n                row=n23_support(plan).effective_row",
 "            if is_n23_v2_plan(plan) or is_n23_validation_plan(plan):\n                row=n23_support(plan).effective_row"),
("                    if is_n23_v2_plan(plan):\n                        n23_audit_binding",
 "                    if is_n23_v2_plan(plan) or is_n23_validation_plan(plan):\n                        n23_audit_binding"),
("                if is_n23_v2_plan(plan) and n23_audit_binding is not None:",
 "                if (is_n23_v2_plan(plan) or is_n23_validation_plan(plan)) and n23_audit_binding is not None:"),
]
ADDITIONS={
'scripts/qd_ed_n23_validation_bridge.py','scripts/qd_ed_n23_validation_contract.py',
'scripts/qd_ed_n23_validation_identity.py','scripts/qd_ed_n23_validation_evidence.py',
'scripts/qd_ed_n23_validation_recovery.py','scripts/qd_ed_n23_validation_prepare.py',
'scripts/qd_ed_n23_validation_supervise.py','scripts/qd_ed_n23_validation_report.py',
'tests/test_qd_ed_n23_validation.py','tests/test_qd_ed_n23_validation_runtime.py',
'experiments/iteration_023_actuator_clipped_quality/protocol-validation-conditional-v1.md',
'experiments/iteration_023_actuator_clipped_quality/validation-runtime-contract-v1.md'}
MODIFIED={'scripts/qd_ed_final_runner.py','scripts/qd_ed_n23_worker.py'}


def original(root,path):
    return subprocess.check_output(['git','show',DEV_COMMIT+':'+path],cwd=root)


def verify_delta(root,parent):
    root=Path(root)
    w.require(parent['source_commit']==DEV_COMMIT and len(parent['code_files'])==214,'validation Dev source identity/count differs')
    changed=set(subprocess.check_output(['git','diff','--name-only',DEV_COMMIT,'HEAD'],cwd=root,text=True).splitlines())
    w.require(changed<=ADDITIONS|MODIFIED,'validation source extends evaluation-only scope')
    for item in parent['code_files']:
        name=item['path'];before=original(root,name);after=(root/name).read_bytes()
        import hashlib
        w.require(hashlib.sha256(before).hexdigest()==item['sha256'],'validation original committed Dev bytes differ')
        if name=='scripts/qd_ed_n23_worker.py':
            insertion=WORKER_INSERT.encode()
            w.require(after.count(insertion)==1,'validation worker exact routing insertion missing')
            after=after.replace(insertion,b'',1)
        elif name=='scripts/qd_ed_final_runner.py':
            for old,new in reversed(RUNNER_EDITS):
                w.require(after.count(new.encode())==1,'validation runner exact routing change differs')
                after=after.replace(new.encode(),old.encode(),1)
        w.require(after==before,'validation changed science/arithmetic/worker or old runner logic')
    return sorted(changed)


def source_record(root,parent,protocol_sha):
    changed=verify_delta(root,parent)
    w.require(w.sha(Path(root)/'experiments/iteration_023_actuator_clipped_quality/protocol-validation-conditional-v1.md')
        ==protocol_sha,'validation tracked protocol changed')
    source=w.source_record(root,{v['path'] for v in parent['code_files']}|ADDITIONS)
    return source,{'schema':'n23-validation-source-bridge-v1','dev_source':{
        'commit':DEV_COMMIT,'files':parent['code_files'],'sha256':w.canonical_sha(parent['code_files'])},
        'validation_source':source,'changed_paths':changed,'scientific_unchanged':True,
        'worker_change':'exact_validate_context_validation_route_only',
        'runner_change':'exact_closed_validation_routing_insertions'}
