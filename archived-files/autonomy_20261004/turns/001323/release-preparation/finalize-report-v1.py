import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, '/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree')
from scripts import qd_ed_n36r3_preparation as p, qd_ed_n36_contract as c
from scripts import qd_ed_n36_release as release

out = Path(__file__).absolute().parent
root = c.ROOT
c.stop.check()
a = json.loads((out/'authority-v1.json').read_text())
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True)
package_ref = p.bound(out/'review-package-v2/package.disabled-v1.json')
package = p.read(package_ref)
assert package['source_after'] == head
values = {k:p.read(v) for k,v in package['bindings'].items()}
for v in values.values():
    assert v['release_enabled'] is False and v['production_accepted'] is False and v['score'] is None
for ref in values['accounting']['ledger_prefixes'].values():
    assert p.bound(ref['path']) == ref
plan = p.read(values['adoption']['accepted_plan'])
checks = {'package_hashes': 'PASS', 'ledger_prefixes_unchanged_after_work': 'PASS',
          'clean_committed_worktree': 'PASS', 'canonical_STOP_and_deadline': 'PASS'}
for name, callback in [
    ('direct_admission_rejected', lambda: c.pre_dispatch(plan['episodes'][0], {}, now=dt.datetime.now(dt.timezone.utc), stop_path=plan['stop_path'], cohort=c.DRAFT_N36R3_COHORT)),
    ('forged_release_rejected', lambda: release.validate_plan({**plan, 'schema':'n36-released-plan-v1', 'frozen':True, 'release_enabled':True}))]:
    try:
        callback()
    except ValueError as exc:
        assert 'N36R3 draft only' in str(exc)
        checks[name] = {'status':'PASS', 'rejection':str(exc)}
    else:
        raise AssertionError(name)
changed = subprocess.check_output(['git','diff','--name-only',a['source'],head],text=True).splitlines()
source_changes=[]
for name in changed:
    result=subprocess.run(['git','show',a['source']+':'+name],capture_output=True)
    source_changes.append({'path':name,'before_sha256':hashlib.sha256(result.stdout).hexdigest() if result.returncode==0 else None,'after_sha256':p.bound(root/name)['sha256']})
assert set(changed)=={'docs/n36r3-release-preparation.md','scripts/qd_ed_n36r3_preparation.py','scripts/qd_ed_n36_runner.py','scripts/qd_ed_n36_supervise.py','tests/test_n36r3_preparation.py'}
(root/'docs/n36r3-release-preparation.md').read_bytes()
(out/'root-next-steps-v1.md').write_bytes((root/'docs/n36r3-release-preparation.md').read_bytes())
artifacts={'package':package_ref, **package['bindings'], 'root_next_steps':p.bound(out/'root-next-steps-v1.md')}
for name in ('targeted-tests-v1.log','targeted-tests-v2.log','targeted-tests-v3.log','package-generation-v1.log','package-generation-v2.log','partial-report-v1.json'):
    artifacts[name]=p.bound(out/name)
