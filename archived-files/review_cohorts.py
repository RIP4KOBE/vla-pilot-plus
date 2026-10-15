"""Read-only re-audit of the six published cohorts with separately bound support."""
from pathlib import Path
import json
import hashlib
import sys
import time

ROOT=Path('/home/hynx/lizhuo/VLA-Pilot++')
sys.path.insert(0,str(ROOT))
from scripts.steering_archive import prepare_support
from scripts.audit_steering import audit

BASE=ROOT/'.worktrees/exp/repository-maintenance-20261015'
results=[]
for protocol,container,names in [
    ('low',ROOT/'.worktrees/exp/steering-integration/runs',{'eds':'eds-common-20261013','vls':'vls-common-20261013','eds_qd':'eds_qd-common-20261013'}),
    ('ultra',ROOT/'.worktrees/exp/steering-ultra-20261014/runs',{'eds':'eds-ultra-recovery-full10-01','vls':'vls-ultra-recovery-full10-01','eds_qd':'eds_qd-ultra-recovery-full10-01'})]:
    for method,name in names.items():
        source=container/name
        support=BASE/'archive-support'/f'{protocol}-{method}'
        report=BASE/'cohort-review'/f'{protocol}-{method}.json'
        hashes={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in ['manifest.json','resolved-config.yaml','environment.json','audit.json','status.json']}
        prepare_support(source,support)
        start=time.time()
        value=audit(source,output_path=report,archive_support=support)
        assert hashes=={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in hashes}
        row={'protocol':protocol,'method':method,'run':str(source),'support':str(support),'report':str(report),'valid':value['valid'],'successes':value.get('successes'),'completed':value.get('completed'),'raw_receipts_unchanged':True,'seconds':time.time()-start,'report_sha256':hashlib.sha256(report.read_bytes()).hexdigest()}
        results.append(row)
        (BASE/'cohort-review-index.json').write_text(json.dumps(results,indent=2)+'\n')
        print(json.dumps(row),flush=True)
        assert value['valid'],value.get('errors')
