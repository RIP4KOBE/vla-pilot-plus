"""Root-only post-prepare metadata completion; no release or approval."""
import json,os,datetime
from pathlib import Path
ROOT=Path.cwd()
OUT=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001214/runtime-preparation')
PLAN=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001214/runtime-preparation/cpu-v2/runtime-candidate-v1/draft/plan.draft.json')
spec=json.loads((OUT/'root-next-commands-v1.json').read_text())
assert str(ROOT)==spec['cwd']
import sys
sys.path.insert(0,str(ROOT))
from scripts import qd_ed_n36_contract as c,qd_ed_n36_bridge as b,qd_ed_n23_worker as w
assert not os.path.lexists(c.stop_path(ROOT))
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(c.DEADLINE.replace('Z','+00:00'))
plan=json.loads(PLAN.read_text());c.validate_draft(plan)
plan.update(spec['required_metadata_after_success']);c.validate_draft(plan)
b.verify_sources(plan);runtime=w.read_ref(plan['runtime'])
for row in plan['episodes']:b._verify_manifest_bound(plan['expected_manifests'][row['episode_key']],plan,runtime,row)
target=PLAN.with_name('plan.metadata-complete.draft.json');assert not target.exists()
target.write_text(json.dumps(plan,indent=2)+'\n')
print(str(target))
