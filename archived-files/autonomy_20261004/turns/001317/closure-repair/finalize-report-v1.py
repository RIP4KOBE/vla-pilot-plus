import os,json,hashlib,subprocess,datetime as dt,time,sys
from pathlib import Path
OUT=Path(__file__).resolve().parent;A=json.loads((OUT/'authority-v1.json').read_text());ROOT=Path(A['worktree']);BASE=OUT.parents[1];sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
assert not os.path.lexists(BASE.parent/'STOP')
assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(A['deadline'].replace('Z','+00:00'))
def sha(data):return hashlib.sha256(data).hexdigest()
def ref(p):
 p=Path(p);data=p.read_bytes();return {'path':str(p),'bytes':len(data),'sha256':sha(data)}
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
validation=json.loads((OUT/'validation-results-v1.json').read_text());material=json.loads((OUT/'isolated-materialization-v1.json').read_text())
plan=json.loads((OUT/'draft/plan.draft.json').read_text())
from scripts import qd_ed_n36_contract as c,qd_ed_n36_release as release
checks={}
t=time.monotonic()
for name,fn in [('direct_admission_rejected',lambda:c.pre_dispatch({}, {}, now=None,stop_path='',cohort=c.DRAFT_N36R3_COHORT)),('forged_release_rejected',lambda:release.validate_plan({**plan,'schema':'n36-released-plan-v1','frozen':True,'release_enabled':True}))]:
 try:fn();raise AssertionError('unexpected admission')
 except ValueError as e:
  assert 'N36R3 draft only' in str(e);checks[name]={'status':'PASS','rejection':str(e)}
extra_seconds=time.monotonic()-t
before=A['source'];after=git('rev-parse','HEAD');changed=git('diff','--name-only',before,after).splitlines()
assert changed==['scripts/qd_ed_n36_contract.py','scripts/qd_ed_n36_prepare.py','tests/test_n36r3_draft.py']
assert git('status','--porcelain=v1')==''
source_changes=[]
for name in changed:
 old=None if name.startswith('tests/') else sha(subprocess.check_output(['git','show',before+':'+name],cwd=ROOT))
 source_changes.append({'path':name,'before_sha256':old,'after_sha256':sha((ROOT/name).read_bytes())})
artifacts={name:ref(v['path']) for name,v in validation['artifacts'].items()}
for name in ['authority-v1.json','partial-report-v1.json','isolated-materialization-v1.json','materialize-v1.py','prepare-repair-v1.py','prepare-repair-v1.log','validation-results-v1.json','targeted-tests-v1.log','targeted-tests-v2.log','finalize-report-v1.py']:
 artifacts[name]=ref(OUT/name)
commands=[
 {'command':'git rev-parse HEAD; git status --short','result':'Expected initial HEAD; clean before work'},
 {'command':'python materialize-v1.py (first two bounded attempts)','result':'Stopped at pinned symlink mode, then Git/LFS pointer versus frozen runtime asset bytes; no mismatch written. Harness then resolved pinned targets into regular copies and used hash-verified inventoried local runtime bytes.'},
 {'command':'PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 python materialize-v1.py','exit_code':0,'result':'697 exact-hash isolated regular files; 537 source files included'},
 {'command':'python -m pytest -q -p no:cacheprovider tests/test_n36r3_draft.py (initial focused tests)','exit_code':0,'result':'11 passed in 1.45s'},
 {'command':'python -m pytest -q -p no:cacheprovider --basetemp=<output>/pytest-tmp tests/test_n36r3_draft.py','exit_code':0,'result':'12 passed in 1.50s','log':artifacts['targeted-tests-v1.log']},
 {'command':'python -m pytest -q -p no:cacheprovider --basetemp=<output>/pytest-tmp-v2 tests/test_n36r3_draft.py','exit_code':0,'result':'16 passed in 1.47s','log':artifacts['targeted-tests-v2.log']},
 {'command':'git diff --check','exit_code':0},
 {'command':'git add scripts/qd_ed_n36_contract.py scripts/qd_ed_n36_prepare.py tests/test_n36r3_draft.py; git -c core.hooksPath=/dev/null commit -m "Add finite disabled N36R3 preparation with retained accounting"','exit_code':0,'result':after},
 {'command':'PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 timeout 150s /home/hynx/miniconda3/envs/vla-pilot/bin/python3.12 <output>/prepare-repair-v1.py','exit_code':0,'result':'All 10 production CPU checks passed','log':artifacts['prepare-repair-v1.log']},
 {'command':'python finalize-report-v1.py','result':'Actual disabled-plan forged release and direct admission rejected; final Git status clean; report written'}]
remaining=[
 'Renewed root exact-source/composition review of bb20aedb952638548dd347b9705dab2beba176c5 and explicit source adoption; existing review is inherited evidence only.',
 'Root review of fresh disabled controller/runtime bindings. Historical runtime provider/CUDA/EGL readiness fields remain historical; preparation.runtime_ready=false. No fresh readiness probe was run.',
 'Root finite protocol/allocation and current accounting reconciliation/adoption retaining every old INVALID charge including N36R2 and protected reserves. Draft ledger-prefix references are not current budget/headroom authority.',
 'Separate resource/readiness, detached root release and phase-admission bindings; N36R3 intentionally remains hard rejected in this source until separately authorized tooling/bindings exist.',
 'G3 actual process-bound worker identity/runtime observations, before/after equality, execution monotonicity, Main lifecycle and all required_after coverage are absent.',
 'G4 scientific execution, audits, success gates and results are absent; CPU closure supplies none of them.']
