"""Preparation-only evidence validator and immutable runtime producer.

The measurement command requires a separate finite root release and committed
source bootstrap. Artifact production requires separate root acceptance. Neither
route grants health or episode authority. CPU fixtures are never live evidence.

DAG: disabled baseline -> source-bound disabled graph -> measurement release ->
observations/accounting -> proof -> derived runtime -> detached root acceptance.
No proof contains its own digest or the derived runtime digest.
"""
import copy
import datetime as dt
import json
import math
from pathlib import Path
import sys
import time

from scripts import qd_ed_n36_engineering_r1 as e
from scripts import qd_ed_gpu_probe as probe

SCHEMA = 'n36-r1-evidence-runtime-derivation-v2'
FIELDS = ['preparation.source', 'preparation.source_record', 'cuda_egl_verified',
          'gpu_mapping.cuda_egl_verified', 'cuda_egl_probe', 'provider_ready',
          'provider_evidence', 'preparation.runtime_ready', 'preparation.status',
          'preparation.readiness_proof']
NEW_FILES = {'scripts/qd_ed_n36_readiness_prepare.py', 'tests/test_n36_readiness_prepare.py'}


def closed(value, keys, label):
    e.w.require(isinstance(value, dict) and set(value) == set(keys), label + ' schema')
    return value


def number(value, label):
    e.w.require(type(value) in (int, float) and math.isfinite(value) and value >= 0, label)
    return value


def timestamp(value):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    e.w.require(parsed.tzinfo is not None, 'timezone required')
    return parsed.timestamp()


def pinned(ref, path):
    e.reference(ref)
    e.w.require(ref['path'] == path and str(Path(path).resolve()) == path
                and not Path(path).is_symlink(), 'fixed readiness evidence path')
    return e.read(ref)


def policy(spec):
    binding = spec['runtime_binding']
    e.exact(binding.get('measurement_contract'), MEASUREMENT_CONTRACT, 'preparation measurement schema')
    e.w.require(binding['schema'] == SCHEMA, 'readiness policy version')
    authority = e.read(binding['repair_authority'])
    amendment = e.read(binding['amendment'])
    e.exact(authority['amendment'], binding['amendment'], 'readiness amendment authority')
    e.exact(authority['source_base'], binding['source_base'], 'readiness source authority')
    e.exact(amendment['source_base'], binding['source_base'], 'readiness amendment base')
    e.exact(binding['mutable_runtime_fields'], FIELDS, 'readiness exact mutable fields')
    expected = {x['file'] for x in amendment['code_change_scope'][:3]} | set(amendment['new_allowed_entrypoints'])
    e.exact(sorted(binding['source_change_allowlist']), sorted(expected), 'readiness scoped changes')
    value = e.read(binding['preparation'])
    closed(value, ('schema', 'baseline', 'previous_specification', 'disabled_runtime_path',
                   'release_path', 'proof_path', 'gpu_path', 'provider_path', 'accounting_path',
                   'acceptance_path', 'resource_id', 'not_before', 'deadline'), 'preparation policy')
    e.w.require(value['schema'] == 'n36-readiness-preparation-policy-v1', 'preparation schema')
    e.exact(value['baseline'], spec['canonical_runtime'], 'immutable disabled baseline')
    previous = e.read(value['previous_specification'])
    e.exact(previous['canonical_runtime'], spec['canonical_runtime'], 'baseline continuity')
    e.exact(value['not_before'], authority['at'], 'post-authority evidence')
    e.exact(value['deadline'], authority['deadline'], 'preparation deadline')
    e.w.require(value['resource_id'] != e.HEALTH_ID, 'separate preparation identity')
    paths = [value[k] for k in value if k.endswith('_path')] + [binding['runtime_path'], binding['source_record_path']]
    e.w.require(len(set(paths)) == len(paths) and all(Path(p).is_absolute() for p in paths),
                'distinct acyclic fixed readiness paths')
    return value


def verify_graph(release, source, baseline):
    """Disabled bootstrap closure, separate from production true-readiness audit.

    Uses native/source/runtime/controller/input/all41 validators, without
    invoking full.verify_audit_closure on an intentionally disabled runtime.
    No CPU certificate can replace these checks or subsequent production audit.
    """
    from scripts.qd_ed_n36_build import manifest as native_manifest
    from scripts.qd_ed_n34_controller import verify_semantics
    graph = release['graph']
    closed(graph, ('plan', 'runtime'), 'preparation graph')
    plan = e.read(graph['plan'])
    e.w.require(plan.get('release_enabled') is False and plan.get('frozen') is False
                and plan.get('authority') is None and plan.get('b5_review') is None
                and plan.get('phase_authorization') == {'engineering': False, 'dev': False,
                                                       'validation': False, 'formal': False},
                'preparation graph cannot carry episode authority')
    e.exact(plan['source'], source, 'preparation graph final source')
    e.exact(plan['runtime'], graph['runtime'], 'preparation disabled runtime binding')
    runtime = e.validate_runtime_binding(plan)
    e.w.require(runtime['preparation']['runtime_ready'] is False, 'bootstrap must use disabled runtime')
    e.exact(runtime['files'], baseline['files'], 'bootstrap frozen file inventory')
    e.validate_plan_shape(plan)
    audit = e.read(plan['audit_plan'])
    e.validate_audit_view(audit)
    e.audit_mapping(plan, audit, e.row())
    e.w.require(Path(plan['worktree']) == Path(e.__file__).resolve().parents[1]
                and plan['worktree'] == str(e.SOURCE), 'deployed preparation checkout')
    e.b.verify_sources(plan)
    e.b.attest_loaded(plan['worktree'], source)
    closure = e.b.closure.verify_runtime(e.read(plan['runtime_closure']), plan['runtime'])
    native_manifest(plan['native_build'])
    verify_semantics(plan['controller_semantics'], plan['runtime'], closure)
    e.r.stage_overrides(runtime)
    e.r.verify_files(runtime['files'], allowed_roots=(runtime['worktree'], runtime['artifact_root']))
    fingerprints = {str(Path(x['path']).resolve()) for x in runtime['files']}
    for task in runtime['tasks'].values():
        actual = {str(p.resolve()) for p in Path(task['cache_dir']).rglob('*') if p.is_file()}
        e.w.require(actual and actual <= fingerprints, 'preparation task cache inventory')
    e.r.validate_runtime_inputs(audit, runtime, e.b.profiles(plan['worktree']),
                               Path(plan['worktree']), {'artifacts': runtime['artifact_root']})
    e.w.require(len(audit['episodes']) == len(audit['expected_manifests']) == 40, 'preparation all40')
    for row in audit['episodes']:
        e.b._verify_manifest_bound(audit['expected_manifests'][row['episode_key']], audit, runtime, row)
    e.b.verify_engineering_manifest(plan['engineering_manifest'], plan, runtime, e.row(), audit=audit)
    return plan


