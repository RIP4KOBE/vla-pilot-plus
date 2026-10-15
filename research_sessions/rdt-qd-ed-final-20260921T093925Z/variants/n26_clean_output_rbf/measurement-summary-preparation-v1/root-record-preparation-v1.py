import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
H = Path(__file__).resolve().parent
W = H.parent.parents[1] / 'study_worktree'
p = H / 'root-cpu-summary-protocol-v1.md'
reference = {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
assert reference['sha256'] == 'fc4f01c8948d21e1696ed13aefbdb0885fbea67491a6ecde3a0d64684824d5f5'
cp = W / '.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
data = json.loads(cp.read_text())
data.update(n26_scalar_summary_cpu_protocol=reference,
            in_flight_executor='/root/n22_cpu_executor', updated_at=datetime.now(timezone.utc).isoformat())
cp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'protocol': reference, 'actual_read_authorized': False}))
