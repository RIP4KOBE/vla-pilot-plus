"""N36R3 admission: exact existing science, distinct root authority and owner.

Consumes external approvals only. No adoption, release generation or retries.
"""
import datetime as dt
import json
from pathlib import Path
from scripts import qd_ed_n23_worker as w, qd_ed_n36_contract as c
from scripts import qd_ed_final_runner as r
from scripts import qd_ed_n36r2_admission as previous

OWNER = previous.OWNER
SOURCE = previous.SESSION / 'variants/n36r3_generated_import_001299/implementation_worktree'
# Fixed successor authorized by node 15.6 / turn 001445; old health stays charged.
PREPARATION_ID = 'n36_healthcheck_n36r3_preparation_001445'
KIND = 'n36r3_resource_preparation_v1'
HEALTH = {**previous.HEALTH, 'preparation_id': PREPARATION_ID}
JOURNALS = {'attempt-ledger.jsonl', 'gpu-healthcheck-ledger.jsonl',
            'gpu-hour-reservation-ledger.jsonl'}
BINDINGS = ('source', 'scientific_source', 'protocol', 'protocol_review', 'accounting',
            'runtime', 'runtime_closure', 'native_build', 'controller_semantics', 'resource_routing')


def identity_contract(plan):
    selected = c.cohort(plan)
    w.require(selected in c.SEPARATE_HEALTH_COHORTS, 'exact successor cohort required')
    if selected == c.DRAFT_N36R4_COHORT:
        from scripts import qd_ed_n36r4_admission as successor
        return {'prefix': 'n36r4', 'health': successor.HEALTH,
                'kind': successor.KIND, 'attempts': 506, 'hours': 75.60616276674473}
    return {'prefix': 'n36r3', 'health': HEALTH, 'kind': KIND,
            'attempts': 505, 'hours': 75.53335346582918}


def owner_root(plan):
    # Preserve the lexical owner: resolving a path is not authority to reroute it.
    expected = {'source_cwd': str(SOURCE), 'owner_root': str(OWNER),
                'physical_gpu': 7, 'gpu_uuid': c.GPU_UUID}
    w.require(plan['resource_routing'] == expected and plan['worktree'] == str(SOURCE)
              and SOURCE.resolve() == SOURCE and OWNER.resolve() == OWNER,
              'N36R3 lexical owner/source routing differs')
    return OWNER


def independent_review(plan):
    owner_root(plan)
    w.require(w.read_ref(plan['b5_review']) == {
        'schema': identity_contract(plan)['prefix'] + '-independent-b5-review-v1',
        'decision': 'PASS_PREPARATION_REQUIRES_ROOT_RELEASE',
        **{k: plan[k] for k in BINDINGS},
        'worker_receipts_are_future': True, 'release_enabled': False},
        'N36R3 exact independent source review required')


