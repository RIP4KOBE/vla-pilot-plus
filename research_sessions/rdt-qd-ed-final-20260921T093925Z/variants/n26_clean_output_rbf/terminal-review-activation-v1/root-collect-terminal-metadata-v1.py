"""Prospective collector: run only after N26 controller death, never during Dev."""
import hashlib, json, os, sys, time
from pathlib import Path

A = Path(__file__).resolve().parent
N = A.parent
W = N.parents[1] / 'study_worktree'
H = N / 'terminal-review-preparation-v1'
COMMIT = '6026794cd5d52f3a5054bf2704ebb3c516f9f47e'
READER_SHA = '29fb5e36e2ef0dac6a2522ec68d8e9a2dc69eb622049efa927418ef0c74f6051'
COHORT = 'N26_CLEAN_OUTPUT_RBF_DEV_20260930'
CAP = 16 * 1024 * 1024
def bounded(p):
    p = Path(p)
    assert p.is_file() and not p.is_symlink() and p.stat().st_size <= CAP
    with p.open('rb') as f: data = f.read(CAP + 1)
    assert len(data) <= CAP
    return data
def sha(p): return hashlib.sha256(bounded(p)).hexdigest()
def ref(p): return {'path': str(Path(p).resolve()), 'sha256': sha(p)}
def read(p): return json.loads(bounded(p))
def by_ref(q):
    assert set(q) == {'path', 'sha256'} and sha(q['path']) == q['sha256']
    return read(q['path'])
def save(name, value):
    p = A / name
    with p.open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
    return ref(p)
def identity(p): return {k: p[k] for k in ('pid', 'proc_start_ticks', 'boot_id')}
def dead(p):
    if p['boot_id'] != Path('/proc/sys/kernel/random/boot_id').read_text().strip(): return True
    q = Path('/proc') / str(p['pid']) / 'stat'
    if not q.exists(): return True
    return q.read_text().rsplit(')', 1)[1].split()[19] != p['proc_start_ticks']