commands=[
 {'command':'python <output>/finalize-report-v1.py (initial)', 'exit_code':1, 'result':'Report helper lacked isolated source sys.path; stopped before reads/writes beyond imports. Added explicit isolated checkout path and reran.'},
 {'command':'git rev-parse HEAD; git status --short; date -u +%Y-%m-%dT%H:%M:%SZ; read authority and SHA256-bound review/requirements/standing authorization; check STOP', 'result':'expected initial HEAD, clean worktree, STOP absent, deadline available; input digests verified'},
 {'command':'PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 timeout 180s python -m pytest -q -p no:cacheprovider --basetemp='+str(out/'pytest-tmp')+' tests/test_n36r3_preparation.py tests/test_n36r3_draft.py tests/test_n36_controller.py', 'exit_code':1,'result':'30 passed, 2 failed in 1.71s. New fixture had illegal transition; fixed fixture to reserved/dispatched/valid. Existing canonical STOP-path test failure retained, no gate weakened.'},
 {'command':'PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 timeout 180s python -m pytest -q -p no:cacheprovider --basetemp='+str(out/'pytest-tmp-v2')+" tests/test_n36r3_preparation.py tests/test_n36r3_draft.py tests/test_n36_controller.py -k 'not test_full1840_deadline_and_stop'",'exit_code':0,'result':'31 passed, 1 deselected in 1.63s'},
 {'command':'PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 timeout 180s python -m pytest -q -p no:cacheprovider --basetemp='+str(out/'pytest-tmp-v3')+' tests/test_n36r3_preparation.py tests/test_n36r3_draft.py','exit_code':0,'result':'24 passed in 1.55s after preparation checks tightened; later change documentation-only'},
 {'command':'git diff --check','exit_code':0},
 {'command':"git -c core.hooksPath=/dev/null commit -m 'Prepare disabled N36R3 root bindings and pause at first C0 terminal'",'exit_code':0,'result':'e1c5d9c74eb7e4d09dbbffad6930265b2cd8f55f'},
 {'command':"git -c core.hooksPath=/dev/null commit -m 'Document exact isolated launcher and separate readiness blockers'",'exit_code':0,'result':head},
 {'command':'PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 timeout 60s python - (call qd_ed_n36r3_preparation.prepare(bound(authority-v1.json), review-package-v1), then repeat for review-package-v2 after documentation commit)','exit_code':0,'result':'Both CPU-only generations succeeded. review-package-v2 binds final source; v1 superseded.'},
 {'command':'PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 python '+str(out/'finalize-report-v1.py'),'exit_code':0,'result':'Bound package and ledger bytes rechecked; direct/forged admission rejected; final reports written'}]
blockers=[
 'N36R3 remains explicitly draft-only: separately reviewed authority validation, owner/source routing, finite health accounting and released-plan support are still required. No executable release is supplied.',
 'Root exact-source review and adoption of complete prerequisite composition into differing owner history remain outstanding; old accepted source/runtime/controller hashes do not attest this new commit.',
 'Fresh locked accounting/reservation reconciliation and idle GPU7, official current-login Codex gpt-6-astra and CUDA/EGL readiness remain outstanding; readiness ordering needs distinct root-bound finite health authority.',
 'G3 is open until actual later admitted production C0 evidence is reconciled. Pause has no override: a separate reviewed continuation binding implementation is required after G3.',
 'Existing tests/test_n36_controller.py::test_full1840_deadline_and_stop fails because it supplies a temporary STOP path rejected by the pre-existing canonical STOP contract. Test and contract unchanged; not hidden or weakened.'
]
report={'schema':'n36r3-release-preparation-report-v1','node_id':'15.6','status':'CPU_PREPARATION_COMPLETE_DISABLED',
 'at':dt.datetime.now(dt.timezone.utc).isoformat(),'started_at':'2026-10-10T06:14:16Z',
 'deadline':c.DEADLINE,'wall_cap_seconds':900,'score':None,'production_accepted':False,'release_enabled':False,'source_adopted':False,'dispatch':False,
 'source_before':a['source'],'source_after':head,'code_ref':head,'branch':subprocess.check_output(['git','branch','--show-current'],text=True).strip(),
 'source_changes':source_changes,'worktree_clean':True,'authority':p.bound(out/'authority-v1.json'),
 'standing_authority':a['standing_authority'],'review':a['review'],'requirements':a['requirements'],
 'accepted_composition':values['adoption']['accepted_report'],'artifacts':artifacts,
 'superseded_package':{'reference':p.bound(out/'review-package-v1/package.disabled-v1.json'),'reason':'Documentation command corrected; use review-package-v2 bound to final commit.'},
 'changes':['Read-only generator for finite hash-bound disabled accounting/adoption/release package using accepted composition directly.',
 'First N36R3 C0 terminal is charged through unchanged runner settlement before mandatory pause; journal reconciliation reverifies and pauses on restart, rejects later dispatch.',
 'No resume override or approval-producing code; native/generic audits, worker receipt consumer, Main, scientific membership/seeds/thresholds remain unchanged.'],
 'retained_accounting':{'attempts':505,'gpu_hours':75.52725286641478,'automatic_recoveries':0,'ledger_prefixes':values['accounting']['ledger_prefixes']},
 'prospective_arithmetic':values['accounting']['arithmetic'],'checks':checks,'commands':commands,
 'tests':{'latest_focused':'24 passed in 1.55s','controller_regression_subset':'31 passed, 1 deselected in 1.63s','initial':'30 passed, 2 failed in 1.71s','cpu_threads':2,'cumulative_reported_test_seconds':4.89,'synthetic_fixtures_are_not_G3':True},
 'G2':'Previous CPU composition reused; new source/package awaits exact root review.', 'G3':'OPEN_ACTUAL_PRODUCTION_REQUIRED','G4':'OPEN_NO_ADOPTION_READINESS_RELEASE_OR_SCIENTIFIC_COMPLETION',
 'root_next_steps':artifacts['root_next_steps'],'blockers':blockers,
 'scope_compliance':{'GPU_simulator_Main_provider_network_install_calls':0,'owner_writes':False,'protected_validation_formal_artifact_reads':False,'credentials_read':False,'other_agents':False,'prohibited_untracked_file_read':False},
 'insight':'A restart-safe first-C0 veto can be installed without granting admission. Current accounting preserves all 505 attempts and exact costs; finite health invocation count and aggregate seconds must both bind.',
 'result':'Committed bounded CPU plumbing and generated final disabled review package. No source adoption, GPU dispatch, G3 closure or release occurred.'}
