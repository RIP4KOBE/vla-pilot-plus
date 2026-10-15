"""Record observed first dispatch without changing any frozen experiment source."""
import json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
import yaml

A = Path(__file__).resolve().parent
N = A.parent
W = N.parents[1] / 'study_worktree'
sys.path[:0] = [str(W / 'scripts'), str(W)]
from scripts import qd_ed_final_runner as r, qd_ed_n23_worker as w, qd_ed_n26_contract as c

observation = json.loads(subprocess.check_output(
    [sys.executable, '-B', str(A / 'root-live-status-v1.py')], text=True))
assert observation['dispatches'] >= 1
assert observation['controller_liveness']['same_start_ticks']
assert observation['controller_liveness']['state'] != 'Z'
assert observation['stage']['observed_transport_pairs'] == [
    ['codex_cli', 'chatgpt', 'gpt-6-astra', 'low']]
record = {
    'schema': 'n26-root-first-dispatch-observation-v1',
    'observed_at': datetime.now(timezone.utc).isoformat(),
    'observation': observation,
    'controller': c.ref(N / 'execution/controller-process-v1.json'),
    'plan': c.ref(N / 'plan.frozen.v1.gpu7.json'),
    'release': c.ref(N / 'execution-release-v1.json'),
    'provider': 'Current managed Codex CLI login only; no Poe or alternate account/provider fallback.',
    'validation_authorized': False,
    'formal_authorized': False,
}
p = N / 'execution/root-first-dispatch-observation-v1.json'
w.atomic_json(p, record)
with r.locked(W / 'data/qd-ed-state.lock'):
    state = r.read_state(W / 'research-state.yaml')
    assert state['current_iteration']['candidate'] == 'N26'
    state['current_iteration'].update(
        status='DEV_RUNNING', first_dispatch_observation=c.ref(p))
    tmp = W / 'research-state.yaml.root-n26-dispatch-tmp'
    with tmp.open('w') as f:
        yaml.safe_dump(state, f, sort_keys=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, W / 'research-state.yaml')
cp_path = W / '.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
cp = json.loads(cp_path.read_text())
cp.update(status='N26_DEV_RUNNING', phase='MONITOR',
          n26_status='DEV_RUNNING', n26_first_dispatch_observation=c.ref(p),
          target_met=False, target_achieved=False,
          updated_at=datetime.now(timezone.utc).isoformat())
cp_path.write_text(json.dumps(cp, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'observation': c.ref(p), 'status': 'DEV_RUNNING',
                  'stage': observation['stage']}, ensure_ascii=False))