def validate_authority(plan, authority):
    spec = identity_contract(plan)
    protocol = c.validate_successor_protocol(plan)
    root = owner_root(plan)
    independent_review(plan)
    w.require(authority['cohort'] == c.cohort(plan)
              and authority['protocol'] == plan['protocol']
              and authority['accounting'] == protocol['accounting']
              and authority['healthchecks'] == spec['health'],
              'N36R3 distinct finite authority required')
    adoption = w.read_ref(authority['source_adoption'])
    w.require(adoption == {'schema': spec['prefix'] + '-source-adoption-v1', 'approved': True,
        'owner_root': str(root), 'source_cwd': str(SOURCE),
        **{k: plan[k] for k in BINDINGS}, 'independent_review': plan['b5_review']},
        'N36R3 exact root source adoption required')
    accounting = w.read_ref(authority['amendment'])
    w.require(accounting['schema'] == spec['prefix'] + '-owning-accounting-v1'
              and accounting['cohort'] == c.cohort(plan)
              and accounting['accounting'] == plan['accounting']
              and accounting['source_adoption'] == authority['source_adoption']
              and accounting['caps'] == c.CAPS and accounting['limits'] == c.LIMITS
              and accounting['healthchecks'] == spec['health']
              and accounting['automatic_recoveries'] == 0
              and accounting['ledger_prefixes'] == authority['ledger_prefixes']
              and set(authority['ledger_prefixes']) == JOURNALS,
              'N36R3 root accounting bindings differ')
    # Each supported identity keeps its own exact retained baseline.
    # A successor cannot relabel its predecessor accounting as new headroom.
    prefix_rows = {}
    from scripts import qd_ed_n36_release as release
    for name, anchor in authority['ledger_prefixes'].items():
        path = root / 'data' / name
        w.require(anchor['path'] == str(path), 'N36R3 foreign ledger anchor')
        release.prefix(path, anchor)
        with path.open('rb') as stream:
            prefix_rows[name] = [json.loads(line) for line in stream.read(anchor['bytes']).splitlines() if line.strip()]
    snap = r.budget_snapshot(prefix_rows['attempt-ledger.jsonl'], prefix_rows['gpu-healthcheck-ledger.jsonl'])
    w.require(snap == accounting['snapshot'] and snap['dispatched'] == snap['reserved_attempts'] == spec['attempts']
              and snap['gpu_hours_consumed'] == spec['hours']
              and snap['running'] == snap['gpu_healthcheck_inflight'] == 0
              and all(g[-1]['event'] in r.TERMINAL for g in r.event_groups(prefix_rows['attempt-ledger.jsonl']).values()),
              spec['prefix'] + ' retained attempts and exact costs required')
    previous.preserve_charges(prefix_rows['attempt-ledger.jsonl'])
    ledger = w.read_ref(plan['accounting'])
    if c.cohort(plan) == c.DRAFT_N36R4_COHORT:
        from scripts.qd_ed_n36r4_admission import validate_accounting
        validate_accounting(plan, authority, accounting, snap)
        return prefix_rows
    from scripts.qd_ed_n36r3_preparation import arithmetic
    w.require(accounting['arithmetic'] == arithmetic(snap), 'N36R3 finite arithmetic differs')
    for key, name in (('retained_ledger_prefix', 'attempt-ledger.jsonl'),
                      ('retained_health_ledger_prefix', 'gpu-healthcheck-ledger.jsonl')):
        release.prefix(root / 'data' / name, ledger[key])
    return prefix_rows


def live_journals(plan, authority, events, resources, reservations):
    baseline = validate_authority(plan, authority)
    suffix = {}
    for name, rows in [('attempt-ledger.jsonl', events), ('gpu-healthcheck-ledger.jsonl', resources),
                       ('gpu-hour-reservation-ledger.jsonl', reservations)]:
        old = baseline[name]
        w.require(rows[:len(old)] == old, 'N36R3 stale ledger snapshot')
        suffix[name] = rows[len(old):]
    local = c.cohort_events(c.plan_rows(plan), suffix['attempt-ledger.jsonl'])
    w.require(local == suffix['attempt-ledger.jsonl'] and not suffix['gpu-hour-reservation-ledger.jsonl'],
              'N36R3 unrelated ledger change requires fresh root accounting')
    binding = c.operational_binding(plan)
    w.require(all(all(e.get(k) == v for k, v in binding.items()) for e in local),
              'N36R3 owning event binding differs')
    health = resource_events(plan, suffix['gpu-healthcheck-ledger.jsonl'])
    w.require(health == suffix['gpu-healthcheck-ledger.jsonl'], 'N36R3 foreign health suffix')
    return local, health


def resource_events(plan, resources):
    spec = identity_contract(plan)
    permitted = {spec['health']['preparation_id']} | {'n36_healthcheck_' + row['episode_key'] for row in c.plan_rows(plan)}
    ids = {e['resource_id'] for e in resources if e.get('cohort') == c.cohort(plan)
           or e.get('kind') == spec['kind'] or str(e.get('resource_id', '')).startswith('n36_healthcheck_' + spec['prefix'])}
    local = [e for e in resources if e['resource_id'] in ids]
    binding = c.operational_binding(plan)
    w.require(all(e['resource_id'] in permitted and e.get('kind') == spec['kind']
        and all(e.get(k) == v for k, v in binding.items())
        and type(e.get('timeout_seconds')) is int and e['timeout_seconds'] == 20
        and e.get('cleanup_seconds') == 40 and e.get('reserved_gpu_seconds') == 60
        and e.get('physical_gpu') == 7 and e.get('gpu_uuid') == c.GPU_UUID
        for e in local), 'N36R3 finite health binding differs')
    # All lifecycle records keep the same source/authority and reservation.
    for identity in ids:
        group = [e for e in local if e['resource_id'] == identity]
        w.require(group[0]['source_commit'] == plan['source']['commit']
                  and group[0]['runtime'] == plan['runtime']
                  and w.read_ref(group[0]['plan']) == plan, 'N36R3 health source/authority differs')
        for key in ('plan', 'release', 'source_commit', 'runtime', 'accounting_admission'):
            w.require(all(key in e and e[key] == group[0][key] for e in group),
                      'N36R3 health lifecycle binding differs')
        for e in group:
            if e['event'] in ('completed', 'aborted'):
                w.require(c.finite(e['gpu_process_wall_seconds'], 'health elapsed') <= 60,
                          'N36R3 health exceeds reservation')
    w.require(len(ids) <= 41, 'N36R3 health invocation ceiling')
    return local