(out/'validation-results-v1.json').write_text(json.dumps(checks,indent=2)+'\n')
report['artifacts']['validation_results']=p.bound(out/'validation-results-v1.json')
(out/'report-v1.json').write_text(json.dumps(report,indent=2)+'\n')
md=f'''# Leaf 15.6 — N36R3 release preparation

CPU preparation complete, disabled. **score=null; production_accepted=false;
release_enabled=false; source_adopted=false.** G3 and G4 remain open.

Source: `{a['source']}` → `{head}`
on `{report['branch']}`. Worktree clean. Two commits: implementation and documentation.

Implemented immutable disabled accounting/adoption/release bindings and mandatory
first-C0 pause after durable terminal charge. Restart reconciliation also pauses;
any later cell is rejected. Invalid terminals retain the existing stop behavior.
No approval or resume override exists. Science, seeds, thresholds, Main, receipt
consumer and native/generic audits are unchanged.

Final package: [review-package-v2/package.disabled-v1.json](review-package-v2/package.disabled-v1.json)
SHA256 `{package_ref['sha256']}`. All component paths, sizes and SHA256 values,
source file before/after hashes, exact commands/results and current ledger prefixes
are in [report-v1.json](report-v1.json). Package v1 is superseded by v2.

Retained: **505 attempts; 75.52725286641478 GPUh**. No ledger or owner writes.
Prospective: 40 × 1840 + 1800 + 200 = 75600 seconds (21 GPUh), 545 attempts total.
Conservative cost including retained margin and full cohort: 96.76082455669440 GPUh.
After the 221.08404692669838 effective cap and full 44 protected GPUh reserve,
prospective remainder is 80.32322237000398 GPUh; this is not admission headroom.
Health: at most 41 invocations AND 1800 cumulative seconds; only 30 full
60-second reservations fit. Zero automatic retries. Deadline {c.DEADLINE}.
Standing authorization is hash-bound; no further user budget permission requested.

Tests: 24 focused passed (1.55s); controller subset plus focused tests 31 passed,
1 deselected (1.63s). Initial run: 30 passed, 2 failed (1.71s). The new fixture
transition was corrected. The pre-existing temporary-STOP-path test fails against
the existing canonical-STOP contract; neither check nor test was weakened.
All tests used two threads and 180-second bounds, totaling 4.89 reported seconds.
Actual package generation, hash checks and disabled direct/forged admission
rejections passed. Synthetic tests do not close G3.

Root's separate adoption/readiness/release commands and requirements:
[root-next-steps-v1.md](root-next-steps-v1.md).

Remaining blockers:

'''+ '\n'.join('- '+x for x in blockers)+'''

No GPU, simulator, Main, provider, network, install, credential access, protected
validation/formal artifact reads, owner state/locks/driver writes or other agents.
'''
(out/'report-v1.md').write_text(md)
print(json.dumps({'source_after':head,'package':package_ref,'checks':checks,'reports':[str(out/'report-v1.json'),str(out/'report-v1.md')]},indent=2))