def validate_release(ref, spec, source, source_ref, *, now=None):
    p = policy(spec)
    value = pinned(ref, p['release_path'])
    closed(value, ('schema', 'approved', 'purpose', 'specification', 'source_record', 'baseline',
                   'resource_id', 'source_cwd', 'interpreter', 'issued_at', 'expires_at',
                   'gpu_seconds', 'provider_calls', 'episode_authorized', 'health_authorized',
                   'stop_authority', 'graph', 'accounting_authority', 'root_review'), 'preparation release')
    e.w.require(value['schema'] == 'n36-preparation-measurement-release-v1'
                and value['approved'] is True and value['purpose'] == 'readiness_preparation_only'
                and value['episode_authorized'] is False and value['health_authorized'] is False,
                'separate preparation release required')
    e.exact(value['specification'], e.SPECIFICATION, 'released specification')
    e.exact(value['source_record'], source_ref, 'released final source')
    e.exact(value['baseline'], spec['canonical_runtime'], 'released immutable baseline')
    e.exact(value['stop_authority'], e.stop.binding(), 'preparation STOP authority')
    e.exact(value['resource_id'], p['resource_id'], 'released preparation identity')
    e.exact(value['source_cwd'], str(e.SOURCE), 'released deployed checkout')
    e.exact(value['interpreter'], {'path': str(Path(sys.executable).resolve()),
            'sha256': e.w.sha(Path(sys.executable).resolve()), 'version': sys.version}, 'released interpreter')
    current = time.time() if now is None else now
    issued, expires = timestamp(value['issued_at']), timestamp(value['expires_at'])
    e.w.require(max(timestamp(p['not_before']), timestamp(MEASUREMENT_CONTRACT['not_before'])) < issued <= current < expires <= timestamp(p['deadline']),
                'fresh preparation release')
    seconds = number(value['gpu_seconds'], 'finite preparation reservation')
    e.w.require(MEASUREMENT_CONTRACT['cleanup_seconds'] < seconds <= expires - issued and type(value['provider_calls']) is int
                and value['provider_calls'] == 1, 'separate finite preparation caps')
    closed(value['graph'], ('plan', 'runtime'), 'released graph')
    e.w.require(value['graph']['runtime']['path'] == p['disabled_runtime_path'],
                'released bootstrap graph must be disabled and acyclic')
    validate_preparation_authority(value['accounting_authority'], spec, value, now=current)
    review = e.read(value['root_review'])
    e.exact(review, {**{k: v for k, v in value.items() if k != 'root_review'},
            'schema': 'n36-preparation-root-measurement-review-v1', 'decision': 'APPROVED'},
            'independent root measurement release')
    e.stop.check(now=dt.datetime.fromtimestamp(current, dt.timezone.utc), ends_at=value['expires_at'])
    return value



AUTHORITY_BINDINGS = ('specification', 'source_record', 'baseline', 'graph', 'source_cwd',
    'interpreter', 'stop_authority', 'resource_id', 'issued_at', 'expires_at', 'gpu_seconds',
    'provider_calls', 'episode_authorized', 'health_authorized')
ADOPTION_SLOT = 'n36_preparation_accounting_adoption'


def validate_preparation_authority(ref, spec, release, *, now=None):
    """Closed preparation approval; never accepts production or CPU task authority.

    The detached review precedes authority, which precedes state adoption and the
    separately reviewed release. No document hashes itself or a downstream node.
    """
    contract_ref = spec['runtime_binding']['accounting_contract']
    contract = e.read(contract_ref)
    closed(contract, ('schema', 'release_enabled', 'root_adopted', 'repair_authority',
        'independent_review', 'standing_authority', 'not_before', 'deadline', 'owner',
        'amendment', 'margin_reference', 'adoption_slot', 'authority_schema', 'review_schema'),
        'preparation accounting contract')
    e.w.require(contract['schema'] == 'n36-preparation-accounting-contract-v1'
                and contract['release_enabled'] is False and contract['root_adopted'] is False
                and contract['adoption_slot'] == ADOPTION_SLOT
                and contract['authority_schema'] == 'n36-preparation-accounting-authority-v1'
                and contract['review_schema'] == 'n36-preparation-accounting-root-review-v1',
                'pinned preparation-only contract')
    # Hash-check the exact prospective policy basis; do not recurse old provenance.
    repair = e.read(contract['repair_authority'])
    e.read(contract['independent_review'])
    e.exact({k: repair['standing_authority'][k] for k in ('path', 'sha256')},
            contract['standing_authority'], 'preparation standing basis')
    e.exact({k: repair['review'][k] for k in ('path', 'sha256')},
            contract['independent_review'], 'preparation independent policy review')
    standing = e.read(contract['standing_authority'])
    e.w.require(standing.get('approved') is True, 'approved standing preparation authority')
    value = e.read(ref)
    fixed = dict(schema=contract['authority_schema'], approved=True,
        purpose='readiness_preparation_only', contract=contract_ref,
        approval_basis=contract['standing_authority'], independent_review=contract['independent_review'],
        owner=contract['owner'], gpu_mapping=e.read(spec['canonical_runtime'])['gpu_mapping'], caps=e.c.CAPS, amendment=contract['amendment'],
        margin_reference=contract['margin_reference'], ledger_prefixes=spec['retained_ledger_prefixes'],
        retained_snapshot=spec['retained_snapshot'], retained_snapshot_reference=spec['retained_snapshot_reference'],
        retained_margin_gpu_hours='0.23357169027962', absolute_gpu_hours='224',
        weekly_window=dict(origin_gpu_hours=53.08404692669838, increment_gpu_hours=168.,
                           ends_at=e.c.DEADLINE),
        cleanup_seconds=MEASUREMENT_CONTRACT['cleanup_seconds'], max_episode_attempts=0,
        max_health_invocations=0, automatic_recoveries=0, adoption_slot=ADOPTION_SLOT,
        **{k: release[k] for k in AUTHORITY_BINDINGS})
    closed(value, (*fixed, 'root_review'), 'preparation accounting authority')
    e.exact({k: value[k] for k in fixed}, fixed, 'exact preparation accounting authority')
    e.w.require(value['episode_authorized'] is False and value['health_authorized'] is False
                and type(value['provider_calls']) is int and value['provider_calls'] == 1,
                'preparation-only resource authority')
    e.exact(value['specification'], e.SPECIFICATION, 'preparation authority specification')
    e.exact(value['baseline'], spec['canonical_runtime'], 'preparation authority baseline')
    e.exact(value['stop_authority'], e.stop.binding(), 'preparation authority STOP')
    closed(value['graph'], ('plan', 'runtime'), 'preparation accounting graph')
    for graph_ref in value['graph'].values():
        e.reference(graph_ref)
    e.w.require(value['source_cwd'] == str(e.SOURCE)
                and value['owner']['canonical_worktree'] == str(e.OWNER), 'preparation authority routes')
    e.read(value['source_record'])
    e.read(value['retained_snapshot_reference'])
    e.read(value['amendment'])
    e.w.require(value['margin_reference']['sha256'] == e.c.ACCOUNTING_SHA, 'preparation frozen margin')
    current = time.time() if now is None else now
    issued, expires = timestamp(value['issued_at']), timestamp(value['expires_at'])
    e.w.require(max(timestamp(contract['not_before']), timestamp(standing['continuous_window']['start_utc']))
                < issued <= current < expires <= min(timestamp(contract['deadline']),
                timestamp(standing['continuous_window']['end_utc']), timestamp(e.c.DEADLINE)),
                'preparation accounting authority window')
    need = number(value['gpu_seconds'], 'preparation authority finite seconds')
    e.w.require(MEASUREMENT_CONTRACT['cleanup_seconds'] < need <= expires - issued,
                'preparation authority finite reservation')
    e.w.require(value['resource_id'] == policy(spec)['resource_id']
                and value['resource_id'] not in (e.HEALTH_ID, e.EPISODE_KEY), 'separate preparation resource')
    e.exact(e.read(value['root_review']),
        {**{k: v for k, v in value.items() if k != 'root_review'},
         'schema': contract['review_schema'], 'decision': 'APPROVED'}, 'detached preparation accounting root review')
    return value


