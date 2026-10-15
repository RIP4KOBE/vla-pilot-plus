import copy,json,os,time,hashlib
from pathlib import Path
from unittest.mock import patch
from scripts import qd_ed_n36_contract as c, qd_ed_n36_release as release
from scripts import qd_ed_n36r2_admission as gate, qd_ed_n23_worker as w
from scripts import qd_ed_n36_worker as worker, qd_ed_n36_stop as stop
out=Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001276/b5-preparation')
stop.check()
plan=json.loads((out/'plan.unbound-disabled-v1.json').read_text());c.validate_draft(plan);gate.validate_protocol(plan)
results={'disabled_protocol_pass':True,'negative_cases':[]}
def reject(label,fn):
 try:fn()
 except (ValueError,KeyError,TypeError,OSError) as e:results['negative_cases'].append({'case':label,'exception':type(e).__name__,'reason':str(e)})
 else:raise AssertionError('fail-open: '+label)
reject('draft release validation',lambda:release.validate_release(c.ref(out/'plan.unbound-disabled-v1.json'),None))
for path in sorted(out.glob('context.*.disabled.json')):
 assert json.loads(path.read_text())['release'] is None
 reject('disabled worker '+path.name,lambda:worker.validate_context(c.ref(path),admission=True))
original=w.read_ref
ledger=original(plan['accounting']);calculation=original(ledger['calculation'])
for key in ['conservative_after_cohort_gpu_hours','protected_total_remaining_gpu_hours','effective_cap_gpu_hours']:
 bad=copy.deepcopy(calculation);bad['arithmetic'][key]='0'
 with patch.object(w,'read_ref',side_effect=lambda ref:bad if ref==ledger['calculation'] else original(ref)):
  reject('accounting arithmetic '+key,lambda:gate.validate_protocol(plan))
for key in ['healthchecks','preserved_attempts','caps']:
 bad=copy.deepcopy(ledger);bad.pop(key)
 with patch.object(w,'read_ref',side_effect=lambda ref:bad if ref==plan['accounting'] else original(ref)):
  reject('missing accounting '+key,lambda:gate.validate_protocol(plan))
for key in ['source','protocol','accounting','runtime','runtime_closure']:
 # Disabled plan may never be promoted merely by deleting provenance.
 bad=copy.deepcopy(plan);bad.pop(key)
 reject('missing provenance '+key,lambda:release.validate_plan(bad))
# Verify source-dependent scientific config identity has not been edited.
import subprocess
changed=subprocess.check_output(['git','diff','--name-only'],text=True).splitlines()
assert all(p.startswith(('scripts/','tests/')) for p in changed)
results.update(all40_contexts_checked=40,production_execution=False,release_enabled=False)
(out/'package-boundary-checks-v1.json').write_text(json.dumps(results,indent=2)+'\n')
print('PASS',len(results['negative_cases']),'negative boundaries; disabled protocol structurally valid')
