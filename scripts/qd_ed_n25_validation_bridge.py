"""Exact, reversible evaluation-only bridge from all257 frozen N25 Dev files."""
import hashlib
import subprocess
from pathlib import Path
from scripts import qd_ed_n23_worker as w
DEV_COMMIT='5a65ef15968cc68c82314e8c0773b3365ad45fa0'
WORKER_INSERT="""    if plan.get('n25_validation') is not None:
        from scripts import qd_ed_n25_validation_contract as validation
        return validation.validate_worker_context(context, main_argv, root, output, plan, runtime)
"""
RUNNER_EDITS=[('def is_n25_plan(plan):\n'
  "    return plan.get('n25_cohort') is not None or 'N25' in plan.get('candidate_profiles', {})",
  'def is_n25_validation_plan(plan):\n'
  "    return plan.get('n25_validation') is not None\n"
  '\n'
  '\n'
  'def is_n25_plan(plan):\n'
  "    return not is_n25_validation_plan(plan) and (plan.get('n25_cohort') is not None or 'N25' in "
  "plan.get('candidate_profiles', {}))",
  1),
 ('return not is_n25_plan(plan) and not is_n24_plan(plan)',
  'return not is_n25_validation_plan(plan) and not is_n25_plan(plan) and not is_n24_plan(plan)',
  3),
 ('    return is_n25_plan(plan) or is_n23_plan(plan) or is_n24_plan(plan)',
  '    return is_n25_validation_plan(plan) or is_n25_plan(plan) or is_n23_plan(plan) or is_n24_plan(plan)',
  1),
 ('    return is_n25_plan(plan) or is_n23_v2_plan(plan) or is_n24_plan(plan)',
  '    return is_n25_validation_plan(plan) or is_n25_plan(plan) or is_n23_v2_plan(plan) or is_n24_plan(plan)',
  1),
 ('def metered_support(plan):\n',
  'def metered_support(plan):\n'
  '    if is_n25_validation_plan(plan):\n'
  '        from scripts import qd_ed_n25_validation_contract\n'
  '        return qd_ed_n25_validation_contract\n',
  1),
 ('or is_n25_plan(plan)),', 'or is_n25_plan(plan) or is_n25_validation_plan(plan)),', 2),
 ("    if row.get('iteration') == 'N25_ACTUATOR_CLIPPED_RBF_DEV_20260930':",
  "    if row.get('iteration') == 'N25_VALIDATION_20260930':\n"
  '        from scripts import qd_ed_n25_validation_contract as validation\n'
  '        validation.require_budget_state(state, globals())\n'
  "        bucket_caps = validation.CAPS['buckets']\n"
  "    elif row.get('iteration') == 'N25_ACTUATOR_CLIPPED_RBF_DEV_20260930':",
  1),
 ('def check_retry(events, row):\n',
  'def check_retry(events, row):\n'
  "    if row.get('n25_validation_recovery_eligibility') is not None:\n"
  '        from scripts import qd_ed_n25_validation_recovery as recovery\n'
  '        return recovery.check_retry(events, row, globals())\n',
  1),
 ('    sync_state_from_journal(root,[*events,event])\n',
  '    sync_state_from_journal(root,[*events,event])\n'
  "    if event.get('identity', {}).get('iteration') == 'N25_VALIDATION_20260930':\n"
  '        from scripts import qd_ed_n25_validation_identity as validation_identity\n'
  '        validation_identity.register_dispatch(root, event)\n',
  1),
 ("terminal['n25_episode_dispatched' if is_n25_plan(plan)",
  "terminal['n25_validation_episode_dispatched' if is_n25_validation_plan(plan) else "
  "'n25_episode_dispatched' if is_n25_plan(plan)",
  2)]
ADDITIONS={f'scripts/qd_ed_n25_validation_{name}.py' for name in ('bridge','contract','identity','evidence','recovery','prepare','supervise','report')}|{
 'tests/test_qd_ed_n25_validation.py','tests/test_qd_ed_n25_validation_runtime.py',
 'experiments/qd_ed_n25/protocol-validation-conditional-v1.md',
 'experiments/qd_ed_n25/protocol-validation-routing-addendum-v1.md','experiments/qd_ed_n25/validation-controller-contract-v1.md'}
MODIFIED={'scripts/qd_ed_final_runner.py','scripts/qd_ed_n23_worker.py'}


def original(root,path):return subprocess.check_output(['git','show',DEV_COMMIT+':'+path],cwd=root)


def verify_delta(root,parent):
    root=Path(root)
    w.require(parent['source_commit']==DEV_COMMIT and len(parent['code_files'])==257,'N25 validation original Dev source/count differs')
    changed=set(subprocess.check_output(['git','diff','--name-only',DEV_COMMIT,'HEAD'],cwd=root,text=True).splitlines())
    w.require(changed<=ADDITIONS|MODIFIED,'N25 validation exceeds evaluation-only file scope')
    for item in parent['code_files']:
        name=item['path'];before=original(root,name);after=(root/name).read_bytes()
        w.require(hashlib.sha256(before).hexdigest()==item['sha256'],'N25 original257 committed bytes differ')
        if name=='scripts/qd_ed_n23_worker.py':
            w.require(after.count(WORKER_INSERT.encode())==1,'N25 validation worker exact insertion differs')
            after=after.replace(WORKER_INSERT.encode(),b'',1)
        elif name=='scripts/qd_ed_final_runner.py':
            for old,new,count in reversed(RUNNER_EDITS):
                w.require(after.count(new.encode())==count,'N25 validation runner exact insertion differs')
                after=after.replace(new.encode(),old.encode(),count)
        w.require(after==before,'N25 validation changed science/worker/old evaluation semantics')
    return sorted(changed)


def source_record(root,parent,protocol_sha,addendum_sha):
    changed=verify_delta(root,parent)
    w.require(w.sha(Path(root)/'experiments/qd_ed_n25/protocol-validation-conditional-v1.md')==protocol_sha,'N25 tracked validation protocol drift')
    w.require(w.sha(Path(root)/'experiments/qd_ed_n25/protocol-validation-routing-addendum-v1.md')==addendum_sha,'N25 tracked routing addendum drift')
    source=w.source_record(root,{x['path'] for x in parent['code_files']}|ADDITIONS)
    return source,{'schema':'n25-validation-source-bridge-v1','dev_source':{'commit':DEV_COMMIT,'files':parent['code_files'],
        'sha256':w.canonical_sha(parent['code_files'])},'validation_source':source,'changed_paths':changed,
        'scientific_unchanged':True,'worker_change':'exact_validate_context_route_only',
        'runner_change':'exact_closed_validation_routing_insertions','new_gpu_preflight':False}
