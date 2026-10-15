"""One end-to-end synthetic file composition; never reads real experiment data."""
import json, os, sys
from pathlib import Path
import summarize_v1 as s
from test_summary_v1 import fixture, wire

h=Path(__file__).resolve().parent
manifest,blobs,_,_=wire([fixture()])
for name,data in blobs.items():
    p=Path(name);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
mp=h/'synthetic-input-v2.json';rp=h/'synthetic-release-v2.json';out=h/'synthetic-cli-result-v2.json'
assert not any(p.exists() for p in (mp,rp,out)), 'do not overwrite prior composition'
mp.write_text(json.dumps(manifest,indent=2)+'\n')
release=dict(schema='n25-measurement-read-release-v1',executable=True,synthetic_only=True,
    manifest_sha256=s.sha(mp.read_bytes()),reader_sha256=s.sha((h/'summarize_v1.py').read_bytes()),
    guard_sha256=s.sha((h/'guard_v1.py').read_bytes()),output=str(out),max_wall_seconds=60)
rp.write_text(json.dumps(release,indent=2)+'\n')
sys.argv=['summarize_v1.py','--manifest',str(mp),'--release',str(rp),'--output',str(out)]
s.main()
print('Synthetic CLI completed: four allowlisted JSON files; original linked tensor path never opened.')
