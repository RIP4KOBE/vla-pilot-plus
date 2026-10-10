"""Preparation-only evidence validator and immutable runtime producer.

This command consumes separately released, independently accepted observations.
It does not measure, launch a provider/device/episode, approve evidence, write an
owning journal, or weaken production audit. The measurement runner is a separate
unreleased dependency. All CPU fixtures must be explicitly synthetic.

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
                   'stop_authority', 'graph', 'root_review'), 'preparation release')
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
    e.w.require(timestamp(p['not_before']) < issued <= current < expires <= timestamp(p['deadline']),
                'fresh preparation release')
    seconds = number(value['gpu_seconds'], 'finite preparation reservation')
    e.w.require(0 < seconds < e.LIMITS['gpu_seconds'] and type(value['provider_calls']) is int
                and value['provider_calls'] == 1, 'separate finite preparation caps')
    closed(value['graph'], ('plan', 'runtime'), 'released graph')
    e.w.require(value['graph']['runtime']['path'] == p['disabled_runtime_path'],
                'released bootstrap graph must be disabled and acyclic')
    review = e.read(value['root_review'])
    e.exact(review, {**{k: v for k, v in value.items() if k != 'root_review'},
            'schema': 'n36-preparation-root-measurement-review-v1', 'decision': 'APPROVED'},
            'independent root measurement release')
    e.stop.check(now=dt.datetime.fromtimestamp(current, dt.timezone.utc), ends_at=value['expires_at'])
    return value


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
                   'accounting', 'native_receipt', 'runtime_receipt', 'runtime_receipt_binding'), 'readiness proof')
    e.w.require(proof['schema'] == 'n36-measured-preparation-proof-v1', 'readiness proof version')
    e.exact(proof['baseline'], spec['canonical_runtime'], 'proof immutable baseline')
    e.exact(proof['source_record'], source_ref, 'proof final source')
    release = validate_release(proof['release'], spec, source, source_ref, now=now)
    plan = verify_graph(release, source, baseline)
    from scripts.qd_ed_n36_build import verify_receipt
    verify_receipt(plan['native_build'], e.read(proof['native_receipt']), after=True)
    receipt_binding = {'release': proof['release'], 'source_record': source_ref,
                       'resource_id': p['resource_id'], 'phase': 'preparation_after'}
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
                       'provider_calls', 'exclusive', 'telemetry_complete', 'gpu', 'provider'), 'accounting event')
        e.exact({k: event[k] for k in common}, common, 'accounted release/source binding')
        e.w.require(event['event'] == kind and event['exclusive'] is True
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


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proof', required=True)
    parser.add_argument('--proof-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(produce({'path': args.proof, 'sha256': args.proof_sha256}), sort_keys=True))


if __name__ == '__main__':
    main()
