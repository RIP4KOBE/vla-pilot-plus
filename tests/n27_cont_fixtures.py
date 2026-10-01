"""Synthetic runner-schema metadata, never actual attempt data."""
import copy
import json
from pathlib import Path
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w
from scripts import qd_ed_n27_cont_history as h,qd_ed_n27_cont_contract as c

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n');return c.ref(path)

def rows():
    return [dict(episode_key=f'n27_screen_t{t:02d}_{a.lower()}_20261001',iteration=h.OLD,split='dev',seed_block='dev',profile=a,task_id=t,
        env_seed=100+t,policy_seed=200+t,init_index=0,init_row_sha256='a'*64,init_file_sha256='b'*64,bddl_sha256='c'*64,
        budget_bucket='baseline' if a=='C0' else 'development',timeout_seconds=1800) for t in range(4) for a in c.ARMS]

def group(row,aid,*,valid=True,success=False,source=h.BASE,plan_sha=h.PLAN_SHA,wall=10.):
    base={'attempt_id':aid,'identity':r.episode_identity(row),'episode_key':row['episode_key'],'retry_of':row.get('retry_of'),
        'budget_bucket':row['budget_bucket'],'source_commit':source,'plan_sha256':plan_sha,'output_dir':'SYNTHETIC',
        'profile_manifest_sha256':'p'*64,'runtime_manifest_sha256':'r'*64,'runtime_inventory_sha256':'i'*64,'init_row_sha256':row['init_row_sha256']}
    return [{**base,'event':ev,'time_unix':i,**({'outcome_valid':valid,'success':success,'gpu_process_wall_seconds':wall,
        'required_cost_telemetry_complete':valid,'guided_chunks':1,'provider_logical_call_attempts':2,'provider_usage_complete_calls':2,
        'provider_token_usage_complete':valid} if ev=='valid' else {})} for i,ev in enumerate(('reserved','dispatched','valid'))]

def seal(tmp):
    oldsource=json.loads((Path(c.ROOT)/'docs/experiments/n27_hydra_continuation/original-source-v1.json').read_text())
    rr=rows();plan={'source_commit':h.BASE,'code_files':oldsource['files'],'episodes':rr,'frozen':True,
        'profiles_sha256':'p'*64,'runtime_manifest_path':str(tmp/'runtime.json'),'runtime_manifest_sha256':'r'*64,
        'runtime_inventory_sha256':'i'*64,'worktree':str(tmp),'artifact_root':str(tmp/'artifact'),
        'candidate_profiles':{'N26':{},'N27':{}},'n27_cohort':{},'phase_authorization':{'dev':True,'validation':False,'formal':False},
        'derived_from':{}}
    events=[]
    for i,row in enumerate(rr[:4]):
        g=group(row,h.FAILED if i==3 else 'old'+str(i),valid=i<3,wall=7.231457023997791 if i==3 else 10.)
        if i==3:
            for k in ('guided_chunks','provider_logical_call_attempts','provider_usage_complete_calls','provider_token_usage_complete'):g[-1].pop(k)
        events+=g
    prefix=[]
    for i,row in enumerate(rr[:3]):
        refs={k:{'path':str(tmp/'old'/str(i)/k),'sha256':k[0]*64} for k in ('audit','worker_context','worker_receipt','attempt_result')}
        prefix.append({'logical_index':i,'cell':{'episode_key':row['episode_key'],'task_id':0,'profile':row['profile'],
            'attempt_id':'old'+str(i),'success':False,**refs},'native':{'guided_decisions':1,'parent_rounds_verified':10},'auxiliary':{}})
    fake=lambda k:{'path':str(tmp/k),'sha256':'d'*64}
    s={'schema':'n27-hydra-history-seal-v1','original_disposition':'INVALID_OR_INTERRUPTED','original_source':oldsource,
        'original_plan':{**fake('old-plan'),'sha256':h.PLAN_SHA},'original_plan_content':plan,'original_plan_content_sha256':w.canonical_sha(plan),
        'root_terminal_review':{**fake('old-review'),'sha256':h.REVIEW_SHA},'startup_classification':{**fake('classification'),'sha256':h.CLASSIFICATION_SHA},
        'runtime':{'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']},'old_events':events,
        'old_resource_events':[{'resource_id':'oldproof','kind':'n27_tensor_arithmetic_v1','event':ev,**({'gpu_process_wall_seconds':16.} if ev=='completed' else {})} for ev in ('reserved','dispatched','completed')],
        'accepted_prefix':prefix,'all_old_attempts':[{'attempt_id':g[-1]['attempt_id'],'episode_key':g[-1]['episode_key'],
            'profile':g[-1]['identity']['profile'],'terminal':g[-1]} for g in h.groups(events).values()],
        'historical_unknowns':h.UNKNOWN,'old_gpu_seconds':53.23145702399779,'cleanup_complete':True,'no_active_owned_worker':True,
        **{k:fake(k) for k in ('original_result','historical_backend_proof','original_source_review','original_authority','budget_authority')}}
    s['old_gpu_seconds']=sum(x['terminal']['gpu_process_wall_seconds'] for x in s['all_old_attempts'])+16.
    return s

def snapshot():
    return {'running':0,'gpu_healthcheck_inflight':0,'dispatched':342,'gpu_hours_consumed':46.86186153036005,
        'by_bucket':{'baseline':59,'development':211,'validation':60,'formal':0,'recovery':12},
        'gpu_hours_by_bucket':{'baseline':5.,'development':20.,'validation':10.,'formal':0.,'recovery':1.}}
