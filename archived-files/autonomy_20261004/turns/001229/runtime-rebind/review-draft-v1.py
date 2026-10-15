"""Read-only strict CPU validation for an independent reviewer; no approval."""
import argparse, datetime as dt, json, os, sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--plan',required=True);p.add_argument('--plan-sha256',required=True)
p.add_argument('--authority',required=True);p.add_argument('--authority-sha256',required=True)
a=p.parse_args()
root=Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree')
assert Path.cwd().resolve()==root and os.environ.get('CUDA_VISIBLE_DEVICES')==''
assert not os.path.lexists(root.parent/'autonomy_20261004/STOP')
assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
sys.path.insert(0,str(root))
from scripts import qd_ed_n36_contract as c, qd_ed_n36_bridge as b, qd_ed_n23_worker as w
from scripts import qd_ed_n36_recovery as recovery, qd_ed_n36_build as native
from scripts.qd_ed_n34_controller import verify_semantics
plan_ref={'path':a.plan,'sha256':a.plan_sha256}
plan=w.read_ref(plan_ref);authority=w.read_ref({'path':a.authority,'sha256':a.authority_sha256})
c.validate_draft(plan);recovery.validate_authority(plan,authority)
b.verify_sources(plan);b.attest_loaded(root,plan['source'])
runtime=w.read_ref(plan['runtime'])
closure=b.closure.verify_runtime(w.read_ref(plan['runtime_closure']),plan['runtime'])
verify_semantics(plan['controller_semantics'],plan['runtime'],closure)
native.manifest(plan['native_build'])
b.runner.stage_overrides(runtime)
b.runner.verify_files(runtime['files'],allowed_roots=(str(root),runtime['artifact_root']))
b.runner.validate_runtime_inputs(plan,runtime,b.profiles(root),root,{'artifacts':runtime['artifact_root']})
for row in plan['episodes']:
    b._verify_manifest_bound(plan['expected_manifests'][row['episode_key']],plan,runtime,row)
print(json.dumps({'status':'PASS_DRAFT_CPU_VALIDATION_ONLY','plan':plan_ref,
    'actual_manifests':len(plan['episodes']),'approval_granted':False,
    'release_enabled':False,'new_live_device_evidence':False}))