def validate_preparation_state(root, plan, authority, release, state):
    """Read-only adoption check using the real disabled plan shape."""
    e.w.require(plan.get('authority') is None and plan.get('b5_review') is None
                and plan.get('frozen') is False and plan.get('release_enabled') is False
                and plan.get('phase_authorization') == dict(engineering=False, dev=False, validation=False, formal=False),
                'preparation requires null production authority and disabled graph')
    e.exact(e.read(release['graph']['plan']), plan, 'preparation adopted graph')
    e.exact(plan['runtime'], release['graph']['runtime'], 'preparation adopted runtime')
    e.exact(plan['source'], e.read(authority['source_record']), 'preparation adopted source')
    e.w.require(Path(root) == e.owner_root(plan), 'preparation owning route')
    e.validate_owner_route(state)
    for key in ('canonical_worktree', 'run_name', 'artifacts'):
        e.exact(state.get(key), authority['owner'][key], 'preparation owner ' + key)
    e.validate_private_budget(authority, state)
    runtime = e.read(plan['runtime'])
    e.exact(runtime['gpu_mapping'], e.read(authority['baseline'])['gpu_mapping'], 'preparation exact GPU binding')
    e.w.require(e.r.runtime_gpu(runtime, state) == 7, 'preparation physical GPU')
    e.exact(state.get(ADOPTION_SLOT), dict(schema='n36-preparation-accounting-adoption-v1',
        approved=True, accounting_authority=release['accounting_authority'],
        owner_root=str(root), resource_id=release['resource_id'], production_adoption=False),
        'preparation dedicated owning adoption missing')
    e.w.require(state.get('n36_engineering_budget_authority') != release['accounting_authority'],
                'preparation authority in production slot')


def derive(spec, source, source_ref, proof_ref, *, now=None):
    """Validate approved observations; return exact prospective runtime in memory."""
    p = policy(spec)
    baseline = e.read(spec['canonical_runtime'])
    e.w.require(baseline['cuda_egl_verified'] is baseline['provider_ready'] is False
                and baseline['gpu_mapping']['cuda_egl_verified'] is False
                and baseline['preparation']['runtime_ready'] is False
                and baseline['preparation']['release_enabled'] is False
                and baseline['preparation']['historical_readiness_is_not_current'] is True,
                'immutable disabled baseline required')
    proof = pinned(proof_ref, p['proof_path'])
    closed(proof, ('schema', 'release', 'baseline', 'source_record', 'gpu', 'provider',
                   'accounting', 'native_receipt', 'runtime_receipt', 'runtime_receipt_binding', 'measurement_envelope'), 'readiness proof')
    e.w.require(proof['schema'] == 'n36-measured-preparation-proof-v2', 'readiness proof version')
    e.exact(proof['baseline'], spec['canonical_runtime'], 'proof immutable baseline')
    e.exact(proof['source_record'], source_ref, 'proof final source')
    release = validate_release(proof['release'], spec, source, source_ref, now=now)
    plan = verify_graph(release, source, baseline)
    from scripts.qd_ed_n36_build import verify_receipt
    verify_receipt(plan['native_build'], e.read(proof['native_receipt']), after=True)
    receipt_binding = {'release': proof['release'], 'source_record': source_ref,
                       'resource_id': p['resource_id'], 'phase': 'preparation_after',
                       'process': e.read(proof['measurement_envelope'])['process']}
    e.exact(proof['runtime_receipt_binding'], receipt_binding, 'measured runtime receipt binding')
    e.b.closure.verify_runtime_receipt(e.read(plan['runtime_closure']), e.read(proof['runtime_receipt']),
                                      binding=receipt_binding, after=True)
    common = {'release': proof['release'], 'source_record': source_ref,
              'baseline': spec['canonical_runtime'], 'resource_id': p['resource_id'],
              'source_cwd': release['source_cwd'], 'interpreter': release['interpreter']}
    gpu = pinned(proof['gpu'], p['gpu_path'])
    provider = pinned(proof['provider'], p['provider_path'])
    for label, evidence, extra in [('gpu', gpu, ('observation', 'frame')),
                                    ('provider', provider, ('provider', 'login_mode', 'response', 'calls', 'success'))]:
        closed(evidence, (*common, 'schema', 'observed_at', 'simulation_steps', *extra), label)
        e.exact({k: evidence[k] for k in common}, common, label + ' observation binding')
        e.w.require(evidence['schema'] == 'n36-preparation-' + label + '-v1'
                    and type(evidence['simulation_steps']) is int and evidence['simulation_steps'] == 0,
                    label + ' zero-transition observation')
        observed = number(evidence['observed_at'], 'observation timestamp')
        e.w.require(timestamp(release['issued_at']) < observed < timestamp(release['expires_at'])
                    and observed <= (time.time() if now is None else now), 'stale/future observation')
    probe.validate_probe_evidence(gpu['observation'], baseline['gpu_mapping'])
    e.w.require(gpu['observation']['resource_id'] == p['resource_id']
                and gpu['observation']['time_unix'] == gpu['observed_at'], 'GPU observation time/identity')
    e.reference(gpu['frame'])
    e.w.require(e.w.sha(gpu['frame']['path']) == gpu['frame']['sha256']
                == gpu['observation']['frame_png_sha256'], 'measured frame bytes')
    e.exact(provider['provider'], baseline['frozen_stage_provider'], 'exact approved provider')
    e.w.require(provider['provider']['backend'] == 'codex_cli'
                and provider['provider']['auth_mode'] == 'chatgpt'
                and provider['provider']['model'] == 'gpt-6-astra'
                and provider['login_mode'] == 'current_official_chatgpt_login'
                and type(provider['calls']) is int and provider['calls'] == 1
                and provider['success'] is True, 'approved official provider response')
    response = e.read(provider['response'])
    closed(response, ('schema', 'resource_id', 'model', 'status', 'request', 'response'), 'provider response')
    e.w.require(response['schema'] == 'n36-preparation-provider-response-v1'
                and response['resource_id'] == p['resource_id'] and response['model'] == 'gpt-6-astra'
                and response['status'] == 'completed', 'provider response identity/outcome')
    for key in ('request', 'response'):
        ref = e.reference(response[key])
        e.w.require(e.w.sha(ref['path']) == ref['sha256'], 'provider ' + key + ' bytes')
    events = pinned(proof['accounting'], p['accounting_path'])
    e.w.require(isinstance(events, list) and len(events) == 3, 'exact one-use terminal sequence')
    last = timestamp(release['issued_at'])
    for event, kind in zip(events, ('reserved', 'dispatched', 'completed')):
        closed(event, (*common, 'event', 'time_unix', 'reserved_gpu_seconds', 'gpu_process_wall_seconds',
                       'provider_calls', 'exclusive', 'telemetry_complete', 'gpu', 'provider',
                       'kind', 'envelope', 'process', 'parent', *(['error'] if kind == 'completed' else [])), 'accounting event')
        e.exact({k: event[k] for k in common}, common, 'accounted release/source binding')
        e.w.require(event['kind'] == 'readiness_preparation'
                    and event['event'] == kind and event['exclusive'] is True
                    and event['telemetry_complete'] is True, 'terminal successful exclusive accounting')
        when = number(event['time_unix'], 'accounting timestamp')
        e.w.require(last < when < timestamp(release['expires_at']), 'accounting ordered timestamps')
        last = when
        e.exact(event['reserved_gpu_seconds'], release['gpu_seconds'], 'separate reservation')
        if kind != 'completed':
            e.exact([event['gpu_process_wall_seconds'], event['provider_calls'], event['gpu'], event['provider']],
                    [0, 0, None, None], 'preterminal accounting')
    terminal = events[-1]
    charge = number(terminal['gpu_process_wall_seconds'], 'actual preparation charge')
    e.w.require(0 < charge <= release['gpu_seconds']
                and charge >= terminal['time_unix'] - events[1]['time_unix']
                and type(terminal['provider_calls']) is int and terminal['provider_calls'] == 1,
                'actual finite terminal charges')
    e.exact([terminal['gpu'], terminal['provider']], [proof['gpu'], proof['provider']], 'terminal evidence hashes')
    e.w.require(all(events[1]['time_unix'] < x['observed_at'] < terminal['time_unix'] for x in (gpu, provider))
                and terminal['time_unix'] <= (time.time() if now is None else now), 'observations within dispatch')
    verify_envelope(proof, plan, common, events)
    result = copy.deepcopy(baseline)
    result['cuda_egl_verified'] = result['provider_ready'] = True
    result['gpu_mapping']['cuda_egl_verified'] = True
    result['cuda_egl_probe'] = {'resource_id': p['resource_id'], 'evidence_path': proof['gpu']['path'],
                               'evidence_sha256': proof['gpu']['sha256']}
    result['provider_evidence'] = proof['provider']
    result['preparation'].update(source=source['commit'], source_record=source_ref,
        runtime_ready=True, status='MEASURED_PREPARATION_ONLY_REQUIRES_SEPARATE_RELEASES', readiness_proof=proof_ref)
    # Closure/manifests can take time: recheck expiry, STOP and unchanged release
    # after validation, before returning even a preparation-only projection.
    validate_release(proof['release'], spec, source, source_ref, now=now)
    return result


