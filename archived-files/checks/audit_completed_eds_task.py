"""Supplementary read-only task checks for frozen common EDS; full audit remains required."""
from pathlib import Path
import datetime, hashlib, json, sys
import yaml
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from scripts.audit_steering_contract import audit_run
from scripts.audit_qd_mechanism import audit_chunk
BASE=ROOT/'.worktrees/exp/steering-integration'
RUN=BASE/'runs/eds-common-20261013'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(path):
    result=[]
    for line in path.read_bytes().splitlines():
        try: result.append(json.loads(line))
        except json.JSONDecodeError: break
    return result

def main(task):
    manifest=json.loads((RUN/'manifest.json').read_text())
    assert manifest['commit']=='33954ead452927fc3168efb610487a688f89169e'
    assert all(sha(ROOT/p)==h and sha(RUN/'source'/p)==h for p,h in manifest['source_sha256'].items())
    ep=[r for r in rows(RUN/'output/evaluation/episode_compute.jsonl') if r.get('task_id')==task]
    assert len(ep)==1 and ep[0]['outcome']=='completed','Task not completed'
    assert list((RUN/'output'/f'episode_{task+1}').glob('*agentview.mp4')),'Terminal video missing'
    destination=BASE/'checks'/f'eds-common-task{task}-supplementary-audit.json'
    if destination.exists(): raise RuntimeError('Supplementary result exists; do not repeat unchanged checks')
    contract=audit_run(RUN,task=task)
    cfg=yaml.safe_load((RUN/'resolved-config.yaml').read_text())
    selected=[r for r in rows(RUN/'output/evaluation/eds_metrics.jsonl') if r.get('task_id')==task]
    mechanism=[{'global_step':r['global_step'],**audit_chunk(r,cfg['main']['eds_config'],expected_mode='eds')} for r in selected]
    valid=contract['summary'].get('fail',0)==0 and all(r['recorded_mechanism_valid'] is True for r in mechanism)
    assert len(mechanism)==ep[0]['guided_chunks'],'Guided mechanism coverage mismatch'
    assert all(sha(ROOT/p)==h for p,h in manifest['source_sha256'].items())
    result={'task_id':task,'seed':ep[0]['episode_seed'],'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'supplementary_valid':valid,'scope':'Completed task contract and recorded EDS chunk reconstruction; full final cohort audit still required',
            'contract':contract,'guided_chunks':len(mechanism),'mechanism':mechanism}
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'task_id':task,'valid':valid,'contract_summary':contract['summary'],'guided_chunks':len(mechanism),'path':str(destination),'sha256':sha(destination)}))
    return 0 if valid else 2
if __name__=='__main__': raise SystemExit(main(int(sys.argv[1])))
