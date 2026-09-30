"""Exact, reversible evaluation-only bridge from all230 frozen N24 Dev files."""
import hashlib
import subprocess
from pathlib import Path
from scripts import qd_ed_n23_worker as w
DEV_COMMIT='3b7afa02757eb3519d95547e4b6e6e939f7068f2'
WORKER_INSERT="""    if plan.get('n24_validation') is not None:
        from scripts import qd_ed_n24_validation_contract as validation
        return validation.validate_worker_context(context, main_argv, root, output, plan, runtime)
"""
RUNNER_EDITS=[
("def is_n24_plan(plan):\n    return plan.get('n24_cohort') is not None or 'N24' in plan.get('candidate_profiles', {})",
 "def is_n24_validation_plan(plan):\n    return plan.get('n24_validation') is not None\n\n\ndef is_n24_plan(plan):\n    return not is_n24_validation_plan(plan) and (plan.get('n24_cohort') is not None or 'N24' in plan.get('candidate_profiles', {}))",1),
("return not is_n24_plan(plan) and (plan.get('n23_cohort')", "return not is_n24_validation_plan(plan) and not is_n24_plan(plan) and (plan.get('n23_cohort')",1),
("return not is_n24_plan(plan) and not is_n23_plan(plan) and (plan.get('n7_cohort')", "return not is_n24_validation_plan(plan) and not is_n24_plan(plan) and not is_n23_plan(plan) and (plan.get('n7_cohort')",1),
("    return is_n23_plan(plan) or is_n24_plan(plan)","    return is_n23_plan(plan) or is_n24_plan(plan) or is_n24_validation_plan(plan)",1),
("    return is_n23_v2_plan(plan) or is_n24_plan(plan)","    return is_n23_v2_plan(plan) or is_n24_plan(plan) or is_n24_validation_plan(plan)",1),
("def metered_support(plan):\n", "def metered_support(plan):\n    if is_n24_validation_plan(plan):\n        from scripts import qd_ed_n24_validation_contract\n        return qd_ed_n24_validation_contract\n",1),
("or is_n23_plan(plan) or is_n24_plan(plan)),", "or is_n23_plan(plan) or is_n24_plan(plan) or is_n24_validation_plan(plan)),",2),
("        if row.get('iteration') == n24.COHORT:\n            n24.require_state(state, globals())\n", "        if row.get('iteration') == n24.COHORT:\n            n24.require_state(state, globals())\n        elif row.get('iteration') == 'N24_VALIDATION_20260930':\n            from scripts import qd_ed_n24_validation_contract as validation\n            validation.require_budget_state(state, globals())\n",1),
("def check_retry(events, row):\n", "def check_retry(events, row):\n    if row.get('n24_validation_recovery_eligibility') is not None:\n        from scripts import qd_ed_n24_validation_recovery as recovery\n        return recovery.check_retry(events, row, globals())\n",1),
("    sync_state_from_journal(root,[*events,event])\n", "    sync_state_from_journal(root,[*events,event])\n    if event.get('identity', {}).get('iteration') == 'N24_VALIDATION_20260930':\n        from scripts import qd_ed_n24_validation_identity as validation_identity\n        validation_identity.register_dispatch(root, event)\n",1),
("terminal['n24_episode_dispatched' if is_n24_plan(plan) else 'n23_episode_dispatched']", "terminal['n24_validation_episode_dispatched' if is_n24_validation_plan(plan) else 'n24_episode_dispatched' if is_n24_plan(plan) else 'n23_episode_dispatched']",2),
]
ADDITIONS={f'scripts/qd_ed_n24_validation_{name}.py' for name in ('bridge','contract','identity','evidence','recovery','prepare','supervise','report')}|{
 'tests/test_qd_ed_n24_validation.py','tests/test_qd_ed_n24_validation_runtime.py',
 'experiments/qd_ed_n24/protocol-validation-conditional-v1.md','experiments/qd_ed_n24/validation-controller-contract-v1.md'}
MODIFIED={'scripts/qd_ed_final_runner.py','scripts/qd_ed_n23_worker.py'}


def original(root,path):return subprocess.check_output(['git','show',DEV_COMMIT+':'+path],cwd=root)


def verify_delta(root,parent):
    root=Path(root)
    w.require(parent['source_commit']==DEV_COMMIT and len(parent['code_files'])==230,'N24 validation original Dev source/count differs')
    changed=set(subprocess.check_output(['git','diff','--name-only',DEV_COMMIT,'HEAD'],cwd=root,text=True).splitlines())
    w.require(changed<=ADDITIONS|MODIFIED,'N24 validation exceeds evaluation-only file scope')
    for item in parent['code_files']:
        name=item['path'];before=original(root,name);after=(root/name).read_bytes()
        w.require(hashlib.sha256(before).hexdigest()==item['sha256'],'N24 original230 committed bytes differ')
        if name=='scripts/qd_ed_n23_worker.py':
            w.require(after.count(WORKER_INSERT.encode())==1,'N24 validation worker exact insertion differs')
            after=after.replace(WORKER_INSERT.encode(),b'',1)
        elif name=='scripts/qd_ed_final_runner.py':
            for old,new,count in reversed(RUNNER_EDITS):
                w.require(after.count(new.encode())==count,'N24 validation runner exact insertion differs')
                after=after.replace(new.encode(),old.encode(),count)
        w.require(after==before,'N24 validation changed science/worker/old evaluation semantics')
    return sorted(changed)


def source_record(root,parent,protocol_sha):
    changed=verify_delta(root,parent)
    w.require(w.sha(Path(root)/'experiments/qd_ed_n24/protocol-validation-conditional-v1.md')==protocol_sha,'N24 tracked validation protocol drift')
    source=w.source_record(root,{x['path'] for x in parent['code_files']}|ADDITIONS)
    return source,{'schema':'n24-validation-source-bridge-v1','dev_source':{'commit':DEV_COMMIT,'files':parent['code_files'],
        'sha256':w.canonical_sha(parent['code_files'])},'validation_source':source,'changed_paths':changed,
        'scientific_unchanged':True,'worker_change':'exact_validate_context_route_only',
        'runner_change':'exact_closed_validation_routing_insertions','new_gpu_preflight':False}