def accepted(spec, proof_ref, runtime_ref):
    p = policy(spec)
    path = p['acceptance_path']
    value = pinned({'path': path, 'sha256': e.w.sha(path)}, path)
    e.exact(value, {'schema': 'n36-preparation-root-acceptance-v1', 'approved': True,
                   'specification': e.SPECIFICATION, 'proof': proof_ref, 'runtime': runtime_ref,
                   'release_enabled': False, 'health_authorized': False, 'episode_authorized': False},
            'external root exact proof/runtime acceptance')


def produce(proof_ref):
    """CPU-only write-once producer, gated by detached root acceptance of bytes."""
    spec = e.specification()
    binding = spec['runtime_binding']
    source_ref = {'path': binding['source_record_path'], 'sha256': e.w.sha(binding['source_record_path'])}
    source = e.read(source_ref)
    result = derive(spec, source, source_ref, proof_ref)
    data = json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    import hashlib
    runtime_ref = {'path': binding['runtime_path'], 'sha256': hashlib.sha256(data).hexdigest()}
    accepted(spec, proof_ref, runtime_ref)
    e.stop.check()
    # Exclusive creation: never mutate baseline, historical artifacts or replay.
    path = Path(runtime_ref['path'])
    e.w.require(str(path.resolve()) == str(path) and not path.exists(), 'new immutable runtime required')
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        import os
        os.fsync(stream.fileno())
    return runtime_ref


# The journal is authoritative for preparation identity. The existing resource
# journal mirrors every transition so unchanged owner budget readers see costs
# and inflight reservations. A torn two-journal write blocks, never repairs itself.
MEASUREMENT_CONTRACT = {'schema': 'n36-preparation-measurement-envelope-v3',
    'not_before': '2026-10-10T22:45:08+00:00',
    'resource_kind': 'readiness_preparation', 'journal': 'readiness-preparation-ledger.jsonl',
    'global_accounting': 'gpu-healthcheck-ledger.jsonl', 'mirror_required': True,
    'unknown_blocks_reuse': True, 'cleanup_seconds': 40, 'provider_calls': 1,
    'child_launch_intent_required': True, 'provider_handle_chain_required': True,
    'suffix_partition': 'strict_preparation_then_sole_health_v1'}


def write_once(path, value):
    import os
    path = Path(path)
    e.w.require(not path.is_symlink() and str(path.resolve()) == str(path), 'immutable output path')
    with path.open('xb') as stream:
        stream.write(json.dumps(value, sort_keys=True, allow_nan=False).encode())
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return {'path': str(path), 'sha256': e.w.sha(path)}


def journal_rows(root):
    path = Path(root) / 'data' / MEASUREMENT_CONTRACT['journal']
    e.w.require(not path.is_symlink(), 'preparation journal symlink')
    rows = e.r.read_events(path)
    e.r.budget_snapshot([], rows)  # Legal one-use transitions and finite charges.
    for row in rows:
        e.w.require(row.get('kind') == 'readiness_preparation', 'preparation resource kind')
    return rows


def append_preparation(root, event):
    """Caller holds operation lock. Journal-first terminals, mirror-first reserve.

    Existing owner append primitive performs state sync under the state lock.
    A crash between writes is deliberately not auto-reconciled.
    """
    import os
    root = Path(root)
    def own_append():
        with e.r.locked(root / 'data/qd-ed-state.lock', nonblocking=False):
            rows = journal_rows(root)
            e.r.budget_snapshot([], [*rows, event])
            path = root / 'data' / MEASUREMENT_CONTRACT['journal']
            with path.open('a') as stream:
                stream.write(json.dumps(event, sort_keys=True, allow_nan=False) + '\n')
                stream.flush()
                os.fsync(stream.fileno())
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    if event['event'] == 'reserved':
        e.r.append_healthcheck_event(root, event)
        own_append()
    else:
        own_append()
        e.r.append_healthcheck_event(root, event)


