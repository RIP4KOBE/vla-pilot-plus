"""Bound read-only CPU checks. Never imports project modules or executes launchers."""
import ast
import copy
from contextlib import contextmanager
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import types
import yaml

OUT = Path(__file__).resolve().parent
AUTH = json.loads((OUT / 'authority-v1.json').read_text())
ROOT = Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n36_nonprogress_tangent/implementation_worktree')
STUDY = ROOT.parents[2] / 'study_worktree'
START = dt.datetime.now(dt.timezone.utc)
refs = {}
checks = []

def require(ok, reason):
    if not ok:
        raise ValueError(reason)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def ref(path):
    return {'path': str(path), 'sha256': sha(path)}

def read_ref(reference):
    require(set(reference) == {'path', 'sha256'}, 'invalid file reference')
    p = Path(reference['path'])
    require(p.is_absolute() and p.is_file() and not p.is_symlink() and sha(p) == reference['sha256'], 'file reference hash/path differs')
    refs[str(p)] = reference
    return json.loads(p.read_text())

def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def extract(relative, names=None):
    """Use exact source AST functions/constants, with imports removed and explicit dependencies.
    This is a pure-function check, not an imported production integration test.
    """
    p = ROOT / relative
    refs[str(p)] = ref(p)
    tree = ast.parse(p.read_text(), filename=str(p))
    tree.body = [node for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))
                 and (names is None or isinstance(node, ast.FunctionDef) and node.name in names)]
    ns = dict(__file__=str(p), Path=Path, dt=dt, copy=copy, json=json, math=math, w=w, contextmanager=contextmanager)
    ns.update(globals().get('dependencies', {}))
    exec(compile(tree, str(p), 'exec'), ns)
    return types.SimpleNamespace(**ns)

def check(name, action):
    result = action()
    checks.append({'name': name, 'status': 'PASS', 'result': result})
    return result

def reject(name, action):
    try:
        action()
    except (ValueError, KeyError) as exc:
        checks.append({'name': name, 'status': 'PASS_EXPECTED_REJECTION', 'reason': str(exc)})
        return
    raise AssertionError('unexpected acceptance: ' + name)

stop = STUDY.parent / 'autonomy_20261004/STOP'
require(not stop.exists() and not stop.is_symlink(), 'driver STOP')
require(START < dt.datetime.fromisoformat(AUTH['deadline'].replace('Z', '+00:00')), 'deadline')
w = types.SimpleNamespace(require=require, read_ref=read_ref, sha=sha, canonical_sha=canonical_sha)
bound = {key: read_ref(AUTH[key]) for key in ('budget_authority', 'candidate_report', 'root_cpu_review', 'approval')}
candidate_ref = {k: bound['candidate_report']['candidate'][k] for k in ('path', 'sha256')}
plan = read_ref(candidate_ref)
authority = bound['budget_authority']
c = extract('scripts/qd_ed_n36_contract.py')
dependencies = {'c': c}
recovery = extract('scripts/qd_ed_n36_recovery.py')
release = extract('scripts/qd_ed_n36_release.py', {'validate_plan', 'validate_caps', 'prefix'})
controller = extract('scripts/qd_ed_n34_controller.py')
require(plan['source']['commit'] == AUTH['source'] and plan['source'] == plan['scientific_source'], 'source identity')
check('protocol_and_accounting_exact_inheritance', lambda: (recovery.validate_protocol(plan), True)[1])
check('adopted_authority_protocol_accounting_amendment', lambda: (recovery.validate_authority(plan, authority), True)[1])
check('caps_and_limits', lambda: (release.validate_caps(authority['caps']), require(authority['limits'] == c.LIMITS, 'limits'), True)[2])
require(authority['coordinator_ends_at'] == c.DEADLINE == plan['deadline'] == AUTH['deadline'], 'deadline identity')
require(plan['stop_path'] == c.stop_path(ROOT) == str(stop), 'STOP binding')
require(plan['schema'] == 'n36-release-draft-v1' and plan['frozen'] is False and plan['release_enabled'] is False
        and plan['phase_authorization'] == dict(dev=False, validation=False, formal=False)
        and all(plan[k] is None for k in ('root_review', 'authority', 'execution_release')), 'disabled candidate')
