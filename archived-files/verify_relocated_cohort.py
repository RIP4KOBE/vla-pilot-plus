"""Verify a representative accepted cohort at its new archival location."""
from pathlib import Path
import json
import subprocess
import sys
import hashlib

ROOT=Path('/home/hynx/lizhuo/VLA-Pilot++');sys.path.insert(0,str(ROOT))
from scripts.audit_steering import audit
BASE=ROOT/'.worktrees/exp/repository-maintenance-20261015'
ARCHIVE=Path('/mnt/data/shared2/hynx/vla-pilot-repository-archive-20261015')
source=ROOT/'.worktrees/exp/steering-integration/runs/eds-common-20261013'
target=ARCHIVE/'accepted-cohorts/low-eds-preserved'
assert not target.exists()
target.parent.mkdir(parents=True,exist_ok=True)
subprocess.run(['rsync','-aH',str(source)+'/',str(target)+'/'],check=True)
r=subprocess.run(['rsync','-aHnci','--delete',str(source)+'/',str(target)+'/'],check=True,capture_output=True,text=True)
assert not r.stdout.strip(),r.stdout
support=BASE/'archive-support/low-eds'
report=BASE/'cohort-review/relocated-low-eds.json'
value=audit(target,output_path=report,archive_support=support)
assert value['valid'] and value['successes']==3 and value['completed']==10
row={'source':str(source),'archive':str(target),'checksum_equal':True,'full_audit_valid':True,'successes':3,'completed':10,'support':str(support),'report':str(report),'report_sha256':hashlib.sha256(report.read_bytes()).hexdigest(),'scope':'new copy and independent output; source run receipts untouched; no simulator/GPU/API execution'}
(BASE/'relocated-cohort-receipt.json').write_text(json.dumps(row,indent=2)+'\n')
print(json.dumps(row),flush=True)