def margin_reference(plan):
    if c.cohort(plan) == c.DRAFT_N36R4_COHORT:
        from scripts.qd_ed_n36r4_admission import margin_reference as successor_margin
        return successor_margin(plan)
    ledger = w.read_ref(plan['accounting'])
    inherited = w.read_ref(ledger['inherited_accounting'])
    return inherited['inherited_accounting']


def validate_readiness(plan_ref, release_record, *, resources=None):
    """Episode authority binds actual completed separately authorized evidence.

    No runtime rewrite is needed: the health release precedes this detached
    episode release and never references it. Locked admission checks the journal.
    """
    from scripts import qd_ed_n36_release as release, qd_ed_gpu_probe as probe
    ready = release_record['readiness']
    plan, runtime, authority = release.validate_health_release(plan_ref, ready['health_release'])
    terminal = w.read_ref(ready['terminal'])
    output = Path(terminal['output_dir'])
    r.owned(output, plan['artifact_root'])
    if c.cohort(plan) == c.DRAFT_N36R4_COHORT:
        w.require(output == Path(plan['artifact_root']) / 'healthchecks' / terminal['resource_id'],
                  'N36R4 exact health output routing')
    w.require(Path(ready['terminal']['path']) == output / 'healthcheck-result.json'
        and terminal['plan'] == plan_ref and terminal['release'] == ready['health_release']
        and terminal['source_commit'] == plan['source']['commit'] and terminal['runtime'] == plan['runtime']
        and terminal['event'] == 'completed' and terminal.get('provider_verified') is True
        and terminal['source_script_sha256'] == w.sha(SOURCE / 'scripts/qd_ed_gpu_probe.py'),
        'N36R3 fresh readiness binding required')
    selected_health = resource_events(plan, [terminal])
    if c.cohort(plan) == c.DRAFT_N36R4_COHORT:
        w.require(selected_health == [terminal], 'N36R4 fresh health identity required')
    starts = dt.datetime.fromisoformat(authority['starts_at'].replace('Z', '+00:00')).timestamp()
    ends = min(dt.datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
               for value in (authority['coordinator_ends_at'], authority['weekly_window']['ends_at']))
    evidence = r.read_json(output / 'probe-evidence.json')
    # The child records observation; the parent records completion after validation.
    # Keep both original timestamps and validate their relationship, not equality.
    observed = c.finite(evidence['time_unix'], 'readiness probe observation time')
    completed = c.finite(terminal['time_unix'], 'readiness terminal completion time')
    w.require(starts <= observed <= completed <= min(ends, dt.datetime.now(dt.timezone.utc).timestamp()),
              'N36R3 readiness outside authority window or timestamps reversed')
    w.require(evidence['resource_id'] == terminal['resource_id']
              and w.sha(output / 'probe-frame.png') == evidence['frame_png_sha256']
              and all(terminal.get(k) == v for k, v in evidence.items() if k != 'time_unix'),
              'N36R3 readiness evidence differs')
    probe.validate_probe_evidence(evidence, runtime['gpu_mapping'])
    if resources is not None:
        group = [e for e in resources if e['resource_id'] == terminal['resource_id']]
        w.require([e['event'] for e in group] == ['reserved', 'dispatched', 'completed']
                  and group[-1] == terminal, 'N36R3 readiness not durably charged')
    return terminal