def preparation_budget(root, plan, authority, release):
    from scripts import qd_ed_n36_runner as owner
    spec = e.specification()
    e.exact(authority, validate_preparation_authority(release['accounting_authority'], spec, release),
            'preparation accounting reference changed')
    e.stop.check(ends_at=release['expires_at'], need=release['gpu_seconds'])
    state, events, resources, reservations = owner.snapshot(root, authority)
    validate_preparation_state(root, plan, authority, release, state)
    retained = {}
    for name in e.JOURNALS:
        anchor = authority['ledger_prefixes'][name]
        path = Path(root) / 'data' / name
        e.w.require(anchor['path'] == str(path), 'preparation owner prefix route')
        with path.open('rb') as stream:
            retained[name] = [json.loads(line) for line in stream.read(anchor['bytes']).splitlines() if line.strip()]
    e.exact(e.r.budget_snapshot(retained[e.JOURNALS[0]], retained[e.JOURNALS[1]]),
            authority['retained_snapshot'], 'preparation whole retained snapshot')
    e.exact(authority['ledger_prefixes'], e.specification()['retained_ledger_prefixes'],
            'preparation exact retained accounting prefixes')
    own = journal_rows(root)
    mirrors = [x for x in resources if x.get('kind') == 'readiness_preparation']
    e.exact(own, mirrors, 'torn preparation accounting requires root reconciliation')
    identity = release['resource_id']
    e.w.require(not any(identity in (x.get('resource_id'), x.get('attempt_id'), x.get('episode_key'))
                        for x in [*events, *resources, *own]), 'global preparation identity replay')
    e.w.require(all(g[-1]['event'] in e.r.TERMINAL for g in e.r.event_groups(events).values()),
                'unfinished attempt reservation')
    snap = e.r.budget_snapshot(events, resources)
    e.exact({k: state['budget'].get(k) for k in snap}, snap, 'preparation state/ledger snapshot')
    e.w.require(snap['gpu_healthcheck_inflight'] == 0, 'inflight resource reservation')
    # Do not borrow the engineering 1900-second or healthcheck 60-second cap.
    need = number(release['gpu_seconds'], 'preparation reservation')
    e.w.require(need > MEASUREMENT_CONTRACT['cleanup_seconds'], 'preparation cleanup headroom')
    selected = {'budget_bucket': 'recovery',
                'timeout_seconds': need - MEASUREMENT_CONTRACT['cleanup_seconds']}
    for cap in (state['budget']['max_gpu_hours'], float(e.accounting.ABSOLUTE_HOURS),
                float(e.accounting.WEEKLY_HOURS)):
        effective = {**state, 'budget': {**state['budget'], 'max_gpu_hours': cap}}
        available = e.r.check_budget_limits(effective, snap, selected, reservations,
            bucket_caps=authority['caps']['buckets'], amendment=authority['amendment'])
        e.w.require(available >= selected['timeout_seconds'], 'preparation full finite reservation')
    protected = sum(max(0., hours - snap['gpu_hours_by_bucket'][key])
                    for key, hours in authority['caps']['protected_gpu_hours'].items())
    margin = e.accounting.retained_margin(root, authority['margin_reference'])
    cap = min(state['budget']['max_gpu_hours'], float(e.accounting.ABSOLUTE_HOURS),
              float(e.accounting.WEEKLY_HOURS))
    e.w.require((snap['gpu_hours_consumed'] + protected + margin) * 3600 + need <= cap * 3600,
                'preparation charged plus inflight plus new/protected cap')
    return snap


def provider_preflight(runtime, env, *, run=None):
    """Public CLI status only; bootstrap does not require provider_ready=True."""
    import os
    import subprocess
    run = run or subprocess.run
    frozen = runtime['frozen_stage_provider']
    e.w.require(frozen['backend'] == 'codex_cli' and frozen['auth_mode'] == 'chatgpt'
                and frozen['model'] == 'gpt-6-astra', 'preparation official provider')
    e.r.stage_overrides(runtime)
    e.w.require(env.get('HOME') and not any(env.get(x) for x in e.r.codex_removed_environment()),
                'preparation current login environment')
    installed = e.r.codex_policy_module().discover_disabled_skill_paths(
        codex_home=env.get('CODEX_HOME') or Path(env['HOME']) / '.codex', user_home=env['HOME'])
    e.exact(installed, frozen['disabled_skill_paths'], 'preparation installed CLI policy')
    cli = Path(frozen['cli_path'])
    e.w.require(cli.is_file() and os.access(cli, os.X_OK) and e.w.sha(cli) == frozen['cli_sha256'],
                'preparation CLI bytes')
    version = run([str(cli), '--version'], capture_output=True, text=True, timeout=15, env=env)
    login = run([str(cli), 'login', 'status'], capture_output=True, text=True, timeout=15, env=env)
    e.w.require(version.returncode == 0 and version.stdout.strip() == 'codex-cli ' + frozen['cli_version'],
                'preparation CLI version')
    e.w.require(login.returncode == 0 and (login.stdout + login.stderr).strip().lower() ==
                'logged in using chatgpt', 'preparation current official login')
    return {'cli_sha256': frozen['cli_sha256'], 'cli_version': frozen['cli_version'],
            'login_mode': 'current_official_chatgpt_login'}


def measure_provider(runtime, env, output, frame, guard):
    """One CLI child, frozen command/parser, durable raw bytes and lifecycle.

    Transport is preparation-specific to retain raw event bytes that the frozen
    scientific recognizer intentionally deletes with its temporary directory.
    """
    import subprocess
    from core.codex_stage import CodexStageRecognizer
    from core.codex_stage_lifecycle import LifecycleTelemetry, StageLifecycle
    from scripts.qd_ed_n36_runner import process_identity, cleanup_owned
    frozen = runtime['frozen_stage_provider']
    status = provider_preflight(runtime, env)
    client = CodexStageRecognizer.__new__(CodexStageRecognizer)
    client._configure_transport(frozen)
    e.exact(client.public_policy, e.r.codex_public_config(frozen), 'preparation frozen public invocation')
    output = Path(output)
    request = b'Current Image. Describe this static preparation image. Return exactly three short lines.'
    request_path = output / 'request.txt'
    with request_path.open('xb') as stream:
        stream.write(request)
    guard()
    lifecycle = LifecycleTelemetry(StageLifecycle, client.public_policy['maximum_event_bytes'])
    process = None
    identity = None
    launch_ref = handle_ref = None
    with (output / 'response.jsonl').open('x+b') as stdout, (output / 'provider-stderr.txt').open('x+b') as stderr:
        try:
            launch_ref = write_once(output / 'provider-launch-intent.json', {'calls_reserved': 1,
                'parent': process_identity(__import__('os').getpid()), 'time_unix': time.time(),
                'monotonic': time.monotonic()})
            lifecycle.mark('spawn_started_at')
            process = subprocess.Popen(client._command(output, [frame]), stdin=subprocess.PIPE,
                stdout=stdout, stderr=stderr, cwd=output, env=env, start_new_session=False)
            identity = process_identity(process.pid)
            handle_ref = write_once(output / 'provider-process.json', {'process': identity,
                'parent': process_identity(__import__('os').getpid()), 'launch_intent': launch_ref,
                'time_unix': time.time(), 'monotonic': time.monotonic()})
            lifecycle.mark('spawn_returned_at')
            lifecycle.start(stdout)
            client.api_request_counter.values['logical_call_attempts'] += 1
            lifecycle.mark('communicate_started_at')
            process.communicate(input=request, timeout=client.timeout_seconds)
            lifecycle.mark('communicate_returned_at')
            stdout.seek(0)
            raw = stdout.read(client.public_policy['maximum_event_bytes'] + 1)
            e.w.require(len(raw) <= client.public_policy['maximum_event_bytes'], 'provider event byte bound')
            client._parse_events(raw)
            e.w.require(process.returncode == 0, 'preparation provider exit')
        except BaseException:
            if process is not None and process.poll() is None and identity is not None:
                cleanup_owned(process, identity)
            raise
        finally:
            lifecycle.finish(process)
            write_once(output / 'provider-transport.json', {'process': identity,
                'launch_intent': launch_ref, 'process_handle': handle_ref,
                'calls': client.api_request_counter.values['logical_call_attempts'],
                'returncode': None if process is None else process.returncode,
                'lifecycle': lifecycle.data, 'preflight': status,
                'parent': process_identity(__import__('os').getpid()),
                'request': {'path': str(request_path), 'sha256': e.w.sha(request_path)},
                'response': {'path': str(output / 'response.jsonl'), 'sha256': e.w.sha(output / 'response.jsonl')},
                'public_policy': client.public_policy})
    e.w.require(lifecycle.data.get('observation_complete') is True
                and lifecycle.data.get('complete_usage_observed') is True, 'provider telemetry incomplete')
    guard()
    ref = lambda name: {'path': str(output / name), 'sha256': e.w.sha(output / name)}
    return ref('request.txt'), ref('response.jsonl'), ref('provider-transport.json')