reject('disabled_candidate_as_released_plan', lambda: release.validate_plan(plan))
reject('bare_plan_authority', lambda: c.require_release(plan))
reject('reference_with_extra_bytes_field', lambda: read_ref(bound['candidate_report']['candidate']))
runtime = read_ref(plan['runtime'])
closure = read_ref(plan['runtime_closure'])
native = read_ref(plan['native_build'])
proof = check('controller_semantics_and_three_source_review_bindings', lambda: controller.verify_semantics(plan['controller_semantics'], plan['runtime'], closure))
checks[-1]['result'] = {'physical_gain_certified': proof['physical_gain_certified'], 'live_instance_observed': False}
require(closure['runtime'] == plan['runtime'], 'closure runtime binding')
require(runtime['provider_ready'] is False and runtime['cuda_egl_verified'] is False, 'disabled readiness')
require(runtime['frozen_stage_provider']['backend'] == 'codex_cli' and runtime['frozen_stage_provider']['model'] == 'gpt-6-astra'
        and runtime['frozen_stage_provider']['auth_mode'] == 'chatgpt', 'provider identity')
manifests = []
require(plan['episodes'] == c.plan_rows(plan) and len(plan['episodes']) == 40, 'fresh all40 rows')
require(set(plan['expected_manifests']) == {r['episode_key'] for r in plan['episodes']}, 'manifest index')
for row in plan['episodes']:
    m = read_ref(plan['expected_manifests'][row['episode_key']])
    require(m['row'] == row and row['replacement'] is None, 'manifest row')
    for key in ('source', 'scientific_source', 'runtime', 'runtime_closure', 'controller_semantics', 'native_build', 'cohort', 'protocol', 'protocol_review', 'accounting'):
        require(m[key] == plan[key], 'manifest binding ' + key)
    require(not Path(m['output_dir']).exists() and not Path(m['output_dir']).is_symlink(), 'fresh output')
    manifests.append({'episode_key': row['episode_key'], 'profile': row['profile'], 'output_absent': True})
checks.append({'name': 'all40_static_identity_and_dependency_bindings', 'status': 'PASS', 'count': len(manifests), 'actual_recomposition': 'INHERITED_TURN1221_NOT_RERUN'})
ledgers = {}
for label, root in [('owning', STUDY), ('implementation', ROOT)]:
    ledgers[label] = {}
    for name, anchor in authority['ledger_prefixes'].items():
        p = root / 'data' / name
        data = p.read_bytes()
        entry = {**ref(p), 'bytes': len(data), 'expected_prefix_bytes': anchor['bytes'],
                 'prefix_matches': len(data) >= anchor['bytes'] and hashlib.sha256(data[:anchor['bytes']]).hexdigest() == anchor['sha256']}
        ledgers[label][name] = entry
        if label == 'owning':
            check('owning_prefix_' + name, lambda p=p, anchor=anchor: (release.prefix(p, anchor), True)[1])
        else:
            reject('implementation_prefix_' + name, lambda p=p, anchor=anchor: release.prefix(p, anchor))
    state_path = root / 'research-state.yaml'
    state_bytes = state_path.read_bytes()
    state = yaml.safe_load(state_bytes)
    ledgers[label]['state'] = {**ref(state_path), 'bytes': len(state_bytes),
        'n36_budget_authority': state.get('n36_budget_authority'),
        'authority_matches_adopted': state.get('n36_budget_authority') == AUTH['budget_authority'],
        'budget_amendment': state['budget'].get('amendment'),
        'amendment_matches_authority': state['budget'].get('amendment') == authority['amendment']}

# Decode only the original aborted primary and fresh N36R1 identities, never protected outcomes.
original = []
fresh = []
line_hashes = []
for line in (STUDY / 'data/attempt-ledger.jsonl').read_bytes().splitlines():
    if b'n36_dev_t00_c0_001147' in line:
        event = json.loads(line)
        if event.get('attempt_id') == 'n36_dev_t00_c0_001147' or event.get('episode_key') == 'n36_dev_t00_c0_001147':
            original.append(event)
            line_hashes.append(hashlib.sha256(line).hexdigest())
    if b'n36r1_dev_' in line:
        event = json.loads(line)
        if any(str(event.get(k, '')).startswith('n36r1_dev_') for k in ('attempt_id', 'episode_key')):
            fresh.append(event)
check('original_aborted_charge_preserved', lambda: (recovery.preserve_charge(original), True)[1])
require(fresh == [], 'fresh identities already used')
checks.append({'name': 'fresh_all40_absent_from_owning_attempt_journal', 'status': 'PASS', 'count': 40})

end = dt.datetime.fromisoformat(c.DEADLINE.replace('Z', '+00:00'))
allowance = dict(authority_starts_at=authority['starts_at'], authority_ends_at=c.DEADLINE,
    private_budget=True, gpu_idle=True, physical_gpu=7, gpu_uuid=c.GPU_UUID, live_handles=[], unsettled_reservations=0,
    global_seconds_remaining=75600, private_seconds_remaining=75600, cohort_seconds_remaining=75600,
    protected_seconds_remaining=0, bucket_attempts_remaining={'baseline':10,'development':30},
    global_attempts_remaining=40, protected_attempts_remaining=0, cohort_attempts_remaining=40)
