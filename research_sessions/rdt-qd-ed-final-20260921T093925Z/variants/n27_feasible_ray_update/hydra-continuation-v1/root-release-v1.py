import json, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'scripts'))
sys.path.insert(0, str(Path.cwd()))
from scripts import qd_ed_final_runner as r, qd_ed_n27_cont_contract as c, qd_ed_n23_worker as w, qd_ed_n27_supervise as old, qd_ed_n27_cont_supervise as sup
plan = r.read_json(c.PLAN)
review = r.read_json(c.RUN_DIR / 'root-command-review-v1.json')
assert review['accepted'] and review['plan'] == c.ref(c.PLAN) and len(review['commands']) == 13
old.device_check()
(c.RUN_DIR / 'execution').mkdir(exist_ok=True)
release_path = c.RUN_DIR / 'execution-release-v1.json'
with r.locked(c.RUN_DIR / 'execution/supervisor.lock', nonblocking=True), r.locked(c.ROOT / 'data/qd-ed-runner.lock', nonblocking=True):
    assert not release_path.exists()
    capacity = c.full_capacity(r.read_state(c.ROOT / 'research-state.yaml'), r.read_events(c.ROOT / 'data/attempt-ledger.jsonl'), r.read_events(c.ROOT / 'data/gpu-healthcheck-ledger.jsonl'), vars(r))
    release = {'schema': 'n27-hydra-execution-release-v1', 'plan': c.ref(c.PLAN), 'source_commit': plan['source_commit'], 'cohort_id': c.COHORT,
               'authority': c.ref(c.AUTHORITY), 'seal': c.ref(c.SEAL), 'episode_keys': [row['episode_key'] for row in plan['episodes']],
               'limits': c.LIMITS, 'one_launch': True, 'physical_gpu': 7, 'validation_authorized': False, 'formal_authorized': False}
    w.atomic_json(release_path, release)
    sup.release_check(release_path, c.PLAN, plan)
    cp = c.ROOT / '.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
    checkpoint = r.read_json(cp)
    checkpoint.update(status='N27_HYDRA_CONTINUATION_RELEASED', source_commit=plan['source_commit'],
        in_flight_executor=None, in_flight_executors=[], active_controller=None, execution_tool_session=None,
        automatic_gpu_dispatch_authorized=True,
        automatic_gpu_dispatch_scope='Exactly the released 13-row N27 Hydra continuation on GPU7; one launch; no further retry; validation/formal remain closed.',
        execution_release=c.ref(release_path), n27_continuation_plan=c.ref(c.PLAN), n27_continuation_authority=c.ref(c.AUTHORITY),
        n27_continuation_root_command_review=c.ref(c.RUN_DIR / 'root-command-review-v1.json'), goal_achieved=False,
        next_action='Launch released continuation once; monitor and independently review every terminal receipt.')
    r.durable_json(cp, checkpoint)
    w.atomic_json(c.RUN_DIR / 'root-release-harness-notes-v1.json', {'schema': 'root-release-harness-notes-v1',
        'earlier_root_only_errors': ['Import path omitted scripts/ when calling device_check from stdin.', 'Fresh execution directory absent before opening supervisor.lock.'],
        'earlier_errors_before_release_or_dispatch': True, 'new_gpu_experiments': 0, 'new_api_calls': 0})
print(json.dumps({'release': c.ref(release_path), 'capacity': capacity, 'gpu': 7, 'codex_only': True}))
