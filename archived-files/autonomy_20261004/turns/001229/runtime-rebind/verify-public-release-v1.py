"""Root-use read-only public validation, after independent review and release.

No plan, review or release is generated. All trusted digests are caller supplied.
This command does not perform GPU/provider admission or start a worker.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sys

p=argparse.ArgumentParser(description=__doc__)
for name in ('plan','plan-sha256','release','release-sha256'):
    p.add_argument('--'+name,required=True)
a=p.parse_args()
root=Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree')
assert Path.cwd().resolve()==root
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
assert not os.path.lexists(root.parent/'autonomy_20261004/STOP')
assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
sys.path.insert(0,str(root))
from scripts.qd_ed_n36_release import verify_prospective_release
plan_ref={'path':a.plan,'sha256':a.plan_sha256}
release_ref={'path':a.release,'sha256':a.release_sha256}
plan,runtime,authority=verify_prospective_release(plan_ref,release_ref)
print(json.dumps({'status':'PASS_PUBLIC_PROSPECTIVE_RELEASE','plan':plan_ref,
    'release':release_ref,'source':plan['source']['commit'],
    'actual_manifests':len(plan['expected_manifests']),
    'gpu_or_provider_admission_performed':False,'worker_started':False}))