check('full1840_deadline_boundary_admits', lambda: c.pre_dispatch(plan['episodes'][0], allowance,
    now=end-dt.timedelta(seconds=1840), stop_path=str(stop), cohort=c.RECOVERY_COHORT))
reject('less_than1840_deadline_boundary_rejects', lambda: c.pre_dispatch(plan['episodes'][0], allowance,
    now=end-dt.timedelta(seconds=1839), stop_path=str(stop), cohort=c.RECOVERY_COHORT))
runner_tree = ast.parse((ROOT/'scripts/qd_ed_n36_runner.py').read_text())
late_guards = []
for node in ast.walk(runner_tree):
    if isinstance(node, ast.Call) and len(node.args) == 2 and isinstance(node.args[1], ast.Constant) and node.args[1].value in ('deadline after reservation', 'deadline before worker start'):
        expr = ast.Expression(node.args[0])
        clock = types.SimpleNamespace(datetime=types.SimpleNamespace(now=lambda *args: end-dt.timedelta(seconds=1)), timezone=dt.timezone)
        accepted = eval(compile(expr, '<exact-runner-deadline-guard>', 'eval'), {'dt': clock, 'end': end})
        late_guards.append({'line': node.lineno, 'guard': ast.unparse(node.args[0]), 'reason': node.args[1].value,
            'seconds_left': 1, 'accepted': accepted, 'worker_timeout_seconds': 1800, 'cleanup_seconds': 40})
require(len(late_guards) == 2 and all(x['accepted'] for x in late_guards), 'deadline reproduction')

reviewed_sources = ['scripts/qd_ed_n36_release.py','scripts/qd_ed_n36_contract.py','scripts/qd_ed_n36_recovery.py',
    'scripts/qd_ed_n36_accounting.py','scripts/qd_ed_n36_runner.py','scripts/qd_ed_n36_supervise.py',
    'scripts/qd_ed_n36_worker.py','scripts/qd_ed_n36_native.py','scripts/qd_ed_n36_response.py',
    'scripts/qd_ed_n36_prepare.py','scripts/qd_ed_n36_bridge.py','scripts/qd_ed_n36_build.py',
    'scripts/qd_ed_n36_source.py','scripts/qd_ed_n36_bootstrap.py','scripts/qd_ed_n36_healthcheck.py',
    'scripts/qd_ed_n34_source.py','scripts/qd_ed_n34_controller.py','scripts/qd_ed_n32_runner.py','scripts/qd_ed_n23_worker.py']
index = {r['path']:r['sha256'] for r in plan['source']['files']}
for relative in reviewed_sources:
    p = ROOT/relative
    require(sha(p) == index[relative], 'reviewed source drift ' + relative)
    refs[str(p)] = ref(p)
checks.append({'name': 'reviewed_source_bytes_match_candidate_source_inventory', 'status':'PASS','count':len(reviewed_sources)})
finish = dt.datetime.now(dt.timezone.utc)
require(not stop.exists() and not stop.is_symlink() and finish < end, 'final STOP/deadline')
result = {'schema':'n36r1-production-cpu-checks-v1','at':finish.isoformat(),
    'execution_method':'Exact AST-extracted pure source functions with explicit CPU-only dependencies; no project module imports, no runtime/worker integration execution.',
    'checks': checks, 'candidate':candidate_ref, 'evidence':list(refs.values()), 'ledgers':ledgers,
    'original_charge':{'attempt_id':recovery.PRESERVED_ATTEMPT['attempt_id'],'events':[r['event'] for r in original],
        'gpu_seconds':original[-1]['gpu_process_wall_seconds'],'line_sha256':line_hashes},
    'late_deadline_guard_reproduction':late_guards, 'stop':{'path':str(stop),'exists_or_symlink':False},
    'deadline':c.DEADLINE,'started_at':START.isoformat(),'finished_at':finish.isoformat(),
    'full_cpu_preparation_repeated':False, 'provider_or_gpu_calls':0, 'workers':0, 'source_edits':0,
    'protected_outcomes_decoded':False}
with (OUT/'checks-v1.json').open('x') as stream:
    json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
print(json.dumps({'checks':len(checks),'evidence_refs':len(refs),'status':'COMPLETED_WITH_PRODUCTION_BLOCKERS','output':str(OUT/'checks-v1.json')}))
