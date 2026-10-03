import copy,json
from pathlib import Path
from scripts import qd_ed_n23_worker as w,qd_ed_n30_r2_bridge as b,qd_ed_n30_r2_contract as c

def write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data));return {'path':str(path),'sha256':w.sha(path)}

def rows():
    return [dict(task_id=t,profile=a,episode_key=f'n30_r2_dev_t{t:02d}_{a.lower()}_20261003',split='dev',seed_block='dev',iteration=c.COHORT,
        env_seed=11+t,policy_seed=22+t,init_index=0,timeout_seconds=1800,budget_bucket='baseline' if a=='C0' else 'development') for t in range(4) for a in c.ARMS]

def history():
    from n30_r1_synthetic import history as original_history
    h=original_history();row=dict(h['plan']['episodes'][2]);row.update(iteration=b.R1,episode_key=row['episode_key'].replace('n30_dev_','n30_r1_dev_'))
    base={'attempt_id':b.FAILED,'episode_key':row['episode_key'],'identity':{k:row[k] for k in ('split','iteration','profile','task_id','env_seed','policy_seed','init_index')},
        'budget_bucket':'recovery','source_commit':b.R1_SOURCE,'plan_sha256':b.R1_PLAN_SHA,'output_dir':'/synthetic/r1','retry_of':b.ORIGINAL_FAILED}
    final={**base,'event':'valid','outcome_valid':False,'success':False,'failure_class':'task_failure','gpu_process_wall_seconds':b.R1_SECONDS,
        'required_cost_telemetry_complete':False,'provider_logical_call_attempts':15,'provider_usage_complete_calls':15,'provider_token_usage_complete':True}
    h['events'] += [{**base,'event':'reserved'},{**base,'event':'dispatched'},final]
    h['old_seconds']=b.OLD_SECONDS
    return h

def new_events(h,count=10,wins=(0,3,6),invalid=None):
    events=copy.deepcopy(h['events'])
    for i,row in enumerate(c.expected_rows(h)[:count]):
        base={'attempt_id':f'new{i}','episode_key':row['episode_key'],'identity':{k:row[k] for k in ('split','iteration','profile','task_id','env_seed','policy_seed','init_index')},
            'budget_bucket':row['budget_bucket'],'source_commit':'NEW','plan_sha256':'p','output_dir':f'/synthetic/new{i}'}
        if row.get('retry_of'):base['retry_of']=row['retry_of']
        events.extend([{**base,'event':'reserved'},{**base,'event':'dispatched'},{**base,'event':'valid','outcome_valid':i!=invalid,
            'success':i in wins,'gpu_process_wall_seconds':10.,'required_cost_telemetry_complete':i!=invalid,
            'provider_logical_call_attempts':3,'provider_usage_complete_calls':2 if i==invalid else 3,'provider_token_usage_complete':i!=invalid}])
    return events

def accept(row,events):
    final=next(e for e in events if e['event']=='valid' and e['episode_key']==row['episode_key'])
    if not final['outcome_valid']:raise ValueError('invalid native')
    return {**{k:row[k] for k in ('episode_key','task_id','profile')},'attempt_id':final['attempt_id'],'success':final['success']}, {'guided_decisions':1,'parent_rounds_verified':10,'active_insertions_verified':1},{}
