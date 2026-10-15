"""Read-only completed-task action comparison; never a substitute for the full audit."""
from pathlib import Path
import datetime, hashlib, json

ROOT=Path(__file__).resolve().parents[1]
CURRENT=ROOT/'runs/eds-common-20261013'
REFERENCE=ROOT/'runs/eds-migration-20261013'
def read_rows(path):
    result=[]
    if not path.exists(): return result
    for line in path.read_bytes().splitlines():
        try: result.append(json.loads(line))
        except json.JSONDecodeError: break
    return result
def canonical_sha(rows):
    return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def evidence(run,evaldir,task):
    rows=read_rows(run/evaldir/'safety_events.jsonl')
    actions=[r for r in rows if r.get('task_id')==task and r.get('event')=='stage_grasp_guard_action']
    exits={(r['episode'],r['global_step']) for r in read_rows(run/evaldir/'phase_timing.jsonl') if r.get('name')=='adapter_step' and r.get('event')=='exit'}
    completed=[r for r in actions if (r['episode'],r['global_step']) in exits]
    return {r['global_step']:r for r in completed}, canonical_sha(completed), len(completed)==len(actions)

def main():
    ce=Path('output/evaluation');re=Path('output/eds_eval')
    completed=read_rows(CURRENT/ce/'episode_compute.jsonl')
    reports=[]
    for row in completed:
        if row.get('outcome')!='completed': continue
        task=row['task_id']; c,cs,all_done=evidence(CURRENT,ce,task);r,rs,reference_done=evidence(REFERENCE,re,task)
        common=sorted(c.keys()&r.keys())
        raw=[i for i in common if c[i]['raw_action']!=r[i]['raw_action']]
        executed=[i for i in common if c[i]['executed_action']!=r[i]['executed_action']]
        expected_c=list(range(len(c)));expected_r=list(range(len(r)))
        reports.append({'task_id':task,'seed':row['episode_seed'],'current_actions':len(c),'reference_actions':len(r),
            'current_contiguous':sorted(c)==expected_c,'reference_contiguous':sorted(r)==expected_r,
            'current_all_adapter_exits':all_done,'reference_all_adapter_exits':reference_done,
            'current_action_records_sha256':cs,'reference_action_records_sha256':rs,
            'common_action_count':len(common),'raw_difference_count':len(raw),'executed_difference_count':len(executed),
            'first_raw_difference':raw[0] if raw else None,'first_executed_difference':executed[0] if executed else None,
            'current_extra_steps':sorted(c.keys()-r.keys()),'reference_extra_steps':sorted(r.keys()-c.keys()),
            'all_current_actions_unmodified':all(v['raw_action']==v['executed_action'] and v.get('override') is False for v in c.values()),
            'all_executed_actions_exact':len(c)==len(r) and sorted(c)==expected_c and sorted(r)==expected_r and not executed})
    result={'schema':'eds_migration_vs_common_completed_actions_v1','generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'current_run':str(CURRENT),'reference_run':str(REFERENCE),
        'current_commit':json.loads((CURRENT/'manifest.json').read_text())['commit'],
        'reference_commit':json.loads((REFERENCE/'manifest.json').read_text())['commit'],
        'tasks':reports,'tasks_compared':len(reports),
        'limits':['Only completed recorded actions are compared; full cohort validity belongs to the independent cohort audit.',
                  'Fresh online responses may change future trajectories; exact trajectory equality is diagnostic, not required for valid task failures.',
                  'Whole append-only logs can grow; per-task selected action rows are bound by canonical SHA-256.']}
    out=ROOT/'checks/eds-common-completed-action-comparison.json'
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'tasks_compared':len(reports),'tasks':[{'task_id':r['task_id'],'actions':r['current_actions'],'executed_differences':r['executed_difference_count'],'all_exact':r['all_executed_actions_exact']} for r in reports],'report':str(out)},ensure_ascii=False))
if __name__=='__main__': main()