def main():
    # This gate precedes any outcome/journal read or production import.
    controller_path = N / 'execution/controller-process-v1.json'
    controller = read(controller_path)
    assert dead(controller['process']), 'N26 controller still alive: collection prohibited'
    assert sha(H / 'root-cpu-review-v1.json') == '51f80969568800222a24baa70639e2be2729bc716826a155a06ef0041fbf9689'
    assert sha(H / 'terminal_reader_v1.py') == READER_SHA
    for q in read(H / 'reader-source-manifest-v1.json')['source_files']:
        assert sha(q['path']) == q['sha256']
    sys.path[:0] = [str(H), str(W / 'scripts'), str(W)]
    from scripts import qd_ed_final_runner as r, qd_ed_n26_contract as c, qd_ed_n26_logical as logical
    from terminal_reader_v1 import inspect_cleanup
    from bounded_metadata_v1 import canonical
    assert c.COHORT == COHORT
    records = {}
    def include(path, role):
        p = Path(path).resolve()
        assert p.name not in {'attempt-ledger.jsonl', 'gpu-healthcheck-ledger.jsonl', 'events.jsonl', 'stage_events.jsonl'}
        assert 'decision_evidence' not in p.parts and p.suffix in {'.json', '.jsonl'}
        present = p.is_file()
        data = bounded(p) if present else b''
        item = {'role': role, 'path': str(p), 'present': present,
                'sha256': hashlib.sha256(data).hexdigest() if present else None,
                'bytes': len(data)}
        if str(p) in records: assert records[str(p)] == item
        else: records[str(p)] = item
        assert len(records) <= 512 and sum(v['bytes'] for v in records.values()) <= 128 * 1024 * 1024
        return {'path': str(p), 'sha256': item['sha256']}
    def add_ref(q, role):
        observed = include(q['path'], role); assert observed == q; return observed
    def project(path, events, schema):
        stat = path.stat()
        return {'schema': schema, 'cohort_id': COHORT, 'events': events, 'event_count': len(events),
                'all_matching_events': True,
                'source_ledger': {'path': str(path.resolve()), 'sha256': r.digest(path)},
                'source_ledger_stat': {'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns, 'inode': stat.st_ino},
                'collected_at': time.time(), 'collector': ref(__file__)}
    with r.locked(N / 'execution/supervisor.lock', nonblocking=True), r.locked(W / 'data/qd-ed-runner.lock', nonblocking=True):
        assert dead(controller['process'])
        plan_path = N / 'plan.frozen.v1.gpu7.json'
        plan, profiles, runtime = r.validate_plan(plan_path, root=W)
        assert plan['source_commit'] == COMMIT and len(plan['code_files']) == 315
        journal_path = W / 'data/attempt-ledger.jsonl'
        resource_path = W / 'data/gpu-healthcheck-ledger.jsonl'
        all_events = r.read_events(journal_path)
        all_resources = r.read_events(resource_path)
        logical.current_matching(all_events, all_resources)
        own = [e for e in all_events if e.get('identity', {}).get('iteration') == COHORT]
        source_path = N / 'source-manifest.logical-v1.json'
        source = read(source_path)
        source_review_ref = plan['n26_cohort']['final_review']
        source_review = by_ref(source_review_ref)
        bridge_ref = source_review['source_bridge']; bridge = by_ref(bridge_ref)
        predecessor = by_ref(source_review['predecessor'])
        assert predecessor['logical_disposition'] in {'REJECT', 'REJECT_NUMERIC_FUTILITY'}
        proof_ref = source_review['backend_proof']; proof = by_ref(proof_ref)
        proof_plan = by_ref(proof['plan'])
        health = [e for e in all_resources if e.get('resource_id') == proof_plan['resource_id']
                  or e.get('kind') == 'n26_tensor_arithmetic_v1']
        refs = {'plan': include(plan_path, 'plan'), 'source': include(source_path, 'source'),
                'runtime': add_ref(source_review['runtime'], 'runtime'),
                'source_review': add_ref(source_review_ref, 'source_review'),
                'source_bridge': add_ref(bridge_ref, 'source_bridge'),
                'result': include(N / 'result-v1.json', 'result'),
                'status': include(N / 'execution/supervisor-status-v1.json', 'status'),
                'controller': include(controller_path, 'controller'),
                'release': include(N / 'execution-release-v1.json', 'release'),
                'proof': add_ref(proof_ref, 'proof')}
        for key in ('plan', 'report', 'process', 'terminal'): add_ref(proof[key], 'proof_' + key)
        snapshot_path = N / 'execution/terminal-ledger-v1.json'
        # Never fabricate or repair the writer's immutable snapshot/result.
        assert snapshot_path.is_file() and read(snapshot_path) == own, 'original terminal snapshot missing or stale'
        refs['journal'] = include(snapshot_path, 'journal')
        refs['current_journal'] = add_ref(save('current-journal-projection-v1.json',
            project(journal_path, own, 'n26-current-terminal-journal-projection-v1')), 'current_journal')
        refs['resources'] = add_ref(save('current-resource-projection-v1.json',
            project(resource_path, health, 'n26-current-terminal-resource-projection-v1')), 'resources')
        templates = []
        for row in plan['episodes']:
            command, _ = r.build_command(plan, profiles, runtime, row, '__N26_REVIEW_ATTEMPT__')
            templates.append({'episode_key': row['episode_key'], 'argv': command})
        precheck = {'schema': 'n26-terminal-prerequisite-attestation-v1',
            'source': refs['source'], 'plan': refs['plan'], 'runtime': refs['runtime'],
            'source_bridge': refs['source_bridge'], 'proof': refs['proof'],
            'source_commit': COMMIT, 'source_files_verified': 315, 'operations': ['validate_plan', 'build_command'],
            'all_prerequisites_passed': True, 'model_api_sim_calls': 0, 'historical_proof_lineage_verified': True,
            'predecessor_current_subset_checked': True, 'collector': ref(__file__), 'command_templates': templates,
            'historical_lineage': {'predecessor': source_review['predecessor'],
                'prior_n25_backend_proof': bridge['prior_n25_backend_proof'],
                'prior_quality_proof': bridge['prior_backend_proof'],
                'original_n25_disposition': 'INVALID_OR_INTERRUPTED',
                'logical_n25_disposition': predecessor['logical_disposition']}}
        refs['precheck'] = add_ref(save('prerequisite-attestation-v1.json', precheck), 'precheck')
        groups = {}
        for event in own: groups.setdefault(event['attempt_id'], []).append(event)
        names = {'terminal': 'attempt-result.json', 'context': 'n23-worker-context.json', 'command': 'command.json',
                 'process': 'process.json', 'audit_start': 'eds_eval/in-worker-audit-start.json',
                 'receipt': 'eds_eval/in-worker-audit-receipt.json', 'audit': 'eds_eval/decision-evidence-audit.json',
                 'metrics': 'eds_eval/eds_metrics.jsonl', 'compute': 'eds_eval/episode_compute.jsonl'}
        processes = {'controller': identity(controller['process']), 'proof': identity(by_ref(proof['process']))}
        bindings = []
        for aid, events in groups.items():
            first = events[0]; folder = Path(first['output_dir']).resolve()
            assert folder == (Path(plan['artifact_root']) / 'attempts' / aid).resolve() and Path(aid).name == aid
            fields = {role: include(folder / name, role) for role, name in names.items()}
            item = {'attempt_id': aid, 'refs': fields}
            process = by_ref(fields['process']) if fields['process']['sha256'] else None
            processes[aid] = identity(process) if process is not None else None
            if first.get('retry_of'):
                eligibility_ref = first['n26_recovery_eligibility']; eligibility = by_ref(eligibility_ref)
                assert eligibility['primary_attempt_id'] == first['retry_of']
                assert eligibility['source_commit'] == COMMIT and eligibility['plan'] == refs['plan']
                assert all(e.get('n26_recovery_eligibility') == eligibility_ref for e in events)
                item['eligibility'] = add_ref(eligibility_ref, 'eligibility')
                attestation = {'schema': 'n26-original-typed-eligibility-attestation-v1',
                    'eligibility': eligibility_ref, 'source': refs['source'], 'plan': refs['plan'],
                    'primary_attempt_id': first['retry_of'], 'method': 'original_frozen_controller_and_classifier_metadata',
                    'classification_basis_sha256': canonical(eligibility), 'root_verified_original_basis': True,
                    'stage_and_tensors_reaudited_by_terminal_reader': False, 'collector': ref(__file__)}
                item['recovery_attestation'] = add_ref(save('recovery-attestation-' + aid + '.json', attestation), 'recovery_attestation')
            bindings.append(item)
        cleanup_observed = inspect_cleanup(processes, W)
        cleanup = {'schema': 'n26-terminal-cleanup-attestation-v1', 'plan': refs['plan'],
            'controller': refs['controller'], 'current_journal': refs['current_journal'], 'resources': refs['resources'],
            'expected_processes': processes, 'all_owned_processes_inspected': True, 'collector': ref(__file__),
            'root_public_cleanup_observation': cleanup_observed}
        refs['cleanup_attestation'] = add_ref(save('cleanup-attestation-v1.json', cleanup), 'cleanup_attestation')
        static = [ref(H / name) for name in ('terminal_reader_v1.py', 'bounded_metadata_v1.py', 'metadata_semantics_v1.py')]
        static += [ref(__file__), controller['wrapper']]
        assert all(sha(q['path']) == q['sha256'] for q in static)
        draft = {'schema': 'n26-terminal-metadata-input-v1', 'root_authorized': False, 'executable': False,
                 'source_root': str(W), 'files': list(records.values()), 'refs': refs, 'attempts': bindings, 'static_objects': static}
        output = save('metadata-input-draft-v1.json', draft)
        print(json.dumps({'draft': output, 'files': len(records), 'metadata_bytes': sum(v['bytes'] for v in records.values()),
                          'attempts': len(bindings), 'automatic_reader_or_gpu_execution': False}))

if __name__ == '__main__': main()
