from pathlib import Path
import json, hashlib, datetime, subprocess, fcntl, os, yaml

W = Path.cwd()
A = W.parent / 'autonomy_20261004'
T = A / 'turns/001787'
R = A / 'turns/001785/independent-b5-review'
C = W / '.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'

def read(p):
    return json.loads(p.read_text())

def ref(p):
    b = p.read_bytes()
    return dict(path=str(p), bytes=len(b), sha256=hashlib.sha256(b).hexdigest())

def verify(r):
    actual = ref(Path(r['path']))
    assert actual['sha256'] == r['sha256'], r['path']
    if 'bytes' in r:
        assert actual['bytes'] == r['bytes'], r['path']
    return actual

def put(p, value):
    assert not p.exists(), p
    p.write_text(json.dumps(value, indent=2) + '\n')
    return ref(p)

def identity(expected):
    p = Path('/proc') / str(expected['pid'])
    if not p.exists():
        return dict(expected, alive=False, identity_verified=False)
    stat = (p / 'stat').read_text().rsplit(')', 1)[1].split()
    actual = dict(pid=expected['pid'], boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(), start_ticks=int(stat[19]), state=stat[0])
    actual['identity_verified'] = all(actual[k] == expected[k] for k in ['pid', 'boot_id', 'start_ticks'])
    actual['alive'] = actual['identity_verified'] and actual['state'] != 'Z'
    return actual

now = datetime.datetime.now(datetime.timezone.utc)
driver = read(A / 'driver-status.json')
assert driver['turn'] == 1787
handles = {k: identity(driver[k]) for k in ['driver', 'process']}
assert all(x['alive'] for x in handles.values())
assessment = read(R / 'scoped-assessment-v1.json')
review = read(R / 'review-v1.json')
exit_record = read(R / 'exit-v1.json')
process = read(R / 'process-v1.json')
terminal_handles = {k: identity(process[k]) for k in ['wrapper', 'executor']}
assert not any(v['alive'] for v in terminal_handles.values())
assert exit_record['exit'] == 0 and not exit_record['timeout']
assert assessment['verdict'] == 'PASS_SCOPED_B5' and not assessment['blockers']
assert all(x['passed'] for x in assessment['checks'])
assert review['decision'] == 'PASS_PREPARATION_REQUIRES_ROOT_RELEASE'
for n in ['review-v1.json', 'scoped-assessment-v1.json', 'file-manifest-v1.json']:
    assert (R / (n + '.sha256')).read_text().split()[0] == ref(R / n)['sha256']
for k in ['authority', 'graph', 'composition', 'consumer_review']:
    verify(assessment[k])
for k, v in review.items():
    if isinstance(v, dict) and 'path' in v and 'sha256' in v:
        verify(v)
graph = read(Path(assessment['graph']['path']))
assert not graph['release_enabled'] and not graph['gpu_authorized'] and graph['authority'] is None
source = assessment['source']
assert subprocess.check_output(['git', '-C', source['worktree'], 'rev-parse', 'HEAD'], text=True).strip() == source['commit']
assert not subprocess.check_output(['git', '-C', source['worktree'], 'status', '--porcelain', '--untracked-files=no'], text=True).strip()
prefixes = assessment['retained_accounting']['prefixes']
for r in prefixes.values():
    verify(r)