def measurement_context(release_ref):
    spec = e.specification()
    e.exact(spec['runtime_binding']['measurement_contract'], MEASUREMENT_CONTRACT, 'measurement contract')
    path = spec['runtime_binding']['source_record_path']
    source_ref = {'path': path, 'sha256': e.w.sha(path)}
    source = e.read(source_ref)
    release = validate_release(release_ref, spec, source, source_ref)
    plan = verify_graph(release, source, e.read(spec['canonical_runtime']))
    return spec, source_ref, source, release, plan


def boundary(release_ref, spec, source_ref, source, release, plan):
    e.exact(validate_release(release_ref, spec, source, source_ref), release, 'release changed at boundary')
    e.b.closure.verify_source(Path(plan['worktree']), source)
    e.b.attest_loaded(plan['worktree'], source)
    e.read(plan['runtime'])


def import_required_after(closure):
    """Initialize admitted producers before requiring their generated modules.

    This is import preparation, not attestation. The caller must still collect
    the unchanged native, runtime and source receipts before accepting evidence.
    No import failure is deferred or suppressed, including transitive failures.
    """
    import importlib
    audit = e.b.closure
    audit._generated_runtime(closure)
    aliases = audit._alias_rules(closure)
    generated = closure.get('generated_modules', {})
    required = closure['required_after']
    e.w.require(set(required) <= set(closure['modules']) | set(generated) | set(aliases),
                'unknown required runtime module')
    # The existing generated rule admits exactly this Torch implementation.
    # Its instantiator import alone does not call the template generator; the
    # remote_module module's initialization does. Never infer a producer from
    # an untrusted module name or add its bytes to the closure here.
    if audit.GENERATED_NAME in generated:
        producer = 'torch.distributed.nn.api.remote_module'
        e.w.require(producer in closure['modules'], 'generated producer not frozen')
        path = audit._runtime_file(closure['modules'][producer])
        importlib.import_module(producer)
        audit._live_source(producer, path)
        inventory = audit._generated_runtime(closure)
        e.w.require(audit.GENERATED_NAME in inventory,
                    'required generated runtime module not loaded')
    for name in required:
        # import_module also rejects a None entry in sys.modules. Presence of
        # an entry alone cannot establish that a required module was loaded.
        importlib.import_module(name)


def child_measure(context_ref):
    import os
    from scripts import qd_ed_n36_source as execution
    from scripts import qd_ed_n36_build as native
    from scripts.qd_ed_n36_runner import process_identity
    execution.active()
    context = e.read(context_ref)
    closed(context, ('release', 'parent', 'output'), 'preparation child context')
    spec, source_ref, source, release, plan = measurement_context(context['release'])
    output = Path(context['output'])
    expected_output = Path(policy(spec)['proof_path']).with_suffix('.measurement')
    e.w.require(output == expected_output, 'fixed child measurement output')
    e.exact(process_identity(os.getppid()), context['parent'], 'admitted parent identity')
    root = e.owner_root(plan)
    rows = journal_rows(root)
    dispatched = [x for x in rows if x['resource_id'] == release['resource_id']]
    e.w.require(len(dispatched) == 2 and dispatched[-1]['event'] == 'dispatched'
                and dispatched[-1]['release'] == context['release'], 'child requires durable admission')
    e.exact(dispatched[-1]['parent'], context['parent'], 'durably admitted parent binding')
    # Parent records exact handle before this gate opens; no measurement precedes it.
    admitted = output / 'child-admitted.json'
    until = time.monotonic() + 5
    while not admitted.exists() and time.monotonic() < until:
        time.sleep(.01)
    identity = process_identity(os.getpid())
    e.exact(e.r.read_json(admitted), identity, 'admitted child process')
    guard = lambda: boundary(context['release'], spec, source_ref, source, release, plan)
    guard()
    started = time.time()
    common = {k: release[k] for k in ('source_record', 'baseline', 'resource_id', 'source_cwd', 'interpreter')}
    common['release'] = context['release']
    runtime = e.read(plan['runtime'])
    observation = probe.child_probe(plan['runtime']['path'], output, release['resource_id'])
    probe.validate_probe_evidence(observation, runtime['gpu_mapping'])
    frame = {'path': str(output / 'probe-frame.png'), 'sha256': e.w.sha(output / 'probe-frame.png')}
    gpu = write_once(policy(spec)['gpu_path'], dict(common, schema='n36-preparation-gpu-v1',
        observed_at=observation['time_unix'], simulation_steps=0, observation=observation, frame=frame))
    guard()
    request, response, transport = measure_provider(runtime, dict(os.environ), output, frame['path'], guard)
    response_ref = write_once(output / 'provider-response.json', {'schema': 'n36-preparation-provider-response-v1',
        'resource_id': release['resource_id'], 'model': 'gpt-6-astra', 'status': 'completed',
        'request': request, 'response': response})
    provider = write_once(policy(spec)['provider_path'], dict(common, schema='n36-preparation-provider-v1',
        observed_at=time.time(), simulation_steps=0, provider=runtime['frozen_stage_provider'],
        login_mode='current_official_chatgpt_login', response=response_ref, calls=1, success=True))
    closure = e.read(plan['runtime_closure'])
    # Import required modules and their admitted producers. No Main, controller
    # instance, environment reset or episode entrypoint is invoked.
    import_required_after(closure)
    binding = {'release': context['release'], 'source_record': source_ref, 'resource_id': release['resource_id'],
               'phase': 'preparation_after', 'process': identity}
    native_ref = write_once(output / 'native-receipt.json', native.attest(plan['native_build'], after=True))
    runtime_ref = write_once(output / 'runtime-receipt.json', e.b.closure.attest_runtime_receipt(
        closure, plan['runtime'], binding=binding, after=True))
    source_receipt = write_once(output / 'source-receipt.json', execution.attest(
        Path(plan['worktree']), source, closure, binding=binding))
    guard()
    return write_once(output / 'envelope.json', dict(common, schema=MEASUREMENT_CONTRACT['schema'],
        process=identity, parent=context['parent'], started_at=started, finished_at=time.time(),
        gpu=gpu, provider=provider, native_receipt=native_ref, runtime_receipt=runtime_ref,
        runtime_receipt_binding=binding, source_receipt=source_receipt, transport=transport))


