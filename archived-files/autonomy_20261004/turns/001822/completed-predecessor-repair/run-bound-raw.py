import hashlib, importlib.util, json, tempfile
from pathlib import Path
out = Path(__file__).parent
spec = importlib.util.spec_from_file_location('isolated', out / 'test_recovery_isolated.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
a = json.loads((out / 'authority-v1.json').read_bytes())
d = Path(a['failure']['path']).read_bytes()
assert hashlib.sha256(d).hexdigest() == a['failure']['sha256']
diagnosis = json.loads(d)
with tempfile.TemporaryDirectory(prefix='bound-raw-', dir=out) as temporary:
    f = m.recovery_cpu.__wrapped__(Path(temporary))
    f = m.recovery_multi_cpu.__wrapped__(f)
    f = m.recovery_terminal_cpu.__wrapped__(f)
    payloads = []
    for entry, predecessor in zip(diagnosis['predecessors'], f.contract['predecessors']):
        ref = entry['raw_sequence']
        raw = Path(ref['path']).read_bytes()
        assert len(raw) == ref['bytes'] and hashlib.sha256(raw).hexdigest() == ref['sha256']
        rows = [json.loads(line) for line in raw.splitlines()]
        assert [row['event'] for row in rows] == entry['events']
        predecessor.update({k:entry[k] for k in ('resource_id', 'events', 'terminal_status',
            'telemetry_complete', 'retained_charge_gpu_seconds', 'retained_charge_gpu_hours', 'provider_calls_retained')})
        predecessor['rows'] = rows
        payloads.append((rows, raw))
    original_encoder = f.raw
    def exact_raw(rows):
        for retained_rows, raw in payloads:
            if rows == retained_rows:
                return raw
        return original_encoder(rows)
    f.raw = exact_raw
    m.repin_terminal_partition(f)
    assert f.retained_raw == b''.join(raw for _, raw in payloads)
    before = {p:p.read_bytes() for p in f.data.iterdir()}
    assert f.e.specification() == f.spec
    assert f.e.preparation_health_suffix(f.plan, f.baseline, f.resources) == f.health
    assert f.calls == ['derive', 'accepted']
    budget = f.e.r.budget_snapshot(f.baseline[f.env['JOURNALS'][0]], f.resources)
    charged = sum(row['gpu_process_wall_seconds'] for row in f.old)
    assert charged == diagnosis['retained_charge_gpu_seconds']
    assert abs(budget['gpu_hours_consumed'] - (7 + 9 + charged + 2 + 1) / 3600) < 1e-12
    assert {p:p.read_bytes() for p in f.data.iterdir()} == before
    result = dict(result='PASS', raw_bytes_identical=True, read_only_captures=True,
        retained_charge_gpu_seconds=charged, retained_charge_gpu_hours=charged/3600,
        raw_references=[p['raw_sequence'] for p in diagnosis['predecessors']],
        terminal_statuses=[p['terminal_status'] for p in diagnosis['predecessors']],
        telemetry_complete=[p['telemetry_complete'] for p in diagnosis['predecessors']],
        scope='Actual diagnosis-bound raw predecessor bytes copied into isolated synthetic journal anchors; no owner journals read or written; detached successor authority boundaries synthetic; no adoption or readiness certification')
(out / 'bound-raw-result.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