stop = [dict(path=x['path'], present=Path(x['path']).exists()) for x in assessment['stop_authority']['observations']]
deadline = assessment['stop_authority']['deadline']
deadline_passed = now >= datetime.datetime.fromisoformat(deadline.replace('Z', '+00:00'))
next_step = 'Compose the already reviewed graph with the exact turn001785 B5 leaf and turn001787 root acceptance; adopt prospective accounting under standing authority, preserving all four ledger prefixes and both failed preparation charges. Issue and validate a separate finite preparation-only release before any measured readiness dispatch, rechecking STOP/deadline and assigned idle GPU admission. No episode or scientific cohort until its separate gates pass; do not repeat accepted static reviews.'
result = dict(schema='n36-current-graph-b5-root-acceptance-v1', at=now.isoformat(), decision='ACCEPT_SCOPED_B5_DISABLED_GRAPH', source=source, graph=verify(assessment['graph']), review=ref(R / 'review-v1.json'), assessment=ref(R / 'scoped-assessment-v1.json'), manifest=ref(R / 'file-manifest-v1.json'), exit=exit_record, terminal_handles=terminal_handles, checks_passed=len(assessment['checks']), ledger_prefixes=prefixes, retained_accounting=assessment['retained_accounting'], limitations=assessment['limitations'], documentation_clarification='Historical and current preparation source records have equal parsed JSON values but different serialization hashes; the runtime delta includes both path and digest. This acceptance binds exact current bytes and does not amend historical attestations.', release_enabled=False, preparation_release_granted=False, episode_authorized=False, measured_readiness=False, scientific_success=False, target_met=False, next_action=next_step)
rr = put(T / 'root-b5-acceptance-v1.json', result)
prev = read(A / 'turns/001786/operational-summary-v1.json')
summary = dict(prev, turn=1787, at=now.isoformat(), live_handles=handles, controller_status='No active GPU cohort; independent B5 reviewer exited successfully and exact disabled graph review accepted.', completed_work=['Verified live driver/coordinator identities, terminal reviewer identities, prior successful turn and unchanged private ledger prefixes.', 'Verified exact source, graph and review artifact hashes; accepted independent B5 with 139 passing scoped checks.', 'Preserved both aborted preparation charges and unknown telemetry; recorded byte-versus-parsed-value clarification without rewriting historical records.'], next_bounded_step=next_step, unresolved_evidence=['Prospective graph/accounting adoption and finite preparation-only release remain pending.', 'Native readiness and separate episode gates remain pending; original validation/formal/ablation goal not evidenced.'], stop_present=any(x['present'] for x in stop), deadline_passed=deadline_passed, review_exit_record_present=True, root_b5_acceptance=rr, gpu_dispatches=0, target_met=False)
summary.pop('review', None)
sr = put(T / 'operational-summary-v1.json', summary)
with (C / 'state.lock').open('a') as cl, (W / 'data/qd-ed-state.lock').open('a') as sl:
    fcntl.flock(cl, fcntl.LOCK_EX)
    fcntl.flock(sl, fcntl.LOCK_EX)
    for r in prefixes.values():
        verify(r)
    for p, is_yaml in [(W / 'research-state.yaml', True), (C / 'checkpoint.json', False)]:
        value = yaml.safe_load(p.read_text()) if is_yaml else read(p)
        assert not value.get('current_owned_workers')
        record = value['n36_current_graph_independent_b5_review']
        record.update(status='TERMINAL_SCOPED_B5_ACCEPTED_PREPARATION_RELEASE_PENDING', live_handles=[], executor_exited=True, terminal_handles=terminal_handles, review=ref(R / 'review-v1.json'), root_acceptance=rr)
        value.update(n36_current_graph_b5_root_acceptance=rr, latest_operational_summary=sr, next_action=next_step, last_updated_utc=now.isoformat())
        tmp = p.with_name(p.name + '.turn001787.tmp')
        tmp.write_text(yaml.safe_dump(value, sort_keys=False, allow_unicode=True) if is_yaml else json.dumps(value, indent=2) + '\n')
        os.replace(tmp, p)
    p = C / 'idea_tree.json'
    tree = read(p)
    tree['nodes']['15.6'].update(result='CURRENT_GRAPH_SCOPED_B5_ACCEPTED_PREPARATION_RELEASE_PENDING', insight=next_step, current_graph_b5_root_acceptance=rr)
    tmp = p.with_name(p.name + '.turn001787.tmp')
    tmp.write_text(json.dumps(tree, indent=2) + '\n')
    os.replace(tmp, p)
(T / 'operational-summary-v1.sha256').write_text(sr['sha256'] + '  operational-summary-v1.json\n')
print(json.dumps(dict(acceptance=rr, summary=sr, checks_passed=len(assessment['checks']), ledger_prefixes_unchanged=True)))