def supervise_measurement(process, identity, timeout, physical_gpu):
    """Monitor through deadline. STOP vetoes acceptance, never signals a child."""
    import subprocess
    from scripts.qd_ed_n36_runner import cleanup_owned
    deadline = time.monotonic() + timeout
    error = None
    while process.poll() is None:
        left = deadline - time.monotonic()
        if left <= 0:
            cleanup_owned(process, identity)
            raise TimeoutError('preparation timeout; retain actual charge')
        try:
            def bounded_run(argv, **kwargs):
                kwargs['timeout'] = min(kwargs.get('timeout', left), max(.001, deadline-time.monotonic()))
                return subprocess.run(argv, **kwargs)
            e.r.check_exclusive_gpu(process, run=bounded_run, physical_gpu=physical_gpu)
        except Exception as exc:
            error = exc
        try:
            process.wait(timeout=min(.25, max(.001, deadline-time.monotonic())))
        except subprocess.TimeoutExpired:
            pass
    if error is not None:
        raise RuntimeError('preparation exclusivity telemetry lost') from error
    e.w.require(process.returncode == 0, 'preparation child failure')


def execute_preparation(release_ref):
    """Future root-released runner. Never called by CPU implementation tests live."""
    import os
    import subprocess
    from scripts import qd_ed_n36_source as execution
    from scripts.qd_ed_n36_runner import process_identity
    execution.active()
    spec, source_ref, source, release, plan = measurement_context(release_ref)
    root = e.owner_root(plan)
    runtime = e.read(plan['runtime'])
    output = Path(policy(spec)['proof_path']).with_suffix('.measurement')
    guard = lambda: boundary(release_ref, spec, source_ref, source, release, plan)
    with e.r.locked(root / 'data/qd-ed-runner.lock', nonblocking=False):
        guard()
        e.stop.check(ends_at=release['expires_at'], need=release['gpu_seconds'])
        with e.r.locked(root / 'data/qd-ed-state.lock', nonblocking=False):
            preparation_budget(root, plan, e.read(release['accounting_authority']), release)
        execution.attest(Path(plan['worktree']), source, e.read(plan['runtime_closure']),
            binding={'release': release_ref, 'source_record': source_ref, 'resource_id': release['resource_id'],
                     'process': process_identity(os.getpid()), 'phase': 'preparation_before'})
        env = e.child_environment(plan, runtime)
        provider_preflight(runtime, env)
        physical = e.r.runtime_gpu(runtime)
        e.r.gpu_admission(physical_gpu=physical, expected_uuid=runtime['gpu_mapping']['uuid'])
        guard()
        e.w.require(not output.exists() and not output.is_symlink(), 'preparation output replay')
        output.mkdir()
        parent = process_identity(os.getpid())
        common = {k: release[k] for k in ('source_record', 'baseline', 'resource_id', 'source_cwd', 'interpreter')}
        common['release'] = release_ref
        base = dict(common, kind='readiness_preparation', reserved_gpu_seconds=release['gpu_seconds'],
            gpu_process_wall_seconds=0, provider_calls=0, exclusive=True, telemetry_complete=True,
            gpu=None, provider=None, envelope=None, process=None, parent=parent)
        records = []
        def append(kind, **changes):
            event = dict(base, event=kind, time_unix=time.time(), **changes)
            append_preparation(root, event)
            records.append(event)
        append('reserved')
        process = None
        identity = None
        dispatched_at = None
        child_admitted = False
        launch_attempted = False
        error = None
        envelope_ref = None
        envelope = None
        try:
            guard()
            e.stop.check(ends_at=release['expires_at'], need=release['gpu_seconds'])
            context_ref = write_once(output / 'context.json', {'release': release_ref, 'parent': parent, 'output': str(output)})
            command = execution.command(sys.executable, Path(plan['worktree']), 'scripts.qd_ed_n36_readiness_prepare',
                '--child-context', context_ref['path'], '--child-context-sha256', context_ref['sha256'])
            env.update(QD_ED_GPU_PROBE_PARENT_PID=str(os.getpid()), QD_ED_GPU_PROBE_RESOURCE_ID=release['resource_id'])
            append('dispatched')
            dispatched_at = records[-1]['time_unix']
            with (output / 'child.log').open('xb') as log:
                write_once(output / 'child-launch-intent.json', {'release': release_ref,
                    'context': context_ref, 'parent': parent, 'time_unix': time.time()})
                launch_attempted = True
                process = subprocess.Popen(command, cwd=plan['worktree'], env=env, stdout=log,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                identity = process_identity(process.pid)
                write_once(output / 'child-admitted.json', identity)
                child_admitted = True
                supervise_measurement(process, identity, release['gpu_seconds'] - 40, physical)
            # Check no descendant remains on the GPU after parent exit.
            e.r.gpu_admission(physical_gpu=physical, expected_uuid=runtime['gpu_mapping']['uuid'])
            guard()
            envelope_ref = {'path': str(output / 'envelope.json'), 'sha256': e.w.sha(output / 'envelope.json')}
            envelope = e.read(envelope_ref)
            e.exact(envelope['process'], identity, 'terminal child identity')
            e.exact(envelope['parent'], parent, 'terminal parent identity')
            e.exact({k: envelope[k] for k in common}, common, 'terminal measurement binding')
        except BaseException as exc:
            error = type(exc).__name__
        # Unknown/live handles remain inflight. No unowned handle is signalled.
        if (launch_attempted or process is not None or (output / 'child-launch-intent.json').exists()) and (
                process is None or identity is None or not child_admitted or process.poll() is None):
            raise RuntimeError('unknown/live preparation child; retain reservation for root reconciliation')
        # A provider descendant may outlive a killed child. Missing transport
        # is not proof of its exit; retain inflight instead of hiding its cost.
        provider_handle = output / 'provider-process.json'
        if (output / 'provider-launch-intent.json').exists() and not provider_handle.exists():
            raise RuntimeError('unknown provider launch; retain preparation reservation')
        if provider_handle.exists():
            handle = e.r.read_json(provider_handle)['process']
            owned_identity(handle)
            try:
                live = process_identity(handle['pid'])
            except FileNotFoundError:
                live = None
            except Exception:
                raise RuntimeError('unknown provider handle; retain preparation reservation')
            if live == handle:
                raise RuntimeError('live provider handle; retain preparation reservation')
        if process is not None:
            try:
                e.r.gpu_admission(physical_gpu=physical, expected_uuid=runtime['gpu_mapping']['uuid'])
            except Exception as exc:
                raise RuntimeError('GPU quiescence unknown; retain preparation reservation') from exc
        try:
            guard()
        except Exception as exc:
            error = type(exc).__name__
        charge = 0 if dispatched_at is None else max(0., time.time() - dispatched_at)
        success = error is None and envelope is not None and charge <= release['gpu_seconds']
        # At least the reserved provider call is retained on telemetry loss.
        calls = 0 if dispatched_at is None else 1
        terminal_time = time.time()
        charge = max(charge, 0 if dispatched_at is None else terminal_time-dispatched_at)
        terminal = dict(base, event='completed' if success else 'aborted', time_unix=terminal_time,
            gpu_process_wall_seconds=charge, provider_calls=calls, exclusive=success,
            telemetry_complete=success, gpu=envelope['gpu'] if success else None,
            provider=envelope['provider'] if success else None, envelope=envelope_ref if success else None,
            process=identity, error=error)
        append_preparation(root, terminal)
        records.append(terminal)
        e.w.require(success, 'preparation failed; charges retained')
        accounting_ref = write_once(policy(spec)['accounting_path'], records)
        proof = {k: envelope[k] for k in ('native_receipt', 'runtime_receipt', 'runtime_receipt_binding', 'gpu', 'provider')}
        proof.update(schema='n36-measured-preparation-proof-v2', release=release_ref, baseline=spec['canonical_runtime'],
            source_record=source_ref, accounting=accounting_ref, measurement_envelope=envelope_ref)
        guard()
        return write_once(policy(spec)['proof_path'], proof)


def owned_identity(value):
    import uuid
    closed(value, ('pid', 'proc_start_ticks', 'boot_id'), 'owned process identity')
    e.w.require(type(value['pid']) is int and value['pid'] > 0
                and isinstance(value['proc_start_ticks'], str) and value['proc_start_ticks'].isascii()
                and value['proc_start_ticks'].isdigit() and int(value['proc_start_ticks']) > 0
                and isinstance(value['boot_id'], str), 'owned process identity values')
    e.w.require(str(uuid.UUID(value['boot_id'])) == value['boot_id'], 'owned process boot identity')
    return value


def verify_envelope(proof, plan, common, events):
    envelope = e.read(proof['measurement_envelope'])
    closed(envelope, (*common, 'schema', 'process', 'parent', 'started_at', 'finished_at', 'gpu', 'provider',
        'native_receipt', 'runtime_receipt', 'runtime_receipt_binding', 'source_receipt', 'transport'), 'measurement envelope')
    e.w.require(envelope['schema'] == MEASUREMENT_CONTRACT['schema'], 'measurement envelope version')
    e.exact({k: envelope[k] for k in common}, common, 'fresh measurement envelope identity')
    for name in ('gpu', 'provider', 'native_receipt', 'runtime_receipt', 'runtime_receipt_binding'):
        e.exact(envelope[name], proof[name], 'measurement envelope ' + name)
    for name in ('process', 'parent'):
        owned_identity(envelope[name])
        e.exact(events[-1][name], envelope[name], 'terminal envelope ' + name)
    e.w.require(events[-1]['error'] is None, 'terminal measurement error')
    e.exact(events[-1]['envelope'], proof['measurement_envelope'], 'terminal native/runtime envelope hashes')
    e.w.require(events[1]['time_unix'] < number(envelope['started_at'], 'measurement start')
                <= number(envelope['finished_at'], 'measurement finish') < events[-1]['time_unix'],
                'stale measurement envelope')
    root = e.owner_root(plan)
    rows = journal_rows(root)
    selected = [x for x in rows if x['resource_id'] == common['resource_id']]
    e.exact(selected, events, 'durable one-use owning accounting')
    mirrors = [x for x in e.r.read_events(root / 'data/gpu-healthcheck-ledger.jsonl')
               if x.get('resource_id') == common['resource_id']]
    e.exact(mirrors, selected, 'durable global preparation charges')
    transport = e.read(envelope['transport'])
    closed(transport, ('process', 'parent', 'launch_intent', 'process_handle', 'calls',
        'returncode', 'lifecycle', 'preflight', 'request', 'response', 'public_policy'), 'provider transport')
    owned_identity(transport['process'])
    output = Path(policy(e.specification())['proof_path']).with_suffix('.measurement')
    launch = pinned(transport['launch_intent'], str(output / 'provider-launch-intent.json'))
    handle = pinned(transport['process_handle'], str(output / 'provider-process.json'))
    closed(launch, ('calls_reserved', 'parent', 'time_unix', 'monotonic'), 'provider launch intent')
    closed(handle, ('process', 'parent', 'launch_intent', 'time_unix', 'monotonic'), 'provider handle')
    e.exact(launch['calls_reserved'], 1, 'provider one launch intent')
    e.exact(handle['launch_intent'], transport['launch_intent'], 'provider handle launch binding')
    e.exact(handle['process'], transport['process'], 'provider durable process binding')
    for record in (launch, handle):
        e.exact(record['parent'], envelope['process'], 'provider launch parent')
    e.w.require(transport['process']['pid'] not in (envelope['process']['pid'], envelope['parent']['pid'])
                and transport['process']['boot_id'] == envelope['process']['boot_id']
                and int(transport['process']['proc_start_ticks']) >= int(envelope['process']['proc_start_ticks']),
                'provider distinct child identity')
    lifecycle = transport['lifecycle']
    e.w.require(lifecycle['clock'] == 'monotonic_seconds', 'provider lifecycle clock')
    times = [number(launch['monotonic'], 'provider launch clock')]
    for key in ('spawn_started_at',):
        times.append(number(lifecycle[key], 'provider ' + key))
    times.append(number(handle['monotonic'], 'provider handle clock'))
    for key in ('spawn_returned_at', 'communicate_started_at', 'communicate_returned_at',
                'process_exit_observed_at', 'observer_finished_at'):
        times.append(number(lifecycle[key], 'provider ' + key))
    e.w.require(times == sorted(times), 'provider ordered lifecycle')
    e.exact(lifecycle['returncode'], 0, 'provider observed terminal exit')
    e.w.require(envelope['started_at'] <= number(launch['time_unix'], 'provider launch time')
                <= number(handle['time_unix'], 'provider handle time')
                <= e.read(proof['provider'])['observed_at'] <= envelope['finished_at']
                and times[-1] - times[0] <= envelope['finished_at'] - envelope['started_at'],
                'provider launch within measurement')
    e.w.require(type(transport['returncode']) is int and transport['returncode'] == 0 and type(transport['calls']) is int and transport['calls'] == 1
                and transport['lifecycle']['observation_complete'] is True
                and transport['lifecycle']['complete_usage_observed'] is True
                and transport['preflight']['login_mode'] == 'current_official_chatgpt_login', 'measured provider lifecycle')
    e.exact(transport['parent'], envelope['process'], 'provider owned by admitted measurement child')
    provider_response = e.read(e.read(proof['provider'])['response'])
    for key in ('request', 'response'):
        e.exact(transport[key], provider_response[key], 'provider actual transport bytes')
    frozen = e.read(proof['provider'])['provider']
    e.exact(transport['public_policy'], e.r.codex_public_config(frozen), 'provider transport policy')
    e.exact(transport['preflight'], {'cli_sha256': frozen['cli_sha256'], 'cli_version': frozen['cli_version'],
        'login_mode': 'current_official_chatgpt_login'}, 'provider actual preflight binding')
    from scripts import qd_ed_n36_source as execution
    execution.verify_receipt(e.read(envelope['source_receipt']), Path(plan['worktree']), plan['source'],
        e.read(plan['runtime_closure']), runtime_receipt=e.read(proof['runtime_receipt']),
        binding=proof['runtime_receipt_binding'])
    return envelope


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proof')
    parser.add_argument('--release')
    parser.add_argument('--release-sha256')
    parser.add_argument('--child-context')
    parser.add_argument('--child-context-sha256')
    parser.add_argument('--proof-sha256')
    args = parser.parse_args()
    e.w.require(sum(bool(x) for x in (args.proof, args.release, args.child_context)) == 1, 'one preparation operation')
    if args.child_context:
        result = child_measure({'path': args.child_context, 'sha256': args.child_context_sha256})
    elif args.release:
        result = execute_preparation({'path': args.release, 'sha256': args.release_sha256})
    else:
        result = produce({'path': args.proof, 'sha256': args.proof_sha256})
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