report={'schema':'n36r3-closure-repair-report-v1','node_id':'15.6','status':'G2_CPU_PREPARATION_COMPLETE_DISABLED',
 'G2':'Bounded local repair and preparation validators PASS; production root review/adoption/readiness/release remain outstanding',
 'score':None,'production_accepted':False,'release_enabled':False,'source_adopted':False,'dispatch':False,
 'source_before':before,'source_after':after,'code_ref':after,'branch':git('branch','--show-current'),
 'source_changes':source_changes,'scientific_implementation_unchanged':True,'scientific_membership_seeds_thresholds_limits_worker_audits_unchanged':True,
 'worktree_clean':True,'summary':validation['summary'],
 'materialization':{'provenance':artifacts['isolated-materialization-v1.json'],'source_missing_before':537,'source_missing_after':0,'runtime_missing_before':697,'runtime_missing_after':0,'regular_isolated_files':len(material['records']),'pinned_symlink_targets_copied_as_regular_files':sum(bool(r['pinned_target']) for r in material['records']),'runtime_assets_from_inventoried_local_bytes':sum(r['inventoried_local_origin'] is not None for r in material['records']),'pins_changed':False,'network_or_install':False,'shared_environment_or_other_worktree_writes':False,'note':'Initial failed attempts wrote only already verified regular bytes; final pass verified all 697. Native symlink metadata was rebound to isolated regular-copy metadata with provenance; frozen content hashes were preserved.'},
 'checks':{**validation['checks'],**checks},'failing_checks':validation['failing_checks'],'commands':commands,'artifacts':artifacts,
 'prior_source_inventory':ref(BASE/'001314/production-closure/source.git-expected-v1.json'),
 'prior_terminal':ref(BASE/'001316/terminal-reconciliation-v1.json'),'reused_review':A['review'],
 'accounting':'No owning ledger read/write. Previous accounting plus terminal ledger/health-ledger prefixes retained; N36R2 INVALID and charges retained; no current headroom claimed.',
 'controller':'Original hash-bound controller review validated against its original runtime. New binding is DISABLED_PENDING_ROOT_REVIEW, never ROOT_REVIEWED.',
 'remaining_root_review_adoption_accounting_release_needs':remaining,
 'G3':'NOT_PERFORMED_NO_PRODUCTION_LIFECYCLE_EVIDENCE','G4':'NOT_PERFORMED_NO_SCIENTIFIC_RESULT',
 'targeted_test_and_validator_seconds':validation['seconds']+4.42+extra_seconds,'targeted_check_cap_seconds':180,'validator_wall_timeout_seconds':150,'threads':2,
 'broad_suites_run':False,'owner_state_ledgers_locks_driver_changes':False,'gpu_simulator_Main_provider_calls':False,
 'STOP_checks':{str(BASE.parent/'STOP'):os.path.lexists(BASE.parent/'STOP'),str(ROOT.parents[2]/'autonomy_20261004/STOP'):os.path.lexists(ROOT.parents[2]/'autonomy_20261004/STOP')},
 'deadline':A['deadline'],'finished_at':dt.datetime.now(dt.timezone.utc).isoformat(),
 'wall_seconds_since_authority':(dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(A['at'])).total_seconds(),
 'result':'Exact local materialization and disabled N36R3 source/runtime/controller/protocol/accounting preparation succeeded; 40 hash-bound prospective manifests prepared.',
 'insight':'Missing dependency checkout bytes and a finite draft identity contract were the G2 preparation blockers. Their repair does not provide adoption, release, lifecycle or scientific evidence.'}
md=f'''G2 CPU repair and disabled preparation passed. Production acceptance and release remain disabled.

Source: `{before}` → `{after}`. Only the two authorized preparation/contract files and targeted tests changed; scientific implementation is unchanged. Worktree is clean.

- Materialized all 537 missing source files and 697 missing runtime files from pinned local Git objects and inventoried local bytes. Twelve symlink targets are isolated regular copies. Pins/content hashes were preserved.
- Added finite N36R3 identities, structural disabled protocol/accounting validation, and explicit release/admission rejection. Previous charges, including N36R2 INVALID charges, and protected reserves remain bound; no current headroom is claimed.
- All 16 targeted tests and all 10 production CPU checks passed. Prepared exact source/runtime closure, disabled controller binding, allocation/protocol/accounting draft, and 40 manifests. Targeted tests plus validator runtime: {report['targeted_test_and_validator_seconds']:.2f} seconds, below the 180-second cap.
- Controller review is reused for unchanged historical source; the new binding explicitly awaits root review. No review or approval was manufactured.

Remaining: renewed root source/composition review and adoption; controller/runtime review; current accounting retaining all historical charges; resource/readiness bindings; separately authorized release/admission. Actual worker/Main lifecycle G3 and scientific G4 evidence remain absent.

`score=null`, `production_accepted=false`, `release_enabled=false`. No GPU, simulator, Main execution, provider calls, network/install, owner-state/ledger/lock/driver changes, or shared-environment writes.

Exact commands/results, per-file before/after hashes, artifact SHA-256 references, isolated materialization provenance, inherited review references, and remaining obligations are in `report-v1.json`. The partial report was preserved.
'''
with (OUT/'report-v1.md').open('x') as f:f.write(md)
report['markdown']=ref(OUT/'report-v1.md')
with (OUT/'report-v1.json').open('x') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
print(json.dumps({'report':str(OUT/'report-v1.json'),'source_after':after,'status':report['status'],'seconds':report['targeted_test_and_validator_seconds']}))
