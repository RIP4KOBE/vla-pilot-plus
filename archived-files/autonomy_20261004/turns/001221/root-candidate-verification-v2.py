import json,sys,os,datetime
from pathlib import Path
BASE=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001219/runtime-input-repair')
sys.path.insert(0,str(Path.cwd()))
from scripts import qd_ed_n36_contract as c, qd_ed_n36_bridge as b, qd_ed_n23_worker as w
ref=json.loads((BASE/'root-next-commands-v1.json').read_text())['candidate']
p=w.read_ref({k:ref[k] for k in ('path','sha256')})
assert os.environ['CUDA_VISIBLE_DEVICES']=='' and os.environ['PYTHONDONTWRITEBYTECODE']=='1'
assert not os.path.lexists(p['stop_path'])
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
c.validate_draft(p);b.verify_sources(p);runtime=w.read_ref(p['runtime'])
for file in runtime['files']:
 assert Path(file['path']).is_file() and w.sha(file['path'])==file['sha256']
 assert Path(file['path']).stat().st_size==file['size_bytes']
for row in p['episodes']:b._verify_manifest_bound(p['expected_manifests'][row['episode_key']],p,runtime,row)
print(json.dumps({'strict_source':'PASS','actual_manifests':len(p['episodes']),'release_enabled':False,'runtime_ready':False}))
