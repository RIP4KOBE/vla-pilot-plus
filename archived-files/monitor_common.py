"""Read-only live monitor; separate from frozen runtime and scientific evidence."""
from pathlib import Path
import datetime, json, time
root = Path(__file__).resolve().parent
modes = [('eds', 'EDS', 0), ('vls', 'VLS', 1), ('eds_qd', 'EDS+QD', 4)]
while True:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    summary = {'updated_at': now, 'runs': {}}
    finished = []
    for method, label, gpu in modes:
        folder = root / 'runs' / (method + '-common-20261013')
        status = json.loads((folder/'status.json').read_text())
        progress_path = folder/'progress.json'
        p = json.loads(progress_path.read_text()) if progress_path.exists() else {}
        row = dict(method=label, gpu=gpu, state=status['state'], **p)
        audit = folder/'audit.json'
        if audit.exists():
            data=json.loads(audit.read_text()); row['audited_valid']=data.get('valid')
            row['audited_successes']=data.get('successes')
        summary['runs'][method]=row
        finished.append(status['state'] in ['finished','preflight_failed'] and
                        (audit.exists() or status['state']=='preflight_failed'))
    target=root/'live-progress.json'; temporary=root/'live-progress.tmp'
    temporary.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');temporary.replace(target)
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    if all(finished): break
    time.sleep(30)
